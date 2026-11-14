"""Tool 1: Life Blocker.

1. Code turns the LifeProfile into busy times and energy-labeled free slots.
2. Gemini assigns tasks to slots (and says why).
3. Code checks every block: inside a free slot, right energy, before the due date,
   no overlaps. Anything Gemini missed goes to a simple backup scheduler.

Formats are in CONTRACTS.md: LifeProfile in, list of Event out (a preview, not booked).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta

from google import genai
from google.genai import types
from pydantic import BaseModel

from .schedule_math import (
    Planner,
    build_segments,
    expand_fixed,
    normalize_tasks,
    parse_date,
)

logger = logging.getLogger(__name__)

PLANNER_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
_client: genai.Client | None = None


def _gemini() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()  # reads GEMINI_API_KEY (or Vertex settings) from env
    return _client


class Suggestion(BaseModel):
    task: str
    start: str
    end: str
    reason: str


class SuggestionList(BaseModel):
    blocks: list[Suggestion]


PLANNER_PROMPT = """You plan a college student's week.

Put each task into the FREE SLOTS below. Rules:
- Every block must sit fully inside one free slot. Use the exact ISO format with the -08:00 offset.
- High-focus tasks (energy "high") go in "high" slots, or "medium" if needed. NEVER in "low" slots.
- Low-focus chores (energy "low") go in "low" or "medium" slots first.
- A task can be split into several blocks of 30 to 120 minutes. Total time per task must equal its minutes.
- Finish every task before the start of its due date. Spread work across days; don't stack everything on one day.
- Tasks are listed in order. When tasks share a due date they are steps of one process:
  schedule them in the listed order (step 1 before step 2).
- Start blocks on :00, :15, :30 or :45.
- "reason" is one short, friendly sentence to the student about why this slot works.

Student: {chronotype} person, job is {job_drain} drain.

FREE SLOTS:
{slots}

TASKS:
{tasks}
"""


async def _ask_gemini(segments, tasks, chronotype, job_drain) -> list[Suggestion]:
    slots = [
        {"start": s.start.isoformat(), "end": s.end.isoformat(),
         "day": s.start.strftime("%a"), "energy": s.energy, "minutes": s.minutes}
        for s in segments
    ]
    task_list = [
        {"title": t.title, "minutes": t.minutes, "energy": t.energy,
         "due": t.due.isoformat() if t.due else None}
        for t in tasks
    ]
    prompt = PLANNER_PROMPT.format(
        chronotype=chronotype, job_drain=job_drain,
        slots=json.dumps(slots, indent=1), tasks=json.dumps(task_list, indent=1),
    )
    resp = await _gemini().aio.models.generate_content(
        model=PLANNER_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SuggestionList,
            temperature=0.2,
        ),
    )
    parsed = resp.parsed
    if isinstance(parsed, SuggestionList):
        return parsed.blocks
    return SuggestionList.model_validate_json(resp.text).blocks


async def plan_life_blocks(profile: dict, start: str, end: str) -> dict:
    """Plans study and chore blocks around a student's fixed schedule and energy.

    Args:
        profile: The student's LifeProfile with keys:
            fixed: list of commitments. Weekly ones look like
                {"title": "CSE 30 lecture", "days": ["Mon", "Wed", "Fri"], "start": "10:40", "end": "11:45"}
                (24-hour times). One-off calendar events can use full ISO datetimes for start and end.
            chronotype: "morning" or "night".
            job_drain: "low" or "high" (how tiring their job is).
            tasks: list like {"title": "Essay draft", "minutes": 120, "energy": "high", "due": "2026-11-20"}.
                energy is "high" for focused work, "low" for chores; due can be null.
        start: First day to plan, ISO date like "2026-11-16".
        end: Last day to plan, ISO date like "2026-11-22".

    Returns:
        A dict with "proposed_blocks" (Event list, NOT on the calendar yet; the
        student previews them first), "unscheduled" (tasks that didn't fit), and "note".
    """
    try:
        start_d, end_d = parse_date(start), parse_date(end)
    except (ValueError, TypeError):
        return {"status": "error", "message": "start and end must be ISO dates like 2026-11-16"}
    if end_d < start_d:
        start_d, end_d = end_d, start_d

    profile = profile or {}
    chronotype = str(profile.get("chronotype") or "morning").lower()
    job_drain = str(profile.get("job_drain") or "low").lower()
    tasks = normalize_tasks(profile.get("tasks"))
    if not tasks:
        return {"status": "error", "message": "No tasks to schedule. Ask what they need to get done."}
    for t in tasks:  # due on or before the first day: allow working on the due day itself
        if t.due and t.due <= start_d:
            t.due = t.due + timedelta(days=1)

    busy = expand_fixed(profile.get("fixed"), start_d, end_d)
    segments = build_segments(busy, start_d, end_d, chronotype, job_drain)
    planner = Planner(segments, tasks)

    planned_by = "fallback"
    if segments:
        try:
            for s in await _ask_gemini(segments, tasks, chronotype, job_drain):
                planner.try_place(s.task, s.start, s.end, s.reason, source="gemini")
            planned_by = "gemini"
        except Exception as exc:  # demo must not break if Gemini errors
            logger.warning("Gemini planner failed, using backup scheduler: %s", exc)
    planner.fill_remaining()

    if planned_by == "gemini" and any(p.source == "fallback" for p in planner.placed):
        planned_by = "gemini+fallback"

    return {
        "status": "ok",
        "proposed_blocks": planner.events(),
        "unscheduled": planner.unscheduled(),
        "planned_by": planned_by,
        "rejected_suggestions": len(planner.rejected),
        "note": "Preview only. Nothing is on the calendar until the student approves.",
    }

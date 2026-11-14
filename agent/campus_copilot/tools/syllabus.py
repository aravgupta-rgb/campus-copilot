"""Tool: Syllabus Import.

Upload a syllabus (PDF, photo or pasted text) and get every exam, assignment,
project and quiz with its due date, plus the class meeting times. Output plugs
straight into Life Blocker: tasks_for_planner -> profile["tasks"],
class_meetings -> profile["fixed"].
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel

from .attachments import latest_attachment
from .life_blocks import _gemini
from .schedule_math import TZ

logger = logging.getLogger(__name__)

SYLLABUS_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


class Meeting(BaseModel):
    kind: str  # "lecture" | "section" | "lab" | "office hours"
    days: list[str]  # ["Mon", "Wed", "Fri"]
    start: str  # "HH:MM" 24-hour
    end: str
    location: str | None


class Item(BaseModel):
    title: str
    type: str  # "exam" | "assignment" | "project" | "quiz" | "reading" | "other"
    due: str | None  # "YYYY-MM-DD"
    due_time: str | None  # "HH:MM"
    weight_percent: float | None
    prep_minutes: int  # realistic total time to prepare or complete it
    confidence: float


class SyllabusRead(BaseModel):
    is_syllabus: bool
    course: str
    term: str | None
    meetings: list[Meeting]
    items: list[Item]
    grading_summary: str
    notes: str


PROMPT = """Read this course syllabus for a college student. Today is {today}.
If a date has no year, use the year that puts it in the current or upcoming term.

Extract:
- course: code and short name, like "CSE 30: Programming Abstractions".
- meetings: weekly lectures, sections, labs (skip office hours unless nothing else is listed).
  days as ["Mon","Tue",...], times as 24-hour "HH:MM".
- items: every exam, assignment, project, quiz and major reading WITH a date.
  If the syllabus says "Week 5", convert it using the term start date if one is given;
  otherwise leave due null and say so in notes. Never invent a date.
  prep_minutes: realistic total time: weekly homework 120-180, project 480-900,
  midterm study 300-480, final study 600, quiz 60, reading 60.
- weight_percent: from the grading breakdown, if given.
- grading_summary: one sentence like "Homework 30%, 2 midterms 40%, final 30%".
- is_syllabus: false if this isn't a course syllabus or schedule.

{source}
"""


def _event(course: str, it: Item) -> dict | None:
    if not it.due:
        return None
    try:
        d = date.fromisoformat(it.due[:10])
    except ValueError:
        return None
    hh, mm = 23, 59
    if it.due_time:
        try:
            hh, mm = (int(x) for x in it.due_time.split(":")[:2])
        except ValueError:
            pass
    start = datetime(d.year, d.month, d.day, hh % 24, mm, tzinfo=TZ)
    return {
        "title": f"{course.split(':')[0]}: {it.title}",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=30)).isoformat() if it.type != "exam" else (start + timedelta(hours=2)).isoformat(),
        "location": None,
        "description": f"{it.type.capitalize()} from the {course} syllabus"
                       + (f" ({it.weight_percent:g}% of grade)" if it.weight_percent else ""),
        "source": "document",
        "confidence": round(max(0.0, min(1.0, it.confidence)), 2),
    }


def _task(course: str, it: Item) -> dict:
    """Exams become study tasks due the day before; everything else is due on its date."""
    code = course.split(":")[0].strip()
    due = it.due
    title = f"{code}: {it.title}"
    if it.type == "exam":
        title = f"{code}: Study for {it.title}"
    return {"title": title, "minutes": max(30, it.prep_minutes),
            "energy": "low" if it.type == "reading" and it.prep_minutes <= 60 else "high",
            "due": due}


async def import_syllabus(tool_context: ToolContext, text: str = "", only_next_days: int = 0) -> dict:
    """Reads a course syllabus and pulls out every deadline, exam and the class meeting times.

    Works on pasted text, or the most recent PDF or photo the student attached.

    Args:
        text: Syllabus text the student pasted. Empty if they attached a PDF or photo.
        only_next_days: If above 0, only return tasks due within this many days
            (useful for "plan my next two weeks"). 0 returns everything.

    Returns:
        course, grading_summary, class_meetings (LifeProfile "fixed" items),
        deadlines (Event list), tasks_for_planner (LifeProfile "tasks"), undated (items
        without a date), and notes.
    """
    parts: list[types.Part] = []
    if text and text.strip():
        source = f"SYLLABUS TEXT:\n\"\"\"\n{text.strip()[:40000]}\n\"\"\""
    else:
        att = latest_attachment(tool_context, ("application/pdf", "image/"))
        if att is None:
            return {"status": "error", "message": "No syllabus found. Ask them to attach the PDF or paste the text."}
        parts.append(att)
        source = "The syllabus is in the attached PDF or image."
    parts.append(types.Part(text=PROMPT.format(today=date.today().isoformat(), source=source)))

    try:
        resp = await _gemini().aio.models.generate_content(
            model=SYLLABUS_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_schema=SyllabusRead, temperature=0.0),
        )
        read = resp.parsed if isinstance(resp.parsed, SyllabusRead) else SyllabusRead.model_validate_json(resp.text)
    except Exception as exc:
        logger.warning("Syllabus import failed: %s", exc)
        return {"status": "error", "message": "Couldn't read that syllabus. Ask for the PDF or a clearer photo."}

    if not read.is_syllabus:
        return {"status": "not_a_syllabus", "message": "That doesn't look like a syllabus."}

    dated = [i for i in read.items if i.due]
    if only_next_days > 0:
        cutoff = date.today() + timedelta(days=only_next_days)
        dated = [i for i in dated if date.fromisoformat(i.due[:10]) <= cutoff]
    code = read.course.split(":")[0].strip()

    return {
        "status": "ok",
        "course": read.course,
        "term": read.term,
        "grading_summary": read.grading_summary,
        "class_meetings": [
            {"title": f"{code} {m.kind}", "kind": "other", "days": m.days, "start": m.start, "end": m.end}
            for m in read.meetings if m.kind != "office hours"
        ],
        "deadlines": [e for e in (_event(read.course, i) for i in dated) if e],
        "tasks_for_planner": [_task(read.course, i) for i in dated],
        "undated": [i.title for i in read.items if not i.due],
        "notes": read.notes,
    }

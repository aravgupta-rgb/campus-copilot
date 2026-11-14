"""Reads a screenshot of a work or class schedule into LifeProfile "fixed" items.

The student uploads an image (adk web paperclip, or the frontend's photo upload).
This tool finds the most recent image in the chat, asks Gemini to read every
shift / class / commitment, and returns them in the CONTRACTS.md "fixed" format
so plan_life_blocks can plan around them.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from google.adk.tools import ToolContext
from google.genai import types
from pydantic import BaseModel

from .life_blocks import _gemini

logger = logging.getLogger(__name__)

VISION_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


class ScheduleItem(BaseModel):
    title: str
    kind: str  # "work" | "class" | "gym" | "other"
    date: str | None  # "YYYY-MM-DD" for a one-off shift; null if it repeats weekly
    days: list[str]  # ["Mon", "Wed"] if it repeats weekly; [] for a one-off
    start: str  # "HH:MM" 24-hour
    end: str  # "HH:MM" 24-hour
    confidence: float  # 0 to 1


class ScheduleRead(BaseModel):
    items: list[ScheduleItem]
    notes: str


PROMPT = """Read this schedule screenshot (a work schedule, class schedule, or calendar).
Today is {today}. If a date has no year, use the year that puts it closest to today.

Return every commitment the person must attend:
- Dated shifts (e.g. "Tue 11/17 2:00p-7:00p") -> date "YYYY-MM-DD", days [].
- Weekly repeating items (e.g. a class "MWF 10:40-11:45") -> date null, days like ["Mon","Wed","Fri"].
- Times in 24-hour "HH:MM". Convert "2p" to "14:00".
- kind: "work" for shifts/jobs, "class" for courses, "gym" for workouts/practice, else "other".
- If several people are listed, only include rows for the person named below; if no name is
  given and it's ambiguous, include all rows and say so in notes.
- confidence: lower it for blurry or guessed values.
- Do not invent anything not visible. Use notes for anything unclear.

Person's name (may be empty): {name}
"""


def _latest_image(tool_context: ToolContext) -> types.Part | None:
    contents = []
    if tool_context.user_content:
        contents.append(tool_context.user_content)
    try:
        events = tool_context.get_invocation_context().session.events
        contents += [e.content for e in reversed(events) if e.author == "user" and e.content]
    except Exception:  # older/newer ADK shapes: the current message is enough
        pass
    for content in contents:
        for part in content.parts or []:
            blob = part.inline_data
            if blob and blob.mime_type and blob.mime_type.startswith("image/"):
                return part
    return None


def _to_fixed(item: ScheduleItem) -> dict:
    kind = "other" if item.kind == "class" else item.kind
    if item.date:
        try:
            d = date.fromisoformat(item.date)
            return {
                "title": item.title,
                "kind": kind,
                "start": f"{d.isoformat()}T{item.start}:00",
                "end": f"{d.isoformat()}T{item.end}:00",
            }
        except ValueError:
            pass
    return {"title": item.title, "kind": kind, "days": item.days or [],
            "start": item.start, "end": item.end}


async def read_schedule_screenshot(tool_context: ToolContext, person_name: str = "") -> dict:
    """Reads the most recent schedule image the student uploaded (work shifts, class schedule, or calendar).

    Args:
        person_name: The student's name, if the schedule lists several people. Empty if unknown.

    Returns:
        A dict with "fixed": commitments in LifeProfile format, ready to pass to
        plan_life_blocks as profile["fixed"]; "check_these": items read with low
        confidence that the student should confirm; and "notes".
    """
    image = _latest_image(tool_context)
    if image is None:
        return {"status": "error",
                "message": "No image found. Ask the student to attach a screenshot of their schedule."}
    prompt = PROMPT.format(today=date.today().isoformat(), name=person_name or "")
    try:
        resp = await _gemini().aio.models.generate_content(
            model=VISION_MODEL,
            contents=[types.Content(role="user", parts=[image, types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ScheduleRead,
                temperature=0.0,
            ),
        )
        read = resp.parsed if isinstance(resp.parsed, ScheduleRead) else ScheduleRead.model_validate_json(resp.text)
    except Exception as exc:
        logger.warning("Schedule screenshot read failed: %s", exc)
        return {"status": "error", "message": "Couldn't read that image. Ask for a clearer screenshot or to type the times."}

    return {
        "status": "ok",
        "fixed": [_to_fixed(i) for i in read.items],
        "check_these": [i.title for i in read.items if i.confidence < 0.7],
        "notes": read.notes,
    }

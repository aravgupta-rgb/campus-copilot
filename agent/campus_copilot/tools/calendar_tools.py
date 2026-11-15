"""Agent tools for Google Calendar, built on Arav's calendar.py.

The student's Google access token comes from the website's "Connect Calendar"
sign-in and is sent with each message as temp:google_token. ADK keeps temp: state
only for the current request, so the token is never stored in the session.
"""

from __future__ import annotations

import asyncio
import logging

from google.adk.tools import ToolContext

from . import calendar as gcal

logger = logging.getLogger(__name__)

TOKEN_KEY = "temp:google_token"
NOT_CONNECTED = {
    "status": "not_connected",
    "message": "Google Calendar isn't connected. Ask the student to tap 'Connect Calendar'"
               " at the top of the page (or use the Book it button under the plan).",
}


def _token(tool_context: ToolContext) -> str | None:
    try:
        return tool_context.state.get(TOKEN_KEY)
    except Exception:
        return None


async def get_schedule(start: str, end: str, tool_context: ToolContext) -> dict:
    """Reads the student's existing Google Calendar events so plans can work around them.

    Call this before plan_life_blocks when planning a week, if the calendar is connected.

    Args:
        start: First day, ISO date like "2026-11-16".
        end: Last day, ISO date like "2026-11-22".

    Returns:
        status, count, events (title/start/end), and as_fixed: timed events in
        LifeProfile "fixed" format to merge into plan_life_blocks' profile["fixed"].
    """
    token = _token(tool_context)
    if not token:
        return NOT_CONNECTED
    events = await asyncio.to_thread(
        gcal.get_schedule, token, f"{start[:10]}T00:00:00-08:00", f"{end[:10]}T23:59:59-08:00")
    timed = [e for e in events if "T" in str(e.get("start"))]
    return {
        "status": "ok",
        "count": len(events),
        "events": [{"title": e["title"], "start": e["start"], "end": e["end"]} for e in events[:40]],
        "as_fixed": [{"title": e["title"], "start": e["start"], "end": e["end"], "from_calendar": True} for e in timed[:40]],
    }


async def book_events(events: list[dict], tool_context: ToolContext) -> dict:
    """Books approved plan blocks onto the student's Google Calendar.

    Only call after the student clearly asks to book or add the plan to their calendar.

    Args:
        events: The Event objects to book, exactly as plan_life_blocks returned them:
            proposed_blocks, plus fixed_events and deadline_events so the calendar matches
            everything the student said (classes, shifts, due dates, exams).

    Returns:
        status and created (how many events were added).
    """
    token = _token(tool_context)
    if not token:
        return NOT_CONNECTED
    bodies = [_body(e) for e in events if e.get("start") and e.get("end")]
    if not bodies:
        return {"status": "error", "message": "No events with start and end times to book."}

    def insert_all():
        service = gcal.get_google_calendar_service(token)  # Arav's client builder
        return [service.events().insert(calendarId="primary", body=b).execute().get("id") for b in bodies]

    try:
        ids = await asyncio.to_thread(insert_all)
    except Exception as exc:
        logger.warning("Booking failed: %s", exc)
        return {"status": "error", "message": "Google Calendar didn't accept the booking. Try the Book it button."}
    return {"status": "ok", "created": len(ids), "titles": [b["summary"] for b in bodies]}


TZ = "America/Los_Angeles"
# Google Calendar colors: 9 blueberry (study), 8 graphite (classes/shifts), 11 tomato (due dates)
_COLOR = {"plan": "9", "fixed": "8", "deadline": "11"}


def _body(e: dict) -> dict:
    """Event -> Google Calendar insert body (timed or all-day)."""
    if e.get("all_day") or "T" not in str(e.get("start")):
        when = {"start": {"date": str(e["start"])[:10]}, "end": {"date": str(e["end"])[:10]}}
    else:
        when = {"start": {"dateTime": e["start"], "timeZone": TZ}, "end": {"dateTime": e["end"], "timeZone": TZ}}
    body = {
        "summary": e.get("title") or "Campus Copilot",
        "description": (e.get("description") or "") + "\n\nPlanned by Campus Copilot.",
        **when,
    }
    if e.get("location"):
        body["location"] = e["location"]
    color = _COLOR.get(e.get("source"))
    if color:
        body["colorId"] = color
    if e.get("source") == "plan":
        body["reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}
    return body

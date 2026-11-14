"""Tool 2: Decode.

Turns a confusing official letter or email (financial aid, enrollment, housing,
billing, academic standing) into plain language: what it means, how urgent it is,
what to do by when, who to contact, a draft reply, and an optional translation
for parents. Action items come with time estimates so Life Blocker can schedule them.

Input: pasted text, or the latest uploaded photo/PDF of the letter.
Output: DecodeResult (CONTRACTS.md), plus "tasks_for_planner".
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

DECODE_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


# ---------- what Gemini returns ----------

class ActionItem(BaseModel):
    task: str
    due: str | None  # "YYYY-MM-DD" or null
    minutes: int  # realistic time to do it
    energy: str  # "high" for forms/writing/calls, "low" for quick errands


class Deadline(BaseModel):
    title: str
    date: str  # "YYYY-MM-DD"
    time: str | None  # "HH:MM" 24-hour if the letter gives one
    confidence: float


class Contact(BaseModel):
    name: str
    email: str | None
    phone: str | None


class Translation(BaseModel):
    language: str
    text: str


class DecodeRead(BaseModel):
    is_official_document: bool
    summary: str
    what_it_means: str
    urgency: str  # "low" | "medium" | "high"
    action_items: list[ActionItem]
    deadlines: list[Deadline]
    contact: Contact | None
    draft_reply: str
    translation: Translation | None
    verify_note: str


PROMPT = """You help a college student understand an official letter or email.
Today is {today}. If a date has no year, use the year that puts it closest to (and usually after) today.

Write for a stressed first-year student, ideally a first-generation student: short,
plain words, no jargon. Explain acronyms (SAP, FAFSA, EFC, hold, verification).

Fields:
- summary: one sentence, the main point.
- what_it_means: 2-3 sentences: what happens if they act, and what happens if they don't.
- urgency: "high" if money, enrollment, housing or graduation is at risk or a deadline is
  within 14 days; "medium" if action is needed later; "low" if it's informational.
- action_items: concrete steps in order. due = deadline for that step or null.
  minutes = realistic time to do it (a form 30-60, gathering documents 45, an office visit 60,
  a short email 15). energy = "high" for forms, writing or calls; "low" for quick errands.
- deadlines: every date the student must meet. Only dates actually in the letter.
  Never invent a deadline. Lower confidence if the date is ambiguous.
- contact: the office or person to contact, with email/phone ONLY if written in the letter.
- draft_reply: a short, polite email the student could send to that contact to confirm
  next steps or ask a question. Use placeholders like [Your Name] and [Student ID];
  never copy a real student ID number into it.
- translation: {translation_rule}
- verify_note: one sentence telling them to confirm details with the office named.
- is_official_document: false if this isn't a letter/email from a school, landlord,
  employer or agency (e.g. a meme or a random photo).
- Never repeat full ID numbers, SSNs or account numbers from the letter; mask them like ***1234.

{source_label}
"""


def _event_from_deadline(d: Deadline) -> dict | None:
    try:
        day = date.fromisoformat(d.date[:10])
    except ValueError:
        return None
    hh, mm = (17, 0)  # no time given: treat as due by 5 PM (office hours)
    if d.time:
        try:
            hh, mm = (int(x) for x in d.time.split(":")[:2])
        except ValueError:
            pass
    start = datetime(day.year, day.month, day.day, hh % 24, mm, tzinfo=TZ)
    return {
        "title": f"Due: {d.title}",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=30)).isoformat(),
        "location": None,
        "description": "Deadline from a letter Campus Copilot decoded. Confirm with the office.",
        "source": "document",
        "confidence": round(max(0.0, min(1.0, d.confidence)), 2),
    }


def _translation_rule(language: str) -> str:
    lang = (language or "").strip()
    if not lang or lang.lower() in ("en", "english"):
        return "null (no translation requested)."
    return (f"translate the summary, what_it_means and action items into {lang}, written "
            f"simply enough for a parent who doesn't know US college terms. language = \"{lang}\".")


async def decode_document(tool_context: ToolContext, text: str = "", language: str = "") -> dict:
    """Explains a confusing official letter or email in plain language.

    Use for financial aid, enrollment, registrar, housing, billing, academic
    standing or similar letters. Works on pasted text, or on the most recent
    photo or PDF the student attached if text is empty.

    Args:
        text: The letter or email text the student pasted. Empty if they attached a photo or PDF.
        language: Optional language to translate the explanation into for a parent,
            like "Spanish" or "Hindi". Empty for no translation.

    Returns:
        A DecodeResult dict: summary, what_it_means, urgency, action_items,
        deadlines (Event list), contact, draft_reply, translation, verify_note,
        plus tasks_for_planner (ready for plan_life_blocks profile["tasks"]).
    """
    parts: list[types.Part] = []
    if text and text.strip():
        source_label = f"LETTER TEXT:\n\"\"\"\n{text.strip()[:20000]}\n\"\"\""
    else:
        attachment = latest_attachment(tool_context, ("image/", "application/pdf"))
        if attachment is None:
            return {"status": "error",
                    "message": "No letter found. Ask the student to paste the text or attach a photo or PDF."}
        parts.append(attachment)
        source_label = "The letter is in the attached image or PDF."

    prompt = PROMPT.format(today=date.today().isoformat(),
                           translation_rule=_translation_rule(language),
                           source_label=source_label)
    parts.append(types.Part(text=prompt))
    try:
        resp = await _gemini().aio.models.generate_content(
            model=DECODE_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DecodeRead,
                temperature=0.1,
            ),
        )
        read = resp.parsed if isinstance(resp.parsed, DecodeRead) else DecodeRead.model_validate_json(resp.text)
    except Exception as exc:
        logger.warning("Decode failed: %s", exc)
        return {"status": "error", "message": "Couldn't read that letter. Ask for clearer text or a sharper photo."}

    if not read.is_official_document:
        return {"status": "not_a_letter",
                "message": "That doesn't look like an official letter or email. Ask what they need help with."}

    urgency = read.urgency if read.urgency in ("low", "medium", "high") else "medium"
    deadlines = [e for e in (_event_from_deadline(d) for d in read.deadlines) if e]
    contact = None
    if read.contact:
        contact = {"name": read.contact.name, "email": read.contact.email}
        if read.contact.phone:
            contact["phone"] = read.contact.phone

    return {
        "status": "ok",
        "summary": read.summary,
        "what_it_means": read.what_it_means,
        "urgency": urgency,
        "action_items": [{"task": a.task, "due": a.due} for a in read.action_items],
        "deadlines": deadlines,
        "contact": contact,
        "draft_reply": read.draft_reply,
        "translation": read.translation.model_dump() if read.translation else None,
        "verify_note": read.verify_note,
        "tasks_for_planner": [
            {"title": a.task, "minutes": max(15, a.minutes),
             "energy": a.energy if a.energy in ("high", "low") else "high", "due": a.due}
            for a in read.action_items
        ],
    }

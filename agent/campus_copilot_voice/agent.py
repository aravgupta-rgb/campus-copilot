"""Campus Copilot, voice edition: talk to it instead of typing.

Same tools as the text agent, on a Gemini Live (native audio) model.
In adk web, pick "campus_copilot_voice" and press the phone (or camera) button.

Live models are served from a region, not "global", so this model pins
us-central1 while the text agent keeps using GOOGLE_CLOUD_LOCATION.
"""

import os

from google.adk.agents import Agent
from google.adk.models import Gemini

from campus_copilot.agent import INSTRUCTION as TEXT_INSTRUCTION
from campus_copilot.tools import decode_document, find_office, plan_life_blocks

LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-live-2.5-flash-native-audio")
LIVE_LOCATION = os.getenv("GEMINI_LIVE_LOCATION", "us-central1")

VOICE_RULES = """
You are speaking out loud, not writing.
- Keep every answer to 2 or 3 short sentences. Ask ONE question at a time.
- No markdown, bullet symbols or emoji. Say times naturally: "Tuesday from 9 to 11 in the morning".
- When you present a plan, say the 2 or 3 most important blocks. Only if the plan has MORE
  blocks than you said, name what's left and offer the full list. Never mention tasks or
  blocks that aren't in the tool result.
- For a decoded letter: say the urgency, the one-line summary, and the first step with its
  due date. Offer to go through the other steps or the email draft.
- If the student holds a letter up to the camera, read it yourself and pass its full text
  to decode_document as `text`.
- If they show a schedule on camera, read the commitments yourself and use them as
  profile["fixed"] for plan_life_blocks.
- If you didn't catch something (a time, a day), ask them to repeat it instead of guessing.
""".strip()

root_agent = Agent(
    name="campus_copilot_voice",
    model=Gemini(model=LIVE_MODEL, client_kwargs={"location": LIVE_LOCATION}),
    description="Voice version of Campus Copilot: plan your week and decode letters by talking.",
    instruction=VOICE_RULES + "\n\n" + TEXT_INSTRUCTION,
    tools=[plan_life_blocks, decode_document, find_office],
)

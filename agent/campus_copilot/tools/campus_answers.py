"""Campus Answers (Arav): a sub-agent that answers UCSC questions with Google Search grounding.

google_search can't share an agent with other tools, so it lives in its own small agent
and the main agent calls it through AgentTool.
"""

import os

from google.adk.agents import Agent
from google.adk.tools import AgentTool, google_search

# Create the Campus Answers sub-agent configured with Google Search grounding
campus_search_agent = Agent(
    name="campus_answers",
    model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
    description=(
        "Answers questions about UC Santa Cruz and college life (policies, deadlines,"
        " offices, how-tos) using Google Search, with source links."
    ),
    instruction=(
        "You are a helpful campus assistant for UC Santa Cruz (UCSC). Answer the"
        " question using Google Search grounding. Prefer official ucsc.edu pages."
        " Give a short, plain-language answer (3-6 sentences or a short list),"
        " include specific deadlines or steps when they exist, and end with the"
        " source links you used. If sources disagree or you aren't sure, say so and"
        " point to the office that can confirm."
    ),
    # Built-in Google Search tool in ADK for web grounding
    tools=[google_search],
)

# Wrap it as an AgentTool so the main agent can invoke it cleanly
campus_answers_tool = AgentTool(agent=campus_search_agent)

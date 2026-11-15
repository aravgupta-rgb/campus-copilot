from google.adk.agents import Agent
from google.adk.tools import AgentTool

# Create the Campus Answers sub-agent configured with Google Search grounding
campus_search_agent = Agent(
    name="campus_answers_sub_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a helpful campus assistant for UCSC. Answer questions about"
        " campus policies, deadlines, and guidelines using Google Search"
        " grounding. Always provide clear answers with source links."
    ),
    # Built-in Google Search tool in ADK for web grounding
    tools=["google_search"],
)

# Wrap it as an AgentTool so Aaryav's main agent can invoke it cleanly
campus_answers_tool = AgentTool(agent=campus_search_agent)
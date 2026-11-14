# Campus Copilot

A Gemini agent, built with Google ADK, that handles college life admin for students.
Team Gupta Tech Bros · UCSC Google DevFest 2026.

**Tools, in build order**

1. **Life Blocker:** plans study and chore blocks around classes, work shifts and energy levels, then books them on Google Calendar.
2. **Decode:** turns confusing official letters into plain language, next steps and deadlines.
3. **Campus Answers:** answers campus questions using Google Search grounding, with sources.

**Stack:** Google ADK, Gemini API, Google Calendar API, Firebase Auth, Firestore, Firebase Hosting, Cloud Run, Next.js.

## Who owns what

| Folder | Owner | What goes there |
|---|---|---|
| `agent/` | Aaryav | ADK agent and the three tools |
| `backend/` | Arav | Python API on Cloud Run, sign-in, Calendar |
| `frontend/` | Shared | Next.js web app. Tell each other before editing |

The data formats both sides use are in [CONTRACTS.md](CONTRACTS.md).

## Setup

1. Copy `.env.example` to `.env` and fill in your values. Never commit `.env`.
2. Install the Python libraries:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   ```
3. Run the agent in the ADK chat UI:
   ```bash
   cd agent && adk web
   ```
   Open the address it prints (usually http://localhost:8000) and pick **campus_copilot**.
4. Run the Life Blocker rule tests:
   ```bash
   cd agent && python -m pytest -q
   ```

The agent needs `GEMINI_API_KEY` in `.env` (repo root). Python 3.12+ works; 3.14 is tested.

## Rules

- Small commits, `git pull` before starting new work.
- Never commit API keys or `.env`.
- Contract changes need a heads-up to the other person.

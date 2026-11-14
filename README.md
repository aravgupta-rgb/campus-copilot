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
   For **voice mode**, pick **campus_copilot_voice** and press the 📞 (or 🎥) button. It needs
   Vertex AI (see below) and uses `gemini-live-2.5-flash-native-audio` in `us-central1`.
   To try Decode, paste `demo/sample_finaid_letter.txt` or attach `demo/sample_finaid_letter.png`.
4. Run the Life Blocker rule tests:
   ```bash
   cd agent && python -m pytest -q
   ```

Python 3.12+ works; 3.14 is tested.

### Gemini access: Vertex AI (default) or AI Studio key (fallback)

**Vertex AI** runs Gemini on our Google Cloud credits, with much higher limits than the free tier.
One-time setup on each laptop:

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install).
2. Sign in with the Google account that has access to `campus-copilot-514718`:
   ```bash
   gcloud auth application-default login
   gcloud auth application-default set-quota-project campus-copilot-514718
   ```
3. In `.env`: `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT=campus-copilot-514718`,
   `GOOGLE_CLOUD_LOCATION=global`.

**Fallback:** if Vertex stops working (for example the credit runs out), set
`GOOGLE_GENAI_USE_VERTEXAI=FALSE` and the agent uses `GEMINI_API_KEY` from AI Studio instead
(free tier: about 20 requests/day per model; change `GEMINI_MODEL` if you hit a 429).

## Rules

- Small commits, `git pull` before starting new work.
- Never commit API keys or `.env`.
- Contract changes need a heads-up to the other person.

## Deploy (Cloud Run)

Live: https://campus-copilot-261781875474.us-central1.run.app

1. Test locally (`npm run dev:navy` in `frontend/` → http://localhost:5175).
2. Commit and push.
3. Run `./deploy.sh` (needs `gcloud auth login`). About 5 minutes, same URL, no downtime.

"""Production server: the ADK agent API and the web app on one Cloud Run service.

- Agent API (same routes as `adk api_server`): /list-apps, /apps/..., /run, /run_sse, /run_live
- Web app: frontend/dist served at /

Run locally (after `cd frontend && VITE_API_URL=/ npm run build`):
    uvicorn server:app --port 8080
"""

import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

HERE = Path(__file__).resolve().parent
# The voice websocket checks Origin. Allow our Cloud Run URLs plus any extras.
origins = [r"regex:https://.*\.run\.app"] + [o for o in os.getenv("ALLOW_ORIGINS", "").split(",") if o]

app = get_fast_api_app(
    agents_dir=str(HERE / "agent"),
    web=False,  # our own frontend instead of the ADK dev UI
    use_local_storage=False,  # in-memory sessions (Cloud Run disk isn't persistent)
    allow_origins=origins,
)

dist = HERE / "frontend" / "dist"
if dist.exists():
    # Mounted last, so the agent API routes above take priority.
    app.mount("/", StaticFiles(directory=dist, html=True), name="web")

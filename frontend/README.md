# Campus Copilot frontend

React + Vite. Talks directly to the ADK agent API (the same API `adk web` serves locally and Cloud Run serves in production).

## Run locally

1. Start the agent server (in another terminal):
   ```bash
   cd agent && adk web --port 8000
   ```
2. Start the frontend:
   ```bash
   cd frontend && npm install && npm run dev
   ```
3. Open http://localhost:5173. Requests to `/api` are proxied to `http://127.0.0.1:8000`.

## Production

Set `VITE_API_URL` to the Cloud Run URL of the agent (and start the agent with
`--allow_origins` for the frontend's domain), then `npm run build` and deploy `dist/`
to Firebase Hosting.

## What's in here

- `src/App.jsx`: nav, hero, quick actions, chat thread, composer (attach, drag-drop, ⌘V paste).
- `src/cards.jsx`: a card for each agent tool result (plan week view, decoded letter,
  office finder, syllabus, schedule screenshot). Formats are in `../CONTRACTS.md`.
- `src/api.js`: sessions + streaming `/run_sse` client.
- `src/styles.css`: design system with light and dark themes.
- `public/samples/`: sample letter, syllabus and work schedule for one-click demos.

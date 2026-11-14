# Shared contracts

Agreed before hacking starts at 11:30 AM Saturday. Don't change these without telling each other.
Paste this file into every Gemini or Claude prompt so both sides generate code that fits together.

## Event

Life Blocker returns a list of these as proposed blocks; Decode returns one per deadline.

```json
{
  "title": "Essay draft (WRIT 2)",
  "start": "2026-11-18T09:00:00-08:00",
  "end": "2026-11-18T11:00:00-08:00",
  "location": null,
  "description": "High-energy morning slot, before your 2 PM shift",
  "source": "plan",
  "confidence": 0.9
}
```

- `end`, `location` and `description` can be `null`.
- `source` is `"plan"` (Life Blocker) or `"document"` (Decode).
- `confidence` is 0 to 1. Below 0.7, the app asks the user to confirm before adding to Calendar.

## DecodeResult

```json
{
  "summary": "Your financial aid is on hold until you submit a form.",
  "what_it_means": "You won't get your aid money until this is done.",
  "urgency": "high",
  "action_items": [{ "task": "Submit the verification worksheet", "due": "2026-12-01" }],
  "deadlines": ["<Event objects>"],
  "contact": { "name": "Financial Aid Office", "email": "finaid@example.edu", "phone": "(831) 555-0142" },
  "draft_reply": "Hi, I received your notice about...",
  "translation": { "language": "Spanish", "text": "..." },
  "verify_note": "Confirm these details with the Financial Aid Office.",
  "tasks_for_planner": [{ "title": "Submit the verification worksheet", "minutes": 45, "energy": "high", "due": "2026-12-01" }]
}
```

- `urgency` is `"low"`, `"medium"` or `"high"`.
- `contact` and `translation` can be `null`. `contact.phone` is only present if the letter has one.
- `deadlines` are Events with `source: "document"`; no time in the letter means 5:00 PM.
- `tasks_for_planner` drops straight into LifeProfile `tasks` for `plan_life_blocks`.
- Tool status can also be `"error"` or `"not_a_letter"` with a `message`.

## LifeProfile

What Life Blocker plans around. The frontend collects it once, and Firestore saves it.

```json
{
  "fixed": [
    { "title": "CSE 30 lecture", "days": ["Mon", "Wed", "Fri"], "start": "10:40", "end": "11:45" },
    { "title": "Shift at the bookstore", "days": ["Tue", "Thu"], "start": "14:00", "end": "19:00" },
    { "title": "Gym", "days": ["Mon", "Wed"], "start": "17:00", "end": "18:00" }
  ],
  "chronotype": "morning",
  "job_drain": "high",
  "tasks": [
    { "title": "Essay draft", "minutes": 120, "energy": "high", "due": "2026-11-20" },
    { "title": "Laundry", "minutes": 60, "energy": "low", "due": null }
  ]
}
```

- `chronotype` is `"morning"` or `"night"`; `job_drain` and each task's `energy` are `"low"` or `"high"`.
- Events already on Google Calendar count as `fixed` too.
- Decode's `action_items` become `tasks`.

## Backend endpoints

Arav builds these; the frontend calls them. Every request sends the Google access token.

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/chat` | `message`, optional `image` (base64), optional `language`, optional `profile` (LifeProfile) | `reply` (text), optional `proposed_blocks` (Event list, not booked yet), `events_created` (Event list), optional `decode` (DecodeResult) |
| GET | `/calendar/events` | `from`, `to` (ISO dates) | Event list |
| POST | `/calendar/events` | Event list | Created event IDs |
| GET | `/health` | none | `ok` |

## Agent tools

Each is a Python function the agent can call, in build order:

1. `plan_life_blocks(profile, start, end)`: Aaryav
2. `decode_document(text, language)`: Aaryav
3. `campus_answers(question)`: Aaryav. A small sub-agent using ADK's built-in `google_search`, wrapped with `AgentTool`.
4. `get_schedule(start, end)` and `create_events(events)`: call Arav's Calendar code.

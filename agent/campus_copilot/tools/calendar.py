from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_google_calendar_service(access_token: str):
  """Builds the Google Calendar API client using the user's incoming OAuth access token."""
  creds = Credentials(token=access_token)
  service = build("calendar", "v3", credentials=creds)
  return service


def get_schedule(access_token: str, time_min: str, time_max: str):
  """Reads events from the user's Google Calendar between time_min and time_max (ISO format)."""
  try:
    service = get_google_calendar_service(access_token)
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    # Format events to match your Shared contract structure
    formatted_events = []
    for event in events:
      start = event["start"].get("dateTime", event["start"].get("date"))
      end = event["end"].get("dateTime", event["end"].get("date"))
      formatted_events.append({
          "title": event.get("summary", "Busy"),
          "start": start,
          "end": end,
          "location": event.get("location"),
          "description": event.get("description"),
          "source": "calendar",
          "confidence": 1.0,
      })
    return formatted_events
  except Exception as e:
    print(f"Error fetching calendar events: {e}")
    return []


def create_events(access_token: str, events_list: list):
  """Creates new events on the user's primary Google Calendar from a list of Event objects."""
  service = get_google_calendar_service(access_token)
  created_ids = []

  for event in events_list:
    body = {
        "summary": event.get("title"),
        "description": event.get("description"),
        "location": event.get("location"),
        "start": {"dateTime": event.get("start")},
        "end": {"dateTime": event.get("end")},
    }

    created_event = (
        service.events().insert(calendarId="primary", body=body).execute()
    )
    created_ids.append(created_event.get("id"))

  return created_ids
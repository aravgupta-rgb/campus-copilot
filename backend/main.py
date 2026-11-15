import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()
# Initialize Firebase Admin SDK safely
cred_path = "serviceAccountKey.json"
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    try:
        firebase_admin.initialize_app(cred)
    except ValueError:
        pass

# Safe client initialization so local testing doesn't crash if keys are missing
try:
    db = firestore.client()
except Exception:
    db = None

app = FastAPI(
    title="Campus Copilot Backend",
    description="Arav's Cloud Run backend wrapping agent & calendar tools",
    version="1.0.0"
)

# Shared Contract Models
class Event(BaseModel):
    title: str
    start: str
    end: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    source: str = "plan"
    confidence: float = 1.0

class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    language: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/calendar/events")
async def get_calendar_events(from_date: str, to_date: str, authorization: Optional[str] = Header(None)):
    """Reads events from the user's primary Google Calendar."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "")
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds = Credentials(token=token)
        service = build("calendar", "v3", credentials=creds)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=from_date,
            timeMax=to_date,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        items = events_result.get('items', [])
        formatted = []
        for event in items:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            formatted.append({
                "title": event.get('summary', 'Untitled'),
                "start": start,
                "end": end,
                "location": event.get('location'),
                "description": event.get('description'),
                "source": "calendar",
                "confidence": 1.0
            })
        return formatted
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/events")
async def create_calendar_events(events: List[Event], authorization: Optional[str] = Header(None)):
    """Books approved events onto the user's Google Calendar."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = authorization.replace("Bearer ", "")
    
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        
        creds = Credentials(token=token)
        service = build("calendar", "v3", credentials=creds)
        created_ids = []
        
        for ev in events:
            body = {
                "summary": ev.title,
                "description": ev.description,
                "location": ev.location,
                "start": {"dateTime": ev.start},
                "end": {"dateTime": ev.end} if ev.end else {"dateTime": ev.start}
            }
            created = service.events().insert(calendarId='primary', body=body).execute()
            created_ids.append(created.get('id'))
            
        return {"created_ids": created_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(payload: ChatRequest, authorization: Optional[str] = Header(None)):
    """Main chat endpoint handling student requests and routing to agent tools."""
    try:
        if payload.profile:
            db.collection("profiles").document("current_user").set(payload.profile)
            
        return {
            "reply": f"Received: {payload.message}. Backend is live and connected!",
            "proposed_blocks": [],
            "events_created": [],
            "decode": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
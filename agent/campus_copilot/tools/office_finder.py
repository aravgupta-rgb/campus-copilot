"""Tool: Office Finder (Google Maps Places API + Routes API).

After Decode says "contact the Financial Aid Office", this finds where the office
actually is, whether it's open, its hours and phone, and how long the walk is.

Auth: the same Google Cloud login as Vertex AI (application default credentials on
laptops, the service account on Cloud Run), so there's no separate Maps key.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import quote_plus

import google.auth
import google.auth.transport.requests
import httpx

logger = logging.getLogger(__name__)

CAMPUS_NAME = os.getenv("CAMPUS_NAME", "UC Santa Cruz")
CAMPUS_CENTER = (36.9914, -122.0609)  # UCSC, used to bias search results to campus
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")

PLACE_FIELDS = ",".join([
    "places.displayName", "places.formattedAddress", "places.location",
    "places.regularOpeningHours.weekdayDescriptions", "places.currentOpeningHours.openNow",
    "places.googleMapsUri", "places.nationalPhoneNumber", "places.websiteUri",
])

_creds = None


def _token() -> str:
    global _creds
    if _creds is None:
        _creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not _creds.valid:
        _creds.refresh(google.auth.transport.requests.Request())
    return _creds.token


def _headers(field_mask: str) -> dict:
    h = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json",
         "X-Goog-FieldMask": field_mask}
    if PROJECT:
        h["x-goog-user-project"] = PROJECT
    return h


async def _search(client: httpx.AsyncClient, query: str, count: int = 1) -> list[dict]:
    body = {
        "textQuery": query,
        "maxResultCount": count,
        "locationBias": {"circle": {
            "center": {"latitude": CAMPUS_CENTER[0], "longitude": CAMPUS_CENTER[1]},
            "radius": 5000.0}},
    }
    r = await client.post("https://places.googleapis.com/v1/places:searchText",
                          headers=_headers(PLACE_FIELDS), json=body)
    r.raise_for_status()
    return r.json().get("places", [])


async def _walk(client: httpx.AsyncClient, origin: dict, dest: dict) -> dict | None:
    body = {
        "origin": {"location": {"latLng": origin}},
        "destination": {"location": {"latLng": dest}},
        "travelMode": "WALK",
    }
    r = await client.post("https://routes.googleapis.com/directions/v2:computeRoutes",
                          headers=_headers("routes.duration,routes.distanceMeters"), json=body)
    r.raise_for_status()
    routes = r.json().get("routes", [])
    if not routes:
        return None
    seconds = int(str(routes[0].get("duration", "0s")).rstrip("s") or 0)
    meters = int(routes[0].get("distanceMeters", 0))
    return {"minutes": max(1, round(seconds / 60)), "miles": round(meters / 1609.34, 2)}


async def find_office(office: str, from_place: str = "") -> dict:
    """Finds a campus office or place: address, hours, open now, phone, and walking time.

    Use after decoding a letter that names an office, or when the student asks
    where something is on campus ("where's the registrar?").

    Args:
        office: The office or place to find, like "Financial Aid Office" or "Registrar".
        from_place: Optional starting point for walking directions, like
            "Baskin Engineering" or "Porter College". Empty to skip directions.

    Returns:
        A dict with name, address, open_now, hours (one line per weekday), phone,
        website, maps_link, and walk ({"minutes", "miles", "from", "directions_link"})
        when from_place is given.
    """
    query = office if CAMPUS_NAME.lower() in office.lower() else f"{office}, {CAMPUS_NAME}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            places = await _search(client, query)
            if not places:
                return {"status": "not_found",
                        "message": f"Couldn't find '{office}' near {CAMPUS_NAME}. Ask for the office's full name."}
            p = places[0]
            result = {
                "status": "ok",
                "name": p.get("displayName", {}).get("text", office),
                "address": p.get("formattedAddress"),
                "open_now": p.get("currentOpeningHours", {}).get("openNow"),
                "hours": [h.replace(" ", " ").replace(" ", " ")
                          for h in p.get("regularOpeningHours", {}).get("weekdayDescriptions", [])],
                "phone": p.get("nationalPhoneNumber"),
                "website": p.get("websiteUri"),
                "maps_link": p.get("googleMapsUri"),
            }
            if from_place and p.get("location"):
                start_q = from_place if CAMPUS_NAME.lower() in from_place.lower() else f"{from_place}, {CAMPUS_NAME}"
                starts = await _search(client, start_q)
                if starts and starts[0].get("location"):
                    walk = await _walk(client, starts[0]["location"], p["location"])
                    if walk:
                        walk["from"] = starts[0].get("displayName", {}).get("text", from_place)
                        walk["directions_link"] = (
                            "https://www.google.com/maps/dir/?api=1"
                            f"&origin={quote_plus(starts[0].get('formattedAddress', from_place))}"
                            f"&destination={quote_plus(result['address'] or result['name'])}"
                            "&travelmode=walking")
                        result["walk"] = walk
            return result
    except (httpx.HTTPError, google.auth.exceptions.GoogleAuthError) as exc:
        logger.warning("Office Finder failed: %s", exc)
        return {"status": "error", "message": "Maps lookup failed. Share the office name and suggest checking the school website."}


if __name__ == "__main__":  # quick manual check: python -m campus_copilot.tools.office_finder
    from dotenv import load_dotenv
    load_dotenv()
    print(asyncio.run(find_office("Financial Aid Office", "Baskin Engineering")))

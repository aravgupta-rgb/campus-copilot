"""Calendar tools: no token -> not_connected; token is read from temp state only."""

import asyncio

from campus_copilot.tools import calendar_tools as ct


class FakeCtx:
    def __init__(self, state):
        self.state = state


def test_no_token_means_not_connected():
    assert asyncio.run(ct.get_schedule("2026-11-16", "2026-11-22", FakeCtx({})))["status"] == "not_connected"
    assert asyncio.run(ct.book_events([{"title": "x", "start": "a", "end": "b"}], FakeCtx({})))["status"] == "not_connected"


def test_schedule_uses_token_and_formats_fixed(monkeypatch):
    seen = {}

    def fake_get(token, tmin, tmax):
        seen.update(token=token, tmin=tmin, tmax=tmax)
        return [
            {"title": "Dentist", "start": "2026-11-17T09:00:00-08:00", "end": "2026-11-17T10:00:00-08:00"},
            {"title": "Holiday", "start": "2026-11-20", "end": "2026-11-21"},  # all-day: not a fixed block
        ]

    monkeypatch.setattr(ct.gcal, "get_schedule", fake_get)
    r = asyncio.run(ct.get_schedule("2026-11-16", "2026-11-22", FakeCtx({ct.TOKEN_KEY: "tok"})))
    assert seen == {"token": "tok", "tmin": "2026-11-16T00:00:00-08:00", "tmax": "2026-11-22T23:59:59-08:00"}
    assert r["status"] == "ok" and r["count"] == 2
    assert [f["title"] for f in r["as_fixed"]] == ["Dentist"]


class FakeService:
    """Records inserted bodies like googleapiclient's events().insert(...).execute()."""

    def __init__(self, fail=False):
        self.bodies, self.fail = [], fail

    def events(self):
        return self

    def insert(self, calendarId, body):
        self.bodies.append(body)
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("401")
        return {"id": f"id{len(self.bodies)}"}


def test_book_everything_timed_and_all_day(monkeypatch):
    svc = FakeService()
    monkeypatch.setattr(ct.gcal, "get_google_calendar_service", lambda token: svc)
    events = [
        {"title": "Study", "start": "2026-11-16T07:30:00-08:00", "end": "2026-11-16T09:00:00-08:00", "source": "plan"},
        {"title": "CSE 30", "start": "2026-11-16T14:40:00-08:00", "end": "2026-11-16T15:45:00-08:00", "source": "fixed"},
        {"title": "📝 CSE 30 Midterm", "start": "2026-11-18", "end": "2026-11-19", "all_day": True, "source": "deadline"},
        {"title": "no times"},
    ]
    ok = asyncio.run(ct.book_events(events, FakeCtx({ct.TOKEN_KEY: "tok"})))
    assert ok["status"] == "ok" and ok["created"] == 3
    study, cls, exam = svc.bodies
    assert study["start"] == {"dateTime": "2026-11-16T07:30:00-08:00", "timeZone": "America/Los_Angeles"}
    assert study["colorId"] == "9" and study["reminders"]["overrides"][0]["minutes"] == 10
    assert cls["colorId"] == "8" and "reminders" not in cls
    assert exam["start"] == {"date": "2026-11-18"} and exam["end"] == {"date": "2026-11-19"} and exam["colorId"] == "11"


def test_book_reports_errors(monkeypatch):
    monkeypatch.setattr(ct.gcal, "get_google_calendar_service", lambda token: FakeService(fail=True))
    bad = asyncio.run(ct.book_events([{"title": "Essay", "start": "s", "end": "e"}], FakeCtx({ct.TOKEN_KEY: "tok"})))
    assert bad["status"] == "error"

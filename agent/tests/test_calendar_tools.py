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


def test_book_skips_incomplete_and_reports_errors(monkeypatch):
    monkeypatch.setattr(ct.gcal, "create_events", lambda token, evs: [f"id{i}" for i, _ in enumerate(evs)])
    ok = asyncio.run(ct.book_events(
        [{"title": "Essay", "start": "2026-11-17T09:00:00-08:00", "end": "2026-11-17T11:00:00-08:00"}, {"title": "no times"}],
        FakeCtx({ct.TOKEN_KEY: "tok"})))
    assert ok == {"status": "ok", "created": 1, "titles": ["Essay"]}

    def boom(token, evs):
        raise RuntimeError("401")

    monkeypatch.setattr(ct.gcal, "create_events", boom)
    bad = asyncio.run(ct.book_events([{"title": "Essay", "start": "s", "end": "e"}], FakeCtx({ct.TOKEN_KEY: "tok"})))
    assert bad["status"] == "error"

"""Syllabus items become Life Blocker tasks and calendar deadlines correctly."""

from campus_copilot.tools.syllabus import Item, _event, _task

COURSE = "CSE 30: Programming Abstractions"


def item(**kw):
    base = dict(title="Homework 6", type="assignment", due="2026-11-16", due_time=None,
                weight_percent=None, prep_minutes=150, confidence=0.95)
    return Item(**{**base, **kw})


def test_exam_becomes_study_task():
    t = _task(COURSE, item(title="Midterm 2", type="exam", due="2026-11-20", prep_minutes=360))
    assert t == {"title": "CSE 30: Study for Midterm 2", "minutes": 360, "energy": "high", "due": "2026-11-20"}


def test_short_reading_is_low_energy():
    assert _task(COURSE, item(title="Chapter 9", type="reading", prep_minutes=60))["energy"] == "low"


def test_homework_deadline_defaults_to_1159pm():
    e = _event(COURSE, item())
    assert e["start"] == "2026-11-16T23:59:00-08:00" and e["title"] == "CSE 30: Homework 6"


def test_exam_event_is_two_hours_with_weight():
    e = _event(COURSE, item(title="Midterm 2", type="exam", due="2026-11-20", due_time="10:40", weight_percent=20))
    assert e["end"] == "2026-11-20T12:40:00-08:00" and "20% of grade" in e["description"]


def test_undated_item_has_no_event():
    assert _event(COURSE, item(due=None)) is None

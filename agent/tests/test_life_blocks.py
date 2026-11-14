"""Rules Life Blocker must never break. Run from agent/:  python -m pytest -q"""

from datetime import date, datetime, timedelta

from campus_copilot.tools.schedule_math import (
    BUFFER,
    TZ,
    Planner,
    build_segments,
    expand_fixed,
    normalize_tasks,
)

START, END = date(2026, 11, 16), date(2026, 11, 22)  # Mon to Sun

PROFILE = {
    "fixed": [
        {"title": "CSE 30 lecture", "days": ["Mon", "Wed", "Fri"], "start": "10:40", "end": "11:45"},
        {"title": "Shift at the bookstore", "days": ["Tue", "Thu"], "start": "14:00", "end": "19:00"},
        {"title": "Gym", "days": ["Mon", "Wed"], "start": "17:00", "end": "18:00"},
    ],
    "chronotype": "morning",
    "job_drain": "high",
    "tasks": [
        {"title": "Essay draft", "minutes": 120, "energy": "high", "due": "2026-11-20"},
        {"title": "Problem set", "minutes": 90, "energy": "high", "due": "2026-11-19"},
        {"title": "Laundry", "minutes": 60, "energy": "low", "due": None},
        {"title": "Groceries", "minutes": 45, "energy": "low", "due": None},
    ],
}


def plan(profile=PROFILE, suggestions=()):
    busy = expand_fixed(profile["fixed"], START, END)
    segs = build_segments(busy, START, END, profile["chronotype"], profile["job_drain"])
    tasks = normalize_tasks(profile["tasks"])
    p = Planner(segs, tasks)
    for s in suggestions:
        p.try_place(*s)
    p.fill_remaining()
    return busy, p


def test_weekly_items_expand_to_right_days():
    busy = expand_fixed(PROFILE["fixed"], START, END)
    assert sum(b.title == "CSE 30 lecture" for b in busy) == 3
    assert sum(b.kind == "work" for b in busy) == 2
    assert sum(b.kind == "gym" for b in busy) == 2


def test_no_block_overlaps_a_commitment_or_its_buffer():
    busy, p = plan()
    for blk in p.placed:
        for b in busy:
            assert blk.end <= b.start - BUFFER or blk.start >= b.end + BUFFER, (blk, b)


def test_blocks_never_overlap_each_other():
    _, p = plan()
    blocks = sorted(p.placed, key=lambda x: x.start)
    for a, b in zip(blocks, blocks[1:]):
        assert a.end <= b.start


def test_every_task_fully_scheduled_with_exact_minutes():
    _, p = plan()
    assert p.unscheduled() == []
    for t in p.tasks:
        total = sum(int((x.end - x.start).total_seconds() // 60) for x in p.placed if x.task is t)
        assert total == t.minutes, t.title


def test_focus_work_never_in_low_energy_slots():
    _, p = plan()
    for x in p.placed:
        if x.task.energy == "high":
            assert x.energy != "low", (x.task.title, x.start)


def test_no_deep_work_right_after_shift_or_gym():
    busy, p = plan()
    for b in busy:
        if b.kind in ("work", "gym"):
            hours = 2 if b.kind == "work" else 1
            for x in p.placed:
                if x.task.energy == "high":
                    assert not (b.end <= x.start < b.end + timedelta(hours=hours)), (x.task.title, b.title)


def test_work_finishes_before_due_date():
    _, p = plan()
    for x in p.placed:
        if x.task.deadline:
            assert x.end <= x.task.deadline, x.task.title


def test_bad_gemini_suggestion_is_rejected():
    # Monday 10:30 to 12:00 overlaps the 10:40 CSE 30 lecture
    bad = ("Essay draft", "2026-11-16T10:30:00-08:00", "2026-11-16T12:00:00-08:00", "bad", "gemini")
    _, p = plan(suggestions=[bad])
    assert p.rejected, "overlapping suggestion should be rejected"
    assert all(x.source == "fallback" for x in p.placed)
    assert p.unscheduled() == []


def test_good_gemini_suggestion_is_kept():
    good = ("Essay draft", "2026-11-17T08:00:00-08:00", "2026-11-17T10:00:00-08:00", "fresh morning", "gemini")
    _, p = plan(suggestions=[good])
    kept = [x for x in p.placed if x.source == "gemini"]
    assert len(kept) == 1 and kept[0].start == datetime(2026, 11, 17, 8, 0, tzinfo=TZ)


def test_too_little_time_reports_unscheduled():
    busy_week = {**PROFILE, "tasks": [{"title": "Thesis", "minutes": 6000, "energy": "high", "due": None}]}
    _, p = plan(busy_week)
    left = p.unscheduled()
    assert left and left[0]["task"] == "Thesis" and left[0]["minutes_left"] > 0

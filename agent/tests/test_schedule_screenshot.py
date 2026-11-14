"""Screenshot items -> LifeProfile fixed format, and that format feeds the planner."""

from datetime import date

from campus_copilot.tools.schedule_math import expand_fixed
from campus_copilot.tools.schedule_screenshot import ScheduleItem, _to_fixed


def item(**kw):
    base = dict(title="Bookstore", kind="work", date=None, days=[], start="14:00", end="19:00", confidence=0.95)
    return ScheduleItem(**{**base, **kw})


def test_dated_shift_becomes_one_off_event():
    f = _to_fixed(item(date="2026-11-17"))
    assert f["start"] == "2026-11-17T14:00:00" and f["end"] == "2026-11-17T19:00:00"
    assert f["kind"] == "work"


def test_weekly_class_keeps_days():
    f = _to_fixed(item(title="CSE 30", kind="class", days=["Mon", "Wed", "Fri"], start="10:40", end="11:45"))
    assert f["days"] == ["Mon", "Wed", "Fri"] and f["kind"] == "other"


def test_screenshot_items_feed_the_planner():
    fixed = [_to_fixed(item(date="2026-11-17")), _to_fixed(item(date="2026-11-19"))]
    busy = expand_fixed(fixed, date(2026, 11, 16), date(2026, 11, 22))
    assert len(busy) == 2 and all(b.kind == "work" for b in busy)
    assert busy[0].start.hour == 14 and busy[0].end.hour == 19

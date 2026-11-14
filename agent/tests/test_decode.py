"""Decode helpers: deadlines become valid Events, translation only when asked."""

from campus_copilot.tools.decode import Deadline, _event_from_deadline, _translation_rule


def test_deadline_without_time_defaults_to_5pm_event():
    e = _event_from_deadline(Deadline(title="Verification documents", date="2026-12-01", time=None, confidence=0.95))
    assert e["start"] == "2026-12-01T17:00:00-08:00"
    assert e["end"] == "2026-12-01T17:30:00-08:00"
    assert e["source"] == "document" and e["title"].startswith("Due:")


def test_deadline_with_time_and_clamped_confidence():
    e = _event_from_deadline(Deadline(title="Housing form", date="2026-11-20", time="23:59", confidence=1.4))
    assert e["start"].startswith("2026-11-20T23:59") and e["confidence"] == 1.0


def test_bad_date_is_dropped_not_crashing():
    assert _event_from_deadline(Deadline(title="x", date="sometime soon", time=None, confidence=0.5)) is None


def test_translation_only_when_requested():
    assert _translation_rule("").startswith("null")
    assert _translation_rule("English").startswith("null")
    assert "Spanish" in _translation_rule("Spanish")

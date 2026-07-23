from datetime import datetime, timedelta, timezone
from formatting import format_countdown, color_for, GREEN, YELLOW, RED

NOW = datetime(2026, 7, 23, 21, 0, tzinfo=timezone.utc)


def _in(**kw):
    return NOW + timedelta(**kw)


def test_countdown_days_and_hours():
    assert format_countdown(_in(days=1, hours=12, minutes=30), NOW) == "1g 12s"


def test_countdown_hours_and_minutes():
    assert format_countdown(_in(hours=1, minutes=12), NOW) == "1s 12dk"


def test_countdown_minutes_only():
    assert format_countdown(_in(minutes=12), NOW) == "12dk"


def test_countdown_under_one_minute():
    assert format_countdown(_in(seconds=30), NOW) == "1dk"


def test_countdown_expired():
    assert format_countdown(_in(seconds=-5), NOW) == "yenilendi"


def test_color_thresholds():
    assert color_for(30.0) == GREEN
    assert color_for(59.9) == GREEN
    assert color_for(60.0) == YELLOW
    assert color_for(71.0) == YELLOW
    assert color_for(85.0) == YELLOW
    assert color_for(85.1) == RED
    assert color_for(90.0) == RED

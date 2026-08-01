from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from formatting import format_reset_time
from usage_client import Window


@pytest.fixture(scope="module")
def root():
    r = app_module.ctk.CTk()
    r.withdraw()
    yield r
    r.destroy()


def _win(hours_ahead: float, util: float = 42.0) -> Window:
    return Window(
        utilization=util,
        resets_at=datetime.now(timezone.utc)
        + timedelta(hours=hours_ahead)
        + timedelta(seconds=30),
    )


def test_row_shows_percent_and_countdown(root):
    row = app_module._Row(root, "5h")
    row.set(_win(2))
    assert row.pct.cget("text") == "42%"
    assert " · " in row.countdown.cget("text")


def test_row_skips_countdown_write_when_text_unchanged(root):
    row = app_module._Row(root, "5h")
    row.set(_win(2))

    writes = []
    original = row.countdown.configure

    def spy(**kwargs):
        if "text" in kwargs:
            writes.append(kwargs["text"])
        return original(**kwargs)

    row.countdown.configure = spy
    row.refresh_countdown()
    row.refresh_countdown()
    row.refresh_countdown()
    assert writes == []


def test_row_recovers_after_set_none(root):
    row = app_module._Row(root, "5h")
    window = _win(2)
    row.set(window)
    good = row.countdown.cget("text")

    row.set(None)
    assert row.countdown.cget("text") == ""
    assert row.pct.cget("text") == ""

    row.set(window)
    assert row.countdown.cget("text") == good


def test_row_expired_has_no_reset_time(root):
    row = app_module._Row(root, "5h")
    row.set(_win(-1))
    text = row.countdown.cget("text")
    assert "reset" in text
    assert " · " not in text


def test_row_day_name_disappears_after_local_midnight(root):
    local_tz = datetime.now().astimezone().tzinfo
    boundary = datetime.now(local_tz).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    resets_at = boundary + timedelta(hours=1)
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5h")
    row.window = window

    now_before_midnight = boundary - timedelta(minutes=10)
    now_after_midnight = boundary + timedelta(minutes=30)

    expected_before = format_reset_time(resets_at, now_before_midnight)
    expected_after = format_reset_time(resets_at, now_after_midnight)
    assert " " in expected_before
    assert " " not in expected_after

    row.refresh_countdown(now=now_before_midnight)
    assert row.countdown.cget("text").endswith(f" · resets {expected_before}")

    row.refresh_countdown(now=now_after_midnight)
    assert row.countdown.cget("text").endswith(f" · resets {expected_after}")


def test_row_reset_time_disappears_when_expired(root):
    local_tz = datetime.now().astimezone().tzinfo
    anchor = datetime.now(local_tz).replace(hour=12, minute=0, second=0, microsecond=0)
    resets_at = anchor
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5h")
    row.window = window

    now_before = anchor - timedelta(minutes=5)
    now_after = anchor + timedelta(minutes=5)
    assert now_before.date() == now_after.date()

    row.refresh_countdown(now=now_before)
    assert " · " in row.countdown.cget("text")

    row.refresh_countdown(now=now_after)
    text_after = row.countdown.cget("text")
    assert "reset" in text_after
    assert " · " not in text_after


def test_row_format_reset_time_called_once_per_cycle(root):
    local_tz = datetime.now().astimezone().tzinfo
    anchor = datetime.now(local_tz).replace(hour=9, minute=0, second=0, microsecond=0)
    resets_at = anchor + timedelta(hours=3)
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5h")
    row.window = window

    calls = []
    original = app_module.format_reset_time

    def counting_wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    app_module.format_reset_time = counting_wrapper
    try:
        now_values = [
            anchor,
            anchor + timedelta(seconds=30),
            anchor + timedelta(minutes=5),
            anchor + timedelta(hours=1),
            anchor + timedelta(hours=2, minutes=50),
        ]
        for now in now_values:
            row.refresh_countdown(now=now)
    finally:
        app_module.format_reset_time = original

    assert len(calls) == 1


def test_row_critical_utilization_gets_a_border(root):
    row = app_module._Row(root, "5h")
    row.set(_win(2, util=90.0))
    assert row.bar.cget("border_width") == 2
    row.set(_win(2, util=30.0))
    assert row.bar.cget("border_width") == 0

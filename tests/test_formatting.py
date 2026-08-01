import re
from datetime import datetime, timedelta, timezone
from formatting import (
    format_countdown,
    format_reset_time,
    color_for,
    worst_color,
    DAY_NAMES,
    GREEN,
    YELLOW,
    RED,
)

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


# Türkiye saati (UTC+3). Testlerde sabitlenir ki sonuç makinenin
# saat dilimine bağlı olmasın.
TR = timezone(timedelta(hours=3))


def test_reset_time_same_local_day():
    # yerel 09:00 -> yerel 14:00, ikisi de 25 Temmuz
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 25, 11, 0, tzinfo=timezone.utc)
    assert format_reset_time(resets, now, TR) == "14:00"


def test_reset_time_crosses_local_midnight_while_utc_day_is_same():
    # Asıl tuzak: UTC'de iki tarih de 25 Temmuz, ama yerelde
    # 25 Temmuz 22:00 -> 26 Temmuz 01:00. Gün adı çıkmalı.
    now = datetime(2026, 7, 25, 19, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc)
    assert now.date() == resets.date()  # UTC tarihleri aynı
    assert format_reset_time(resets, now, TR) == "Paz 01:00"


def test_reset_time_days_away():
    # haftalık dilim: yerel 25 Temmuz 09:00 -> 31 Temmuz 12:58
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 31, 9, 58, tzinfo=timezone.utc)
    assert format_reset_time(resets, now, TR) == "Cum 12:58"


def test_reset_time_expired_returns_empty():
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    assert format_reset_time(now - timedelta(seconds=5), now, TR) == ""


def test_reset_time_exactly_now_returns_empty():
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    assert format_reset_time(now, now, TR) == ""


def test_reset_time_uses_system_local_when_tz_omitted():
    # tz verilmezse çökmemeli ve SS:DD biçiminde bir şey dönmeli.
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    out = format_reset_time(now + timedelta(hours=2), now)
    assert re.fullmatch(r"(\w{3} )?\d{2}:\d{2}", out)


def test_day_names_are_turkish_and_locale_independent():
    assert DAY_NAMES == ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def test_worst_color_picks_the_more_severe_window():
    assert worst_color(22.0, 92.0) == RED
    assert worst_color(92.0, 22.0) == RED
    assert worst_color(22.0, 68.0) == YELLOW
    assert worst_color(22.0, 40.0) == GREEN


def test_worst_color_ignores_missing_windows():
    assert worst_color(None, 68.0) == YELLOW
    assert worst_color(22.0, None) == GREEN


def test_worst_color_defaults_to_safe_before_any_data():
    assert worst_color(None, None) == GREEN

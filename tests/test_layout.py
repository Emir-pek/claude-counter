from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from usage_client import UsageData, UsageError, Window


@pytest.fixture(scope="module")
def widget():
    w = app_module.UsageApp()
    w.update()
    w.withdraw()
    yield w
    w.destroy()


def _fill(widget, five=100.0, seven=100.0):
    now = datetime.now(timezone.utc)
    midnight = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    widget.render(UsageData(
        five_hour=Window(utilization=five,
                         resets_at=(midnight + timedelta(hours=1)).astimezone(timezone.utc)),
        seven_day=Window(utilization=seven,
                         resets_at=(midnight + timedelta(days=6, hours=23)).astimezone(timezone.utc)),
        fetched_at=now,
    ))
    widget.update_idletasks()


def _width(widget):
    return int(widget.wm_geometry().split("+")[0].split("x")[0])


def test_window_has_no_native_titlebar(widget):
    assert widget.overrideredirect()


def test_idle_card_is_148_wide(widget):
    assert _width(widget) == app_module.CARD_W_IDLE


def test_idle_opacity_matches_the_configured_default(widget):
    assert widget.attributes("-alpha") == pytest.approx(app_module.IDLE_OPACITY)


def test_header_and_countdowns_are_hidden_while_idle(widget):
    assert widget.header.grid_info() == {}
    assert widget.five.countdown.grid_info() == {}
    assert widget.seven.countdown.grid_info() == {}


def test_row_labels_are_short_turkish_abbreviations(widget):
    assert widget.five.label.cget("text") == "5s"
    assert widget.seven.label.cget("text") == "7g"


def test_render_updates_both_rows(widget):
    _fill(widget)
    assert widget.five.pct.cget("text") == "100%"
    assert widget.seven.pct.cget("text") == "100%"


def test_render_error_sets_the_status_line_but_only_shows_it_expanded(widget):
    widget.render_error(UsageError("network", "sunucuya ulaşılamadı"))
    assert widget._status_text == "sunucuya ulaşılamadı"
    assert widget.status_label.grid_info() == {}  # idle: gizli


def test_rate_limited_error_uses_the_spec_copy(widget):
    widget.render_error(UsageError("rate_limited", "429"))
    assert widget._status_text == "Sınıra takıldı — yeniden deneniyor"
    assert widget._status_color == app_module.COLORS["bar_mid"]


def test_render_clears_the_status_line(widget):
    widget.render_error(UsageError("network", "hata"))
    _fill(widget)
    assert widget._status_text == ""


def test_window_is_smaller_than_the_old_decorated_layout(widget):
    assert app_module.CARD_W_IDLE < 260
    assert app_module.CARD_W_EXPANDED < 260


def test_snap_to_survives_a_win32_failure(widget, monkeypatch):
    def _boom(_window):
        raise OSError("GetParent failed")

    monkeypatch.setattr(app_module, "frame_hwnd", _boom)
    widget._snap_to(app_module.CARD_W_IDLE, 100, app_module.IDLE_OPACITY)

from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from crab_overlay import NULL_CRAB
from usage_client import UsageData, UsageError, Window


class RecordingCrab:
    def __init__(self):
        self.moods = []

    def set_mood(self, utilization):
        self.moods.append(utilization)


@pytest.fixture
def widget():
    w = app_module.UsageApp()
    w.withdraw()  # test sirasinda pencere gorunmesin
    yield w
    w.destroy()


def _win(util):
    return Window(utilization=util,
                  resets_at=datetime.now(timezone.utc) + timedelta(hours=1))


def _data(five=None, seven=None):
    return UsageData(five_hour=five, seven_day=seven,
                     fetched_at=datetime.now(timezone.utc))


def test_widget_starts_with_a_safe_default_crab():
    # main() overlay'i kurmadan once render() cagrilabilir; varsayilan
    # null-object olmazsa AttributeError ile patlardi.
    assert app_module.UsageApp.crab is NULL_CRAB


def test_render_reports_the_busier_window(widget):
    widget.crab = RecordingCrab()
    widget.render(_data(_win(30.0), _win(78.0)))
    assert widget.crab.moods == [78.0]


def test_render_uses_the_only_window_present(widget):
    widget.crab = RecordingCrab()
    widget.render(_data(None, _win(12.0)))
    assert widget.crab.moods == [12.0]


def test_render_skips_the_crab_when_both_windows_are_missing(widget):
    widget.crab = RecordingCrab()
    widget.render(_data(None, None))
    assert widget.crab.moods == []


def test_render_error_leaves_the_mood_untouched(widget):
    # Veri yokken ruh hali son bilinen degerde kalmali, sifirlanmamali.
    widget.crab = RecordingCrab()
    widget.render_error(UsageError("network", "yok"))
    assert widget.crab.moods == []

from datetime import datetime, timedelta, timezone

from app import UsageApp
from crab_overlay import NULL_CRAB
from usage_client import UsageData, UsageError, Window


class RecordingCrab:
    def __init__(self):
        self.moods = []

    def set_mood(self, utilization):
        self.moods.append(utilization)


class StubRow:
    def set(self, window):
        self.window = window


class StubLabel:
    def configure(self, **kwargs):
        self.kwargs = kwargs


class StubApp:
    """render()/render_error()'un dokundugu yuzeyin tamami.

    Gercek UsageApp acilmiyor: bu Python kurulumunda ikinci bir Tk koku
    yaratmak init.tcl'i bulamayip patliyor, test_app_row.py zaten bir kok
    aciyor. Metotlar sinif uzerinden cagrilarak gercek kod calistiriliyor.
    """

    def __init__(self):
        self.five = StubRow()
        self.seven = StubRow()
        self.status = StubLabel()
        self.crab = RecordingCrab()
        self._data = None


def _win(util):
    return Window(utilization=util,
                  resets_at=datetime.now(timezone.utc) + timedelta(hours=1))


def _data(five=None, seven=None):
    return UsageData(five_hour=five, seven_day=seven,
                     fetched_at=datetime.now(timezone.utc))


def _render(app, data):
    UsageApp.render(app, data)


def test_widget_starts_with_a_safe_default_crab():
    # main() overlay'i kurmadan once render() cagrilabilir; varsayilan
    # null-object olmazsa AttributeError ile patlardi.
    assert UsageApp.crab is NULL_CRAB


def test_render_reports_the_five_hour_window():
    app = StubApp()
    _render(app, _data(_win(30.0), _win(78.0)))
    assert app.crab.moods == [30.0]


def test_weekly_window_does_not_drive_the_mood():
    # Haftalik dolmus olsa da 5 saatlik bosken yengec sakin kalmali.
    app = StubApp()
    _render(app, _data(_win(12.0), _win(99.0)))
    assert app.crab.moods == [12.0]


def test_render_passes_none_when_the_five_hour_window_is_missing():
    # app.py dallanmiyor; None'i set_mood yutuyor ve kademe korunuyor.
    # Korumanin kendisi test_crab_overlay.py'de dogrulaniyor.
    app = StubApp()
    _render(app, _data(None, _win(12.0)))
    assert app.crab.moods == [None]


def test_render_error_leaves_the_mood_untouched():
    # Veri yokken ruh hali son bilinen degerde kalmali, sifirlanmamali.
    app = StubApp()
    UsageApp.render_error(app, UsageError("network", "yok"))
    assert app.crab.moods == []


def test_render_still_updates_the_rows():
    # Yengec eklentisi asil isi bozmamali.
    app = StubApp()
    five, seven = _win(30.0), _win(78.0)
    _render(app, _data(five, seven))
    assert app.five.window is five
    assert app.seven.window is seven

from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from formatting import GREEN, RED
from usage_client import UsageData, Window


@pytest.fixture(scope="module")
def widget():
    w = app_module.UsageApp()
    w.withdraw()
    yield w
    w.destroy()


def _stop_ring(widget):
    if widget._ring_after is not None:
        widget.after_cancel(widget._ring_after)
        widget._ring_after = None


def test_dot_has_one_canvas_item_when_calm(widget):
    widget._level = GREEN
    widget._redraw_dot()
    assert len(widget.dot_canvas.find_all()) == 1


def test_dot_gets_a_second_item_for_the_ring(widget):
    # glow=0 burada: yalnızca halkanın kendi öğesini eklediğini sınıyoruz,
    # glow halosunun eklediği üçüncü öğeyle karışmasın.
    widget._redraw_dot(ring_scale=1.2, ring_visible=True, glow=0.0)
    try:
        assert len(widget.dot_canvas.find_all()) == 2
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_dot_gets_a_third_item_for_the_glow_halo(widget):
    # Ring + glow halosu + nokta = 3 ayrı canvas öğesi. Halo, noktanın kendi
    # outline'ını kalınlaştırmak yerine arkasına ayrı bir oval çizer (bkz.
    # _redraw_dot) — bu yüzden glow > 0 iken öğe sayısı 2 değil 3 olmalı.
    widget._redraw_dot(ring_scale=1.2, ring_visible=True, glow=0.5)
    try:
        assert len(widget.dot_canvas.find_all()) == 3
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_glow_halo_alone_adds_one_item_without_the_ring(widget):
    widget._redraw_dot(glow=0.5)
    try:
        assert len(widget.dot_canvas.find_all()) == 2
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_update_dot_starts_the_ring_timer_when_critical(widget):
    widget._level = GREEN
    widget._update_dot()
    assert widget._ring_after is None

    widget._level = RED
    widget._update_dot()
    try:
        assert widget._ring_after is not None
    finally:
        _stop_ring(widget)
        widget._level = GREEN
        widget._redraw_dot()


def test_update_dot_stops_the_ring_timer_when_no_longer_critical(widget):
    widget._level = RED
    widget._update_dot()
    assert widget._ring_after is not None

    widget._level = GREEN
    widget._update_dot()
    assert widget._ring_after is None


def test_render_with_high_utilization_wires_up_the_ring_end_to_end(widget):
    # render() -> worst_color -> _level -> _update_dot -> ring zincirinin
    # her parçası ayrı ayrı sınanıyordu (worst_color izole, _update_dot
    # elle atanmış _level ile); gerçek render() ile uçtan uca çalıştığını
    # doğrulayan hiçbir test yoktu.
    now = datetime.now(timezone.utc)
    data = UsageData(
        five_hour=Window(utilization=90.0, resets_at=now + timedelta(hours=1)),
        seven_day=Window(utilization=10.0, resets_at=now + timedelta(days=6)),
        fetched_at=now,
    )
    try:
        widget.render(data)
        assert widget._level == RED
        assert widget._ring_after is not None
    finally:
        _stop_ring(widget)
        widget._level = GREEN
        widget._redraw_dot()

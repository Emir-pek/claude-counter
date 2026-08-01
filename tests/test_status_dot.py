import pytest

import app as app_module
from formatting import GREEN, RED


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
    widget._redraw_dot(ring_scale=1.2, ring_visible=True, glow=0.5)
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

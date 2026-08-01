import pytest

from card_geometry import (
    corner_position, ease_out_cubic, glow_phase, interpolate,
    point_in_rect, ring_phase, tween_frames,
)


def test_corner_position_bottom_right():
    assert corner_position((0, 0, 1920, 1040), (148, 52), "bottom-right", 16) == (1756, 972)


def test_corner_position_bottom_left():
    assert corner_position((0, 0, 1920, 1040), (148, 52), "bottom-left", 16) == (16, 972)


def test_corner_position_top_right():
    assert corner_position((0, 0, 1920, 1040), (148, 52), "top-right", 16) == (1756, 16)


def test_corner_position_top_left():
    assert corner_position((0, 0, 1920, 1040), (148, 52), "top-left", 16) == (16, 16)


def test_corner_position_honours_work_area_origin():
    # Cok monitorlu kurulumda calisma alani (0,0)'da baslamayabilir.
    assert corner_position((-1920, 0, 1920, 1040), (148, 52), "bottom-right", 16) == (-164, 972)


def test_corner_position_rejects_unknown_corner():
    with pytest.raises(ValueError):
        corner_position((0, 0, 100, 100), (10, 10), "middle", 0)


def test_point_in_rect_edges():
    rect = (100, 100, 50, 50)
    assert point_in_rect(120, 120, rect) is True
    assert point_in_rect(100, 100, rect) is True   # sol/üst kenar dahil
    assert point_in_rect(150, 120, rect) is False  # sağ kenar hariç
    assert point_in_rect(120, 150, rect) is False  # alt kenar hariç
    assert point_in_rect(99, 120, rect) is False


def test_ease_out_cubic_endpoints_and_clamping():
    assert ease_out_cubic(0.0) == 0.0
    assert ease_out_cubic(1.0) == 1.0
    assert ease_out_cubic(-1.0) == 0.0
    assert ease_out_cubic(2.0) == 1.0


def test_ease_out_cubic_frontloads_motion():
    # ease-out: erken hizli, sona dogru yavas -> orta nokta lineer yariden ileride.
    assert ease_out_cubic(0.5) > 0.5


def test_interpolate_uses_eased_progress():
    assert interpolate(100, 200, 0.0) == 100
    assert interpolate(100, 200, 1.0) == 200
    assert interpolate(100, 200, 0.5) == pytest.approx(100 + 100 * ease_out_cubic(0.5))


def test_tween_frames_includes_start_and_end():
    frames = tween_frames(4)
    assert frames[0] == 0.0
    assert frames[-1] == 1.0
    assert len(frames) == 5


def test_tween_frames_rejects_zero_steps():
    with pytest.raises(ValueError):
        tween_frames(0)


def test_ring_phase_grows_then_hides_each_cycle():
    scale_start, visible_start = ring_phase(0)
    assert visible_start is True
    assert scale_start == pytest.approx(0.9)

    scale_mid, visible_mid = ring_phase(900)  # %50 faz
    assert visible_mid is True
    assert scale_mid > scale_start

    _scale_late, visible_late = ring_phase(1700)  # %94 faz
    assert visible_late is False


def test_ring_phase_wraps_every_period():
    assert ring_phase(0) == ring_phase(1800)


def test_glow_phase_peaks_at_midpoint_and_returns_to_zero():
    assert glow_phase(0) == pytest.approx(0.0)
    assert glow_phase(900) == pytest.approx(1.0)
    assert glow_phase(1800) == pytest.approx(0.0, abs=1e-9)

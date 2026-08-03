import pytest

from card_geometry import (
    DOT_OVERLAY_BIAS_RATIO, corner_position, dot_overlay_center, ease_out_cubic,
    smoothstep, glow_phase, interpolate, point_in_rect, ring_phase, tween_frames,
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


def test_smoothstep_endpoints_and_clamping():
    assert smoothstep(0.0) == 0.0
    assert smoothstep(1.0) == 1.0
    assert smoothstep(-1.0) == 0.0
    assert smoothstep(2.0) == 1.0


def test_smoothstep_is_symmetric_around_the_midpoint():
    assert smoothstep(0.5) == pytest.approx(0.5)
    for t in (0.1, 0.25, 0.4):
        assert smoothstep(t) + smoothstep(1 - t) == pytest.approx(1.0)


def test_smoothstep_spreads_motion_more_evenly_than_ease_out():
    """Dar kare bütçesinde asıl mesele bu: en büyük tek adım küçülmeli.

    app.py'nin tween'i ~11 kare çizebiliyor; ease_out ilk karede mesafenin
    dörtte birini harcıyordu. Aynı kare sayısında en büyük adımı ölçüyoruz.
    """
    frames = [i / 11 for i in range(12)]

    def biggest_step(ease):
        vals = [ease(t) for t in frames]
        return max(vals[i] - vals[i - 1] for i in range(1, len(vals)))

    assert biggest_step(smoothstep) < biggest_step(ease_out_cubic)
    assert biggest_step(ease_out_cubic) > 0.20   # ilk kare tek başına >%20
    assert biggest_step(smoothstep) < 0.15


def test_interpolate_uses_eased_progress():
    assert interpolate(100, 200, 0.0) == 100
    assert interpolate(100, 200, 1.0) == 200
    # varsayılan eğri artık smoothstep
    assert interpolate(100, 200, 0.5) == pytest.approx(100 + 100 * smoothstep(0.5))


def test_interpolate_accepts_a_custom_easing():
    assert interpolate(100, 200, 0.5, ease=ease_out_cubic) == pytest.approx(
        100 + 100 * ease_out_cubic(0.5))


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


# --------------------------------------------------------------------------
# Finding 2 (user-qa-fix-report.md): DOT_OVERLAY_BIAS_RATIO eskiden bir CSS
# KENAR-ofsetini (top:-6px;right:-6px) yanlışlıkla bir MERKEZ-yanlılığı gibi
# ele alıp dot_overlay_center'ın zaten doğru köşe merkezinin ÜSTÜNE
# ekliyordu — bu da noktayı köşeden gerçekte ~10px kadar koparıyordu.
# Doğru referans, kartın kendi keskin köşe noktası (card_x+card_w, card_y).
# --------------------------------------------------------------------------

def test_dot_overlay_bias_ratio_is_zero():
    # Regresyon: bu sıfır olmalı — sıfırdan farklı herhangi bir değer
    # noktayı köşeden ekstra dışa itip görsel olarak koparır (bkz. rapor).
    assert DOT_OVERLAY_BIAS_RATIO == 0.0


def test_dot_overlay_center_sits_exactly_on_the_cards_sharp_corner():
    card_x, card_y, card_w = 100.0, 200.0, 148.0
    cx, cy = dot_overlay_center(card_x, card_y, card_w)
    assert cx == pytest.approx(card_x + card_w)
    assert cy == pytest.approx(card_y)


def test_dot_overlay_center_drawn_content_overlaps_the_card():
    # "Overlay canvas kutusunun %90'ı kartın dışında" yanıltıcı bir metrik
    # (canvas'ın çoğu saydam dolgu) — asıl soru noktanın/halkanın/parlamanın
    # GERÇEK ÇİZİLİ piksellerinin kartla örtüşüp örtüşmediği. Merkez noktası
    # tam kartın keskin köşesinde olduğundan (bkz. yukarıdaki test), merkezin
    # kart dikdörtgenine mesafesi 0 olmalı — bu da sıfırdan büyük HERHANGİ
    # bir çizim yarıçapının (nokta, halka ya da parlama halosu) kartla
    # gerçekten örtüştüğünü garanti eder.
    card_x, card_y, card_w, card_h = 100.0, 200.0, 148.0, 52.0
    cx, cy = dot_overlay_center(card_x, card_y, card_w)

    nearest_x = min(max(cx, card_x), card_x + card_w)
    nearest_y = min(max(cy, card_y), card_y + card_h)
    dist_to_card = ((cx - nearest_x) ** 2 + (cy - nearest_y) ** 2) ** 0.5

    assert dist_to_card == pytest.approx(0.0, abs=1e-9), (
        f"nokta merkezi ({cx},{cy}) karttan {dist_to_card}px uzakta — "
        "sıfırdan büyük olsaydı, çizili nokta/halka piksellerinin bir kısmı "
        "kartla hiç örtüşmeyebilirdi"
    )

from PIL import Image

from crab_overlay import (EDGE_ANGLES, CrabOverlay, frame_boxes, frame_rect, mood_from,
                          perimeter_length, position_at, slice_sheet)
from usage_client import Window

W, H = 200, 100
PERIM = 2 * (W + H)


class FakeApp:
    """winfo_* istemci alanini taklit eder; Tk penceresi acmaz."""

    def __init__(self):
        self.idle_calls = 0

    def update_idletasks(self):
        self.idle_calls += 1

    def winfo_rootx(self):
        return 100

    def winfo_rooty(self):
        return 200

    def winfo_width(self):
        return 260

    def winfo_height(self):
        return 310


def test_perimeter_is_twice_width_plus_height():
    assert perimeter_length(W, H) == PERIM


def test_walk_starts_at_the_top_left_corner():
    edge, x, y, angle = position_at(0, W, H)
    assert (edge, x, y) == ("top", 0, 0)


def test_each_corner_is_hit_exactly_at_its_distance():
    assert position_at(W, W, H)[1:3] == (W, 0)
    assert position_at(W + H, W, H)[1:3] == (W, H)
    assert position_at(2 * W + H, W, H)[1:3] == (0, H)


def test_full_lap_wraps_back_to_the_start():
    # Sarma yoksa mesafe buyudukce yengec cerceveden kacar.
    assert position_at(PERIM, W, H) == position_at(0, W, H)
    assert position_at(PERIM + 25, W, H) == position_at(25, W, H)


def test_walk_is_clockwise_along_the_top_edge():
    assert position_at(10, W, H)[1] < position_at(40, W, H)[1]


def test_bottom_edge_runs_right_to_left():
    # Saat yonu: alt kenarda x azalmali. Artarsa yengec ters yone yurur.
    a = position_at(W + H + 10, W, H)[1]
    b = position_at(W + H + 40, W, H)[1]
    assert a > b


def test_left_edge_runs_bottom_to_top():
    a = position_at(2 * W + H + 10, W, H)[2]
    b = position_at(2 * W + H + 40, W, H)[2]
    assert a > b


def test_angle_matches_the_edge_being_walked():
    # Aci kenarla uyusmazsa yengec yan yan veya geri geri yurur.
    for d in (5, W + 5, W + H + 5, 2 * W + H + 5):
        edge, _, _, angle = position_at(d, W, H)
        assert angle == EDGE_ANGLES[edge]


def test_every_edge_is_visited_over_a_full_lap():
    edges = {position_at(d, W, H)[0] for d in range(0, PERIM, 7)}
    assert edges == {"top", "right", "bottom", "left"}


def _sheet(count=8, size=32):
    """Her karesi farkli renkte sentetik sprite sheet."""
    img = Image.new("RGBA", (count * size, size), (0, 0, 0, 0))
    for i in range(count):
        block = Image.new("RGBA", (size, size), (i * 30, 60, 90, 255))
        img.paste(block, (i * size, 0))
    return img


def test_frame_boxes_tile_the_sheet_without_gaps():
    boxes = frame_boxes(count=8, size=32)
    assert len(boxes) == 8
    assert boxes[0] == (0, 0, 32, 32)
    assert boxes[-1] == (224, 0, 256, 32)


def test_slicing_yields_eight_distinct_frames():
    # Ayni kare 8 kez donerse animasyon donuk olur ve bu sessiz bir hata:
    # hicbir istisna atilmaz, yengec sadece hic adim atmaz.
    frames = slice_sheet(_sheet(), count=8, size=32, scale=1)
    assert len(frames) == 8
    assert len({f.tobytes() for f in frames}) == 8


def test_slicing_scales_with_nearest_neighbour():
    frames = slice_sheet(_sheet(), count=8, size=32, scale=2)
    assert frames[0].size == (64, 64)


def test_frame_rect_prefers_the_win32_getter():
    # winfo_* istemci alanini verir; nativ baslik cubugu onun DISINDA kalir.
    assert frame_rect(FakeApp(), getter=lambda a: (10, 20, 300, 400)) == (10, 20, 300, 400)


def test_frame_rect_falls_back_when_the_getter_raises():
    def boom(_):
        raise OSError("GetWindowRect yok")

    app = FakeApp()
    assert frame_rect(app, getter=boom) == (100, 200, 260, 310)
    assert app.idle_calls == 1, "fallback once geometriyi tazelemeli"


def test_frame_rect_falls_back_when_the_getter_returns_nothing():
    assert frame_rect(FakeApp(), getter=lambda a: None) == (100, 200, 260, 310)


def test_overlay_is_unavailable_without_a_sprite():
    crab = CrabOverlay(FakeApp(), sprite_path="yok_boyle_bir_dosya.png")
    assert crab.available is False


def test_set_mood_is_safe_on_an_unavailable_overlay():
    # app.py dallanma yapmiyor; cagri her durumda sessizce yutulmali.
    crab = CrabOverlay(FakeApp(), sprite_path="yok_boyle_bir_dosya.png")
    crab.set_mood(42.0)
    crab.set_mood(None)


def test_mood_takes_the_busier_window():
    five = Window(utilization=30.0, resets_at=None)
    seven = Window(utilization=78.0, resets_at=None)
    assert mood_from(five, seven) == 78.0
    assert mood_from(seven, five) == 78.0


def test_mood_ignores_a_missing_window():
    assert mood_from(None, Window(utilization=12.0, resets_at=None)) == 12.0
    assert mood_from(Window(utilization=12.0, resets_at=None), None) == 12.0


def test_mood_is_none_when_both_windows_are_missing():
    # Veri yokken ruh hali son bilinen degerde kalmali, sifirlanmamali.
    assert mood_from(None, None) is None

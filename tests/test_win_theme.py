import pytest

from win_theme import (DWMWA_BORDER_COLOR, DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR,
                       apply_titlebar_theme, colorref)


class RecordingSetter:
    def __init__(self, ok=True):
        self.calls = []
        self.ok = ok

    def __call__(self, hwnd, attr, value):
        self.calls.append((hwnd, attr, value))
        return self.ok


def test_colorref_reverses_byte_order():
    # DWM 0x00BBGGRR ister; hex'i olduğu gibi geçmek mavi ile kırmızıyı
    # takas eder ve turuncu istediğimiz yerde mavi çıkardı.
    assert colorref("#C25F42") == 0x00425FC2


def test_colorref_accepts_hash_free_input():
    assert colorref("C25F42") == 0x00425FC2


def test_colorref_expands_three_digit_shorthand():
    assert colorref("#F00") == 0x000000FF


def test_colorref_pure_channels():
    assert colorref("#FF0000") == 0x000000FF
    assert colorref("#00FF00") == 0x0000FF00
    assert colorref("#0000FF") == 0x00FF0000


def test_colorref_rejects_garbage():
    with pytest.raises(ValueError):
        colorref("turuncu")


def test_applies_all_three_attributes():
    setter = RecordingSetter()
    apply_titlebar_theme(42, caption="#C25F42", text="#FAF9F5",
                         border="#C25F42", setter=setter)
    attrs = [c[1] for c in setter.calls]
    assert attrs == [DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR, DWMWA_BORDER_COLOR]
    assert all(c[0] == 42 for c in setter.calls)


def test_passes_converted_colorref_not_raw_hex():
    setter = RecordingSetter()
    apply_titlebar_theme(1, caption="#C25F42", setter=setter)
    assert setter.calls[0][2] == 0x00425FC2


def test_skips_attributes_left_unset():
    setter = RecordingSetter()
    apply_titlebar_theme(1, caption="#C25F42", setter=setter)
    assert [c[1] for c in setter.calls] == [DWMWA_CAPTION_COLOR]


def test_reports_failure_when_dwm_rejects():
    # Windows 10'da bu attribute'lar yok; çağrı sıfırdan farklı döner.
    setter = RecordingSetter(ok=False)
    assert apply_titlebar_theme(1, caption="#C25F42", setter=setter) is False


def test_failure_does_not_raise():
    def exploding(hwnd, attr, value):
        raise OSError("dwmapi yok")

    # Tema uygulanamaması pencerenin açılmasını engellememeli.
    assert apply_titlebar_theme(1, caption="#C25F42", setter=exploding) is False


def test_success_reports_true():
    assert apply_titlebar_theme(1, caption="#C25F42", setter=RecordingSetter()) is True


def test_one_failure_makes_the_whole_call_false_but_others_still_tried():
    calls = []

    def flaky(hwnd, attr, value):
        calls.append(attr)
        return attr != DWMWA_CAPTION_COLOR

    result = apply_titlebar_theme(1, caption="#C25F42", text="#FFFFFF", setter=flaky)
    assert result is False
    assert calls == [DWMWA_CAPTION_COLOR, DWMWA_TEXT_COLOR]


import win_theme


def test_work_area_rect_returns_the_getter_result():
    assert win_theme.work_area_rect(getter=lambda: (0, 0, 1920, 1032)) == (0, 0, 1920, 1032)


def test_work_area_rect_swallows_failure():
    def boom():
        raise OSError("SPI yok")
    assert win_theme.work_area_rect(getter=boom) is None


def test_work_area_rect_uses_real_win32_by_default():
    # Bu makinede calisma alani gercekten okunabiliyor (plan hazirlanirken
    # dogrulandi); regresyonu yakalar.
    rect = win_theme.work_area_rect()
    assert rect is not None
    x, y, w, h = rect
    assert w > 0 and h > 0


def test_set_rounded_region_calls_setter_with_dimensions():
    calls = []

    def setter(hwnd, width, height, radius):
        calls.append((hwnd, width, height, radius))
        return True

    assert win_theme.set_rounded_region(1, 148, 52, 14, setter=setter) is True
    assert calls == [(1, 148, 52, 14)]


def test_set_rounded_region_swallows_failure():
    def boom(hwnd, width, height, radius):
        raise OSError("gdi32 yok")
    assert win_theme.set_rounded_region(1, 148, 52, 14, setter=boom) is False


def test_set_rounded_region_reports_setter_false():
    assert win_theme.set_rounded_region(1, 148, 52, 14, setter=lambda *a: False) is False

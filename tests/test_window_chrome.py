import os

import app as app_module
from app import COLORS, ICON_PATH, set_window_icon, theme_titlebar


class FakeWindow:
    def __init__(self, fail=False):
        self.fail = fail
        self.icons = []

    def iconbitmap(self, path):
        if self.fail:
            raise Exception("gecersiz ikon")
        self.icons.append(path)


def test_icon_file_ships_with_the_app():
    assert os.path.exists(ICON_PATH), "ikon dosyasi commit edilmis olmali"


def test_set_window_icon_passes_the_path():
    win = FakeWindow()
    assert set_window_icon(win, "x.ico") is True
    assert win.icons == ["x.ico"]


def test_missing_icon_does_not_break_the_window():
    # Simge yoklugu widget'i acilmaz yapmamali.
    assert set_window_icon(FakeWindow(fail=True), "yok.ico") is False


def test_titlebar_uses_the_palette_not_a_hardcoded_hex(monkeypatch):
    seen = {}

    def fake_apply(hwnd, caption=None, text=None, border=None):
        seen.update(hwnd=hwnd, caption=caption, text=text, border=border)
        return True

    monkeypatch.setattr(app_module, "frame_hwnd", lambda w: 99)
    monkeypatch.setattr(app_module, "apply_titlebar_theme", fake_apply)
    assert theme_titlebar(object()) is True
    assert seen["hwnd"] == 99
    assert seen["caption"] == COLORS["titlebar"]
    assert seen["text"] == COLORS["titlebar_text"]


def test_titlebar_failure_is_swallowed(monkeypatch):
    # Windows 10'da GetParent/DWM patlayabilir; pencere yine acilmali.
    def boom(_):
        raise OSError("dwmapi yok")

    monkeypatch.setattr(app_module, "frame_hwnd", boom)
    assert theme_titlebar(object()) is False


def test_titlebar_colour_is_distinct_from_the_button_accent():
    # accent_hover odunc alinmadi: dugme hover'i ile baslik cubugu ayri roller.
    assert "titlebar" in COLORS
    assert COLORS["titlebar"] == "#C25F42"

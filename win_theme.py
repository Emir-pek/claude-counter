"""Windows 11 başlık çubuğunu boyar (DWM).

Nativ çubuğu kendimiz çizmek yerine boyuyoruz: küçültme/kapatma düğmeleri,
sürükleme, Aero Snap ve sağ tık menüsü Windows'un kendi davranışı olarak
kalsın. Windows 11 öncesinde bu attribute'lar yok; çağrı sessizce başarısız
olur ve pencere eski görünümüyle çalışmaya devam eder.
"""
from __future__ import annotations

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36


def colorref(value: str) -> int:
    """`#RRGGBB` → Windows COLORREF (`0x00BBGGRR`).

    DWM byte sırasını ters bekliyor; hex'i olduğu gibi geçmek kırmızı ile
    maviyi takas eder, yani turuncu istediğimiz yerde mavi çıkar.
    """
    text = value.lstrip("#").strip()
    if len(text) == 3:  # #F00 kısaltması
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"geçersiz renk: {value!r}")
    try:
        r, g, b = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        raise ValueError(f"geçersiz renk: {value!r}")
    return (b << 16) | (g << 8) | r


def _dwm_set(hwnd: int, attr: int, value: int) -> bool:
    import ctypes
    from ctypes import wintypes

    dwmapi = ctypes.windll.dwmapi
    dwmapi.DwmSetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    ]
    packed = ctypes.c_int(value)
    result = dwmapi.DwmSetWindowAttribute(
        wintypes.HWND(hwnd), attr, ctypes.byref(packed), ctypes.sizeof(packed)
    )
    return result == 0


def apply_titlebar_theme(hwnd: int, caption: str | None = None,
                         text: str | None = None, border: str | None = None,
                         setter=None) -> bool:
    """Verilen renkleri başlık çubuğuna uygular. Hiçbir istisna sızdırmaz.

    Tema uygulanamaması pencerenin açılmasını engellememeli, o yüzden her
    başarısızlık False'a çevrilir.
    """
    setter = setter or _dwm_set
    ok = True
    for attr, value in ((DWMWA_CAPTION_COLOR, caption),
                        (DWMWA_TEXT_COLOR, text),
                        (DWMWA_BORDER_COLOR, border)):
        if value is None:
            continue
        try:
            ok = bool(setter(hwnd, attr, colorref(value))) and ok
        except Exception:
            ok = False
    return ok


def frame_hwnd(widget) -> int:
    """Başlık çubuğunu taşıyan gerçek pencere tutamacı.

    winfo_id() Tk'nin çocuk penceresini verir; başlık çubuğu ebeveyndedir.
    GetParent atlanırsa DWM çağrısı başarılı görünür ama hiçbir şey değişmez.
    """
    import ctypes

    child = widget.winfo_id()
    parent = ctypes.windll.user32.GetParent(child)
    return parent or child

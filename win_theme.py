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


def _win32_work_area():
    import ctypes
    from ctypes import wintypes

    SPI_GETWORKAREA = 0x0030

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    user32 = ctypes.windll.user32
    user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT
    ]
    rect = RECT()
    ok = user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    if not ok:
        return None
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def work_area_rect(getter=None):
    """Görev çubuğu hariç çalışma alanı: (x, y, genişlik, yükseklik).

    Win32 çağrısı yoksa ya da başarısız olursa None döner; çağıran taraf ham
    ekran dikdörtgenine düşmekle yükümlü — crab_overlay.frame_rect'teki
    win32-yoksa-düş kalıbının aynısı.
    """
    getter = getter or _win32_work_area
    try:
        return getter()
    except Exception:
        return None


def _win32_set_region(hwnd: int, width: int, height: int, radius: int) -> bool:
    import ctypes
    from ctypes import wintypes

    gdi32 = ctypes.windll.gdi32
    user32 = ctypes.windll.user32
    gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
    gdi32.CreateRoundRectRgn.restype = ctypes.c_void_p
    user32.SetWindowRgn.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
    user32.SetWindowRgn.restype = ctypes.c_int

    diameter = radius * 2
    hrgn = gdi32.CreateRoundRectRgn(0, 0, width, height, diameter, diameter)
    if not hrgn:
        return False
    return bool(user32.SetWindowRgn(wintypes.HWND(hwnd), hrgn, True))


def set_rounded_region(hwnd: int, width: int, height: int, radius: int,
                       setter=None) -> bool:
    """Pencereyi yuvarlak köşeli bir bölgeye kırpar. Hiçbir istisna sızdırmaz.

    Bölge kırpma başarısız olursa pencere dikdörtgen köşelerle açılmaya devam
    etmeli, uygulamayı çökertmemeli — apply_titlebar_theme'deki yutma
    kalıbının aynısı. -transparentcolor yerine gerçek Win32 bölge kırpma
    kullanılıyor: CTk'nin kendi yuvarlak-köşe blend'i saydam renk anahtarına
    karşı magenta sızıntısı üretirdi.
    """
    setter = setter or _win32_set_region
    try:
        return bool(setter(hwnd, width, height, radius))
    except Exception:
        return False

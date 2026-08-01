"""Kartın köşe yerleşimi ve animasyonları için saf matematik.

Tk'siz: crab_overlay.py'deki perimeter_length/position_at kalıbının aynısı —
gerçek pencere olmadan doğrudan test edilebilsin diye.
"""
from __future__ import annotations

CORNERS = ("bottom-right", "bottom-left", "top-right", "top-left")


def corner_position(work_rect, size, corner: str, margin: int) -> tuple[int, int]:
    """(x, y): pencerenin çalışma alanı köşesine margin payıyla yerleşmiş hali.

    work_rect: (x, y, genişlik, yükseklik) — görev çubuğu hariç çalışma alanı.
    size: (genişlik, yükseklik) — konumlanacak pencere.
    """
    if corner not in CORNERS:
        raise ValueError(f"geçersiz köşe: {corner!r}")
    wx, wy, ww, wh = work_rect
    w, h = size
    x = wx + ww - w - margin if "right" in corner else wx + margin
    y = wy + wh - h - margin if "bottom" in corner else wy + margin
    return (int(x), int(y))


def point_in_rect(px: float, py: float, rect) -> bool:
    """Sol/üst kenar dahil, sağ/alt kenar hariç — Tk pencere dikdörtgeniyle tutarlı."""
    x, y, w, h = rect
    return x <= px < x + w and y <= py < y + h


def ease_out_cubic(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def interpolate(start: float, end: float, t: float) -> float:
    return start + (end - start) * ease_out_cubic(t)


def tween_frames(steps: int) -> list[float]:
    """0..1 arası zaman noktaları (start ve end dahil, steps+1 eleman)."""
    if steps < 1:
        raise ValueError("steps >= 1 olmalı")
    return [i / steps for i in range(steps + 1)]


def ring_phase(elapsed_ms: float, period_ms: float = 1800.0) -> tuple[float, bool]:
    """CSS pulseRing yaklaşıklaması: (ölçek, görünür mü).

    CSS: 0% scale .9 opacity .9 -> 70% scale 1.7 opacity 0 -> 100% opacity 0.
    Tk canvas'ta kesirli opacity yok; %70'e kadar halka büyüyerek görünür,
    sonrasında bir sonraki döngüye kadar tamamen gizlenir.
    """
    phase = (elapsed_ms % period_ms) / period_ms
    grow_end = 0.70
    if phase >= grow_end:
        return (1.7, False)
    t = phase / grow_end
    return (0.9 + (1.7 - 0.9) * t, True)


def glow_phase(elapsed_ms: float, period_ms: float = 1800.0) -> float:
    """CSS pulseGlow yaklaşıklaması: 0..1 nabız yoğunluğu, 50%'de tepe."""
    phase = (elapsed_ms % period_ms) / period_ms
    return 1.0 - abs(phase - 0.5) * 2.0


# CSS mockup'ta durum noktası top:-6px;right:-6px ile 148-208px genişlikli
# bir karta göre konumlanıyordu. Kart genişliği bizim ortamımızda farklı
# olduğundan literal 6px yerine bu oran kullanılıyor — 6/148, referans
# mockup'ın idle genişliğine (148px) karşılık gelen kesir.
DOT_OVERLAY_BIAS_RATIO = 6.0 / 148.0


def dot_overlay_center(card_x: float, card_y: float, card_w: float) -> tuple[float, float]:
    """Kayan durum noktası penceresinin ekran koordinatlarındaki merkezi.

    card_x, card_y, card_w: kartın kendi penceresinin GERÇEK ekran
    koordinatları (winfo_rootx/rooty/width) — kartın yükseklik bilgisine
    ihtiyaç yok, nokta yalnızca sağ-üst köşeyle ilgileniyor.

    Neden kartın "keskin" köşesi (card_x + card_w, card_y) referans alınıyor:
    Win32 SetWindowRgn köşeyi CARD_RADIUS kadar içeri keser, yani kartın
    GÖRÜNÜR yuvarlatılmış silüeti bu keskin köşe noktasına asla ulaşmaz —
    silüetin sınırı oradan her zaman en az bir miktar içeride kalır (yarıçap
    ne olursa olsun, sıfırdan büyük olduğu sürece). Bu yüzden merkezi tam bu
    keskin köşe noktasına (ya da ondan biraz daha dışına) koymak, DOT_SIZE
    ya da CARD_RADIUS'un tam değerini bilmeye gerek kalmadan noktanın
    görünür yuvarlatılmış silüetin tamamen dışında kalacağını garantiler —
    sabit bir piksel sayısının "yeterli" olup olmadığını tahmin etmek yerine
    geometrinin kendisinden gelen bir garanti, bu yüzden DPI/ölçeklemeden
    bağımsız. Üstüne CSS mockup'ın "poke out" görünümünü yeniden üretmek için
    küçük bir dışa taşma payı ekleniyor (bkz. DOT_OVERLAY_BIAS_RATIO).
    """
    bias = card_w * DOT_OVERLAY_BIAS_RATIO
    cx = card_x + card_w + bias
    cy = card_y - bias
    return (cx, cy)

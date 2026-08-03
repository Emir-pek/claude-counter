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


def smoothstep(t: float) -> float:
    """Klasik smoothstep (3t² - 2t³): iki uçta da sıfır hızla girip çıkar.

    Neden kartın tween'i buna geçti (bkz. app.TWEEN_MS): pencereyi yeniden
    boyutlandırmanın ÖLÇÜLEN maliyeti ~15ms (CTk çocukları her boyutta
    canvas'larını yeniden çiziyor), yani 180ms'lik bir animasyonda ancak
    ~11 AYRI konum çizilebiliyor. Kare bütçesi bu kadar darken belirleyici
    olan eğrinin TEPE HIZI: bir karede atlanan mesafe = tepe eğim / kare
    sayısı.

    - ease_out_cubic: tepe eğim 3.0 (t=0'da) -> ölçülen adımlar
      15, 11, 10, 8, 5, 4, 3, 3, 1 px. Mesafenin **%25'i ilk karede**:
      bir sıçrama, ardından sürünme.
    - CSS'in ease-in-out kübiği (4t³ / 1-(-2t+2)³/2) BU İŞE YARAMAZ:
      tepe eğimi de 3.0, yalnızca sıçramayı ortaya taşır. Denendi ve
      ölçüldü, en büyük adım değişmedi (0.249 -> 0.249).
    - smoothstep: tepe eğim 1.5, yani en büyük adım YARIYA iner
      (~1.4, 3.8, 5.6, 7.0, 7.8, 8.1, 7.9, 7.1, 5.8, 4.0, 1.7 px).

    Kare sayısı aynı kalıyor; adımlar birbirine yakınlaştığı için hareket
    "akıcı" okunuyor. Daha atak bir his istenirse interpolate(...,
    ease=ease_out_cubic) ile eski eğriye dönülebilir.
    """
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def interpolate(start: float, end: float, t: float, ease=smoothstep) -> float:
    """Eğri parametrik: çağıran taraf hangi his istediğini seçebilsin.

    Varsayılan ease_in_out_cubic — kartın tween'inin kullandığı. ease_out_cubic
    hâlâ burada ve test ediliyor; daha "atak" bir his istenirse tek argümanla
    geri dönülebilir.
    """
    return start + (end - start) * ease(t)


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


# DÜZELTME (bkz. user-qa-fix-report.md, Finding 2): eskiden buradaki 6/148
# oranı, CSS mockup'ının top:-6px;right:-6px'ini bir merkez-yanlılığı
# (bias) sanıp dot_overlay_center'ın zaten köşeye doğru merkezlediği
# noktanın ÜSTÜNE ekliyordu. Ama mockup'taki -6px/-3px değerleri (ringStyle:
# top:-6,right:-6,width:14,height:14 ve dotStyle: top:-3,right:-3,width:8,
# height:8) birer KENAR ofsetiydi — iki farklı boyuttaki kutunun kendi
# kenarına göre ifade edilmiş, ama ikisi de AYNI gerçek merkez noktasını
# tarif ediyordu (14/2-6=1, 8/2-3=1 — ikisi de kutunun kendi merkezinden
# 1px içeride, yani gerçekte kartın keskin köşesine merkezlenmiş demek).
# Bunu ekstra bir dışa-itme olarak yeniden uygulamak noktayı köşeden
# ölçülen ~10px kadar gerçekten kopartıyordu (bkz. rapor: idle'da nokta
# köşeyle hiç örtüşmüyordu, en büyük kritik halka ölçeğinde bile 2.4px
# kısa kalıyordu). Sıfıra çekildi: dot_overlay_center'ın kendi köşe
# merkezlemesi zaten doğru referans noktası, üstüne ek bir pay gerekmiyor.
DOT_OVERLAY_BIAS_RATIO = 0.0


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
    keskin köşe noktasına koymak, DOT_SIZE ya da CARD_RADIUS'un tam değerini
    bilmeye gerek kalmadan noktanın görünür yuvarlatılmış silüetin tamamen
    dışında kalacağını garantiler — sabit bir piksel sayısının "yeterli"
    olup olmadığını tahmin etmek yerine geometrinin kendisinden gelen bir
    garanti, bu yüzden DPI/ölçeklemeden bağımsız. DOT_OVERLAY_BIAS_RATIO artık
    0.0 (bkz. sabitin kendi yorumu, Finding 2): merkez tam bu keskin köşede
    kalıyor, ekstra bir dışa itme YOK — nokta/halka/parlamanın gerçek çizili
    piksel alanı böylece kartın köşesiyle gerçekten örtüşüyor, birkaç piksel
    ötesinde havada asılı bir benek olarak durmuyor.
    """
    bias = card_w * DOT_OVERLAY_BIAS_RATIO
    cx = card_x + card_w + bias
    cy = card_y - bias
    return (cx, cy)

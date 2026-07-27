from __future__ import annotations

import os
from datetime import datetime, timezone

import customtkinter as ctk

from crab_overlay import NULL_CRAB, mood_from
from formatting import GREEN, RED, YELLOW, color_for, format_countdown, format_reset_time
from usage_client import UsageData, UsageError
from win_theme import apply_titlebar_theme, frame_hwnd

ctk.set_appearance_mode("dark")

# Tüm renkler burada. Başka hiçbir yere hex gömülmez.
COLORS = {
    "window": "#1F1E1D",
    "surface": "#262624",
    "border": "#3D3D3A",
    "text_primary": "#FAF9F5",
    "text_secondary": "#B0AEA5",
    "accent": "#D97757",
    "accent_hover": "#C25F42",
    "bar_safe": "#788C5D",
    "bar_mid": "#D4A27F",
    "bar_critical": "#BF4D3B",
    "bar_track": "#3D3D3A",
    # Başlık çubuğu ayrı bir rol; accent_hover ödünç alınmadı, o düğme
    # hover'ının anlamı ve bağımsız değişebilmeli.
    "titlebar": "#C25F42",
    "titlebar_text": "#FAF9F5",
}

ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "claude_counter.ico")


def set_window_icon(window, icon_path: str = ICON_PATH) -> bool:
    """Pencere simgesini uygular. Simge yokluğu widget'ı açılmaz yapmamalı."""
    try:
        window.iconbitmap(icon_path)
        return True
    except Exception:
        return False


def theme_titlebar(window) -> bool:
    """Başlık çubuğunu Claude turuncusuna boyar (Windows 11).

    Eski Windows'ta DWM bu attribute'ları tanımaz; başarısızlık yutulur ve
    pencere varsayılan çubuğuyla çalışmaya devam eder.
    """
    try:
        return apply_titlebar_theme(
            frame_hwnd(window),
            caption=COLORS["titlebar"],
            text=COLORS["titlebar_text"],
            border=COLORS["titlebar"],
        )
    except Exception:
        return False

# Eşik mantığının tek sahibi formatting.color_for. Burada yalnızca
# döndürdüğü seviye ekranda kullanılan renge çevriliyor; böylece
# eşikler tek yerde kalır ve formatting.py'ye dokunulmaz.
_BAR_COLOR = {
    GREEN: COLORS["bar_safe"],
    YELLOW: COLORS["bar_mid"],
    RED: COLORS["bar_critical"],
}

PAD_WINDOW = 10  # pencere iç kenar boşluğu
PAD_CARD = 8  # kartlar arası boşluk

# CTkLabel varsayılanı 28px; metin 17-20px'e sığıyor. Altı label boyunca
# aradaki fark pencerenin yüksekliğinde göze batıyordu, o yüzden her
# label kendi satır yüksekliğine sabitleniyor. (CTk font boyutunu punto
# değil piksel olarak uyguluyor: 11 -> 11px yüksek harfler.)
LINE_TITLE = 20  # 11'lik başlık
LINE_TEXT = 17  # 10'luk gövde

# Pencere içeriğine göre ölçülmüş sabit boyut. Genişliği belirleyen
# şey kartlar değil, durum satırındaki en uzun hata mesajı; yerleşim
# değişince test_layout.py kırpma sınırından haber veriyor.
WINDOW_W = 200
WINDOW_H = 200


class _Row:
    """Tek bir limit kartı: başlık + çubuk + yüzde + geri sayım."""

    def __init__(self, parent, title: str):
        self.card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=COLORS["surface"],
            border_width=1,
            border_color=COLORS["border"],
        )
        self.card.grid_columnconfigure(1, weight=1)

        self.title = ctk.CTkLabel(
            self.card,
            text=title,
            anchor="w",
            height=LINE_TITLE,
            font=("Segoe UI", 11, "bold"),
            text_color=COLORS["text_primary"],
        )
        self.bar = ctk.CTkProgressBar(
            self.card,
            # Varsayılan 200px genişlik pencerenin darlığına taban
            # koyuyordu; bar zaten sticky="ew" ile satıra yayılıyor.
            width=120,
            height=6,
            corner_radius=3,
            fg_color=COLORS["bar_track"],
            progress_color=COLORS["bar_safe"],
        )
        self.bar.set(0)
        # Yüzde ayrı bir label: Tk tek label içinde karışık biçimlendirme
        # yapamaz, yüzde bold ve barın renginde olmalı.
        self.pct = ctk.CTkLabel(
            self.card,
            text="",
            anchor="w",
            height=LINE_TEXT,
            font=("Segoe UI", 10, "bold"),
            text_color=COLORS["text_secondary"],
        )
        self.info = ctk.CTkLabel(
            self.card,
            text="—",
            anchor="w",
            height=LINE_TEXT,
            font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"],
        )

        self.window = None  # type: ignore
        # Saat metni sadece anahtar değişince hesaplanır; anahtar bir
        # döngü boyunca sabit kalır (5 saatte / haftada bir).
        self._reset_key = None
        self._reset_text = ""
        self._last_info = None

    def grid(self, r: int, pady_bottom: int = PAD_CARD):
        self.card.grid(row=r, column=0, sticky="ew", padx=PAD_WINDOW, pady=(0, pady_bottom))
        self.title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(7, 5))
        self.bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
        self.pct.grid(row=2, column=0, sticky="w", padx=(10, 6), pady=(5, 7))
        self.info.grid(row=2, column=1, sticky="w", padx=(0, 10), pady=(5, 7))

    def set(self, window):
        self.window = window
        if window is None:
            self.bar.set(0)
            self.pct.configure(text="", text_color=COLORS["text_secondary"])
            self.info.configure(text="—")
            # Önbellek temizlenmezse aynı resets_at ile gelen sonraki
            # geçerli veri aynı metni üretir, yazma koruması devreye
            # girer ve satır "—" takılı kalır.
            self._reset_key = None
            self._reset_text = ""
            self._last_info = None
            return
        bar_color = _BAR_COLOR[color_for(window.utilization)]
        self.bar.set(window.utilization / 100)
        self.bar.configure(progress_color=bar_color)
        # Yüzde yalnızca yeni veriyle değişir, geri sayımla değil.
        self.pct.configure(text=f"%{window.utilization:.0f}", text_color=bar_color)
        self.refresh_countdown()

    def refresh_countdown(self, now=None):
        if self.window is None:
            return
        now = now or datetime.now(timezone.utc)
        resets_at = self.window.resets_at
        expired = int((resets_at - now).total_seconds()) <= 0

        # Yerel gün anahtarda: gün adının varlığı gece yarısı bayatlar.
        # Süresi dolmuşluk anahtarda: dolduğunda saat metni boşalmalı
        # ama resets_at ve yerel gün değişmez.
        key = (resets_at, now.astimezone().date(), expired)
        if key != self._reset_key:
            self._reset_key = key
            self._reset_text = format_reset_time(resets_at, now)

        text = f"⟳ {format_countdown(resets_at, now)}"
        if self._reset_text:
            text += f" · {self._reset_text}"

        # Geri sayım dakika hassasiyetinde; saniyede bir yazmanın anlamı yok.
        if text != self._last_info:
            self._last_info = text
            self.info.configure(text=text)


class UsageApp(ctk.CTk):
    # Yengeç overlay'ini main() kuruyor. O ana kadar — ve overlay hiç
    # kurulamazsa — null-object devrede kalır, böylece render()'da
    # "overlay var mı" dallanmasına gerek kalmıyor.
    crab = NULL_CRAB

    def __init__(self):
        super().__init__()
        self.title("Claude Kullanımı")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["window"])
        self.grid_columnconfigure(0, weight=1)
        self.on_refresh = None
        self._data = None

        # Pencere başlığı zaten "Claude Kullanımı" yazıyor; aynı metni
        # içeride tekrarlamak bir satır harcıyordu. O satırı durum
        # metni devraldı: hem son güncelleme saati hem hata mesajı.
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.grid(row=0, column=0, sticky="ew", padx=PAD_WINDOW,
                         pady=(PAD_WINDOW, PAD_CARD))
        self.header.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            self.header,
            text="yükleniyor…",
            anchor="w",
            height=LINE_TEXT,
            font=("Segoe UI", 10),
            text_color=COLORS["text_secondary"],
        )
        self.status.grid(row=0, column=0, sticky="ew")
        self.refresh = ctk.CTkButton(
            self.header,
            text="↻",
            width=26,
            height=24,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["text_primary"],
            command=self._refresh_clicked,
        )
        self.refresh.grid(row=0, column=1, padx=(PAD_CARD, 0))

        self.five = _Row(self, "5 saatlik")
        self.five.grid(1)
        self.seven = _Row(self, "Haftalık")
        # Son kartın altı pencere kenarı: kart arası değil, kenar boşluğu.
        self.seven.grid(2, pady_bottom=PAD_WINDOW)

        set_window_icon(self)
        # Pencere haritalanmadan DWM çağrısı tutmuyor, ilk boşta uygula.
        self.after(0, lambda: theme_titlebar(self))

    def _refresh_clicked(self):
        if self.on_refresh:
            self.on_refresh()

    def render(self, data: UsageData):
        self._data = data
        self.five.set(data.five_hour)
        self.seven.set(data.seven_day)
        self.status.configure(
            text=f"güncellendi: {data.fetched_at.astimezone().strftime('%H:%M')}",
            text_color=COLORS["text_secondary"],
        )
        # Yalnızca veri geldiğinde güncelleniyor; render_error'da bilerek
        # dokunulmuyor ki veri yokken ruh hali son bilinen değerde kalsın.
        self.crab.set_mood(mood_from(data.five_hour))

    def render_error(self, err: UsageError):
        # İstek sınırı geçici ve kendi kendine toparlıyor; kırmızı yerine
        # amber, kullanıcı bunu bozulma sanmasın.
        color = "bar_mid" if err.kind == "rate_limited" else "bar_critical"
        self.status.configure(text=err.message, text_color=COLORS[color])

    def tick(self):
        self.five.refresh_countdown()
        self.seven.refresh_countdown()

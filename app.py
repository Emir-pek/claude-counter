from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime, timezone

import customtkinter as ctk

from card_geometry import corner_position, interpolate, point_in_rect, tween_frames
from formatting import GREEN, RED, YELLOW, color_for, format_countdown, format_reset_time, worst_color
from usage_client import UsageData, UsageError
from win_theme import apply_titlebar_theme, frame_hwnd, set_rounded_region, work_area_rect

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
    # theme_titlebar/apply_titlebar_theme artık çağrılmıyor (kart artık
    # çerçevesiz), ama fonksiyonlar ve bu roller genel amaçlı kaldığı için
    # sözlükten silinmedi.
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

    Artık çağrılmıyor: kart çerçevesiz olduğundan boyanacak nativ başlık
    çubuğu yok. Fonksiyon genel amaçlı olduğu ve kendi testleri onu
    doğrudan sınadığı için kaldırılmadı.
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

# Eşik mantığının tek sahibi formatting.color_for.
_BAR_COLOR = {
    GREEN: COLORS["bar_safe"],
    YELLOW: COLORS["bar_mid"],
    RED: COLORS["bar_critical"],
}

# --- Kart yerleşim/davranış sabitleri -----------------------------------
# Ayarlar ekranı yok; bu sabitler dosyada düzenlenerek değiştirilir —
# projenin geri kalan ayarlarının (COLORS, eski WINDOW_W) zaten yaptığı gibi.
CORNER = "bottom-right"  # "bottom-right" | "bottom-left" | "top-right" | "top-left"
SCREEN_MARGIN = 16
IDLE_OPACITY = 0.55
EXPAND_ON_HOVER = True

CARD_RADIUS = 14
CARD_W_IDLE = 148
CARD_W_EXPANDED = 208
BAR_H_IDLE = 5
BAR_H_EXPANDED = 7
DOT_SIZE = 8
RING_SIZE = 14
DOT_CANVAS_SIZE = 24
REOPEN_SIZE = 34

HOVER_POLL_MS = 50
TWEEN_MS = 280
TWEEN_STEPS = 8
RING_TICK_MS = 60


class _Row:
    """Tek limit satırı: kısa etiket + çubuk + yüzde; genişkken altında geri sayım."""

    def __init__(self, parent, label: str):
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.frame.grid_columnconfigure(1, weight=1)

        self.label = ctk.CTkLabel(
            self.frame, text=label, width=18, anchor="w",
            font=("Segoe UI", 9), text_color=COLORS["text_secondary"],
        )
        self.bar = ctk.CTkProgressBar(
            self.frame, height=BAR_H_IDLE, corner_radius=4, border_width=0,
            fg_color=COLORS["bar_track"], progress_color=COLORS["bar_safe"],
            border_color=COLORS["bar_critical"],
        )
        self.bar.set(0)
        self.pct = ctk.CTkLabel(
            self.frame, text="", width=30, anchor="e",
            font=("Segoe UI", 11, "bold"), text_color=COLORS["text_secondary"],
        )
        self.label.grid(row=0, column=0, sticky="w")
        self.bar.grid(row=0, column=1, sticky="ew", padx=6)
        self.pct.grid(row=0, column=2, sticky="e")

        # Geri sayım kartın grid'ine (bu satırın frame'ine değil) bağlı:
        # yalnızca genişkken görünür, satırın hemen altına hizalanır.
        self.countdown = ctk.CTkLabel(
            parent, text="", anchor="w",
            font=("Segoe UI", 10), text_color=COLORS["text_secondary"],
        )

        self.window = None
        self._reset_key = None
        self._reset_text = ""
        self._last_text = None

    def grid(self, row: int):
        self.frame.grid(row=row, column=0, sticky="ew")
        self.countdown.grid(row=row + 1, column=0, sticky="w", padx=(24, 10), pady=(2, 0))
        self.countdown.grid_remove()

    def set_expanded(self, expanded: bool):
        self.bar.configure(height=BAR_H_EXPANDED if expanded else BAR_H_IDLE)
        if expanded:
            self.countdown.grid()
        else:
            self.countdown.grid_remove()

    def set(self, window):
        self.window = window
        if window is None:
            self.bar.set(0)
            self.bar.configure(progress_color=COLORS["bar_safe"], border_width=0)
            self.pct.configure(text="", text_color=COLORS["text_secondary"])
            self.countdown.configure(text="")
            self._reset_key = None
            self._reset_text = ""
            self._last_text = None
            return
        level = color_for(window.utilization)
        bar_color = _BAR_COLOR[level]
        self.bar.set(window.utilization / 100)
        self.bar.configure(
            progress_color=bar_color,
            border_width=2 if level == RED else 0,
        )
        self.pct.configure(text=f"{window.utilization:.0f}%", text_color=bar_color)
        self.refresh_countdown()

    def refresh_countdown(self, now=None):
        if self.window is None:
            return
        now = now or datetime.now(timezone.utc)
        resets_at = self.window.resets_at
        expired = int((resets_at - now).total_seconds()) <= 0

        key = (resets_at, now.astimezone().date(), expired)
        if key != self._reset_key:
            self._reset_key = key
            self._reset_text = format_reset_time(resets_at, now)

        text = format_countdown(resets_at, now)
        if self._reset_text:
            text += f" · sıfırlanma {self._reset_text}"

        if text != self._last_text:
            self._last_text = text
            self.countdown.configure(text=text)


class UsageApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Claude Kullanımı")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["window"])
        self.on_refresh = None
        self._data = None
        self._laid_out = False
        self._expanded = False
        self._hovered = False
        self._level = GREEN
        self._status_text = ""
        self._status_color = COLORS["bar_mid"]
        self._ring_after = None

        self.card = ctk.CTkFrame(
            self, corner_radius=CARD_RADIUS, fg_color=COLORS["window"],
            border_width=1, border_color=COLORS["border"],
        )
        self.card.pack(fill="both", expand=True)
        self.card.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.card, fg_color="transparent")
        self.header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            self.header, text="Claude Kullanımı", anchor="w",
            font=("Segoe UI", 11, "bold"), text_color=COLORS["text_primary"],
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.refresh_icon = ctk.CTkLabel(
            self.header, text="↻", width=14, font=("Segoe UI", 12),
            text_color=COLORS["accent"], cursor="hand2",
        )
        self.refresh_icon.grid(row=0, column=1, padx=(8, 4))
        self.close_icon = ctk.CTkLabel(
            self.header, text="✕", width=12, font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"], cursor="hand2",
        )
        self.close_icon.grid(row=0, column=2)
        self.refresh_icon.bind("<Button-1>", self._on_refresh_click)
        self.close_icon.bind("<Button-1>", self._on_close_click)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        self.header.grid_remove()

        self.five = _Row(self.card, "5s")
        self.five.grid(1)
        self.seven = _Row(self.card, "7g")
        self.seven.grid(3)
        self.five.frame.grid_configure(padx=10, pady=(8, 0))
        self.seven.frame.grid_configure(padx=10, pady=(6, 0))

        self.status_label = ctk.CTkLabel(
            self.card, text="", anchor="w", font=("Segoe UI", 10),
        )
        self.status_label.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 8))
        self.status_label.grid_remove()

        self.dot_canvas = tk.Canvas(
            self.card, width=DOT_CANVAS_SIZE, height=DOT_CANVAS_SIZE,
            bg=COLORS["window"], highlightthickness=0, bd=0,
        )
        self.dot_canvas.place(relx=1.0, rely=0.0, anchor="ne", x=-2, y=2)
        self._redraw_dot()

        set_window_icon(self)

        self.update_idletasks()
        self._set_expanded(False, animate=False)
        self.after(HOVER_POLL_MS, self._poll_hover_loop)

    def _on_refresh_click(self, _event=None):
        if self.on_refresh:
            self.on_refresh()

    def _on_close_click(self, _event=None):
        pass  # Task 8'de dolduruluyor

    def _set_expanded(self, expanded: bool, animate: bool = True):
        self._expanded = expanded

        # Not: grid_configure() gizli (grid_remove'lu) bir widget'ı Tk'de
        # yeniden haritalar ("grid configure" == parametreli "grid" çağrısı).
        # Bu yüzden pad/pady ayarları önce, görünürlük kararları (aşağıda
        # header.grid()/grid_remove() ve set_expanded çağrıları) sonra
        # gelmeli — aksi halde gizlenmesi gereken widget'lar tekrar görünür
        # olur.
        pad_x = 12 if expanded else 10
        top_pad = 10 if expanded else 8
        self.header.grid_configure(padx=pad_x, pady=(top_pad, 6))
        self.five.frame.grid_configure(padx=pad_x, pady=(0 if expanded else top_pad, 0))
        self.five.countdown.grid_configure(padx=(24, pad_x))
        self.seven.frame.grid_configure(padx=pad_x, pady=(8 if expanded else 6, 0))
        self.seven.countdown.grid_configure(padx=(24, pad_x))
        self.status_label.grid_configure(padx=pad_x, pady=(4, top_pad))

        if expanded:
            self.header.grid()
        else:
            self.header.grid_remove()
        self.five.set_expanded(expanded)
        self.seven.set_expanded(expanded)

        self._refresh_status_visibility()
        self.update_idletasks()

        width = CARD_W_EXPANDED if expanded else CARD_W_IDLE
        height = self.card.winfo_reqheight()
        alpha = 1.0 if expanded else IDLE_OPACITY

        if not self._laid_out or not animate:
            self._snap_to(width, height, alpha)
        else:
            self._tween_to(width, height, alpha)

    def _snap_to(self, width: int, height: int, alpha: float):
        work = work_area_rect() or (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        x, y = corner_position(work, (width, height), CORNER, SCREEN_MARGIN)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-alpha", alpha)
        self.update_idletasks()
        try:
            set_rounded_region(frame_hwnd(self), width, height, CARD_RADIUS)
        except Exception:
            pass
        self._laid_out = True

    def _tween_to(self, target_w: int, target_h: int, target_alpha: float):
        # Aradaki bir hover geldiğinde eski animasyon iptal olsun diye token.
        self._tween_token = getattr(self, "_tween_token", 0) + 1
        token = self._tween_token
        start_w, start_h = self.winfo_width(), self.winfo_height()
        start_alpha = float(self.attributes("-alpha"))
        frames = tween_frames(TWEEN_STEPS)
        step_delay = max(1, TWEEN_MS // TWEEN_STEPS)

        def step(i):
            if token != self._tween_token:
                return
            t = frames[i]
            w = round(interpolate(start_w, target_w, t))
            h = round(interpolate(start_h, target_h, t))
            alpha = interpolate(start_alpha, target_alpha, t)
            self._snap_to(w, h, alpha)
            if i + 1 < len(frames):
                self.after(step_delay, lambda: step(i + 1))

        step(0)

    def _poll_hover_once(self):
        try:
            px, py = self.winfo_pointerxy()
            rect = (self.winfo_rootx(), self.winfo_rooty(),
                   self.winfo_width(), self.winfo_height())
            hovered = point_in_rect(px, py, rect)
        except Exception:
            hovered = self._hovered
        if hovered != self._hovered:
            self._hovered = hovered
            if EXPAND_ON_HOVER:
                self._set_expanded(hovered)
            else:
                self.attributes("-alpha", 1.0 if hovered else IDLE_OPACITY)

    def _poll_hover_loop(self):
        self._poll_hover_once()
        self.after(HOVER_POLL_MS, self._poll_hover_loop)

    def _refresh_status_visibility(self):
        show = self._expanded and bool(self._status_text)
        if show:
            self.status_label.configure(text=self._status_text, text_color=self._status_color)
            self.status_label.grid()
        else:
            self.status_label.grid_remove()

    def _redraw_dot(self, ring_scale=None, ring_visible=False, glow=0.0):
        c = self.dot_canvas
        c.delete("all")
        cx = cy = DOT_CANVAS_SIZE / 2
        if ring_visible and ring_scale:
            r = (RING_SIZE / 2) * ring_scale
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=COLORS["bar_critical"], width=1.5)
        dot_r = DOT_SIZE / 2
        c.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r,
                      fill=_BAR_COLOR[self._level], outline=COLORS["window"],
                      width=1.5 + glow * 2.0)

    def render(self, data: UsageData):
        self._data = data
        self._status_text = ""
        self.five.set(data.five_hour)
        self.seven.set(data.seven_day)
        utils = [w.utilization if w is not None else None
                for w in (data.five_hour, data.seven_day)]
        self._level = worst_color(*utils)
        self._redraw_dot()
        self._refresh_status_visibility()

    def render_error(self, err: UsageError):
        if err.kind == "rate_limited":
            self._status_text = "Sınıra takıldı — yeniden deneniyor"
            self._status_color = COLORS["bar_mid"]
        else:
            self._status_text = err.message
            self._status_color = COLORS["bar_critical"]
        self._refresh_status_visibility()

    def tick(self):
        self.five.refresh_countdown()
        self.seven.refresh_countdown()

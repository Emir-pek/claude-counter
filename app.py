from __future__ import annotations

import os
import time
import tkinter as tk
from datetime import datetime, timezone

import customtkinter as ctk

from card_geometry import (corner_position, dot_overlay_center, glow_phase, interpolate,
                          point_in_rect, ring_phase, tween_frames)
from crab_overlay import TRANSPARENT_KEY
from formatting import GREEN, RED, YELLOW, color_for, format_countdown, format_reset_time, worst_color
from usage_client import UsageData, UsageError
from win_theme import (apply_titlebar_theme, begin_high_res_timer, end_high_res_timer,
                       frame_hwnd, set_rounded_region, work_area_rect)

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
IDLE_OPACITY = 0.7
EXPAND_ON_HOVER = True

CARD_RADIUS = 14
CARD_W_IDLE = 148
CARD_W_EXPANDED = 208
BAR_H_IDLE = 5
BAR_H_EXPANDED = 7
DOT_SIZE = 8
RING_SIZE = 14
# 32×32: kritik halka en büyük ölçeğinde (RING_SIZE/2*1.7 ≈ 11.9px yarıçap)
# ve parlama halosuyla (dot_r + glow*3 ≈ 7px yarıçap) birlikte gerçek pay
# bırakıyor. Artık bir kırpma bölgesinden kaçınmak gerekmiyor (bkz.
# DotOverlay) — bu kendi bölgesi olmayan, tamamen saydam ayrı bir pencere.
DOT_CANVAS_SIZE = 32
REOPEN_SIZE = 34

HOVER_POLL_MS = 50
# Ölçüldü (bkz. user-qa-fix-report.md, Task 3): Windows'ta Tk'nin after()
# zamanlayıcısı — begin_high_res_timer(1) etkin haldeyken bile — adım
# başına gerçekte ~17-23ms alıyor (Windows'un ~15.6ms zamanlayıcı
# çözünürlüğü + her adımın kendi win32 iş yükü: geometry()/SetWindowRgn).
# Eski TWEEN_MS=180/TWEEN_STEPS=18 (adım başına istenen 10ms, bu tabanın
# ALTINDA) yüzünden gerçek süre ~300ms'ydi — istenen gecikmeyi küçültmenin
# hiçbir faydası yoktu, çünkü adım sayısı × taban gerçek süreyi belirliyordu.
# Bu yüzden adım sayısı 5'e indirildi: 5 × ~20-24ms ≈ ölçülen 120-123ms,
# kullanıcının istediği 120-150ms aralığında — DPI'dan bağımsız, çünkü bu
# taban Tk'nin kendi zamanlayıcı mekanizmasından ve gerçek win32 işinden
# geliyor, piksel/font ölçeklemesinden değil.
TWEEN_MS = 100
TWEEN_STEPS = 5
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
        # width kasıtlı olarak sabitlenmedi (0 = CTkLabel'in "içeriğe göre
        # boyutlan" değeri): daha önceki sabit width=44 bu ortamda
        # (widget_scaling=1.0) yetiyordu ama kullanıcının gerçek makinesinde
        # farklı DPI/font ölçeklemesiyle metni kırpıyordu. Sütun 2'nin
        # grid_columnconfigure'da weight'i yok (yalnız sütun 1/bar ağırlıklı),
        # bu yüzden width vermemek etiketi gerçek render edilen fontun gerçek
        # piksel genişliğine oturtuyor — hangi makinede çalışırsa çalışsın.
        self.pct = ctk.CTkLabel(
            self.frame, text="", width=0, anchor="e",
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
            text += f" · resets {self._reset_text}"

        if text != self._last_text:
            self._last_text = text
            self.countdown.configure(text=text)


class ReopenTab(tk.Toplevel):
    """Kart gizlendiğinde köşede kalan küçük 'yeniden aç' sekmesi."""

    def __init__(self, app: "UsageApp"):
        super().__init__(app)
        self._app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.configure(bg=COLORS["window"])

        canvas = tk.Canvas(self, width=REOPEN_SIZE, height=REOPEN_SIZE,
                           bg=COLORS["window"], highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        r = 4
        cx = cy = REOPEN_SIZE / 2
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                           fill=COLORS["accent"], outline="")
        canvas.bind("<Button-1>", self._on_click)
        canvas.bind("<Button-3>", self._on_menu)

        self._menu = tk.Menu(self, tearoff=0)
        # command=self._app.quit_app doğrudan bağlanırsa (early binding),
        # __init__ anındaki quit_app metodunu sabitler; testlerin
        # monkeypatch.setattr(app, "quit_app", ...) ile yaptığı override
        # görülmez ve menü hep gerçek quit_app'i çağırır. lambda ile çağrı
        # anında self._app.quit_app'i yeniden çözüyoruz (late binding).
        self._menu.add_command(label="Quit", command=lambda: self._app.quit_app())

        self.withdraw()

    def show(self):
        work = work_area_rect() or (0, 0, self._app.winfo_screenwidth(),
                                    self._app.winfo_screenheight())
        x, y = corner_position(work, (REOPEN_SIZE, REOPEN_SIZE), CORNER, SCREEN_MARGIN)
        self.geometry(f"{REOPEN_SIZE}x{REOPEN_SIZE}+{x}+{y}")
        self.update_idletasks()
        try:
            set_rounded_region(frame_hwnd(self), REOPEN_SIZE, REOPEN_SIZE, 10)
        except Exception:
            pass
        self.deiconify()

    def _on_click(self, _event=None):
        self.withdraw()
        self._app.reopen()

    def _on_menu(self, event):
        self._menu.tk_popup(event.x_root, event.y_root)


class DotOverlay(tk.Toplevel):
    """Durum noktası/halka/parlama için kartın kendi penceresinden AYRI,
    saydam, kayan bir pencere.

    Neden ayrı pencere: kart kendi penceresi win_theme.set_rounded_region
    ile yuvarlak köşeli bir Win32 bölgeye (SetWindowRgn) kırpılıyor.
    Kartın ÇOCUĞU olan hiçbir widget bu kırpmanın dışına asla taşamaz —
    "dışarısı" bir çocuk widget için yok, offset ne olursa olsun. Nokta
    köşeden taşıp gerçekten dışarı görünmesi gerektiğinden (orijinal CSS
    mockup: top:-6px;right:-6px, kartın kutusunun dışına taşan bir
    kardeş eleman), crab_overlay.py'deki CrabOverlay ile birebir aynı
    kalıp izleniyor: -transparentcolor'lı ayrı bir overrideredirect
    Toplevel, sahibinin geometrisine göre elle senkronlanıyor.

    Kendi zamanlayıcı döngüsü YOK (CrabOverlay'in _move_tick/_walk_tick'inin
    aksine) — tamamen dışarıdan, UsageApp._apply_geometry çağrıldığında
    sync() ile itiliyor. Bu kasıtlı: bağımsız bir after() döngüsü,
    quit_app() sırasında iptal edilmesi unutulabilecek ayrı bir yeniden
    zamanlanan zamanlayıcı anlamına gelirdi (bu kod tabanının _ring_after
    ve CrabOverlay._shutdown ile daha önce iki kez çözdüğü sınıf bir hata) —
    zamanlayıcısız olmak bu hata sınıfını baştan imkânsız kılıyor.
    """

    def __init__(self, app: "UsageApp"):
        super().__init__(app)
        self._app = app
        # CrabOverlay'deki gibi: Toplevel başlığı ana pencereden miras
        # alınmasın, dış araçlar iki pencereden yanlışını "asıl pencere"
        # sanmasın.
        self.title("")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.configure(bg=TRANSPARENT_KEY)

        self.canvas = tk.Canvas(
            self, width=DOT_CANVAS_SIZE, height=DOT_CANVAS_SIZE,
            bg=TRANSPARENT_KEY, highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # _on_close_click/reopen() kartın kendi withdraw/deiconify'ıyla
        # birlikte bunu da açıkça çağırıyor (görünürlük değişikliğini
        # okuyan biri için en dolaysız yer) — ama CrabOverlay'in aynı
        # sorunu neden <Unmap>/<Map> ile çözdüğünü unutmayalım: ana
        # pencerenin withdraw()'ı Tk'de ÇOCUK widget'ları otomatik gizler
        # ama bağımsız bir Toplevel'i (bu overlay gibi) OTOMATİK gizlemez.
        # Kart .withdraw()'ı _on_close_click DIŞINDA bir yoldan (ör. bir
        # test fixture'ının doğrudan çağrısı, ileride eklenecek başka bir
        # kapatma yolu) çağrılırsa, açık withdraw() çağrısı olmadan bu
        # overlay ekranda kartsız, tek başına asılı kalırdı. Bağlama, aynı
        # sınıf hatayı CrabOverlay'in çözdüğü gibi kapatıyor: hangi yoldan
        # gelirse gelsin ana pencerenin gerçek haritalanma durumunu izliyor.
        self._app.bind("<Unmap>", self._on_app_unmap, add="+")
        self._app.bind("<Map>", self._on_app_map, add="+")

        self._last_key = None
        self.sync()

    def _on_app_unmap(self, _event=None):
        try:
            self.withdraw()
        except Exception:
            pass

    def _on_app_map(self, _event=None):
        try:
            self.deiconify()
        except Exception:
            pass

    def sync(self):
        """Kartın GERÇEK ekran konumuna göre kendini yeniden konumlar.

        _apply_geometry'nin her tween adımında ve her snap'te çağrılması
        bekleniyor — kart genişlerken/daralırken nokta da sorunsuzca onunla
        birlikte hareket etsin diye. Kart henüz haritalanmamışsa ya da
        pencere yok edilmişse (destroy sırası, bkz. sınıf docstring'i)
        sessizce hiçbir şey yapmıyor — diğer win32 sarmalayıcılarıyla aynı
        yutma kalıbı.
        """
        try:
            card_x = self._app.winfo_rootx()
            card_y = self._app.winfo_rooty()
            card_w = self._app.winfo_width()
        except Exception:
            return
        key = (card_x, card_y, card_w)
        if key == self._last_key:
            return
        self._last_key = key
        cx, cy = dot_overlay_center(card_x, card_y, card_w)
        x = round(cx - DOT_CANVAS_SIZE / 2)
        y = round(cy - DOT_CANVAS_SIZE / 2)
        try:
            self.geometry(f"{DOT_CANVAS_SIZE}x{DOT_CANVAS_SIZE}+{x}+{y}")
        except Exception:
            pass


class UsageApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Claude Usage")
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
        # win_theme.begin_high_res_timer'daki nota bak: quit_app()'te
        # eşleşen end_high_res_timer() ile bırakılmalı, o yüzden başarı
        # durumu burada tutuluyor.
        self._timer_res_active = begin_high_res_timer(1)

        self.card = ctk.CTkFrame(
            self, corner_radius=CARD_RADIUS, fg_color=COLORS["window"],
            border_width=1, border_color=COLORS["border"],
        )
        self.card.pack(fill="both", expand=True)
        self.card.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.card, fg_color="transparent")
        self.header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            self.header, text="Claude Usage", anchor="w",
            font=("Segoe UI", 11, "bold"), text_color=COLORS["text_primary"],
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.refresh_icon = ctk.CTkLabel(
            self.header, text="↻", width=14, font=("Segoe UI", 12),
            text_color=COLORS["accent"], cursor="hand2",
        )
        self.refresh_icon.grid(row=0, column=1, padx=(8, 4))
        self.close_icon = ctk.CTkLabel(
            self.header, text="✕", width=16, font=("Segoe UI", 11),
            text_color=COLORS["text_secondary"], cursor="hand2",
        )
        self.close_icon.grid(row=0, column=2, padx=(0, 6))
        self.refresh_icon.bind("<Button-1>", self._on_refresh_click)
        self.close_icon.bind("<Button-1>", self._on_close_click)
        self.header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        self.header.grid_remove()

        self.five = _Row(self.card, "5h")
        self.five.grid(1)
        self.seven = _Row(self.card, "7d")
        self.seven.grid(3)
        self.five.frame.grid_configure(padx=10, pady=(8, 0))
        self.seven.frame.grid_configure(padx=10, pady=(6, 0))

        self.status_label = ctk.CTkLabel(
            self.card, text="", anchor="w", font=("Segoe UI", 10),
        )
        self.status_label.grid(row=5, column=0, sticky="ew", padx=10, pady=(4, 8))
        self.status_label.grid_remove()

        # Durum noktası artık kartın çocuğu değil — bkz. DotOverlay
        # docstring'i: kartın kendi penceresi yuvarlak köşeye kırpılıyor,
        # bir çocuk widget bu kırpmanın dışına asla taşamaz. dot_canvas
        # burada bilinçli olarak ayrı Toplevel'in canvas'ına bir takma ad
        # (alias): mevcut kod/testler (tests/test_status_dot.py)
        # widget.dot_canvas.find_all() gibi doğrudan canvas API'sini
        # kullanıyor — çizim/zamanlayıcı mantığı (_redraw_dot/_tick_ring)
        # canvas'ın hangi pencerede yaşadığını bilmeden aynı kalabilsin diye
        # her çağrı noktasını değiştirmek yerine bu takma ad tutuluyor.
        self.dot_overlay = DotOverlay(self)
        self.dot_canvas = self.dot_overlay.canvas
        self._redraw_dot()

        set_window_icon(self)

        self.update_idletasks()
        self._set_expanded(False, animate=False)
        self.after(HOVER_POLL_MS, self._poll_hover_loop)
        self.reopen_tab = ReopenTab(self)

    def _on_refresh_click(self, _event=None):
        if self.on_refresh:
            self.on_refresh()

    def _on_close_click(self, _event=None):
        self._hovered = False  # gizliyken hover durumu anlamsız
        self.withdraw()
        # Kart gizlenince onunla kayan noktayı da gizle — aksi halde ayrı
        # bir pencere olduğu için ekranda kartsız, tek başına asılı kalır.
        self.dot_overlay.withdraw()
        self.reopen_tab.show()

    def reopen(self):
        self.deiconify()
        self.dot_overlay.deiconify()
        self._set_expanded(False, animate=False)

    def quit_app(self):
        # Task 7'nin _ring_after zamanlayıcısı kritik durumdayken kendini
        # yeniden zamanlar. Bu, o zamanlayıcı beklerken gerçekten .destroy()
        # çağırabilen ilk yol — bekleyen callback yok edilmiş pencereye karşı
        # ateşlenip hataya yol açmasın diye önce iptal ediyoruz. Kapanışı
        # engellememesi için sarmalanmış.
        if self._ring_after is not None:
            try:
                self.after_cancel(self._ring_after)
            except Exception:
                pass
            self._ring_after = None
        if self._timer_res_active:
            end_high_res_timer(1)
            self._timer_res_active = False
        self.reopen_tab.destroy()
        # DotOverlay'in kendi zamanlayıcı döngüsü yok (bkz. sınıf
        # docstring'i), bu yüzden _ring_after'ın aksine iptal edilecek
        # bekleyen bir after() callback'i yok — doğrudan yok edilebilir.
        self.dot_overlay.destroy()
        self.destroy()

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
        # Herhangi bir dışarıdan çağrılan anlık snap, o an sürmekte olan bir
        # tween'i (varsa) geçersiz kılmalı — yoksa tween'in bekleyen after()
        # adımları bu anlık geometriyle çakışıp eski hedefe doğru sürüklemeye
        # devam eder. _tween_to kendi adımları için _apply_geometry'yi
        # doğrudan çağırır (bu metodu değil), böylece kendi token'ını her
        # karede kendi kendine geçersiz kılmaz.
        self._tween_token = getattr(self, "_tween_token", 0) + 1
        self._apply_geometry(width, height, alpha)

    def _apply_geometry(self, width: int, height: int, alpha: float):
        work = work_area_rect() or (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        x, y = corner_position(work, (width, height), CORNER, SCREEN_MARGIN)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.attributes("-alpha", alpha)
        self.update_idletasks()
        try:
            set_rounded_region(frame_hwnd(self), width, height, CARD_RADIUS)
        except Exception:
            pass
        # Nokta, kartın her tween adımında/snap'inde onunla birlikte
        # kaymalı — bu yüzden her _apply_geometry çağrısında senkronlanıyor,
        # yalnızca dinlenme durumunda değil.
        self.dot_overlay.sync()
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
            self._apply_geometry(w, h, alpha)
            if i + 1 < len(frames):
                self.after(step_delay, lambda: step(i + 1))

        step(0)

    def _poll_hover_once(self):
        if not self.winfo_ismapped():
            # Kart gizliyken (withdraw sonrası) eski dikdörtgene karşı
            # yoklama yapmanın anlamı yok — hem gereksiz tween adımları
            # animasyonlanır hem de reopen sekmesinin üstündeki imleç
            # hâlâ "kartın üstünde" gibi okunup hover durumunu bozar.
            return
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
        if glow > 0:
            # Nabız, noktanın kendi outline'ını kalınlaştırarak değil —
            # arkasına, gerçek şiddet rengiyle çizilmiş ayrı ve büyüyen bir
            # halka ("halo") ile gösterilir. Outline arka planla aynı renkte
            # olsaydı (nokta çapını pulsing width ile büyütmenin eski yolu),
            # Tk'nin merkezden çizdiği outline'ın dışa taşan yarısı arka
            # planla görünmez kalır, içe taşan yarısı ise noktanın kendi
            # dolgusunu yiyip "parlama" yerine "küçülme" izlenimi verirdi.
            glow_r = dot_r + glow * 3
            c.create_oval(cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r,
                          outline=_BAR_COLOR[self._level], width=1.5)
        c.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r,
                      fill=_BAR_COLOR[self._level], outline=COLORS["window"],
                      width=1.5)

    def _update_dot(self):
        was_critical = self._ring_after is not None
        is_critical = self._level == RED
        self._redraw_dot()
        if is_critical and not was_critical:
            self._ring_start = time.monotonic()
            self._tick_ring()
        elif not is_critical and was_critical:
            self.after_cancel(self._ring_after)
            self._ring_after = None

    def _tick_ring(self):
        if self._level != RED:
            self._ring_after = None
            return
        elapsed_ms = (time.monotonic() - self._ring_start) * 1000
        scale, visible = ring_phase(elapsed_ms)
        glow = glow_phase(elapsed_ms)
        self._redraw_dot(ring_scale=scale, ring_visible=visible, glow=glow)
        self._ring_after = self.after(RING_TICK_MS, self._tick_ring)

    def render(self, data: UsageData):
        self._data = data
        self._status_text = ""
        self.five.set(data.five_hour)
        self.seven.set(data.seven_day)
        utils = [w.utilization if w is not None else None
                for w in (data.five_hour, data.seven_day)]
        self._level = worst_color(*utils)
        self._update_dot()
        self._refresh_status_visibility()

    def render_error(self, err: UsageError):
        if err.kind == "rate_limited":
            self._status_text = "Rate limited — retrying"
            self._status_color = COLORS["bar_mid"]
        else:
            self._status_text = err.message
            self._status_color = COLORS["bar_critical"]
        self._refresh_status_visibility()

    def tick(self):
        self.five.refresh_countdown()
        self.seven.refresh_countdown()

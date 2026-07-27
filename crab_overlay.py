"""Widget'ın çerçevesi etrafında dolaşan pixel-art yengeç.

Ayrı, saydam bir Toplevel içinde çizilir; ana pencereye hiç dokunmaz.
Geometri matematiği Tk'siz saf fonksiyonlarda, Win32 erişimi enjekte
edilebilir bir parametrenin arkasında — scheduling.py ve win_theme.py'deki
kalıbın aynısı.

Overlay tamamen isteğe bağlıdır: sprite, Pillow ya da -transparentcolor
yoksa sessizce devre dışı kalır ve uygulama normal açılır.
"""
from __future__ import annotations

import os
import tkinter as tk

try:
    from PIL import Image, ImageTk
except Exception:  # Pillow kurulu değilse overlay'siz devam edilir
    Image = ImageTk = None

from formatting import GREEN, RED, YELLOW, color_for
from win_theme import frame_hwnd

SPRITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "assets", "crab_walk.png")

# Teknik sentinel, tasarım rengi değil: bu yüzden app.py'deki COLORS
# sözlüğüne konmuyor. Tk bu renkteki pikselleri hem görünmez yapar hem de
# tıklamayı altındaki pencereye geçirir.
TRANSPARENT_KEY = "#FF00FF"

FRAME_SIZE = 32
FRAME_COUNT = 8
SCALE = 1
MARGIN = 40  # overlay çerçeveden her yöne bu kadar taşar
SPEED_PX_PER_SEC = 40.0
WALK_MS = 125  # 8 fps yürüyüş
MOVE_MS = 16  # ~60 fps hareket

# Sprite sağa bakıyor; açı "sağa bakmaktan itibaren saat yönünde derece".
EDGE_ANGLES = {"top": 0, "right": 90, "bottom": 180, "left": 270}

# Sprite sheet'in satırları: 0 sakin, 1 gergin, 2 kızgın.
# Eşiklerin tek sahibi formatting.color_for; burada yalnızca döndürdüğü
# seviye satıra çevriliyor — app.py'deki _BAR_COLOR ile aynı kalıp. Böylece
# çubuk kırmızıya döndüğü an yengeç de kızıyor, ikisi asla çelişmiyor.
TIER_BY_COLOR = {GREEN: 0, YELLOW: 1, RED: 2}
MOOD_ROWS = len(TIER_BY_COLOR)

# Kızgın yengeç daha hızlı yürüsün. Taban hızın katı olarak ifade ediliyor
# ki CrabOverlay(speed=...) parametresi anlamını korusun.
TIER_SPEED_FACTOR = (1.0, 1.2, 1.45)


# --------------------------------------------------------------------------
# Saf geometri — Tk gerektirmez, doğrudan test edilir
# --------------------------------------------------------------------------

def perimeter_length(w: float, h: float) -> float:
    return 2.0 * (w + h)


def position_at(d: float, w: float, h: float):
    """Çevre üzerindeki `d` mesafesinden (kenar, x, y, açı).

    Konum tek bir mesafe değerinden türetiliyor; dört ayrı kenar durumu
    tutulsaydı köşe geçişlerinde bunların senkronu kolayca bozulurdu.
    """
    perim = perimeter_length(w, h)
    if perim <= 0:
        # Pencere henüz haritalanmadıysa genişlik 0 olabilir; sıfıra bölme
        # yerine başlangıç noktası döner.
        return ("top", 0, 0, EDGE_ANGLES["top"])

    # Sarma olmazsa mesafe büyüdükçe yengeç çerçeveden kaçar.
    d = d % perim

    if d < w:
        return ("top", int(d), 0, EDGE_ANGLES["top"])
    d -= w
    if d < h:
        return ("right", int(w), int(d), EDGE_ANGLES["right"])
    d -= h
    if d < w:
        # Saat yönü: alt kenarda sağdan sola.
        return ("bottom", int(w - d), int(h), EDGE_ANGLES["bottom"])
    d -= w
    return ("left", 0, int(h - d), EDGE_ANGLES["left"])


def _win32_frame_rect(app):
    """Pencerenin DIŞ dikdörtgeni (nativ başlık çubuğu dahil)."""
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    hwnd = frame_hwnd(app)
    rect = RECT()
    if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)


def frame_rect(app, getter=None):
    """Yengecin dolaşacağı dikdörtgen: (x, y, genişlik, yükseklik).

    winfo_* İSTEMCİ alanını verir ve nativ başlık çubuğu onun dışında kalır;
    o değerler kullanılsaydı yengeç üst kenarda çubuğun altına girerdi.
    """
    getter = getter or _win32_frame_rect
    try:
        rect = getter(app)
        if rect:
            return rect
    except Exception:
        pass
    # Win32 yoksa (Windows dışı, ctypes yok) istemci alanına düşülür:
    # yengeç biraz yanlış yerde yürür ama uygulama yine açılır.
    app.update_idletasks()
    return (app.winfo_rootx(), app.winfo_rooty(),
            app.winfo_width(), app.winfo_height())


# --------------------------------------------------------------------------
# Sprite
# --------------------------------------------------------------------------

def frame_boxes(count: int = FRAME_COUNT, size: int = FRAME_SIZE):
    return [(i * size, 0, (i + 1) * size, size) for i in range(count)]


def slice_sheet(sheet, count: int = FRAME_COUNT, size: int = FRAME_SIZE,
                scale: int = SCALE, row: int = 0):
    """Sheet'in `row` satırını karelere böler ve NEAREST ile büyütür.

    NEAREST şart: pixel-art'ı bilinear büyütmek kenarları bulandırır.
    """
    frames = []
    for x0, _y0, x1, _y1 in frame_boxes(count, size):
        frame = sheet.crop((x0, row * size, x1, (row + 1) * size))
        if scale != 1:
            frame = frame.resize((size * scale, size * scale), Image.NEAREST)
        frames.append(frame)
    return frames


def mood_from(five_hour):
    """Ruh hali 5 saatlik pencereden gelir; haftalık kasıtlı olarak yok sayılır.

    Haftalık %90 olsa bile 5 saatlik %20'yse yengeç sakin kalmalı: kullanıcı
    o an ne kadar sıkıştığını 5 saatlik dilimden okuyor.
    """
    return five_hour.utilization if five_hour is not None else None


def tier_for(utilization: float) -> int:
    """Kullanım yüzdesini sprite satırına çevirir (0 sakin … 2 kızgın)."""
    return TIER_BY_COLOR[color_for(utilization)]


def speed_for(tier: int, base: float = SPEED_PX_PER_SEC) -> float:
    return base * TIER_SPEED_FACTOR[tier]


# --------------------------------------------------------------------------
# Overlay
# --------------------------------------------------------------------------

class NullCrab:
    """Overlay kurulamadığında geçerli hedef.

    app.py'de "if self.crab:" dallanması olmasın diye null-object: render()
    her durumda aynı çağrıyı yapar.
    """

    available = False
    tier = 0

    def set_mood(self, utilization) -> None:
        pass


NULL_CRAB = NullCrab()


class CrabOverlay:
    """Çerçeve etrafında saat yönünde yürüyen yengeç."""

    def __init__(self, app, sprite_path: str = SPRITE_PATH,
                 margin: int = MARGIN, speed: float = SPEED_PX_PER_SEC):
        self.available = False
        self._app = app
        self._margin = margin
        self._speed = speed
        self._mood = None
        self._tier = 0
        self._distance = 0.0
        self._frame = 0
        self._rect = (0, 0, 0, 0)
        self._win = None
        self._canvas = None
        self._item = None
        self._sprites = {}
        self._move_timer = None
        self._walk_timer = None
        try:
            self._build(sprite_path)
            self.available = True
        except Exception:
            # Sprite yok, Pillow yok ya da -transparentcolor desteklenmiyor:
            # overlay sessizce kapanır, uygulama normal açılır.
            self._shutdown()

    # -- kurulum ----------------------------------------------------------

    def _build(self, sprite_path: str) -> None:
        if Image is None or ImageTk is None:
            raise RuntimeError("Pillow yok")

        sheet = Image.open(sprite_path).convert("RGBA")

        self._win = tk.Toplevel(self._app)
        # Toplevel başlığı ana pencereden miras alıyor; iki pencere aynı adı
        # taşıyınca dış araçlar (ve Process.MainWindowHandle) yanlış olanı
        # bulup asıl pencere sanıyor.
        self._win.title("")
        self._win.overrideredirect(True)
        # Windows dışında TclError atar; yakalanıp overlay kapanır.
        self._win.attributes("-transparentcolor", TRANSPARENT_KEY)
        self._win.configure(bg=TRANSPARENT_KEY)

        self._canvas = tk.Canvas(self._win, bg=TRANSPARENT_KEY,
                                 highlightthickness=0, borderwidth=0)
        self._canvas.pack(fill="both", expand=True)

        # 3 ruh hali x 4 yön x 8 kare açılışta üretilip saklanıyor. Her
        # karede yeni PhotoImage yaratmak GC'nin sprite'ı toplamasına ve
        # canvas'ın boşalmasına yol açar — referanslar burada tutulmak
        # zorunda.
        for tier in range(MOOD_ROWS):
            frames = slice_sheet(sheet, row=tier)
            self._sprites[tier] = {
                angle: [ImageTk.PhotoImage(f.rotate(-angle, expand=True)) for f in frames]
                for angle in EDGE_ANGLES.values()
            }

        self._item = self._canvas.create_image(
            0, 0, image=self._sprites[0][EDGE_ANGLES["top"]][0])

        # Ana pencere zaten -topmost. İki topmost pencere arasında z-order
        # yarışı olur; overlay ana pencereden SONRA topmost yapılmazsa
        # yengeç aralıklarla widget'ın arkasına düşer.
        self._win.attributes("-topmost", True)
        self._win.lift()

        self._app.bind("<Configure>", self._on_configure, add="+")
        self._app.bind("<FocusIn>", self._on_focus, add="+")
        self._app.bind("<Unmap>", self._on_unmap, add="+")
        self._app.bind("<Map>", self._on_map, add="+")
        self._app.protocol("WM_DELETE_WINDOW", self._on_close)

        self._sync_geometry()
        self._walk_tick()
        self._move_tick()

    # -- olaylar ----------------------------------------------------------

    def _on_configure(self, _event=None):
        self._sync_geometry()

    def _on_focus(self, _event=None):
        # Ana pencere öne geldiğinde overlay altında kalmasın.
        try:
            self._win.lift()
        except Exception:
            pass

    def _on_unmap(self, _event=None):
        try:
            self._win.withdraw()
        except Exception:
            pass

    def _on_map(self, _event=None):
        try:
            self._win.deiconify()
            self._win.lift()
        except Exception:
            pass

    def _on_close(self):
        # Overlay ayrı bir Toplevel; kapatılmazsa ana pencere gittikten
        # sonra ekranda asılı kalır ve uygulama sonlanmaz.
        self._shutdown()
        try:
            self._app.destroy()
        except Exception:
            pass

    # -- animasyon --------------------------------------------------------

    def _sync_geometry(self) -> None:
        try:
            rect = frame_rect(self._app)
            # Değişmediyse geometry() çağrılmıyor: 60 fps'te her karede
            # yeniden konumlandırmak overlay'i titretir.
            if rect == self._rect:
                return
            self._rect = rect
            x, y, w, h = rect
            self._win.geometry(
                f"{w + 2 * self._margin}x{h + 2 * self._margin}"
                f"+{x - self._margin}+{y - self._margin}")
        except Exception:
            pass

    def _walk_tick(self) -> None:
        # Yürüyüş 8 fps, hareket 60 fps: ayrı zamanlayıcılar. Bunların
        # hiçbiri scheduling.Poller'a dokunmaz; Poller ağ isteği zincirini
        # yönetiyor, animasyon oraya karışmamalı.
        if self._win is None:
            return
        self._frame = (self._frame + 1) % FRAME_COUNT
        self._walk_timer = self._safe_after(WALK_MS, self._walk_tick)

    def _move_tick(self) -> None:
        if self._win is None:
            return
        try:
            # <Configure> tek başına yetmiyor: overlay pencere henüz
            # haritalanmadan kurulursa ilk ölçüm yanlış olur ve düzeltecek
            # bir olay gelmeyebilir. Döngü her karede kontrol eder.
            self._sync_geometry()
            self._advance(MOVE_MS / 1000.0)
        except Exception:
            pass
        self._move_timer = self._safe_after(MOVE_MS, self._move_tick)

    def _advance(self, dt: float) -> None:
        _x, _y, w, h = self._rect
        perim = perimeter_length(w, h)
        if perim <= 0:
            return
        self._distance = (self._distance + speed_for(self._tier, self._speed) * dt) % perim
        _edge, cx, cy, angle = position_at(self._distance, w, h)
        # Overlay çerçeveden margin kadar taşıyor; çerçeve koordinatı
        # overlay'in kendi koordinatına bu ofsetle çevriliyor.
        self._canvas.coords(self._item, cx + self._margin, cy + self._margin)
        self._canvas.itemconfigure(
            self._item, image=self._sprites[self._tier][angle][self._frame])

    def _safe_after(self, delay: int, fn):
        try:
            return self._win.after(delay, fn)
        except Exception:
            # Pencere kapanırken after() TclError atabilir; döngü sessizce biter.
            return None

    # -- dış arayüz -------------------------------------------------------

    @property
    def tier(self) -> int:
        """Aktif ruh hali kademesi (0 sakin … 2 kızgın)."""
        return self._tier

    def set_mood(self, utilization) -> None:
        """5 saatlik kullanıma göre sakin / gergin / kızgın kademesini seçer.

        None gelirse kademe korunuyor: veri gelmediğinde ruh hali son bilinen
        değerde kalmalı, sıfırlanmamalı.
        """
        if utilization is None:
            return
        self._mood = utilization
        try:
            self._tier = tier_for(utilization)
        except Exception:
            # Beklenmedik bir değer animasyonu durdurmamalı.
            pass

    def _shutdown(self) -> None:
        for name in ("_move_timer", "_walk_timer"):
            timer = getattr(self, name, None)
            if timer is not None and self._win is not None:
                try:
                    self._win.after_cancel(timer)
                except Exception:
                    pass
            setattr(self, name, None)
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
        self._win = None
        self.available = False


def install(app, **kwargs):
    """Overlay'i kurar; kurulamazsa null-object döner. İstisna sızdırmaz."""
    try:
        crab = CrabOverlay(app, **kwargs)
    except Exception:
        return NULL_CRAB
    return crab if crab.available else NULL_CRAB

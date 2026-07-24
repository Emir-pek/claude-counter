# Yerel sıfırlanma saati — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her limit satırına, geri sayımın yanına sıfırlanmanın yerel saatini eklemek (`%5   ⟳ 4s 39dk · 05:12`) ve bu metni saniyede bir değil, yalnızca değiştiğinde hesaplamak.

**Architecture:** Tüm biçimlendirme mantığı `formatting.py`'ye yeni bir saf fonksiyon olarak eklenir (`format_reset_time`); test edilen yer burasıdır. `app.py`'deki `_Row` sınıfı bu fonksiyonun sonucunu `(resets_at, yerel_bugün, süresi_doldu)` anahtarıyla önbellekler ve etikete yalnızca metin gerçekten değiştiğinde yazar.

**Tech Stack:** Python 3.11, CustomTkinter 6.0.0, pytest. Yeni bağımlılık yok — yalnızca standart kütüphane `datetime`.

**Spec:** `docs/superpowers/specs/2026-07-25-yerel-sifirlama-saati-design.md`

## Global Constraints

- Dil: kullanıcıya görünen tüm metinler Türkçe. Kod içi yorumlar da Türkçe (mevcut dosyaların üslubu).
- Gün adları **sabit** olarak yazılır: `("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")`, `weekday()` ile indekslenir (0 = Pazartesi). `strftime("%a")` **kullanılmayacak** — sistem diline bağlıdır ve bu makinede `Fri` döndürür.
- Zaman karşılaştırmaları **yerel saate çevrildikten sonra** yapılır. `resets_at` sunucudan `+00:00` gelir, `now` UTC'dir; doğrudan `.date()` karşılaştırması Türkiye'de her akşam yanlış sonuç verir.
- Süre dolmuşluk eşiği mevcut `format_countdown` ile aynı: `int((resets_at - now).total_seconds()) <= 0`.
- Ayraç ` · ` (U+00B7, iki yanında birer boşluk). Saat metni boşsa ayraç da yazılmaz.
- Pencere boyutu (`260x235`) **değişmeyecek**. Ölçüldü: gün adlı en uzun hal 150 px, kullanılabilir alan 240 px.
- Mevcut 21 test geçmeye devam etmeli.
- Her task sonunda commit.

---

### Task 1: `format_reset_time` biçimlendirme fonksiyonu

**Files:**
- Modify: `formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: yok (saf fonksiyon, standart kütüphane dışında bağımlılığı yok).
- Produces:
  - `DAY_NAMES: tuple[str, ...]` — 7 elemanlı Türkçe gün kısaltmaları.
  - `format_reset_time(resets_at: datetime, now: datetime, tz=None) -> str`
    - `tz=None` → sistem yerel saat dilimi.
    - Süre dolmuşsa `""`, sıfırlanma yerelde bugünse `"14:00"`, başka bir güne düşüyorsa `"Paz 01:00"`.
    - Task 2 bu fonksiyonu `app.py`'den `tz` vermeden çağırır.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_formatting.py` dosyasının ilk iki satırı şu an şöyle:

```python
from datetime import datetime, timedelta, timezone
from formatting import format_countdown, color_for, GREEN, YELLOW, RED
```

Bu **iki satırı** şununla değiştir:

```python
import re
from datetime import datetime, timedelta, timezone
from formatting import (
    format_countdown,
    format_reset_time,
    color_for,
    DAY_NAMES,
    GREEN,
    YELLOW,
    RED,
)
```

Ardından dosyanın **sonuna** şunları ekle:

```python
# Türkiye saati (UTC+3). Testlerde sabitlenir ki sonuç makinenin
# saat dilimine bağlı olmasın.
TR = timezone(timedelta(hours=3))


def test_reset_time_same_local_day():
    # yerel 09:00 -> yerel 14:00, ikisi de 25 Temmuz
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 25, 11, 0, tzinfo=timezone.utc)
    assert format_reset_time(resets, now, TR) == "14:00"


def test_reset_time_crosses_local_midnight_while_utc_day_is_same():
    # Asıl tuzak: UTC'de iki tarih de 25 Temmuz, ama yerelde
    # 25 Temmuz 22:00 -> 26 Temmuz 01:00. Gün adı çıkmalı.
    now = datetime(2026, 7, 25, 19, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 25, 22, 0, tzinfo=timezone.utc)
    assert now.date() == resets.date()  # UTC tarihleri aynı
    assert format_reset_time(resets, now, TR) == "Paz 01:00"


def test_reset_time_days_away():
    # haftalık dilim: yerel 25 Temmuz 09:00 -> 31 Temmuz 12:58
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    resets = datetime(2026, 7, 31, 9, 58, tzinfo=timezone.utc)
    assert format_reset_time(resets, now, TR) == "Cum 12:58"


def test_reset_time_expired_returns_empty():
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    assert format_reset_time(now - timedelta(seconds=5), now, TR) == ""


def test_reset_time_exactly_now_returns_empty():
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    assert format_reset_time(now, now, TR) == ""


def test_reset_time_uses_system_local_when_tz_omitted():
    # tz verilmezse çökmemeli ve SS:DD biçiminde bir şey dönmeli.
    now = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)
    out = format_reset_time(now + timedelta(hours=2), now)
    assert re.fullmatch(r"(\w{3} )?\d{2}:\d{2}", out)


def test_day_names_are_turkish_and_locale_independent():
    assert DAY_NAMES == ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
```

- [ ] **Step 2: Testlerin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: FAIL — `ImportError: cannot import name 'format_reset_time' from 'formatting'`

- [ ] **Step 3: Minimum uygulamayı yaz**

`formatting.py` mevcut import'u (`from datetime import datetime`) yeterli,
dokunma. Renk sabitlerinin (`RED = "#e74c3c"`) **altına**, `format_countdown`
tanımının üstüne ekle:

```python
# weekday() sırası: 0 = Pazartesi. strftime("%a") kullanılmıyor,
# çünkü sistem diline bağlı ve bu makinede "Fri" döndürüyor.
DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
```

Dosyanın **sonuna** ekle:

```python
def format_reset_time(resets_at: datetime, now: datetime, tz=None) -> str:
    """Sıfırlanmanın yerel saati. Süre dolmuşsa boş string.

    Karşılaştırma yerel saate çevrildikten sonra yapılır: resets_at
    UTC gelir, doğrudan tarih kıyaslamak UTC+3'te gece yarısını aşan
    dilimlerde yanlış sonuç verir.
    """
    if int((resets_at - now).total_seconds()) <= 0:
        return ""
    local_reset = resets_at.astimezone(tz)
    local_now = now.astimezone(tz)
    hhmm = local_reset.strftime("%H:%M")
    if local_reset.date() == local_now.date():
        return hhmm
    return f"{DAY_NAMES[local_reset.weekday()]} {hhmm}"
```

`astimezone(None)` sistem yerel saat dilimine çevirir — `tz` verilmediğinde
istenen davranış budur.

- [ ] **Step 4: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: PASS — 7 yeni test dahil hepsi yeşil.

Ardından tüm suite: `python -m pytest -q`
Expected: 28 passed (mevcut 21 + yeni 7)

- [ ] **Step 5: Commit**

```bash
git add formatting.py tests/test_formatting.py
git commit -m "feat: yerel sıfırlanma saati biçimlendirmesi"
```

---

### Task 2: `_Row` önbelleği ve satır metni

**Files:**
- Modify: `app.py:13-43` (`_Row` sınıfı: `__init__`, `set`, `refresh_countdown`)
- Test: `tests/test_app_row.py` (yeni)

**Interfaces:**
- Consumes: Task 1'den `format_reset_time(resets_at, now, tz=None) -> str`. `app.py` bunu `tz` vermeden çağırır (sistem yerel saati).
- Produces: kullanıcıya görünen satır metni. Biçim:
  `f"%{util:.0f}   ⟳ {countdown}"` + saat metni boş değilse ` · {reset_text}`.

**Not:** `app.py`'nin şu ana kadar otomatik testi yoktu. Bu task iki gerçek
davranışı kilitleyen küçük bir test dosyası ekler (yazma koruması ve
`set(None)` sonrası önbelleğin temizlenmesi). Testler tek bir `CTk` kökü
oluşturur; bu makinede ekran var, sorun çıkmaz.

- [ ] **Step 1: Başarısız testleri yaz**

Yeni dosya `tests/test_app_row.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from usage_client import Window


@pytest.fixture(scope="module")
def root():
    r = app_module.ctk.CTk()
    r.withdraw()  # test sırasında pencere görünmesin
    yield r
    r.destroy()


def _win(hours_ahead: float, util: float = 42.0) -> Window:
    return Window(
        utilization=util,
        resets_at=datetime.now(timezone.utc) + timedelta(hours=hours_ahead),
    )


def test_row_shows_percent_countdown_and_reset_time(root):
    row = app_module._Row(root, "5 saatlik")
    row.set(_win(2))
    text = row.info.cget("text")
    assert text.startswith("%42   ⟳ ")
    assert " · " in text


def test_row_skips_label_write_when_text_unchanged(root):
    row = app_module._Row(root, "5 saatlik")
    row.set(_win(2))

    writes = []
    original = row.info.configure

    def spy(**kwargs):
        if "text" in kwargs:
            writes.append(kwargs["text"])
        return original(**kwargs)

    row.info.configure = spy
    row.refresh_countdown()
    row.refresh_countdown()
    row.refresh_countdown()
    assert writes == []  # metin değişmedi, hiç yazılmamalı


def test_row_recovers_after_set_none(root):
    # Regresyon: set(None) sonrası önbellek temizlenmezse, aynı
    # resets_at ile gelen geçerli veri aynı metni üretir, yazma
    # koruması devreye girer ve satır "—" takılı kalır.
    row = app_module._Row(root, "5 saatlik")
    window = _win(2)
    row.set(window)
    good = row.info.cget("text")

    row.set(None)
    assert row.info.cget("text") == "—"

    row.set(window)
    assert row.info.cget("text") == good


def test_row_expired_has_no_reset_time(root):
    row = app_module._Row(root, "5 saatlik")
    row.set(_win(-1))
    text = row.info.cget("text")
    assert "yenilendi" in text
    assert " · " not in text
```

- [ ] **Step 2: Testlerin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_app_row.py -v`
Expected: FAIL — `test_row_shows_percent_countdown_and_reset_time` " · " bulamaz
(satırda henüz saat yok), `test_row_skips_label_write_when_text_unchanged`
üç yazma görür.

- [ ] **Step 3: `_Row` sınıfını güncelle**

`app.py`'de import satırını şununla değiştir:

```python
from formatting import color_for, format_countdown, format_reset_time
```

`_Row.__init__` içinde `self.window = None  # type: ignore` satırının altına ekle:

```python
        # Saat metni sadece anahtar değişince hesaplanır; anahtar bir
        # döngü boyunca sabit kalır (5 saatte / haftada bir).
        self._reset_key = None
        self._reset_text = ""
        self._last_info = None
```

`set` metodunun tamamını şununla değiştir:

```python
    def set(self, window):
        self.window = window
        if window is None:
            self.bar.set(0)
            self.info.configure(text="—")
            # Önbellek temizlenmezse aynı resets_at ile gelen sonraki
            # geçerli veri aynı metni üretir, yazma koruması devreye
            # girer ve satır "—" takılı kalır.
            self._reset_key = None
            self._reset_text = ""
            self._last_info = None
            return
        self.bar.set(window.utilization / 100)
        self.bar.configure(progress_color=color_for(window.utilization))
        self.refresh_countdown()
```

`refresh_countdown` metodunun tamamını şununla değiştir:

```python
    def refresh_countdown(self):
        if self.window is None:
            return
        now = datetime.now(timezone.utc)
        resets_at = self.window.resets_at
        expired = int((resets_at - now).total_seconds()) <= 0

        # Yerel gün anahtarda: gün adının varlığı gece yarısı bayatlar.
        # Süresi dolmuşluk anahtarda: dolduğunda saat metni boşalmalı
        # ama resets_at ve yerel gün değişmez.
        key = (resets_at, now.astimezone().date(), expired)
        if key != self._reset_key:
            self._reset_key = key
            self._reset_text = format_reset_time(resets_at, now)

        text = f"%{self.window.utilization:.0f}   ⟳ {format_countdown(resets_at, now)}"
        if self._reset_text:
            text += f" · {self._reset_text}"

        # Geri sayım dakika hassasiyetinde; saniyede bir yazmanın anlamı yok.
        if text != self._last_info:
            self._last_info = text
            self.info.configure(text=text)
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_app_row.py -v`
Expected: PASS — 4 test yeşil.

Ardından tüm suite: `python -m pytest -q`
Expected: 32 passed (21 mevcut + 7 Task 1 + 4 Task 2)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_row.py
git commit -m "feat: satırda yerel sıfırlanma saati, döngü başına tek hesap"
```

---

### Task 3: Görsel doğrulama

**Files:**
- Değişiklik yok (yalnızca doğrulama). Taşma çıkarsa: `app.py:51` (`geometry`).

**Interfaces:**
- Consumes: Task 1 ve Task 2'nin tamamı.
- Produces: yok.

- [ ] **Step 1: Uygulamayı başlat**

```bash
python main.py
```

Windows'ta arka planda başlatmak için:

```powershell
Start-Process python -ArgumentList "main.py" -WorkingDirectory "C:\Users\emire\Desktop\projeler\claude-counter"
```

- [ ] **Step 2: Pencereyi ekran görüntüsüyle kontrol et**

"Claude Kullanımı" başlıklı pencerenin ekran görüntüsünü al ve **bak**.
Kontrol listesi:

- Her iki satırda da `%NN   ⟳ ... · SS:DD` biçimi görünüyor mu?
- Metin pencerenin sağ kenarından taşıyor mu? (taşmamalı — ölçüm 150/240 px)
- Alttaki `güncellendi: SS:DD` satırı hâlâ görünür mü? (v1'de kırpılma hatası
  vardı, tekrarlamamalı)
- Haftalık satırdaki sıfırlanma bugüne düşmüyorsa gün adı var mı?

- [ ] **Step 3: Elle yenilemeyi dene**

↻ butonuna tıkla. Satırlar kaybolmamalı, hata mesajı çıkmamalı.

- [ ] **Step 4: Uygulamayı kapat**

Taşma veya kırpılma görülürse `app.py`'deki `geometry("260x235")` değerini
yükselt, testleri tekrar çalıştır ve ayrı bir commit at. Sorun yoksa commit
gerekmez — bu task doğrulamadır.

---

## Bitiş

Üç task bittiğinde:

- `python -m pytest -q` → 32 passed
- Görsel kontrol yapılmış olmalı
- `superpowers:finishing-a-development-branch` ile branch kararı kullanıcıya sorulur.
  **Not:** bu depoda git remote yok ve kullanıcı GitHub'a kendisi push edecek —
  remote ekleme veya push önerilmeyecek.

# claude-counter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her zaman üstte duran küçük bir Python widget'ı ile Claude aboneliğinin 5 saatlik ve haftalık kullanım limitlerini (yüzde + yenilenme geri sayımı) göstermek.

**Architecture:** Üç katman — `usage_client.py` (token okuma + API çağrısı + parse), `formatting.py` (geri sayım metni + renk eşiği, saf fonksiyonlar), `app.py` (CustomTkinter penceresi), `main.py` (bağlama noktası). Veri, Claude Code'un kullandığı `GET https://api.anthropic.com/api/oauth/usage` endpoint'inden gelir; token her istekte `~/.claude/.credentials.json`'dan yeniden okunur. Ağ isteği ayrı thread'de, geri sayım her saniye yerelde hesaplanır.

**Tech Stack:** Python 3.11, CustomTkinter (GUI), standart kütüphane `urllib.request` (ağ), pytest (test).

## Global Constraints

- Python 3.11 (sistemde kurulu). Test/çalıştırma komutu: `python -m pytest` / `python main.py`.
- Tek çalışma-zamanı dış bağımlılığı: `customtkinter`. Ağ için ekstra paket YOK (`urllib.request` kullan). Test için `pytest`.
- Kimlik: token yalnızca `~/.claude/.credentials.json` içindeki `claudeAiOauth.accessToken` alanından okunur; token yenileme YAPILMAZ (Claude Code'a bırakılır).
- Endpoint: `https://api.anthropic.com/api/oauth/usage`, header `Authorization: Bearer <token>` + `Content-Type: application/json`, timeout 5 sn.
- Zaman dilimleri: `resets_at` timezone-aware (UTC). Geri sayım karşılaştırmalarında "now" da aware olmalı (`datetime.now(timezone.utc)`) — aware/naive karıştırma yasak.
- Kullanıcıya görünen tüm metinler Türkçe.
- Renk eşiği: `<60` yeşil `#2ecc71`, `60..85` sarı `#f1c40f`, `>85` kırmızı `#e74c3c`.
- Tüm dosyalar `claude-counter/` kök dizininde; testler `claude-counter/tests/` altında.

---

### Task 1: Proje iskeleti + token okuma

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py` (boş)
- Create: `usage_client.py`
- Test: `tests/test_usage_client.py`

**Interfaces:**
- Consumes: (yok)
- Produces:
  - `CREDENTIALS_PATH: str` — varsayılan credentials yolu.
  - `USAGE_URL: str = "https://api.anthropic.com/api/oauth/usage"`
  - `class NoCredentialsError(Exception)`
  - `read_token(path: str = CREDENTIALS_PATH) -> str` — başarıda access token string; token yoksa/bozuksa `NoCredentialsError`.

- [ ] **Step 1: `requirements.txt` oluştur**

```
customtkinter
pytest
```

- [ ] **Step 2: `tests/__init__.py` oluştur** (boş dosya)

- [ ] **Step 3: Başarısız testi yaz** — `tests/test_usage_client.py`

```python
import json
import pytest
from usage_client import read_token, NoCredentialsError


def _write_creds(tmp_path, obj):
    p = tmp_path / ".credentials.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_read_token_returns_access_token(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok-123"}})
    assert read_token(path) == "tok-123"


def test_read_token_missing_file_raises(tmp_path):
    with pytest.raises(NoCredentialsError):
        read_token(str(tmp_path / "yok.json"))


def test_read_token_missing_field_raises(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {}})
    with pytest.raises(NoCredentialsError):
        read_token(path)
```

- [ ] **Step 4: Testin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_usage_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'usage_client'`

- [ ] **Step 5: Minimal implementasyonu yaz** — `usage_client.py`

```python
from __future__ import annotations

import json
import os

CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class NoCredentialsError(Exception):
    pass


def read_token(path: str = CREDENTIALS_PATH) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise NoCredentialsError(str(e))
    try:
        return data["claudeAiOauth"]["accessToken"]
    except (KeyError, TypeError):
        raise NoCredentialsError("accessToken bulunamadı")
```

- [ ] **Step 6: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_usage_client.py -v`
Expected: PASS (3 test)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt tests/__init__.py tests/test_usage_client.py usage_client.py
git commit -m "feat: proje iskeleti ve token okuma"
```

---

### Task 2: Yanıtı parse etme (`parse_usage`)

**Files:**
- Modify: `usage_client.py`
- Test: `tests/test_usage_client.py`

**Interfaces:**
- Consumes: `usage_client` modülü (Task 1).
- Produces:
  - `@dataclass Window(utilization: float, resets_at: datetime)`
  - `@dataclass UsageData(five_hour: Window | None, seven_day: Window | None, fetched_at: datetime)`
  - `parse_usage(payload: dict, fetched_at: datetime) -> UsageData` — eksik/bozuk pencere `None` olur, diğerini etkilemez.

- [ ] **Step 1: Başarısız testi yaz** — `tests/test_usage_client.py` sonuna ekle

```python
from datetime import datetime, timezone
from usage_client import parse_usage, UsageData, Window

SAMPLE = {
    "five_hour": {"utilization": 30.0, "resets_at": "2026-07-23T21:09:59.349625+00:00"},
    "seven_day": {"utilization": 71.0, "resets_at": "2026-07-25T10:00:00.349653+00:00"},
}


def test_parse_usage_reads_both_windows():
    now = datetime(2026, 7, 23, 21, 0, tzinfo=timezone.utc)
    data = parse_usage(SAMPLE, now)
    assert isinstance(data, UsageData)
    assert data.five_hour.utilization == 30.0
    assert data.five_hour.resets_at == datetime(2026, 7, 23, 21, 9, 59, 349625, tzinfo=timezone.utc)
    assert data.seven_day.utilization == 71.0
    assert data.fetched_at == now


def test_parse_usage_missing_window_is_none():
    data = parse_usage({"five_hour": None, "seven_day": SAMPLE["seven_day"]}, datetime.now(timezone.utc))
    assert data.five_hour is None
    assert data.seven_day.utilization == 71.0


def test_parse_usage_incomplete_window_is_none():
    data = parse_usage({"five_hour": {"utilization": 5.0}, "seven_day": {}}, datetime.now(timezone.utc))
    assert data.five_hour is None
    assert data.seven_day is None
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_usage_client.py -k parse -v`
Expected: FAIL — `ImportError: cannot import name 'parse_usage'`

- [ ] **Step 3: Minimal implementasyonu yaz** — `usage_client.py`, importları güncelle ve ekle

`usage_client.py` başındaki importları şu hale getir:

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
```

Dosyanın sonuna ekle:

```python
@dataclass
class Window:
    utilization: float
    resets_at: datetime


@dataclass
class UsageData:
    five_hour: Window | None
    seven_day: Window | None
    fetched_at: datetime


def _parse_window(obj) -> Window | None:
    if not isinstance(obj, dict):
        return None
    util = obj.get("utilization")
    resets = obj.get("resets_at")
    if util is None or resets is None:
        return None
    try:
        return Window(utilization=float(util), resets_at=datetime.fromisoformat(resets))
    except (TypeError, ValueError):
        return None


def parse_usage(payload: dict, fetched_at: datetime) -> UsageData:
    return UsageData(
        five_hour=_parse_window(payload.get("five_hour")),
        seven_day=_parse_window(payload.get("seven_day")),
        fetched_at=fetched_at,
    )
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_usage_client.py -v`
Expected: PASS (6 test)

- [ ] **Step 5: Commit**

```bash
git add usage_client.py tests/test_usage_client.py
git commit -m "feat: usage yanıtını parse et"
```

---

### Task 3: API çağrısı ve hata yönetimi (`fetch_usage`)

**Files:**
- Modify: `usage_client.py`
- Test: `tests/test_usage_client.py`

**Interfaces:**
- Consumes: `read_token`, `parse_usage`, `UsageData`, `USAGE_URL`, `CREDENTIALS_PATH` (Task 1–2).
- Produces:
  - `@dataclass UsageError(kind: str, message: str)` — `kind ∈ {"no_credentials","unauthorized","network","bad_response"}`.
  - `fetch_usage(path=CREDENTIALS_PATH, url=USAGE_URL, opener=urllib.request.urlopen) -> UsageData | UsageError`. `opener` çağrılabilir `opener(request, timeout=...) -> context manager` olup test edilebilir; gerçek kullanımda `urllib.request.urlopen`.

- [ ] **Step 1: Başarısız testi yaz** — `tests/test_usage_client.py` sonuna ekle

```python
import io
import urllib.error
from contextlib import contextmanager
from usage_client import fetch_usage, UsageError


@contextmanager
def _fake_response(body: bytes):
    yield io.BytesIO(body)


def _opener_returning(body: bytes):
    def opener(req, timeout=None):
        return _fake_response(body)
    return opener


def _opener_raising(exc):
    def opener(req, timeout=None):
        raise exc
    return opener


def test_fetch_usage_success(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok"}})
    body = json.dumps(SAMPLE).encode("utf-8")
    result = fetch_usage(path=path, opener=_opener_returning(body))
    assert isinstance(result, UsageData)
    assert result.seven_day.utilization == 71.0


def test_fetch_usage_no_credentials(tmp_path):
    result = fetch_usage(path=str(tmp_path / "yok.json"), opener=_opener_returning(b"{}"))
    assert isinstance(result, UsageError)
    assert result.kind == "no_credentials"


def test_fetch_usage_unauthorized(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok"}})
    exc = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    result = fetch_usage(path=path, opener=_opener_raising(exc))
    assert isinstance(result, UsageError)
    assert result.kind == "unauthorized"


def test_fetch_usage_network_error(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok"}})
    result = fetch_usage(path=path, opener=_opener_raising(urllib.error.URLError("down")))
    assert isinstance(result, UsageError)
    assert result.kind == "network"


def test_fetch_usage_bad_json(tmp_path):
    path = _write_creds(tmp_path, {"claudeAiOauth": {"accessToken": "tok"}})
    result = fetch_usage(path=path, opener=_opener_returning(b"not json"))
    assert isinstance(result, UsageError)
    assert result.kind == "bad_response"
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_usage_client.py -k fetch -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_usage'`

- [ ] **Step 3: Minimal implementasyonu yaz** — `usage_client.py`

Import bloğunu güncelle (üste ekle):

```python
import urllib.error
import urllib.request
from datetime import datetime, timezone
```
(Not: `from datetime import datetime` satırını yukarıdaki ile birleştir — tek satır `from datetime import datetime, timezone` olsun.)

Dosyanın sonuna ekle:

```python
@dataclass
class UsageError:
    kind: str
    message: str


def fetch_usage(path: str = CREDENTIALS_PATH, url: str = USAGE_URL,
                opener=urllib.request.urlopen) -> "UsageData | UsageError":
    try:
        token = read_token(path)
    except NoCredentialsError:
        return UsageError("no_credentials", "Claude oturumu bulunamadı")

    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with opener(req, timeout=5) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return UsageError("unauthorized", "Oturum süresi dolmuş — Claude Code'da giriş yapın")
        return UsageError("network", f"Sunucu hatası ({e.code})")
    except (urllib.error.URLError, TimeoutError, OSError):
        return UsageError("network", "Bağlantı yok")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return UsageError("bad_response", "Beklenmedik yanıt")
    return parse_usage(payload, datetime.now(timezone.utc))
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_usage_client.py -v`
Expected: PASS (11 test)

- [ ] **Step 5: Commit**

```bash
git add usage_client.py tests/test_usage_client.py
git commit -m "feat: fetch_usage ağ çağrısı ve hata yönetimi"
```

---

### Task 4: Biçimlendirme yardımcıları (`format_countdown`, `color_for`)

**Files:**
- Create: `formatting.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: (yok — saf fonksiyonlar)
- Produces:
  - `format_countdown(resets_at: datetime, now: datetime) -> str` — ikisi de timezone-aware. Çıktı: `"1g 12s"`, `"1s 12dk"`, `"12dk"`, süre ≤0 ise `"yenilendi"`, 1 dk altındaki pozitif süre `"1dk"`.
  - `GREEN`, `YELLOW`, `RED` renk sabitleri (hex str).
  - `color_for(util: float) -> str` — `<60` GREEN, `60..85` YELLOW, `>85` RED.

- [ ] **Step 1: Başarısız testi yaz** — `tests/test_formatting.py`

```python
from datetime import datetime, timedelta, timezone
from formatting import format_countdown, color_for, GREEN, YELLOW, RED

NOW = datetime(2026, 7, 23, 21, 0, tzinfo=timezone.utc)


def _in(**kw):
    return NOW + timedelta(**kw)


def test_countdown_days_and_hours():
    assert format_countdown(_in(days=1, hours=12, minutes=30), NOW) == "1g 12s"


def test_countdown_hours_and_minutes():
    assert format_countdown(_in(hours=1, minutes=12), NOW) == "1s 12dk"


def test_countdown_minutes_only():
    assert format_countdown(_in(minutes=12), NOW) == "12dk"


def test_countdown_under_one_minute():
    assert format_countdown(_in(seconds=30), NOW) == "1dk"


def test_countdown_expired():
    assert format_countdown(_in(seconds=-5), NOW) == "yenilendi"


def test_color_thresholds():
    assert color_for(30.0) == GREEN
    assert color_for(59.9) == GREEN
    assert color_for(60.0) == YELLOW
    assert color_for(71.0) == YELLOW
    assert color_for(85.0) == YELLOW
    assert color_for(85.1) == RED
    assert color_for(90.0) == RED
```

- [ ] **Step 2: Testin başarısız olduğunu doğrula**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'formatting'`

- [ ] **Step 3: Minimal implementasyonu yaz** — `formatting.py`

```python
from __future__ import annotations

from datetime import datetime

GREEN = "#2ecc71"
YELLOW = "#f1c40f"
RED = "#e74c3c"


def format_countdown(resets_at: datetime, now: datetime) -> str:
    secs = int((resets_at - now).total_seconds())
    if secs <= 0:
        return "yenilendi"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days > 0:
        return f"{days}g {hours}s"
    if hours > 0:
        return f"{hours}s {mins}dk"
    if mins > 0:
        return f"{mins}dk"
    return "1dk"


def color_for(util: float) -> str:
    if util < 60:
        return GREEN
    if util <= 85:
        return YELLOW
    return RED
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: PASS (6 test)

- [ ] **Step 5: Commit**

```bash
git add formatting.py tests/test_formatting.py
git commit -m "feat: geri sayım biçimi ve renk eşiği"
```

---

### Task 5: Widget penceresi (`app.py`)

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `UsageData`, `UsageError` (usage_client); `format_countdown`, `color_for` (formatting).
- Produces:
  - `class UsageApp(customtkinter.CTk)` — pencere.
  - `UsageApp.render(data: UsageData) -> None` — iki limiti çizer, `self._data`'yı günceller.
  - `UsageApp.render_error(err: UsageError) -> None` — hata mesajını gösterir.
  - `UsageApp.tick() -> None` — geri sayımları mevcut `self._data`'dan yeniden hesaplar (ağa gitmez).
  - `on_refresh: callable | None` — ↻ butonuna basınca çağrılır (Task 6 bağlar).

Bu görev UI'dır; otomatik test yok, adımlar elle doğrulama içerir.

- [ ] **Step 1: `app.py` oluştur**

```python
from __future__ import annotations

from datetime import datetime, timezone

import customtkinter as ctk

from formatting import color_for, format_countdown
from usage_client import UsageData, UsageError

ctk.set_appearance_mode("dark")


class _Row:
    """Tek bir limit satırı: etiket + çubuk + yüzde + geri sayım."""

    def __init__(self, parent, title: str):
        self.title = ctk.CTkLabel(parent, text=title, anchor="w", font=("Segoe UI", 12, "bold"))
        self.bar = ctk.CTkProgressBar(parent, height=12)
        self.bar.set(0)
        self.info = ctk.CTkLabel(parent, text="—", anchor="w", font=("Segoe UI", 11))
        self.window = None  # type: ignore

    def grid(self, r: int):
        self.title.grid(row=r, column=0, sticky="w", padx=10, pady=(6, 0))
        self.bar.grid(row=r + 1, column=0, sticky="ew", padx=10)
        self.info.grid(row=r + 2, column=0, sticky="w", padx=10, pady=(0, 4))

    def set(self, window):
        self.window = window
        if window is None:
            self.bar.set(0)
            self.info.configure(text="—")
            return
        self.bar.set(window.utilization / 100)
        self.bar.configure(progress_color=color_for(window.utilization))
        self.refresh_countdown()

    def refresh_countdown(self):
        if self.window is None:
            return
        now = datetime.now(timezone.utc)
        cd = format_countdown(self.window.resets_at, now)
        self.info.configure(text=f"%{self.window.utilization:.0f}   ⟳ {cd}")


class UsageApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Claude Kullanımı")
        self.geometry("260x170")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        self.on_refresh = None
        self._data = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Claude Kullanımı", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="↻", width=28, command=self._refresh_clicked).grid(row=0, column=1)

        self.five = _Row(self, "5 saatlik")
        self.five.grid(1)
        self.seven = _Row(self, "Haftalık")
        self.seven.grid(4)

        self.status = ctk.CTkLabel(self, text="yükleniyor…", anchor="w", font=("Segoe UI", 10), text_color="gray")
        self.status.grid(row=7, column=0, sticky="w", padx=10, pady=(2, 6))

    def _refresh_clicked(self):
        if self.on_refresh:
            self.on_refresh()

    def render(self, data: UsageData):
        self._data = data
        self.five.set(data.five_hour)
        self.seven.set(data.seven_day)
        self.status.configure(text=f"güncellendi: {data.fetched_at.astimezone().strftime('%H:%M')}", text_color="gray")

    def render_error(self, err: UsageError):
        self.status.configure(text=err.message, text_color="#e74c3c")

    def tick(self):
        self.five.refresh_countdown()
        self.seven.refresh_countdown()
```

- [ ] **Step 2: Pencereyi elle doğrula (sahte veri ile)**

Geçici olarak dosyanın sonuna ekleyip çalıştır:

```python
if __name__ == "__main__":
    from usage_client import Window
    app = UsageApp()
    app.render(UsageData(
        five_hour=Window(30.0, datetime.now(timezone.utc).replace(microsecond=0)),
        seven_day=Window(71.0, datetime.now(timezone.utc)),
        fetched_at=datetime.now(timezone.utc),
    ))
    app.mainloop()
```

Run: `python app.py`
Expected: Koyu temalı ~260x170 pencere; "5 saatlik" yeşil çubuk %30, "Haftalık" sarı çubuk %71, ↻ butonu, altta "güncellendi: HH:MM". Pencere her zaman üstte.

- [ ] **Step 3: Geçici `__main__` bloğunu sil**

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: CustomTkinter widget penceresi"
```

---

### Task 6: Bağlama, zamanlayıcı ve thread (`main.py`)

**Files:**
- Create: `main.py`

**Interfaces:**
- Consumes: `UsageApp` (app), `fetch_usage`, `UsageData` (usage_client).
- Produces: `main() -> None` çalıştırılabilir giriş noktası. 60 sn'lik otomatik yenileme + ↻ elle yenileme; ağ ayrı thread'de; geri sayım her saniye `tick()` ile.

Bu görev UI/entegrasyondur; otomatik test yok.

- [ ] **Step 1: `main.py` oluştur**

```python
from __future__ import annotations

import threading

from app import UsageApp
from usage_client import UsageData, fetch_usage

REFRESH_MS = 60_000
TICK_MS = 1_000


def main():
    app = UsageApp()

    def apply(result):
        # Ana thread'de çalışır (after ile sıralanır).
        if isinstance(result, UsageData):
            app.render(result)
        else:
            app.render_error(result)

    def do_fetch():
        result = fetch_usage()
        app.after(0, lambda: apply(result))

    def trigger_fetch():
        threading.Thread(target=do_fetch, daemon=True).start()

    def auto_refresh():
        trigger_fetch()
        app.after(REFRESH_MS, auto_refresh)

    def tick():
        app.tick()
        app.after(TICK_MS, tick)

    app.on_refresh = trigger_fetch
    app.after(100, auto_refresh)   # açılışta ilk çekim
    app.after(TICK_MS, tick)       # saniyelik geri sayım
    app.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Uçtan uca elle doğrula**

Run: `python main.py`
Expected: Pencere açılır, ~kısa sürede gerçek veriyle dolar (5 saatlik + haftalık yüzdeler ve geri sayımlar). Geri sayım her saniye ilerler. ↻ butonu anında yeniler. "güncellendi" saati güncellenir. İnternet kesikse önceki veri kalır, durum satırında hata mesajı görünür.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main giriş noktası, 60sn yenileme ve saniyelik geri sayım"
```

- [ ] **Step 4: Tüm testleri son kez çalıştır**

Run: `python -m pytest -v`
Expected: PASS (17 test)

---

## Kullanım (README için not — opsiyonel)

```bash
python -m pip install -r requirements.txt
python main.py
```

## Self-Review Notu

Bu plan spec'in her bölümünü karşılar: veri kaynağı/parse (Task 1–3), hata yönetimi (Task 3 + app.render_error), biçimlendirme ve renk (Task 4), görünüm (Task 5), zamanlama/thread/geri sayım (Task 6). Kapsam dışı öğeler (ekstra kredi, tray, token yenileme) dahil edilmedi.

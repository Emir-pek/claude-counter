from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class NoCredentialsError(Exception):
    pass


def read_token(path: str = CREDENTIALS_PATH) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise NoCredentialsError(str(e))
    try:
        return data["claudeAiOauth"]["accessToken"]
    except (KeyError, TypeError):
        raise NoCredentialsError("accessToken bulunamadı")


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


@dataclass
class UsageError:
    kind: str
    message: str
    # Yalnızca kind == "rate_limited" için dolu olabilir: sunucunun
    # kaç saniye beklememizi istediği. Yoksa None, zamanlayıcı kendi
    # geri çekilmesini uygular.
    retry_after: float | None = None


def _header(headers, name: str):
    """Retry-After'ı büyük/küçük harf farkına takılmadan okur.

    Gerçek yanıtta headers case-insensitive bir HTTPMessage, ama
    HTTPError düz bir dict ile de kurulabiliyor; o durumda .get()
    harfe duyarlı olur ve başlığı sessizce kaçırırız.
    """
    if headers is None:
        return None
    try:
        items = headers.items()
    except AttributeError:
        return None
    target = name.lower()
    for key, value in items:
        if str(key).lower() == target:
            return value
    return None


def parse_retry_after(value, now: datetime | None = None) -> float | None:
    """RFC 7231 Retry-After: ya delta-saniye ya da HTTP-date."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return max(0.0, float(int(text)))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    # Geçmiş bir tarih negatif vermemeli: negatif gecikme "hemen tekrar
    # dene" demek olurdu ve bizi doğrudan limite geri sokar.
    return max(0.0, (when - now).total_seconds())


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
            # Mesajlar durum satırına sığacak kadar kısa tutuluyor;
            # widget dar ve kırpılan bir uyarı işe yaramaz.
            return UsageError("unauthorized", "Oturum doldu — giriş yapın")
        if e.code == 429:
            # Ayrı bir kind: zamanlayıcının geri çekilmesi gereken tek durum.
            return UsageError("rate_limited", "İstek sınırı — bekleniyor",
                              retry_after=parse_retry_after(_header(e.headers, "Retry-After")))
        return UsageError("network", f"Sunucu hatası ({e.code})")
    except (urllib.error.URLError, TimeoutError, OSError):
        return UsageError("network", "Bağlantı yok")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return UsageError("bad_response", "Beklenmedik yanıt")
    if not isinstance(payload, dict):
        return UsageError("bad_response", "Beklenmedik yanıt")
    return parse_usage(payload, datetime.now(timezone.utc))

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

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
    if not isinstance(payload, dict):
        return UsageError("bad_response", "Beklenmedik yanıt")
    return parse_usage(payload, datetime.now(timezone.utc))

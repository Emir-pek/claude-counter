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

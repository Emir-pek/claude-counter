from __future__ import annotations

from datetime import datetime

GREEN = "#2ecc71"
YELLOW = "#f1c40f"
RED = "#e74c3c"

# weekday() sırası: 0 = Pazartesi. strftime("%a") kullanılmıyor,
# çünkü sistem diline bağlı ve bu makinede "Fri" döndürüyor.
DAY_NAMES = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


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

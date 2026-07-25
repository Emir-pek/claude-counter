from usage_client import UsageData, UsageError
from datetime import datetime, timezone
from scheduling import BASE_INTERVAL_MS, MAX_BACKOFF_MS, next_delay_ms


def _ok():
    return UsageData(five_hour=None, seven_day=None, fetched_at=datetime.now(timezone.utc))


def _limited(retry_after=None):
    return UsageError("rate_limited", "sınır", retry_after=retry_after)


def test_success_resets_to_base_interval():
    # Backoff'tan çıkış: tek bir başarılı çekim taban aralığa döndürmeli,
    # yoksa app bir kez 429 yedikten sonra sonsuza dek yavaş kalır.
    assert next_delay_ms(_ok(), MAX_BACKOFF_MS) == BASE_INTERVAL_MS


def test_rate_limited_without_header_backs_off_exponentially():
    assert next_delay_ms(_limited(), BASE_INTERVAL_MS) == BASE_INTERVAL_MS * 2


def test_rate_limited_never_polls_faster_than_base():
    # Açılıştaki ilk çekim 429 alırsa current çok küçüktür (100 ms).
    # İkiye katlamak onu taban aralığın ALTINA indirirdi: 429 yiyince
    # sağlıklı haldekinden daha sık yoklamak tam da hatayı büyütür.
    assert next_delay_ms(_limited(), 100) > BASE_INTERVAL_MS


def test_rate_limited_backoff_is_capped():
    assert next_delay_ms(_limited(), MAX_BACKOFF_MS) == MAX_BACKOFF_MS


def test_longer_retry_after_overrides_backoff():
    # Sunucu bizim hesabımızdan uzun beklememizi istiyorsa sözü geçer.
    assert next_delay_ms(_limited(retry_after=1_200.0), BASE_INTERVAL_MS) == 1_201_000


def test_shorter_retry_after_does_not_speed_us_up():
    # 90 sn'de tekrar denemeye iznimiz olması, denememiz gerektiği anlamına
    # gelmez; taban aralık zaten daha yavaş ve daha güvenli.
    assert next_delay_ms(_limited(retry_after=90.0), BASE_INTERVAL_MS) == BASE_INTERVAL_MS * 2


def test_rate_limited_retry_after_is_capped():
    assert next_delay_ms(_limited(retry_after=99_999.0), BASE_INTERVAL_MS) == MAX_BACKOFF_MS


def test_rate_limited_retry_after_zero_still_waits():
    # retry_after=0 yanlışlıkla "hemen tekrar dene" olmamalı — kendini
    # tekrar limite çivilemenin en kısa yolu bu.
    assert next_delay_ms(_limited(retry_after=0.0), BASE_INTERVAL_MS) == BASE_INTERVAL_MS * 2


def test_network_error_keeps_base_interval():
    assert next_delay_ms(UsageError("network", "yok"), MAX_BACKOFF_MS) == BASE_INTERVAL_MS


def test_unauthorized_keeps_base_interval():
    assert next_delay_ms(UsageError("unauthorized", "giriş"), BASE_INTERVAL_MS) == BASE_INTERVAL_MS

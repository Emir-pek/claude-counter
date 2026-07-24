from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from formatting import format_reset_time
from usage_client import Window


@pytest.fixture(scope="module")
def root():
    r = app_module.ctk.CTk()
    r.withdraw()  # test sırasında pencere görünmesin
    yield r
    r.destroy()


def _win(hours_ahead: float, util: float = 42.0) -> Window:
    # Sıfırlanmayı dakika ortasına koy: dakika sınırında (+2sa 0dk 0sn)
    # Windows saat çözünürlüğü yüzünden geri sayım "2s 0dk" ile
    # "1s 59dk" arasında değişebiliyor ve test flaky oluyor.
    return Window(
        utilization=util,
        resets_at=datetime.now(timezone.utc)
        + timedelta(hours=hours_ahead)
        + timedelta(seconds=30),
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


def test_row_day_name_disappears_after_local_midnight(root):
    # Anahtardaki yerel_bugün alanı olmadan bu test kırmızı verir:
    # resets_at değişmeden gece yarısını geçince gün adı düşmeli.
    local_tz = datetime.now().astimezone().tzinfo
    # Bir sonraki yerel gece yarısı: her iki 'now' değeri de bunun
    # çevresinde, resets_at'tan önce kalacak şekilde seçiliyor.
    boundary = datetime.now(local_tz).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    resets_at = boundary + timedelta(hours=1)  # yarın yerel 01:00
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5 saatlik")
    row.window = window  # set() yerine: gerçek 'now' önbelleğe karışmasın

    now_before_midnight = boundary - timedelta(minutes=10)  # bugün 23:50
    now_after_midnight = boundary + timedelta(minutes=30)  # yarın 00:30

    expected_before = format_reset_time(resets_at, now_before_midnight)
    expected_after = format_reset_time(resets_at, now_after_midnight)
    # Sağlık kontrolü: senaryo gerçekten gün adının kaybolmasını sınıyor.
    assert " " in expected_before  # "Cmt 01:00" gibi: gün adı + saat
    assert " " not in expected_after  # yalnızca "01:00"

    row.refresh_countdown(now=now_before_midnight)
    assert row.info.cget("text").endswith(f" · {expected_before}")

    row.refresh_countdown(now=now_after_midnight)
    assert row.info.cget("text").endswith(f" · {expected_after}")


def test_row_reset_time_disappears_when_expired(root):
    # Anahtardaki süresi_doldu alanı olmadan bu test kırmızı verir:
    # resets_at ve yerel_bugün değişmeden süre dolunca saat metni
    # düşmeli, aksi halde "⟳ yenilendi · 12:00" gibi çelişkili bir
    # satır oluşur.
    local_tz = datetime.now().astimezone().tzinfo
    anchor = datetime.now(local_tz).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    resets_at = anchor
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5 saatlik")
    row.window = window  # set() yerine: gerçek 'now' önbelleğe karışmasın

    now_before = anchor - timedelta(minutes=5)
    now_after = anchor + timedelta(minutes=5)
    assert now_before.date() == now_after.date()  # yerel gün aynı kalmalı

    row.refresh_countdown(now=now_before)
    text_before = row.info.cget("text")
    assert " · " in text_before

    row.refresh_countdown(now=now_after)
    text_after = row.info.cget("text")
    assert "yenilendi" in text_after
    assert " · " not in text_after


def test_row_format_reset_time_called_once_per_cycle(root):
    # Önbelleğin asıl amacı: anahtar (resets_at, yerel_gün, süresi_doldu)
    # değişmediği sürece format_reset_time saniyede bir değil, döngü
    # başına yalnızca bir kez çağrılmalı. Bu test önbellek isabetini
    # (cache hit) sabitler; yalnızca geçersiz kılmayı değil.
    local_tz = datetime.now().astimezone().tzinfo
    anchor = datetime.now(local_tz).replace(hour=9, minute=0, second=0, microsecond=0)
    resets_at = anchor + timedelta(hours=3)
    window = Window(utilization=42.0, resets_at=resets_at)

    row = app_module._Row(root, "5 saatlik")
    row.window = window  # set() yerine: gerçek 'now' önbelleğe karışmasın

    calls = []
    original = app_module.format_reset_time

    def counting_wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    app_module.format_reset_time = counting_wrapper
    try:
        # Anahtarı değiştirmeyecek şekilde saniye/dakika ilerleyen dört
        # farklı 'now' değeri: resets_at ve yerel gün aynı, süre dolmadı.
        now_values = [
            anchor,
            anchor + timedelta(seconds=30),
            anchor + timedelta(minutes=5),
            anchor + timedelta(hours=1),
            anchor + timedelta(hours=2, minutes=50),
        ]
        for now in now_values:
            row.refresh_countdown(now=now)
    finally:
        app_module.format_reset_time = original

    assert len(calls) == 1

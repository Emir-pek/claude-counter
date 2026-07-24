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

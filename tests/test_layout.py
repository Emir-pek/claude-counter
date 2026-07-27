import io
import json
import tempfile
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from usage_client import UsageData, Window, fetch_usage


@pytest.fixture(scope="module")
def widget():
    w = app_module.UsageApp()
    w.withdraw()  # test sırasında pencere görünmesin
    yield w
    w.destroy()


def _fill(widget):
    """En geniş gerçekçi içerikle doldurur.

    Sıfırlanma yerel gece yarısının ötesine konuyor: geri sayımın yanına
    gün adı da eklenir ("Sal 01:00"), yani en uzun hâli ölçülür.
    """
    now = datetime.now(timezone.utc)
    midnight = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    widget.render(UsageData(
        five_hour=Window(utilization=100.0,
                         resets_at=(midnight + timedelta(hours=1)).astimezone(timezone.utc)),
        seven_day=Window(utilization=100.0,
                         resets_at=(midnight + timedelta(days=6, hours=23)).astimezone(timezone.utc)),
        fetched_at=now,
    ))
    widget.update_idletasks()


def _size(widget):
    """Pencerenin gerçek piksel ölçüsü (genişlik, yükseklik).

    CTk.geometry() okurken DPI ölçeğini geri çeviriyor, winfo_req* ise
    ölçekli piksel veriyor. İkisi karşılaştırılacaksa ham değer gerekir;
    wm_geometry CTk tarafından sarılmadığı için ham kalıyor.
    """
    width, height = widget.wm_geometry().split("+")[0].split("x")
    return int(width), int(height)


def _label_texts(widget):
    found = []

    def walk(parent):
        for child in parent.winfo_children():
            try:
                found.append(child.cget("text"))
            except Exception:
                pass
            walk(child)

    walk(widget)
    return found


def _credentials_file():
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                    encoding="utf-8")
    json.dump({"claudeAiOauth": {"accessToken": "t"}}, f)
    f.close()
    return f.name


def _raises(exc):
    def opener(*_args, **_kwargs):
        raise exc
    return opener


def _returns(payload: bytes):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    def opener(*_args, **_kwargs):
        return _Resp(payload)
    return opener


def _all_error_messages():
    """fetch_usage'ın üretebildiği bütün hata metinleri.

    Metinler kopyalanmıyor, üretildikleri yerden okunuyor; usage_client'ta
    uzayan bir mesaj bu testi kırsın diye.
    """
    token = _credentials_file()
    results = [
        fetch_usage(path="boyle-bir-dosya-yok.json"),
        fetch_usage(path=token, opener=_returns(b"bozuk")),
        fetch_usage(path=token, opener=_raises(urllib.error.URLError("yok"))),
    ]
    for code in (401, 429, 503):
        error = urllib.error.HTTPError("u", code, "err", {}, None)
        results.append(fetch_usage(path=token, opener=_raises(error)))
    return [r.message for r in results]


def test_window_title_is_not_repeated_inside_the_window(widget):
    # Başlık çubuğu zaten "Claude Kullanımı" yazıyor; aynı metni pencere
    # içinde ikinci kez göstermek bütün bir satırı harcıyordu.
    assert widget.title() == "Claude Kullanımı"
    assert "Claude Kullanımı" not in _label_texts(widget)


def test_status_line_sits_in_the_header(widget):
    # Silinen başlığın yerini "güncellendi: 18:04" aldı, alt satır kalktı.
    assert widget.status.master is widget.header
    assert int(widget.status.grid_info()["row"]) == 0


def test_window_height_fits_its_content_without_slack(widget):
    # Çift yönlü koruma: sabit yükseklik içerik büyüyünce sessizce
    # kırpmamalı, küçülünce de şişik kalmamalı. Yalnızca yükseklik
    # sınanıyor; genişlikte winfo_reqwidth gerçeği söylemiyor, çünkü
    # esneyen label'lar (sticky="ew") istedikleri yeri talep etmiyor.
    _fill(widget)
    _width, height = _size(widget)
    assert height >= widget.winfo_reqheight()
    assert height - widget.winfo_reqheight() <= 16


def test_window_is_smaller_than_the_old_layout(widget):
    # v1.1.0'daki 260x310'a geri kaymayı yakalar.
    width, height = _size(widget)
    assert width < 260
    assert height < 260


def test_error_messages_fit_the_status_line(widget):
    # status hem saati hem hata mesajını gösteriyor. Header'da yenile
    # düğmesiyle yan yana durduğu için yer daraldı; mesaj kırpılırsa
    # kullanıcı ne yapması gerektiğini okuyamaz.
    #
    # Metin genişliği label'ın kendisinden okunuyor: CTk font boyutunu
    # punto değil piksel olarak uyguluyor, dışarıdan kurulan bir
    # tkfont.Font başka bir şey ölçer.
    width, _height = _size(widget)
    room = (width - 2 * app_module.PAD_WINDOW
            - widget.refresh.winfo_reqwidth() - app_module.PAD_CARD)

    original = widget.status.cget("text")
    try:
        for message in _all_error_messages() + [original]:
            widget.status.configure(text=message)
            widget.update_idletasks()
            assert widget.status.winfo_reqwidth() <= room, message
    finally:
        widget.status.configure(text=original)


def test_countdown_fits_its_column(widget):
    # Geri sayım kartın en geniş metni; yüzde sütunundan artan yere
    # sığmazsa saat sessizce kırpılır.
    _fill(widget)
    # Sağlık kontrolü: ölçüm gerçekten yerleşmiş bir kartı görüyor.
    # Boş bir label 1px döner ve testi sessizce anlamsızlaştırırdı.
    assert widget.five.pct.cget("text") == "%100"
    assert widget.five.card.winfo_width() > 100

    room = (widget.five.card.winfo_width() - widget.five.pct.winfo_reqwidth()
            - 10 - 6 - 10)  # kart iç boşlukları
    for row in (widget.five, widget.seven):
        assert row.info.winfo_reqwidth() <= room, row.info.cget("text")

from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from formatting import GREEN, RED
from usage_client import UsageData, Window


@pytest.fixture(scope="module")
def widget():
    w = app_module.UsageApp()
    w.withdraw()
    yield w
    w.destroy()


def _stop_ring(widget):
    if widget._ring_after is not None:
        widget.after_cancel(widget._ring_after)
        widget._ring_after = None


def test_dot_has_one_canvas_item_when_calm(widget):
    widget._level = GREEN
    widget._redraw_dot()
    assert len(widget.dot_canvas.find_all()) == 1


def test_dot_gets_a_second_item_for_the_ring(widget):
    # glow=0 burada: yalnızca halkanın kendi öğesini eklediğini sınıyoruz,
    # glow halosunun eklediği üçüncü öğeyle karışmasın.
    widget._redraw_dot(ring_scale=1.2, ring_visible=True, glow=0.0)
    try:
        assert len(widget.dot_canvas.find_all()) == 2
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_dot_gets_a_third_item_for_the_glow_halo(widget):
    # Ring + glow halosu + nokta = 3 ayrı canvas öğesi. Halo, noktanın kendi
    # outline'ını kalınlaştırmak yerine arkasına ayrı bir oval çizer (bkz.
    # _redraw_dot) — bu yüzden glow > 0 iken öğe sayısı 2 değil 3 olmalı.
    widget._redraw_dot(ring_scale=1.2, ring_visible=True, glow=0.5)
    try:
        assert len(widget.dot_canvas.find_all()) == 3
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_glow_halo_alone_adds_one_item_without_the_ring(widget):
    widget._redraw_dot(glow=0.5)
    try:
        assert len(widget.dot_canvas.find_all()) == 2
    finally:
        widget._level = GREEN
        widget._redraw_dot()


def test_update_dot_starts_the_ring_timer_when_critical(widget):
    widget._level = GREEN
    widget._update_dot()
    assert widget._ring_after is None

    widget._level = RED
    widget._update_dot()
    try:
        assert widget._ring_after is not None
    finally:
        _stop_ring(widget)
        widget._level = GREEN
        widget._redraw_dot()


def test_update_dot_stops_the_ring_timer_when_no_longer_critical(widget):
    widget._level = RED
    widget._update_dot()
    assert widget._ring_after is not None

    widget._level = GREEN
    widget._update_dot()
    assert widget._ring_after is None


def test_dot_canvas_lives_in_a_separate_toplevel_from_the_card(widget):
    # Kök nedeni bu: nokta artık kartın ÇOCUĞU değil. Kartın kendi
    # penceresi win_theme.set_rounded_region ile yuvarlak köşeli bir Win32
    # bölgeye kırpılıyor, çocuk widget'lar bu kırpmanın asla dışına
    # taşamaz. dot_canvas'ın winfo_toplevel()'i artık kartın kendisi (widget)
    # değil, ayrı bir DotOverlay Toplevel'i olmalı.
    assert isinstance(widget.dot_overlay, app_module.DotOverlay)
    assert widget.dot_canvas is widget.dot_overlay.canvas
    assert widget.dot_canvas.winfo_toplevel() is widget.dot_overlay
    assert widget.dot_canvas.winfo_toplevel() is not widget


def test_render_with_high_utilization_wires_up_the_ring_end_to_end(widget):
    # render() -> worst_color -> _level -> _update_dot -> ring zincirinin
    # her parçası ayrı ayrı sınanıyordu (worst_color izole, _update_dot
    # elle atanmış _level ile); gerçek render() ile uçtan uca çalıştığını
    # doğrulayan hiçbir test yoktu.
    now = datetime.now(timezone.utc)
    data = UsageData(
        five_hour=Window(utilization=90.0, resets_at=now + timedelta(hours=1)),
        seven_day=Window(utilization=10.0, resets_at=now + timedelta(days=6)),
        fetched_at=now,
    )
    try:
        widget.render(data)
        assert widget._level == RED
        assert widget._ring_after is not None
    finally:
        _stop_ring(widget)
        widget._level = GREEN
        widget._redraw_dot()


# --------------------------------------------------------------------------
# DotOverlay geometrisi — gerçek ekran koordinatlarına karşı, görsel olarak
# doğrulanamayan (bu ortamda göremiyoruz) ama geometrik bir gerçek olarak
# doğrulanabilen bir iddia: "overlay çoğunlukla kartın kendi dikdörtgeninin
# DIŞINDA duruyor mu?" — test_app_row.py'nin work_area_rect sahtesi kalıbının
# aynısı: pencere gerçekten haritalı kalıyor (withdraw sonrası
# overrideredirect pencereler yeniden boyutlanmıyor), kullanıcı hiçbir zaman
# gerçek bir pencere görmüyor çünkü sahte çalışma alanı ekranın çok dışında.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def geo_widget():
    # NOT: test_app_row.py'nin kullandığı 100_000 ofseti burada
    # kullanılmadı — Windows'ta Tk'nin winfo_rootx()/rooty() döndürdüğü
    # koordinatlar imzalı 16 bit'e sığıyor (±32767); 100_000 gibi bir
    # değer bu sınırı aşıp 32767'ye kenetleniyor ve pozisyon ölçümlerini
    # anlamsız kılıyor (bu dosyadaki geometrik testler gerçek piksel
    # konumlarını karşılaştırıyor, yalnızca genişlik değil). 9000 hem bu
    # sınırın hem de gerçekçi ekran çözünürlüklerinin (çok monitörlü
    # kurulumlar dahil, tipik olarak birkaç bin piksel) rahatça altında
    # kalıyor.
    original_work_area_rect = app_module.work_area_rect
    app_module.work_area_rect = lambda: (9000, 9000, 400, 300)
    w = app_module.UsageApp()
    w.update()
    try:
        yield w
    finally:
        w.destroy()
        app_module.work_area_rect = original_work_area_rect


def _rect_overlap_area(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy


def _card_rect(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_width(), widget.winfo_height())


def _overlay_rect(widget):
    ov = widget.dot_overlay
    return (ov.winfo_rootx(), ov.winfo_rooty(),
            ov.winfo_width(), ov.winfo_height())


def test_dot_overlay_sits_mostly_outside_the_idle_cards_rect(geo_widget):
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    card = _card_rect(geo_widget)
    overlay = _overlay_rect(geo_widget)

    overlap = _rect_overlap_area(card, overlay)
    overlay_area = overlay[2] * overlay[3]
    assert overlay_area > 0
    outside_fraction = 1.0 - (overlap / overlay_area)

    # Eski (kartın çocuğu olan) tasarımda overlay TAMAMEN kartın içindeydi
    # (outside_fraction == 0). Yeni tasarımda çoğunlukla dışında olmalı.
    assert outside_fraction > 0.5, (
        f"overlay {overlay} kartın {card} içine gömülü kalmış "
        f"(yalnızca %{outside_fraction*100:.1f} dışarıda)"
    )

    # Overlay'in kendisi kartın sağ kenarının sağına VE üst kenarının
    # üstüne taşıyor olmalı — yalnızca "çoğunlukla dışarıda" değil,
    # gerçekten her iki eksende de kenarları aşıyor.
    card_x, card_y, card_w, card_h = card
    overlay_x, overlay_y, overlay_w, overlay_h = overlay
    assert overlay_x + overlay_w > card_x + card_w, "overlay sağ kenarı aşmıyor"
    assert overlay_y < card_y, "overlay üst kenarı aşmıyor"


def test_dot_drawn_extent_overlaps_the_cards_corner(geo_widget):
    # Finding 2 (user-qa-fix-report.md): "overlay kutusunun %90'ı kartın
    # dışında" yanıltıcı bir metrik, çünkü DOT_CANVAS_SIZE'ın çoğu saydam
    # dolgu. Asıl soru: noktanın kendi ÇİZİLİ pikselleri (_redraw_dot'un
    # DOT_CANVAS_SIZE/2 merkezine dot_r yarıçapıyla çizdiği daire) kartla
    # gerçekten örtüşüyor mu? Eski (bias=6/148) geometriyle bu test başarısız
    # olurdu — nokta merkezi karttan ~8.5px uzaktaydı, dot_r=4'ün çok
    # ötesinde.
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    card_x, card_y, card_w, card_h = _card_rect(geo_widget)
    overlay_x, overlay_y, overlay_w, overlay_h = _overlay_rect(geo_widget)

    dot_cx = overlay_x + overlay_w / 2
    dot_cy = overlay_y + overlay_h / 2
    dot_r = app_module.DOT_SIZE / 2

    nearest_x = min(max(dot_cx, card_x), card_x + card_w)
    nearest_y = min(max(dot_cy, card_y), card_y + card_h)
    dist = ((dot_cx - nearest_x) ** 2 + (dot_cy - nearest_y) ** 2) ** 0.5

    assert dist <= dot_r, (
        f"nokta merkezi ({dot_cx},{dot_cy}) yarıçap {dot_r} ile kartın "
        f"({card_x},{card_y},{card_w},{card_h}) köşesini örtmüyor "
        f"(mesafe {dist:.2f}px)"
    )


def test_dot_overlay_tracks_the_card_when_it_expands(geo_widget):
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    idle_overlay = _overlay_rect(geo_widget)

    geo_widget._set_expanded(True, animate=False)
    geo_widget.update()
    try:
        expanded_overlay = _overlay_rect(geo_widget)
        expanded_card = _card_rect(geo_widget)

        # Kart genişleyince sağ kenarı sağa kayar (bkz. corner_position:
        # sağ-alt köşeye sabitli, kart genişledikçe sol kenar sola açılır,
        # sağ kenar sabit KALMAZ çünkü genişlik CARD_W_IDLE -> CARD_W_EXPANDED
        # değişir ama x hep work_area'nın sağ kenarına göre yeniden
        # hesaplanır) — asıl doğrulanması gereken, overlay'in duruk kalmayıp
        # kartla birlikte gerçekten hareket ettiği.
        assert expanded_overlay != idle_overlay, "overlay kart genişlerken sabit kaldı"

        overlap = _rect_overlap_area(expanded_card, expanded_overlay)
        overlay_area = expanded_overlay[2] * expanded_overlay[3]
        outside_fraction = 1.0 - (overlap / overlay_area)
        assert outside_fraction > 0.5
    finally:
        geo_widget._set_expanded(False, animate=False)
        geo_widget.update()


def test_close_hides_the_dot_overlay(geo_widget):
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    try:
        geo_widget._on_close_click()
        assert geo_widget.dot_overlay.state() == "withdrawn"
    finally:
        geo_widget.reopen()
        geo_widget.update()


def test_reopen_shows_the_dot_overlay_again(geo_widget):
    geo_widget._on_close_click()
    assert geo_widget.dot_overlay.state() == "withdrawn"
    geo_widget.reopen()
    geo_widget.update()
    try:
        assert geo_widget.dot_overlay.state() != "withdrawn"
    finally:
        geo_widget._set_expanded(False, animate=False)


def test_dot_overlay_survives_a_normal_hover_cycle(geo_widget):
    # Kritik regresyon (Finding 1, user-qa-fix-report.md): _Row.set_expanded
    # genişlerken/daralırken countdown.grid()/grid_remove() ile çocuk
    # widget'ı haritaya alıp kaldırıyor. DotOverlay._on_app_unmap/_on_app_map
    # guard'sız hâliyle bunu ana pencerenin kendi <Unmap>/<Map>'i sanıp
    # overlay'i her idle'a dönüşte withdraw ediyordu — nokta varsayılan
    # dinlenme durumunda hep görünmezdi. .state() kullanılıyor (gerçek
    # Tk haritalanma durumu), winfo_rootx/vb DEĞİL: withdraw edilmiş bir
    # overrideredirect pencere geometri sorgularında son bilinen değerleri
    # döndürmeye devam eder, bu yüzden görünürlüğü ayırt etmezler.
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    try:
        assert geo_widget.dot_overlay.state() != "withdrawn", (
            "başlangıçta (idle) nokta zaten gizli"
        )

        geo_widget._set_expanded(True, animate=False)
        geo_widget.update()
        assert geo_widget.dot_overlay.state() != "withdrawn", (
            "genişlerken nokta gizlendi"
        )

        geo_widget._set_expanded(False, animate=False)
        geo_widget.update()
        # Asıl kritik iddia: hover'dan idle'a DÖNÜNCE nokta hâlâ görünür
        # olmalı. Eski (guard'sız) kodda tam burada withdrawn olurdu.
        assert geo_widget.dot_overlay.state() != "withdrawn", (
            "idle'a dönünce nokta gizlendi — bu Finding 1'in tam kendisi"
        )
    finally:
        geo_widget._set_expanded(False, animate=False)
        geo_widget.update()


def test_a_raw_withdraw_on_the_card_also_hides_the_dot_overlay(geo_widget):
    # Kök nedeni doğrulanan regresyon: dot_canvas eskiden kartın ÇOCUĞUYDU,
    # bu yüzden kartın kendi penceresini (self, yani UsageApp/root) doğrudan
    # .withdraw() ile gizlemek her zaman noktayı da otomatik gizlerdi (Tk
    # bir pencereyi withdraw ettiğinde çocukları da haritadan kalkar).
    # dot_overlay artık AYRI bir Toplevel olduğundan, Tk bunu ana pencere
    # withdraw edildiğinde OTOMATİK gizlemez (crab_overlay.py'nin
    # <Unmap>/<Map> bağlaması tam olarak bu yüzden var). _on_close_click
    # DIŞINDA bir yoldan (burada: doğrudan widget.withdraw() çağrısı, tıpkı
    # bazı test fixture'larının yaptığı gibi) kart gizlenirse bile overlay
    # ekranda kartsız asılı kalmamalı.
    geo_widget._set_expanded(False, animate=False)
    geo_widget.update()
    try:
        geo_widget.withdraw()  # _on_close_click'i BİLEREK atlıyor
        geo_widget.update()
        assert geo_widget.dot_overlay.state() == "withdrawn"
    finally:
        geo_widget.deiconify()
        geo_widget.update()
        assert geo_widget.dot_overlay.state() != "withdrawn"

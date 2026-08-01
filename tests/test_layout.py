from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from usage_client import UsageData, UsageError, Window


@pytest.fixture(scope="module")
def widget():
    # widget.withdraw() gizler ama Windows'ta bu Tk derlemesinde withdraw
    # edilmiş bir overrideredirect penceresi bir daha asla yeniden
    # boyutlanmıyor (yalnızca konum güncelleniyor) — Task 6'nın tween/hover
    # testleri gerçek bir _set_expanded sonrası genişliği doğrulamak zorunda
    # olduğu için bu artık işe yaramıyor. Bunun yerine pencereyi haritalı
    # (mapped) tutup work_area_rect'i ekranın çok dışına sahte bir alana
    # yönlendiriyoruz: yeniden boyutlanma normal çalışıyor, kullanıcı hiçbir
    # zaman gerçek bir pencere görmüyor.
    original_work_area_rect = app_module.work_area_rect
    app_module.work_area_rect = lambda: (100_000, 100_000, 400, 300)
    w = app_module.UsageApp()
    w.update()
    try:
        yield w
    finally:
        w.destroy()
        app_module.work_area_rect = original_work_area_rect


def _fill(widget, five=100.0, seven=100.0):
    now = datetime.now(timezone.utc)
    midnight = datetime.now().astimezone().replace(
        hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    widget.render(UsageData(
        five_hour=Window(utilization=five,
                         resets_at=(midnight + timedelta(hours=1)).astimezone(timezone.utc)),
        seven_day=Window(utilization=seven,
                         resets_at=(midnight + timedelta(days=6, hours=23)).astimezone(timezone.utc)),
        fetched_at=now,
    ))
    widget.update_idletasks()


def _width(widget):
    return int(widget.wm_geometry().split("+")[0].split("x")[0])


def test_window_has_no_native_titlebar(widget):
    assert widget.overrideredirect()


def test_idle_card_is_148_wide(widget):
    assert _width(widget) == app_module.CARD_W_IDLE


def test_idle_opacity_matches_the_configured_default(widget):
    assert widget.attributes("-alpha") == pytest.approx(app_module.IDLE_OPACITY)


def test_header_and_countdowns_are_hidden_while_idle(widget):
    assert widget.header.grid_info() == {}
    assert widget.five.countdown.grid_info() == {}
    assert widget.seven.countdown.grid_info() == {}


def test_row_labels_are_short_turkish_abbreviations(widget):
    assert widget.five.label.cget("text") == "5s"
    assert widget.seven.label.cget("text") == "7g"


def test_render_updates_both_rows(widget):
    _fill(widget)
    assert widget.five.pct.cget("text") == "100%"
    assert widget.seven.pct.cget("text") == "100%"


def test_render_error_sets_the_status_line_but_only_shows_it_expanded(widget):
    widget.render_error(UsageError("network", "sunucuya ulaşılamadı"))
    assert widget._status_text == "sunucuya ulaşılamadı"
    assert widget.status_label.grid_info() == {}  # idle: gizli


def test_rate_limited_error_uses_the_spec_copy(widget):
    widget.render_error(UsageError("rate_limited", "429"))
    assert widget._status_text == "Sınıra takıldı — yeniden deneniyor"
    assert widget._status_color == app_module.COLORS["bar_mid"]


def test_render_clears_the_status_line(widget):
    widget.render_error(UsageError("network", "hata"))
    _fill(widget)
    assert widget._status_text == ""


def test_window_is_smaller_than_the_old_decorated_layout(widget):
    assert app_module.CARD_W_IDLE < 260
    assert app_module.CARD_W_EXPANDED < 260


def test_snap_to_survives_a_win32_failure(widget, monkeypatch):
    def _boom(_window):
        raise OSError("GetParent failed")

    monkeypatch.setattr(app_module, "frame_hwnd", _boom)
    widget._snap_to(app_module.CARD_W_IDLE, 100, app_module.IDLE_OPACITY)


def test_expanding_reveals_header_and_countdowns(widget):
    widget._set_expanded(True, animate=False)
    try:
        assert widget.header.grid_info() != {}
        assert widget.five.countdown.grid_info() != {}
        assert widget.seven.countdown.grid_info() != {}
        assert _width(widget) == app_module.CARD_W_EXPANDED
        assert widget.attributes("-alpha") == pytest.approx(1.0)
    finally:
        widget._set_expanded(False, animate=False)


def test_expanding_grows_the_bars(widget):
    widget._set_expanded(True, animate=False)
    try:
        assert widget.five.bar.cget("height") == app_module.BAR_H_EXPANDED
    finally:
        widget._set_expanded(False, animate=False)
    assert widget.five.bar.cget("height") == app_module.BAR_H_IDLE


def test_poll_hover_expands_when_pointer_is_inside(widget):
    widget._set_expanded(False, animate=False)
    widget._hovered = False
    original = widget.winfo_pointerxy
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    widget.winfo_pointerxy = lambda: (x + 5, y + 5)  # kartın içi
    try:
        widget._poll_hover_once()
        assert widget._hovered is True
        assert widget._expanded is True
    finally:
        widget.winfo_pointerxy = original
        widget._set_expanded(False, animate=False)


def test_poll_hover_collapses_when_pointer_leaves(widget):
    widget._set_expanded(True, animate=False)
    widget._hovered = True
    original = widget.winfo_pointerxy
    widget.winfo_pointerxy = lambda: (-500, -500)  # kartın dışı
    try:
        widget._poll_hover_once()
        assert widget._hovered is False
        assert widget._expanded is False
    finally:
        widget.winfo_pointerxy = original
        widget._set_expanded(False, animate=False)


def test_instant_snap_cancels_a_pending_tween(widget):
    # Bir tween ortasında animate=False ile anlık bir snap gelirse, tween'in
    # zaten zamanlanmış after() adımları sessizce askıda kalmamalı — devreye
    # girdiklerinde eski (artık geçersiz) hedefe doğru sürüklemeye
    # başlamamalılar. self.after()'ı yakalayıp bu bekleyen adımı elle
    # tetikleyerek deterministik biçimde doğruluyoruz.
    widget._set_expanded(False, animate=False)
    pending = []
    original_after = widget.after

    def capturing_after(delay, callback=None, *args):
        if callback is None:
            return original_after(delay)
        pending.append(callback)
        return "fake-after-id"

    widget.after = capturing_after
    try:
        widget._set_expanded(True, animate=True)  # tween başlar, bir sonraki kare after() ile zamanlanır
        assert pending, "tween en az bir after() adımı zamanlamalıydı"

        widget._set_expanded(False, animate=False)  # anlık snap: bekleyen tween'i geçersiz kılmalı
        assert _width(widget) == app_module.CARD_W_IDLE
        assert widget.attributes("-alpha") == pytest.approx(app_module.IDLE_OPACITY)

        for callback in pending:
            callback()  # tween'in artık öksüz kalan adımını elle tetikle

        # Öksüz adım hiçbir şey yapmamalı: geometri hâlâ anlık snap hedefinde.
        assert _width(widget) == app_module.CARD_W_IDLE
        assert widget.attributes("-alpha") == pytest.approx(app_module.IDLE_OPACITY)
    finally:
        widget.after = original_after
        widget._set_expanded(False, animate=False)


def test_close_hides_the_card_and_shows_the_reopen_tab(widget):
    widget._on_close_click()
    try:
        assert widget.state() == "withdrawn"
        assert widget.reopen_tab.state() != "withdrawn"
    finally:
        widget.reopen()


def test_reopen_restores_the_idle_card(widget):
    widget._on_close_click()
    widget.reopen_tab._on_click()
    assert widget.state() != "withdrawn"
    assert widget.reopen_tab.state() == "withdrawn"
    assert widget._expanded is False


def test_reopen_tab_quit_menu_calls_quit_app(widget, monkeypatch):
    called = []
    monkeypatch.setattr(widget, "quit_app", lambda: called.append(True))
    widget.reopen_tab._menu.invoke(0)
    assert called == [True]


def test_quit_app_cancels_a_pending_ring_timer(widget, monkeypatch):
    # Task 7'nin _ring_after zamanlayıcısı, kritik durumdayken kendini
    # yeniden zamanlar (self.after(RING_TICK_MS, ...)). quit_app() ilk defa
    # gerçekten .destroy() çağıran yol olduğu için, bekleyen bir ring
    # callback'i yok edilmiş pencereye karşı ateşleyip hataya yol açmamalı.
    # Gerçek destroy() paylaşılan modül kapsamlı widget'ı (ve bu süreçteki
    # tek Tk yorumlayıcısını) yok edip sonraki testleri/teardown'ı
    # kıracağından burada no-op'a alınıyor; yalnızca zamanlayıcı iptalinin
    # gerçekleştiğini doğruluyoruz.
    monkeypatch.setattr(widget, "destroy", lambda: None)
    monkeypatch.setattr(widget.reopen_tab, "destroy", lambda: None)
    original_level = widget._level
    try:
        widget._level = app_module.RED
        widget._update_dot()
        assert widget._ring_after is not None
        widget.quit_app()
        assert widget._ring_after is None
    finally:
        widget._level = original_level
        widget._update_dot()

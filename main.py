from __future__ import annotations

import threading

from app import UsageApp
from scheduling import Poller
from usage_client import UsageData, UsageError, fetch_usage

TICK_MS = 1_000


def safe_fetch(fetch=fetch_usage):
    """fetch_usage'ı hiçbir istisnanın dışarı sızmayacağı şekilde sarar.

    Sızan bir istisna çekim thread'ini sonucu postalayamadan öldürür;
    o zaman poller "fetching" durumunda asılı kalır, yeni timer kurulmaz
    ve widget ↻ dahil kalıcı olarak ölür.
    """
    try:
        return fetch()
    except Exception:
        return UsageError("network", "Beklenmedik hata")


def build_apply(app, poller):
    """Sonucu ekrana basar ve her hâlükârda zinciri sürdürür."""

    def apply(result):
        # Ana thread'de çalışır (after ile sıralanır).
        try:
            if isinstance(result, UsageData):
                app.render(result)
            else:
                app.render_error(result)
        finally:
            # Zinciri yeniden kuran tek yer burası: render patlarsa
            # atlanmamalı, yoksa bir daha hiç yoklama yapılmaz.
            # Sıradaki gecikme sonuca göre hesaplanır; sabit aralıkla
            # yeniden kuran eski zamanlayıcı, 429 yendiğinde her denemede
            # kayan pencereyi tazeleyip uygulamayı kalıcı hataya çiviliyordu.
            poller.finished(result)

    return apply


def main():
    app = UsageApp()

    def do_fetch():
        result = safe_fetch()
        app.after(0, lambda: apply(result))

    def start_fetch():
        threading.Thread(target=do_fetch, daemon=True).start()

    def tick():
        app.tick()
        app.after(TICK_MS, tick)

    poller = Poller(app, start_fetch)
    apply = build_apply(app, poller)
    app.on_refresh = poller.manual_request
    poller.start()            # açılışta ilk çekim
    app.after(TICK_MS, tick)  # saniyelik geri sayım
    app.mainloop()


if __name__ == "__main__":
    main()

from __future__ import annotations

import threading

from app import UsageApp
from scheduling import Poller
from usage_client import UsageData, fetch_usage

TICK_MS = 1_000


def main():
    app = UsageApp()

    def apply(result):
        # Ana thread'de çalışır (after ile sıralanır).
        if isinstance(result, UsageData):
            app.render(result)
        else:
            app.render_error(result)
        # Sıradaki çekim sonuca göre planlanır. Sabit aralıkla yeniden
        # kurulan eski zamanlayıcı, 429 yendiğinde her denemede kayan
        # pencereyi tazeleyip uygulamayı kalıcı hataya çiviliyordu.
        poller.finished(result)

    def do_fetch():
        result = fetch_usage()
        app.after(0, lambda: apply(result))

    def start_fetch():
        threading.Thread(target=do_fetch, daemon=True).start()

    def tick():
        app.tick()
        app.after(TICK_MS, tick)

    poller = Poller(app, start_fetch)
    app.on_refresh = poller.request
    poller.start()           # açılışta ilk çekim
    app.after(TICK_MS, tick)  # saniyelik geri sayım
    app.mainloop()


if __name__ == "__main__":
    main()

from __future__ import annotations

import threading

from app import UsageApp
from usage_client import UsageData, fetch_usage

REFRESH_MS = 60_000
TICK_MS = 1_000


def main():
    app = UsageApp()

    def apply(result):
        # Ana thread'de çalışır (after ile sıralanır).
        if isinstance(result, UsageData):
            app.render(result)
        else:
            app.render_error(result)

    def do_fetch():
        result = fetch_usage()
        app.after(0, lambda: apply(result))

    def trigger_fetch():
        threading.Thread(target=do_fetch, daemon=True).start()

    def auto_refresh():
        trigger_fetch()
        app.after(REFRESH_MS, auto_refresh)

    def tick():
        app.tick()
        app.after(TICK_MS, tick)

    app.on_refresh = trigger_fetch
    app.after(100, auto_refresh)   # açılışta ilk çekim
    app.after(TICK_MS, tick)       # saniyelik geri sayım
    app.mainloop()


if __name__ == "__main__":
    main()

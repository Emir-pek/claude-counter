from datetime import datetime, timezone

from scheduling import BASE_INTERVAL_MS, Poller
from usage_client import UsageData, UsageError


class FakeScheduler:
    """Tk'nin after/after_cancel'ı yerine geçen sayılabilir bir sahte."""

    def __init__(self):
        self.timers = {}
        self.cancelled = []
        self._n = 0

    def after(self, ms, cb):
        self._n += 1
        tid = f"t{self._n}"
        self.timers[tid] = (ms, cb)
        return tid

    def after_cancel(self, tid):
        self.cancelled.append(tid)
        self.timers.pop(tid, None)

    def pending(self):
        return list(self.timers)

    def delay(self):
        assert len(self.timers) == 1, f"tam bir timer bekleniyordu: {self.timers}"
        return next(iter(self.timers.values()))[0]

    def fire(self):
        tid = next(iter(self.timers))
        _, cb = self.timers.pop(tid)
        cb()


def _ok():
    return UsageData(five_hour=None, seven_day=None, fetched_at=datetime.now(timezone.utc))


def _limited():
    return UsageError("rate_limited", "sınır")


def _build():
    sched = FakeScheduler()
    calls = []
    poller = Poller(sched, lambda: calls.append(1))
    return sched, calls, poller


def test_start_schedules_exactly_one_timer():
    sched, calls, poller = _build()
    poller.start()
    assert len(sched.pending()) == 1
    assert calls == []


def test_timer_fire_starts_fetch_and_leaves_no_timer():
    # Çekim uçuştayken bekleyen timer olmamalı; olursa istek hızı ikiye katlanır.
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    assert calls == [1]
    assert sched.pending() == []


def test_result_reschedules_the_chain():
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    assert sched.delay() == BASE_INTERVAL_MS


def test_manual_request_while_fetching_is_ignored():
    # ↻'ye üst üste basmak asıl 429 tetikleyicisiydi.
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.request()
    poller.request()
    assert calls == [1]


def test_manual_request_cancels_pending_timer():
    # İptal edilmezse eski timer da ateşlenir ve arka arkaya iki istek gider.
    sched, calls, poller = _build()
    poller.start()
    poller.request()
    assert calls == [1]
    assert sched.pending() == []


def test_fired_timer_is_never_cancelled():
    # Ateşlenmiş bir id'yi after_cancel'a vermek Tk'de TclError riski.
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    assert sched.cancelled == []


def test_rate_limited_result_backs_off_instead_of_base():
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_limited())
    assert sched.delay() > BASE_INTERVAL_MS


def test_repeated_rate_limits_keep_growing_the_delay():
    sched, calls, poller = _build()
    poller.start()
    delays = []
    for _ in range(3):
        sched.fire()
        poller.finished(_limited())
        delays.append(sched.delay())
    assert delays == sorted(delays) and delays[0] < delays[-1]


def test_success_after_backoff_returns_to_base():
    sched, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_limited())
    sched.fire()
    poller.finished(_ok())
    assert sched.delay() == BASE_INTERVAL_MS


def test_first_delay_is_short_so_window_fills_immediately():
    sched, calls, poller = _build()
    poller.start()
    assert sched.delay() < BASE_INTERVAL_MS

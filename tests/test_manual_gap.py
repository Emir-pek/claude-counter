from datetime import datetime, timezone

from scheduling import MANUAL_MIN_GAP_MS, Poller
from usage_client import UsageData

from tests.test_poller import FakeScheduler


class FakeClock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now

    def advance_ms(self, ms):
        self.now += ms / 1000


def _ok():
    return UsageData(five_hour=None, seven_day=None, fetched_at=datetime.now(timezone.utc))


def _build():
    sched, clock, calls = FakeScheduler(), FakeClock(), []
    poller = Poller(sched, lambda: calls.append(1), clock=clock)
    return sched, clock, calls, poller


def test_first_manual_click_is_allowed():
    sched, clock, calls, poller = _build()
    poller.start()
    assert poller.manual_request() is True
    assert calls == [1]


def test_manual_click_right_after_a_fetch_is_refused():
    # Amber "İstek sınırı" görünce kullanıcının ilk refleksi ↻'ye
    # basmak; eşzamanlılık koruması ard arda tıklamaları durdurmuyor.
    sched, clock, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    assert poller.manual_request() is False
    assert calls == [1]


def test_manual_click_allowed_once_the_gap_elapses():
    sched, clock, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    clock.advance_ms(MANUAL_MIN_GAP_MS + 1)
    assert poller.manual_request() is True
    assert calls == [1, 1]


def test_twenty_rapid_clicks_produce_no_extra_requests():
    sched, clock, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    for _ in range(20):
        poller.manual_request()
    assert calls == [1]


def test_timer_driven_fetch_ignores_the_manual_gap():
    # Boşluk kuralı yalnızca ↻ için; zamanlayıcı gecikmesi zaten taban
    # aralık kadar, onu da geciktirmek yoklamayı durdururdu.
    sched, clock, calls, poller = _build()
    poller.start()
    sched.fire()
    poller.finished(_ok())
    sched.fire()
    assert calls == [1, 1]

"""Bir sonraki çekimin ne zaman yapılacağına karar veren saf mantık.

Tk'den ve ağdan bağımsız tutuldu: main.py'deki zamanlayıcı kapanışların
içinde olduğu için doğrudan test edilemiyordu, karar burada test edilebilir
tek bir fonksiyona indirildi.
"""
from __future__ import annotations

import time

from usage_client import UsageError

BASE_INTERVAL_MS = 300_000  # 5 dk — saatte 12 istek, limitin çok altında
MAX_BACKOFF_MS = 1_800_000  # 30 dk tavan
FIRST_FETCH_MS = 100  # açılışta pencere hemen dolsun
MANUAL_MIN_GAP_MS = 20_000  # ↻ tıklamaları arasındaki asgari boşluk


def _clamp(ms: float) -> int:
    # Alt sınır taban aralık: 429 yedikten sonra sağlıklı haldekinden daha
    # sık yoklamak anlamsız olurdu.
    return int(min(MAX_BACKOFF_MS, max(BASE_INTERVAL_MS, ms)))


def next_delay_ms(result, current_ms: int) -> int:
    """Sonuca bakarak bir sonraki çekime kalan süreyi verir.

    Sabit aralıkla yeniden kurulan bir zamanlayıcı 429 yediğinde her
    denemede kayan pencereyi yeniden doldurur ve uygulama kendini kalıcı
    olarak limite çivilerdi. Gecikme artık sonuçtan türetiliyor.
    """
    if not isinstance(result, UsageError) or result.kind != "rate_limited":
        # Başarı da, 429 dışı hatalar da tabana döner: tek bir başarılı
        # çekimden sonra yavaş kalmamalıyız.
        return BASE_INTERVAL_MS

    # Üstel geri çekilme, her zaman en az taban aralıktan başlayarak.
    step = max(current_ms, BASE_INTERVAL_MS) * 2

    if result.retry_after is not None:
        # Sunucu daha uzun beklememizi istiyorsa sözü geçer (üstüne saat
        # kaymalarını yutacak 1 sn pay). Daha kısa istiyorsa aldırmayız:
        # zaten bu hızda yoklamamıza gerek yok.
        step = max(step, result.retry_after * 1000 + 1000)

    return _clamp(step)


class Poller:
    """Çekim zincirini yürütür: aynı anda tek timer, tek uçuşta istek.

    Zamanlayıcı main.py'de kapanışların içindeyken test edilemiyordu ve
    hatanın yaşadığı yer tam olarak burasıydı; Tk yerine after/after_cancel
    sağlayan herhangi bir nesne enjekte edilebilir.
    """

    def __init__(self, scheduler, start_fetch, base_ms: int = BASE_INTERVAL_MS,
                 clock=time.monotonic):
        self._scheduler = scheduler
        self._start_fetch = start_fetch
        self._clock = clock
        self.delay_ms = base_ms
        self.fetching = False
        self._timer = None
        self._last_finished = None

    def start(self, first_delay_ms: int = FIRST_FETCH_MS) -> None:
        self._schedule(first_delay_ms)

    def request(self) -> bool:
        """Çekimi başlatır. Zaten uçuşta bir istek varsa yok sayar.

        ↻ ile timer'ın çakışması istek hızını sessizce ikiye katlıyordu.
        """
        if self.fetching:
            return False
        self._cancel()
        self.fetching = True
        self._start_fetch()
        return True

    def manual_request(self) -> bool:
        """↻ düğmesi. Ard arda tıklamalar arasında asgari boşluk şartı var.

        request()'teki koruma yalnızca eşzamanlı isteği engelliyor; ↻'ye
        yirmi kez basmak yirmi istek üretiyordu ve limiti ilk tetikleyen
        de tam olarak buydu.
        """
        if self._last_finished is not None:
            if (self._clock() - self._last_finished) * 1000 < MANUAL_MIN_GAP_MS:
                return False
        return self.request()

    def finished(self, result) -> None:
        """Sonuç geldiğinde ana thread'den çağrılır; zinciri sürdürür."""
        self.fetching = False
        self._last_finished = self._clock()
        self._schedule(next_delay_ms(result, self.delay_ms))

    def _schedule(self, ms: int) -> None:
        self._cancel()
        self.delay_ms = ms
        self._timer = self._scheduler.after(ms, self._fired)

    def _fired(self) -> None:
        # Ateşlenen id artık geçersiz; iptal edilmeye çalışılmamalı.
        self._timer = None
        self.request()

    def _cancel(self) -> None:
        if self._timer is not None:
            self._scheduler.after_cancel(self._timer)
            self._timer = None

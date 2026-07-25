from datetime import datetime, timezone

import pytest

from main import build_apply, safe_fetch
from usage_client import UsageData, UsageError


class FakePoller:
    def __init__(self):
        self.finished_with = []

    def finished(self, result):
        self.finished_with.append(result)


class ExplodingApp:
    def render(self, data):
        raise RuntimeError("render patladi")

    def render_error(self, err):
        raise RuntimeError("render_error patladi")


class RecordingApp:
    def __init__(self):
        self.rendered = []
        self.errors = []

    def render(self, data):
        self.rendered.append(data)

    def render_error(self, err):
        self.errors.append(err)


def _ok():
    return UsageData(five_hour=None, seven_day=None, fetched_at=datetime.now(timezone.utc))


def test_apply_renders_and_continues_chain():
    app, poller = RecordingApp(), FakePoller()
    data = _ok()
    build_apply(app, poller)(data)
    assert app.rendered == [data]
    assert poller.finished_with == [data]


def test_apply_renders_errors():
    app, poller = RecordingApp(), FakePoller()
    err = UsageError("rate_limited", "sınır")
    build_apply(app, poller)(err)
    assert app.errors == [err]
    assert poller.finished_with == [err]


def test_chain_continues_even_if_render_raises():
    # Zinciri yeniden kuran tek yer finished(); render patlayıp onu
    # atlarsa timer bir daha hiç kurulmaz, fetching True'da kalır ve
    # widget ↻ dahil kalıcı olarak ölür.
    app, poller = ExplodingApp(), FakePoller()
    with pytest.raises(RuntimeError):
        build_apply(app, poller)(_ok())
    assert poller.finished_with, "render patlasa da sıradaki çekim planlanmalı"


def test_chain_continues_even_if_render_error_raises():
    app, poller = ExplodingApp(), FakePoller()
    with pytest.raises(RuntimeError):
        build_apply(app, poller)(UsageError("network", "yok"))
    assert poller.finished_with


def test_safe_fetch_passes_result_through():
    data = _ok()
    assert safe_fetch(lambda: data) is data


def test_safe_fetch_converts_unexpected_exception_to_error():
    # Beklenmedik istisna thread'i öldürür, sonuç ana thread'e hiç
    # postalanmaz ve poller aynı şekilde kilitlenir.
    def boom():
        raise RuntimeError("beklenmedik")

    result = safe_fetch(boom)
    assert isinstance(result, UsageError)
    assert result.kind == "network"

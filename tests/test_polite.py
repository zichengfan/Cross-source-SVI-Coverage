"""Tests for the polite-scraper utilities."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError

import pytest

from coverage_acquisition import polite
from coverage_acquisition.polite import PolitePolicy, _HostThrottle, polite_fetch


class _FakeResponse:
    def __init__(self, payload: bytes = b"ok", content_type: str = "text/plain", status: int = 200):
        self._payload = payload
        self.headers = {"Content-Type": content_type}
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_policy_defaults():
    policy = PolitePolicy()
    assert policy.max_retries >= 1
    assert policy.min_interval_seconds >= 0.0
    assert policy.user_agent.startswith("global-svi-coverage")


def test_host_throttle_enforces_interval():
    throttle = _HostThrottle()
    interval = 0.05
    throttle.wait("host.test", interval)  # first call: no prior request, no wait
    start = time.monotonic()
    throttle.wait("host.test", interval)  # second call must wait ~interval
    assert time.monotonic() - start >= interval * 0.8


def test_polite_fetch_success(monkeypatch):
    monkeypatch.setattr(polite, "urlopen", lambda *a, **k: _FakeResponse(b"hello", "image/png", 200))
    payload, content_type, status = polite_fetch(
        "https://example.test/a", policy=PolitePolicy(min_interval_seconds=0.0)
    )
    assert payload == b"hello"
    assert content_type == "image/png"
    assert status == 200


def test_polite_fetch_retries_then_succeeds(monkeypatch):
    attempts = []

    def fake_urlopen(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise URLError("transient")
        return _FakeResponse(b"recovered")

    monkeypatch.setattr(polite, "urlopen", fake_urlopen)
    payload, _, _ = polite_fetch(
        "https://example.test/b",
        policy=PolitePolicy(min_interval_seconds=0.0, backoff_base_seconds=0.001),
    )
    assert payload == b"recovered"
    assert len(attempts) == 3


def test_polite_fetch_retries_on_retryable_status(monkeypatch):
    attempts = []

    def fake_urlopen(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < 2:
            raise HTTPError("https://example.test/c", 503, "Service Unavailable", {}, None)
        return _FakeResponse(b"ok-after-503")

    monkeypatch.setattr(polite, "urlopen", fake_urlopen)
    payload, _, _ = polite_fetch(
        "https://example.test/c",
        policy=PolitePolicy(min_interval_seconds=0.0, backoff_base_seconds=0.001),
    )
    assert payload == b"ok-after-503"
    assert len(attempts) == 2


def test_polite_fetch_raises_on_non_retryable_status(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise HTTPError("https://example.test/d", 404, "Not Found", {}, None)

    monkeypatch.setattr(polite, "urlopen", fake_urlopen)
    with pytest.raises(HTTPError):
        polite_fetch("https://example.test/d", policy=PolitePolicy(min_interval_seconds=0.0))

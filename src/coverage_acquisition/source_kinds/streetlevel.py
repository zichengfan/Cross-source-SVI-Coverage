"""`streetlevel` source kind foundation for point-probe coverage acquisition."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from coverage_acquisition.source_kinds._base import DecodeContext, DecodeResult, register_source_kind

StreetlevelProbe = Callable[[float, float, float], list[dict]]

STREETLEVEL_PROBES: dict[str, StreetlevelProbe] = {}


class ProbeBlockedError(RuntimeError):
    """Raised when a streetlevel probe endpoint is blocked or returns undecodable data."""


class GlobalRateLimiter:
    """Thread-safe global request-rate limiter shared by probe workers."""

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive.")
        self._min_interval_seconds = 1.0 / requests_per_second
        self._last_request: float | None = None
        self._lock = Lock()

    def acquire(self) -> None:
        """Block until the next global request slot is available."""
        with self._lock:
            now = time.monotonic()
            if self._last_request is not None:
                elapsed = now - self._last_request
                if elapsed < self._min_interval_seconds:
                    time.sleep(self._min_interval_seconds - elapsed)
                    now = time.monotonic()
            self._last_request = now


def register_streetlevel_probe(provider_key: str, probe: StreetlevelProbe) -> None:
    """Register a provider-specific point probe."""
    if provider_key in STREETLEVEL_PROBES:
        raise ValueError(f"Streetlevel probe already registered: {provider_key!r}")
    STREETLEVEL_PROBES[provider_key] = probe


def get_streetlevel_probe(provider_key: str) -> StreetlevelProbe:
    """Return the registered point probe for a provider."""
    try:
        return STREETLEVEL_PROBES[provider_key]
    except KeyError as exc:
        known = ", ".join(sorted(STREETLEVEL_PROBES)) or "<none>"
        raise KeyError(f"No streetlevel probe registered for {provider_key!r}. Registered: {known}.") from exc


class RateLimitedProbe:
    """Wrap a streetlevel probe with minimum-interval throttling and retries."""

    def __init__(
        self,
        probe: StreetlevelProbe,
        requests_per_second: float,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        limiter: GlobalRateLimiter | None = None,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative.")
        self._probe = probe
        self._limiter = limiter or GlobalRateLimiter(requests_per_second)
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def __call__(self, lat: float, lon: float, radius_m: float) -> list[dict]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            self._wait_for_slot()
            try:
                return self._probe(lat, lon, radius_m)
            except ProbeBlockedError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    raise
                time.sleep(self._backoff_base_seconds * (2**attempt))
        raise last_error if last_error is not None else RuntimeError("Streetlevel probe failed.")

    def _wait_for_slot(self) -> None:
        self._limiter.acquire()


def decode_streetlevel(_ctx: DecodeContext) -> DecodeResult:
    """Reject tile-decoder use; streetlevel sources use the point-probe runner."""
    raise RuntimeError("Streetlevel sources are acquired by coverage_acquisition.probe.fetch_probe_coverage.")


register_source_kind("streetlevel", decode_streetlevel)

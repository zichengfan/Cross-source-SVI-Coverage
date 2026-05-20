"""Tests for the streetlevel source kind and probe registry."""

from __future__ import annotations

import pytest

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.source_kinds import SOURCE_KIND_HANDLERS
from coverage_acquisition.source_kinds._base import DecodeContext
from coverage_acquisition.source_kinds.streetlevel import (
    STREETLEVEL_PROBES,
    ProbeBlockedError,
    RateLimitedProbe,
    get_streetlevel_probe,
    register_streetlevel_probe,
)


def test_registry_registers_and_rejects_duplicates():
    provider_key = "registry_test"
    STREETLEVEL_PROBES.pop(provider_key, None)

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        return [{"panoid": "a", "lat": lat, "lon": lon, "date": None, "raw": {"radius_m": radius_m}}]

    register_streetlevel_probe(provider_key, probe)
    assert get_streetlevel_probe(provider_key) is probe

    with pytest.raises(ValueError, match="already registered"):
        register_streetlevel_probe(provider_key, probe)


def test_registry_missing_key_has_clear_error():
    with pytest.raises(KeyError, match="No streetlevel probe registered"):
        get_streetlevel_probe("missing_provider")


def test_rate_limited_probe_spaces_calls(monkeypatch):
    clock = {"now": 100.0, "slept": []}

    def fake_monotonic() -> float:
        return clock["now"]

    def fake_sleep(seconds: float) -> None:
        clock["slept"].append(seconds)
        clock["now"] += seconds

    monkeypatch.setattr("coverage_acquisition.source_kinds.streetlevel.time.monotonic", fake_monotonic)
    monkeypatch.setattr("coverage_acquisition.source_kinds.streetlevel.time.sleep", fake_sleep)

    calls = []

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        calls.append((lat, lon, radius_m, clock["now"]))
        return []

    limited = RateLimitedProbe(probe, requests_per_second=2.0, max_retries=0)
    limited(1.0, 2.0, 100.0)
    limited(1.0, 2.0, 100.0)

    assert calls[1][3] - calls[0][3] >= 0.5
    assert clock["slept"] == [0.5]


def test_rate_limited_probe_retries_transient_error(monkeypatch):
    monkeypatch.setattr("coverage_acquisition.source_kinds.streetlevel.time.sleep", lambda seconds: None)
    attempts = []

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        attempts.append((lat, lon, radius_m))
        if len(attempts) == 1:
            raise RuntimeError("temporary")
        return [{"panoid": "ok", "lat": lat, "lon": lon, "date": None, "raw": {}}]

    limited = RateLimitedProbe(probe, requests_per_second=1000.0, max_retries=1, backoff_base_seconds=0.001)
    assert limited(1.0, 2.0, 50.0)[0]["panoid"] == "ok"
    assert len(attempts) == 2


def test_rate_limited_probe_does_not_retry_blocked(monkeypatch):
    monkeypatch.setattr("coverage_acquisition.source_kinds.streetlevel.time.sleep", lambda seconds: None)
    attempts = []

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        attempts.append((lat, lon, radius_m))
        raise ProbeBlockedError("blocked")

    limited = RateLimitedProbe(probe, requests_per_second=1000.0, max_retries=3, backoff_base_seconds=0.001)
    with pytest.raises(ProbeBlockedError):
        limited(1.0, 2.0, 50.0)
    assert len(attempts) == 1


def test_streetlevel_source_kind_handler_points_to_probe_runner(tmp_path):
    assert "streetlevel" in SOURCE_KIND_HANDLERS
    source = SourceDefinition(id="streetlevel", kind="streetlevel", template="")
    provider = ProviderDefinition(
        key="stub",
        output_namespace="stub",
        run_label_prefix="stub",
        default_display_zoom=14,
        sources=(source,),
    )
    ctx = DecodeContext(
        source=source,
        provider=provider,
        job={"display_zoom": 14, "source_zoom": 14},
        x=0,
        y=0,
        tile_url="",
        fetched_at="2026-05-20T00:00:00+00:00",
        output_dir=tmp_path,
        wire_payload=b"",
        content_type="",
        http_status=200,
    )
    with pytest.raises(RuntimeError, match="fetch_probe_coverage"):
        SOURCE_KIND_HANDLERS["streetlevel"](ctx)

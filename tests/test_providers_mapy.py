"""Offline tests for the Mapy.com streetlevel provider."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from streetlevel.mapy.parse import parse_getbest_response

from coverage_acquisition.io_utils import read_csv_rows
from coverage_acquisition.models import BoundingBox, ProbeFetchRequest
from coverage_acquisition.probe import fetch_probe_coverage, generate_probe_grid
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds.streetlevel import STREETLEVEL_PROBES, ProbeBlockedError, RateLimitedProbe

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapy"
PILOT_BBOX = BoundingBox(min_lon=14.40, min_lat=50.075, max_lon=14.44, max_lat=50.095)


def _load_getbest_fixture(name: str) -> dict:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    pan_info = payload.get("result", {}).get("panInfo")
    if pan_info and isinstance(pan_info.get("createdAt"), str):
        pan_info["createdAt"] = datetime.fromisoformat(pan_info["createdAt"])
    return payload


def _present_pano():
    pano = parse_getbest_response(_load_getbest_fixture("getbest_present.json"))
    assert pano is not None
    return pano


def _import_mapy_provider():
    import coverage_acquisition.providers.mapy as mapy_provider

    return mapy_provider


def test_mapy_registers():
    _import_mapy_provider()

    assert "mapy" in PROVIDERS
    provider = get_provider("mapy")
    assert provider.key == "mapy"
    assert provider.sources


def test_mapy_source_kind_is_streetlevel():
    provider = _import_mapy_provider().PROVIDER

    assert len(provider.sources) == 1
    source = provider.sources[0]
    assert source.kind == "streetlevel"
    assert source.options["streetlevel_module"] == "mapy"


def test_mapy_coordinate_scheme():
    assert _import_mapy_provider().PROVIDER.coordinate_scheme == "web_mercator"


def test_mapy_probe_grid_build():
    source = _import_mapy_provider().PROVIDER.sources[0]
    grid = generate_probe_grid(PILOT_BBOX, spacing_m=float(source.options["probe_spacing_m"]))

    assert len(grid) == 208
    assert grid[0] == (50.075, 14.4)
    assert grid[-1] == (50.095, 14.44)


def test_mapy_decode_present(monkeypatch):
    mapy_provider = _import_mapy_provider()
    pano = _present_pano()

    def fake_find_panorama(lat: float, lon: float, radius: float, *, links: bool, historical: bool):
        assert (lat, lon, radius) == (50.0875, 14.4215, 125.0)
        assert links is False
        assert historical is False
        return pano

    monkeypatch.setattr("streetlevel.mapy.find_panorama", fake_find_panorama)

    records = mapy_provider.probe_mapy(50.0875, 14.4215, 125.0)

    assert len(records) == 1
    assert records[0]["panoid"] == "104046742"
    assert records[0]["lat"] == 50.08756
    assert records[0]["lon"] == 14.42158
    assert records[0]["date"] == "2023-08-11"
    assert records[0]["raw"]["provider"] == "cyclomedia"


def test_mapy_decode_absent(monkeypatch):
    mapy_provider = _import_mapy_provider()
    absent = parse_getbest_response(_load_getbest_fixture("getbest_absent.json"))
    assert absent is None

    monkeypatch.setattr("streetlevel.mapy.find_panorama", lambda *args, **kwargs: absent)

    assert mapy_provider.probe_mapy(0.0, 0.0, 125.0) == []


def test_mapy_decode_uses_returned_location(monkeypatch):
    mapy_provider = _import_mapy_provider()
    pano = replace(_present_pano(), lat=50.08756, lon=14.42158)
    monkeypatch.setattr("streetlevel.mapy.find_panorama", lambda *args, **kwargs: pano)

    records = mapy_provider.probe_mapy(50.08, 14.4, 125.0)

    assert records[0]["lat"] == 50.08756
    assert records[0]["lon"] == 14.42158


def test_mapy_dedup_by_panoid(monkeypatch, tmp_path):
    _import_mapy_provider()
    pano = _present_pano()
    monkeypatch.setattr("streetlevel.mapy.find_panorama", lambda *args, **kwargs: pano)
    request = ProbeFetchRequest(
        provider="mapy",
        bbox=BoundingBox(min_lon=14.4215, min_lat=50.0875, max_lon=14.4216, max_lat=50.0876),
        output_root=tmp_path,
        coarse_spacing_m=20.0,
        fine_spacing_m=20.0,
        radius_m=125.0,
        requests_per_second=1000.0,
        two_pass=False,
        run_label="dedup",
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["total_probe_count"] == 4
    assert manifest["pano_count"] == 1
    rows = read_csv_rows(Path(manifest["pano_records_path"]))
    assert [row["panoid"] for row in rows] == ["104046742"]


def test_mapy_no_auth_required():
    source = _import_mapy_provider().PROVIDER.sources[0]

    assert source.token_query_param is None
    assert "env" not in source.options
    assert "api_key" not in source.options
    assert "token" not in source.options


def test_mapy_transport_error_retries():
    _import_mapy_provider()
    pano = _present_pano()
    calls = {"count": 0}

    def flaky_probe(lat: float, lon: float, radius_m: float):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("temporary transport failure")
        return [{"panoid": str(pano.id), "lat": pano.lat, "lon": pano.lon, "date": pano.date.date().isoformat()}]

    probe = RateLimitedProbe(flaky_probe, requests_per_second=1000.0, max_retries=1, backoff_base_seconds=0.0)

    records = probe(50.0875, 14.4215, 125.0)

    assert calls["count"] == 2
    assert records[0]["panoid"] == "104046742"


def test_mapy_probe_registered():
    _import_mapy_provider()

    assert STREETLEVEL_PROBES["mapy"]


def test_mapy_probe_wraps_undecodable_failure(monkeypatch):
    mapy_provider = _import_mapy_provider()

    def broken_find_panorama(*args, **kwargs):
        raise ValueError("could not decode FRPC response")

    monkeypatch.setattr("streetlevel.mapy.find_panorama", broken_find_panorama)

    with pytest.raises(ProbeBlockedError, match="Mapy streetlevel probe failed"):
        mapy_provider.probe_mapy(50.0875, 14.4215, 125.0)

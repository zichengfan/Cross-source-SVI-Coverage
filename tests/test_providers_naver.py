"""Offline tests for the Naver streetlevel provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds.streetlevel import get_streetlevel_probe

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "naver"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_naver_registers():
    assert "naver" in PROVIDERS
    provider = get_provider("naver")

    assert provider.key == "naver"
    assert len(provider.sources) == 1
    assert provider.sources[0].kind == "streetlevel"
    assert get_streetlevel_probe("naver")


def test_naver_source_definition():
    provider = get_provider("naver")
    source = provider.sources[0]

    assert source.id == "naver_streetlevel_panos"
    assert source.template == ""
    assert source.storage_subdir == "streetlevel"
    assert source.options["streetlevel_module"] == "naver"
    assert source.options["streetlevel_type_allowlist"] == (3, 4, 13, 15)
    assert source.options["discovery"]["posture"] == "option_b_minimize_map_naver_seed_calls"
    assert source.options["discovery"]["frontier_cap"] > 0
    assert "global-svi-coverage-observatory" in source.headers["User-Agent"]
    assert source.headers["Referer"] == "https://map.naver.com"


def test_naver_decode_nearby_present():
    from coverage_acquisition.providers.naver import decode_nearby_payload

    result = decode_nearby_payload(_load_fixture("nearby_gangnam.json"))

    assert result.is_empty is False
    assert len(result.records) >= 1
    record = result.records[0]
    assert record["panoid"] == "naver-gangnam-seed"
    assert isinstance(record["lat"], float)
    assert isinstance(record["lon"], float)
    assert 33 <= record["lat"] <= 39
    assert 124 <= record["lon"] <= 132
    assert record["date"] == "2026-01-29T03:04:05"


def test_naver_decode_nearby_empty():
    from coverage_acquisition.providers.naver import decode_nearby_payload

    result = decode_nearby_payload(_load_fixture("nearby_empty.json"))

    assert result.records == []
    assert result.is_empty is True


def test_naver_decode_around_type_filter():
    from coverage_acquisition.providers.naver import STREETLEVEL_PANORAMA_TYPES, decode_around_payload

    result = decode_around_payload(_load_fixture("around_gangnam.json"), parent_id="naver-gangnam-seed")

    assert result.dropped_count == 2
    assert len(result.records) == 4
    assert {record["raw"]["panorama_type"] for record in result.records} == STREETLEVEL_PANORAMA_TYPES
    assert "naver-gangnam-air" not in {record["panoid"] for record in result.records}
    assert "naver-gangnam-indoor" not in {record["panoid"] for record in result.records}


def test_naver_coordinate_order():
    from coverage_acquisition.providers.naver import decode_nearby_payload

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [127.5, 37.5]},
                "properties": {
                    "id": "coordinate-order",
                    "camera_angle": [0.0, 0.0, 0.0],
                    "photodate": "2026-01-29 00:00:00",
                    "description": "coordinate regression",
                    "title": "lon lat",
                    "camera_altitude": 1000,
                    "type": 3,
                },
            }
        ],
    }

    record = decode_nearby_payload(payload).records[0]

    assert record["lat"] == 37.5
    assert record["lon"] == 127.5


def test_naver_dedup_by_id():
    from coverage_acquisition.providers.naver import decode_nearby_payload

    payload = _load_fixture("nearby_gangnam.json")
    payload["features"].append(payload["features"][0])

    result = decode_nearby_payload(payload)

    assert [record["panoid"] for record in result.records] == ["naver-gangnam-seed"]


def test_naver_discovery_offline(monkeypatch):
    import streetlevel.naver.api as naver_api

    import coverage_acquisition.providers.naver as naver_provider

    calls = {"find": [], "neighbors": []}
    nearby_payload = _load_fixture("nearby_gangnam.json")

    def fake_find_panorama(lat: float, lon: float, session=None):
        calls["find"].append((lat, lon, session))
        return nearby_payload

    def fake_get_neighbors(panoid: str, session=None):
        calls["neighbors"].append((panoid, session))
        if panoid == "naver-gangnam-seed":
            return {
                "panoramas": {
                    "street": [
                        {
                            "id": "naver-gangnam-car-east",
                            "latitude": 37.4981,
                            "longitude": 127.0282,
                            "altitude": 42.1,
                            "dtl_type": 3,
                        },
                        {
                            "id": "naver-gangnam-car-east",
                            "latitude": 37.4981,
                            "longitude": 127.0282,
                            "altitude": 42.1,
                            "dtl_type": 3,
                        },
                        {
                            "id": "naver-gangnam-mesh",
                            "latitude": 37.4972,
                            "longitude": 127.0261,
                            "altitude": 40.2,
                            "dtl_type": 15,
                        },
                    ],
                    "air": [
                        {
                            "id": "naver-gangnam-air",
                            "latitude": 37.5000,
                            "longitude": 127.0300,
                            "altitude": 120.0,
                            "dtl_type": 1,
                        }
                    ],
                }
            }
        raise AssertionError("frontier cap should prevent expanding past the seed")

    def fake_get_json(*args, **kwargs):
        raise AssertionError(f"unexpected network call: {args!r} {kwargs!r}")

    monkeypatch.setattr(naver_api, "find_panorama", fake_find_panorama)
    monkeypatch.setattr(naver_api, "get_neighbors", fake_get_neighbors)
    monkeypatch.setattr("streetlevel.util.get_json", fake_get_json)
    monkeypatch.setattr(naver_provider, "DEFAULT_FRONTIER_CAP", 1)

    records = naver_provider.probe_naver(37.4979, 127.0276, 100.0)

    assert {record["panoid"] for record in records} == {
        "naver-gangnam-seed",
        "naver-gangnam-car-east",
        "naver-gangnam-mesh",
    }
    assert calls["find"] == [(37.4979, 127.0276, None)]
    assert calls["neighbors"] == [("naver-gangnam-seed", None)]


def test_naver_discovery_returns_empty_for_checked_empty(monkeypatch):
    import streetlevel.naver.api as naver_api

    import coverage_acquisition.providers.naver as naver_provider

    monkeypatch.setattr(naver_api, "find_panorama", lambda lat, lon, session=None: {"features": []})

    assert naver_provider.probe_naver(35.0, 129.0, 100.0) == []


def test_naver_discovery_skips_unknown_neighbor_panorama_type(monkeypatch):
    import streetlevel.naver.api as naver_api

    import coverage_acquisition.providers.naver as naver_provider

    nearby_payload = _load_fixture("nearby_gangnam.json")
    around_payload = {
        "panoramas": {
            "street": [
                {
                    "id": "naver-gangnam-unknown",
                    "latitude": 37.4980,
                    "longitude": 127.0279,
                    "altitude": 41.9,
                    "dtl_type": 14,
                },
                {
                    "id": "naver-gangnam-car-east",
                    "latitude": 37.4981,
                    "longitude": 127.0282,
                    "altitude": 42.1,
                    "dtl_type": 3,
                },
            ],
            "air": [],
        }
    }

    monkeypatch.setattr(naver_api, "find_panorama", lambda lat, lon, session=None: nearby_payload)
    monkeypatch.setattr(naver_api, "get_neighbors", lambda panoid, session=None: around_payload)
    monkeypatch.setattr(naver_provider, "DEFAULT_FRONTIER_CAP", 1)

    records = naver_provider.probe_naver(37.4979, 127.0276, 100.0)

    assert {record["panoid"] for record in records} == {"naver-gangnam-seed", "naver-gangnam-car-east"}


def test_naver_discovery_raises_probe_blocked_on_undecodable(monkeypatch):
    import streetlevel.naver.api as naver_api

    import coverage_acquisition.providers.naver as naver_provider
    from coverage_acquisition.source_kinds.streetlevel import ProbeBlockedError

    def fake_find_panorama(lat: float, lon: float, session=None):
        raise KeyError("features")

    monkeypatch.setattr(naver_api, "find_panorama", fake_find_panorama)

    with pytest.raises(ProbeBlockedError):
        naver_provider.probe_naver(37.4979, 127.0276, 100.0)


def test_naver_get_neighbors_flood_fill_is_throttled(monkeypatch):
    import time

    import streetlevel.naver.api as naver_api

    import coverage_acquisition.providers.naver as naver_provider

    call_times: list[float] = []

    def fake_get_neighbors(panoid: str, session=None):
        call_times.append(time.monotonic())
        if panoid == "seed":
            return {
                "panoramas": {
                    "street": [
                        {"id": "east", "latitude": 37.5001, "longitude": 127.0002, "altitude": 0.0, "dtl_type": 3},
                        {"id": "west", "latitude": 37.4999, "longitude": 126.9998, "altitude": 0.0, "dtl_type": 3},
                    ],
                    "air": [],
                }
            }
        return {"panoramas": {"street": [], "air": []}}

    monkeypatch.setattr(
        naver_api,
        "find_panorama",
        lambda lat, lon, session=None: {
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [127.0, 37.5]},
                    "properties": {
                        "id": "seed",
                        "camera_angle": [0.0, 0.0, 0.0],
                        "photodate": "2026-01-29 00:00:00",
                        "description": "seed",
                        "title": "seed",
                        "camera_altitude": 0,
                        "type": 3,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(naver_api, "get_neighbors", fake_get_neighbors)
    monkeypatch.setattr(naver_provider, "GET_NEIGHBORS_MIN_INTERVAL_SECONDS", 0.05)

    naver_provider.probe_naver(37.5, 127.0, 100.0)

    # seed + east + west = 3 get_neighbors calls; consecutive calls must be
    # spaced by at least the configured throttle interval.
    assert len(call_times) == 3
    gaps = [call_times[i + 1] - call_times[i] for i in range(len(call_times) - 1)]
    assert all(gap >= 0.05 * 0.8 for gap in gaps), gaps

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from coverage_acquisition.providers import PROVIDERS
from coverage_acquisition.source_kinds.streetlevel import ProbeBlockedError, get_streetlevel_probe

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kakao"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def fixture_json(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_kakao_registers():
    import coverage_acquisition.providers.kakao  # noqa: F401

    assert "kakao" in PROVIDERS
    assert PROVIDERS["kakao"].key == "kakao"


def test_kakao_provider_shape():
    import coverage_acquisition.providers.kakao  # noqa: F401

    provider = PROVIDERS["kakao"]

    assert len(provider.sources) == 1
    assert provider.coordinate_scheme == "web_mercator"
    assert provider.sources[0].kind == "streetlevel"
    assert provider.sources[0].token_query_param is None
    assert "Authorization" not in provider.sources[0].headers


def test_kakao_query_url_build():
    from coverage_acquisition.providers.kakao import build_kakao_query_url

    url = build_kakao_query_url(lat=37.5663, lon=126.9779, radius_m=100, limit=100)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "rv.map.kakao.com"
    assert parsed.path == "/roadview-search/v2/nodes"
    assert query == {
        "PX": ["126.9779"],
        "PY": ["37.5663"],
        "RAD": ["100"],
        "PAGE_SIZE": ["100"],
        "INPUT": ["wgs"],
        "TYPE": ["w"],
        "SERVICE": ["glpano"],
    }


def test_kakao_decode_coverage(monkeypatch):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (fixture_bytes("nodes_seoul.json"), "application/json", 200))

    panos = get_streetlevel_probe("kakao")(37.5663, 126.9779, 50)

    assert len(panos) == 3
    assert all(isinstance(pano["panoid"], int) for pano in panos)
    assert all(126.5 < pano["lon"] < 127.5 for pano in panos)
    assert all(37.4 < pano["lat"] < 37.7 for pano in panos)
    assert bool(panos) is True


def test_kakao_decode_empty(monkeypatch):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (fixture_bytes("nodes_empty.json"), "application/json", 200))

    panos = get_streetlevel_probe("kakao")(0.0, 0.0, 50)

    assert panos == []
    assert bool(panos) is False


def test_kakao_decode_uses_wgs_not_wcong(monkeypatch):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (fixture_bytes("nodes_seoul.json"), "application/json", 200))
    expected = fixture_json("nodes_seoul.json")["street_view"]["streetList"][0]

    pano = get_streetlevel_probe("kakao")(37.5663, 126.9779, 50)[0]

    assert pano["lon"] == expected["wgsx"]
    assert pano["lat"] == expected["wgsy"]
    assert pano["lon"] != expected["wcongx"]
    assert pano["lat"] != expected["wcongy"]
    assert pano["lon"] != expected["wtmx"]
    assert pano["lat"] != expected["wtmy"]


def test_kakao_decode_date(monkeypatch):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (fixture_bytes("nodes_seoul.json"), "application/json", 200))

    pano = get_streetlevel_probe("kakao")(37.5663, 126.9779, 50)[0]

    assert pano["date"] == "2015-09-30"


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("nodes_seoul.json", True),
        ("nodes_empty.json", False),
    ],
)
def test_kakao_presence_rule(monkeypatch, fixture_name, expected):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (fixture_bytes(fixture_name), "application/json", 200))

    panos = get_streetlevel_probe("kakao")(37.5663, 126.9779, 50)

    assert bool(panos) is expected


def test_kakao_probe_raises_blocked_on_undecodable_response(monkeypatch):
    import coverage_acquisition.providers.kakao as kakao

    monkeypatch.setattr(kakao, "polite_fetch", lambda *args, **kwargs: (b"<html>blocked</html>", "text/html", 200))

    with pytest.raises(ProbeBlockedError):
        get_streetlevel_probe("kakao")(37.5663, 126.9779, 50)

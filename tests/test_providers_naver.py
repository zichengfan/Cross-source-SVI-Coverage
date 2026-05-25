"""Offline tests for the Naver Street View raster coverage-overlay provider."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from PIL import Image

from coverage_acquisition import geo
from coverage_acquisition.models import BoundingBox, FetchAreaRequest, TileRange
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.runtime_config import build_runtime_options
from coverage_acquisition.source_kinds.raster import summarize_png

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "naver"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def fixture_json(name: str) -> dict:
    return json.loads(fixture_bytes(name).decode("utf-8"))


def alpha_channel(name: str) -> np.ndarray:
    with Image.open(FIXTURE_DIR / name) as image:
        return np.array(image.convert("RGBA"))[:, :, 3]


def test_naver_registers():
    import coverage_acquisition.providers.naver  # noqa: F401

    assert "naver" in PROVIDERS
    provider = get_provider("naver")
    source = provider.sources[0]

    assert provider.key == "naver"
    assert provider.coordinate_scheme == "web_mercator"
    assert len(provider.sources) == 1
    assert source.kind == "raster"


def test_naver_tile_url_build():
    source = get_provider("naver").sources[0]
    url = source.template.format(version="1778829614", z=14, x=13973, y=6348)
    parsed = urlparse(url)

    assert url == "https://map.pstatic.net/nrb/styles/basic/1778829614/14/13973/6348.png?mt=ps"
    assert parsed.netloc == "map.pstatic.net"
    assert parsed.query == "mt=ps"
    assert "/14/13973/6348.png" in parsed.path


def test_naver_source_definition():
    source = get_provider("naver").sources[0]

    assert source.id == "naver_streetview_overlay_png"
    assert source.kind == "raster"
    assert source.expect_content_type_prefix == "image/"
    assert source.storage_subdir == "tiles"
    assert "global-svi-coverage-observatory" in source.headers["User-Agent"]
    assert source.headers["Referer"] == "https://map.naver.com/"
    assert source.headers["Accept"] == "image/png,image/*;q=0.9,*/*;q=0.1"
    assert source.options["config_kind"] == "naver_pstatic_tiles"
    assert source.options["tilejson_url"] == "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps"
    assert source.options["mt"] == "ps"
    assert source.options["version_fallback"] == "1778829614"
    assert source.options["empty_tile_rule"] == "transparent_png"
    assert source.options["coverage_from"] == "alpha"


def test_naver_tilejson_parse(monkeypatch, tmp_path):
    source = get_provider("naver").sources[0]
    payload = fixture_bytes("basic_styles_ps.json")

    def fake_polite_fetch(url, *, headers=None, policy=None):
        assert url == source.options["tilejson_url"]
        assert headers["Referer"] == "https://map.naver.com/"
        assert policy.timeout_seconds == 60
        return payload, "image/json", 200

    monkeypatch.setattr("coverage_acquisition.polite.polite_fetch", fake_polite_fetch)

    request = FetchAreaRequest(
        provider="naver",
        bbox=BoundingBox(127.020, 37.490, 127.060, 37.520),
        output_root=tmp_path,
    )
    runtime_options = build_runtime_options(source, request)
    tilejson = fixture_json("basic_styles_ps.json")

    assert runtime_options["format_values"]["version"] == "1778829614"
    assert runtime_options["frontend_config"]["version"] == "1778829614"
    assert runtime_options["frontend_config"]["config_source"] == "live_tilejson"
    assert tilejson["scheme"] == "xyz"
    assert "{z}/{x}/{y}" in tilejson["tiles"][0]
    assert "mt=ps" in tilejson["tiles"][0]


def test_naver_decode_present():
    summary = summarize_png(fixture_bytes("overlay_gangnam_z14.png"))

    assert summary["width"] == 256
    assert summary["height"] == 256
    assert summary["coverage_pixel_count"] > 0


def test_naver_decode_empty():
    summary = summarize_png(fixture_bytes("overlay_empty_ocean_z14.png"))

    assert summary["coverage_pixel_count"] == 0
    assert summary["coverage_ratio"] == 0.0


def test_naver_coverage_from_alpha():
    empty_alpha = alpha_channel("overlay_empty_ocean_z14.png")
    gangnam_alpha = alpha_channel("overlay_gangnam_z14.png")

    assert np.count_nonzero(empty_alpha) == 0
    assert np.count_nonzero(gangnam_alpha > 0) > 0


def test_naver_web_mercator_scheme():
    tile_range = geo.tile_range_for_bbox(BoundingBox(127.020, 37.490, 127.060, 37.520), 14, "web_mercator")

    assert tile_range == TileRange(x_min=13972, x_max=13974, y_min=6347, y_max=6349)
    assert tile_range.x_min <= 13973 <= tile_range.x_max
    assert tile_range.y_min <= 6348 <= tile_range.y_max

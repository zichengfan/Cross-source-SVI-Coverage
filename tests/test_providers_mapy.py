"""Offline tests for the Mapy.com Panorama raster coverage-overlay provider."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapy"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _import_mapy_provider():
    import coverage_acquisition.providers.mapy as mapy_provider

    return mapy_provider


def test_mapy_registers():
    _import_mapy_provider()

    assert "mapy" in PROVIDERS
    provider = get_provider("mapy")
    assert provider.key == "mapy"
    assert len(provider.sources) == 1


def test_mapy_source_kind_is_raster():
    provider = _import_mapy_provider().PROVIDER

    assert len(provider.sources) == 1
    assert provider.sources[0].kind == "raster"


def test_mapy_coordinate_scheme():
    assert _import_mapy_provider().PROVIDER.coordinate_scheme == "web_mercator"


def test_mapy_tile_url_build():
    source = _import_mapy_provider().PROVIDER.sources[0]
    url = source.template.format(z=14, x=8848, y=5550)

    assert url == "https://mapserver.mapy.cz/panorama_ln_hybrid-m/14-8848-5550"
    assert "/14/8848/5550" not in url
    assert "sdk=" not in url
    assert "apikey=" not in url


def test_mapy_decode_present(make_decode_context):
    source = _import_mapy_provider().PROVIDER.sources[0]
    ctx = make_decode_context(
        source,
        payload=fixture_bytes("tile_prague_z14.png"),
        content_type="image/png",
        x=8848,
        y=5550,
    )

    result = get_source_kind_handler("raster")(ctx)

    assert result.coverage_pixel_count > 0
    assert result.is_empty is False
    assert result.tile_path is not None
    assert result.tile_path.exists()


def test_mapy_decode_empty(make_decode_context):
    source = _import_mapy_provider().PROVIDER.sources[0]
    ctx = make_decode_context(
        source,
        payload=fixture_bytes("tile_empty_default.png"),
        content_type="image/png",
        x=6371,
        y=6759,
    )

    result = get_source_kind_handler("raster")(ctx)

    assert result.coverage_pixel_count == 0
    assert result.is_empty is True
    assert result.tile_path is None


def test_mapy_empty_tile_rule_wired(make_decode_context, make_png):
    source = _import_mapy_provider().PROVIDER.sources[0]
    assert source.options["empty_tile_rule"] == "transparent_png"

    ctx = make_decode_context(source, payload=make_png(opaque=False), content_type="image/png")

    assert get_source_kind_handler("raster")(ctx).is_empty is True


def test_mapy_no_auth_required():
    source = _import_mapy_provider().PROVIDER.sources[0]

    assert source.token_query_param is None
    assert "env" not in source.options
    assert "api_key" not in source.options
    assert "token" not in source.options
    assert "Authorization" not in source.headers


def test_mapy_coverage_color_is_red():
    with Image.open(FIXTURE_DIR / "tile_prague_z14.png") as image:
        raw_rgba = image.convert("RGBA").tobytes()

    opaque_pixels = [
        (raw_rgba[offset], raw_rgba[offset + 1], raw_rgba[offset + 2], raw_rgba[offset + 3])
        for offset in range(0, len(raw_rgba), 4)
        if raw_rgba[offset + 3] > 0
    ]

    assert opaque_pixels
    assert all(red > 0 and green == 0 and blue == 0 for red, green, blue, _alpha in opaque_pixels)

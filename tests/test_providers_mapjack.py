from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from coverage_acquisition.models import BoundingBox
from coverage_acquisition.providers import PROVIDERS
from coverage_acquisition.source_kinds.raster import summarize_png

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapjack"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def transparent_rgba_png(size: tuple[int, int]) -> bytes:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_mapjack_registers():
    import coverage_acquisition.providers.mapjack  # noqa: F401

    assert "mapjack" in PROVIDERS
    assert PROVIDERS["mapjack"].key == "mapjack"


def test_mapjack_provider_shape():
    import coverage_acquisition.providers.mapjack  # noqa: F401

    provider = PROVIDERS["mapjack"]
    source = provider.sources[0]

    assert len(provider.sources) == 1
    assert source.kind == "raster"
    assert provider.coordinate_scheme == "web_mercator"
    assert provider.default_display_zoom == 14
    assert source.display_zoom_min == 14
    assert source.display_zoom_max == 16
    assert source.expect_content_type_prefix == "image/"
    assert source.storage_subdir == "tiles"
    assert source.token_query_param is None
    assert "Authorization" not in source.headers


def test_mapjack_chiang_mai_area_preset():
    import coverage_acquisition.providers.mapjack  # noqa: F401

    assert PROVIDERS["mapjack"].area_presets["chiang_mai_bbox"] == BoundingBox(
        min_lon=98.899549,
        min_lat=18.697236,
        max_lon=99.073957,
        max_lat=18.864633,
    )


def test_mapjack_tile_url_build():
    import coverage_acquisition.providers.mapjack  # noqa: F401

    source = PROVIDERS["mapjack"].sources[0]
    url = source.template.format(z=14, x=12696, y=7321)

    assert url == "https://www.mapjack.com/dots_r5/14/12696/14_12696_7321.gif"
    assert url.startswith("https://www.mapjack.com/dots_r5/")
    assert "/14/12696/" in url
    assert url.endswith("/14_12696_7321.gif")


def test_mapjack_decode_covered_fixture():
    summary = summarize_png(fixture_bytes("dots_z14_chiangmai_covered.gif"))

    assert summary["width"] == 256
    assert summary["height"] == 256
    assert summary["coverage_pixel_count"] == 4187


def test_mapjack_decode_second_covered_fixture():
    summary = summarize_png(fixture_bytes("dots_z14_chiangmai_covered2.gif"))

    assert summary["width"] == 256
    assert summary["height"] == 256
    assert summary["coverage_pixel_count"] == 3692


def test_mapjack_transparent_rgba_is_empty():
    summary = summarize_png(transparent_rgba_png((256, 256)))

    assert summary["width"] == 256
    assert summary["height"] == 256
    assert summary["coverage_pixel_count"] == 0

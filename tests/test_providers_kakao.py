from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from coverage_acquisition import geo
from coverage_acquisition.models import BoundingBox, TileRange
from coverage_acquisition.providers import PROVIDERS
from coverage_acquisition.source_kinds.raster import summarize_png

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "kakao"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def rgba_png(pixels: list[tuple[int, int, int, int]], size: tuple[int, int]) -> bytes:
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_kakao_registers():
    import coverage_acquisition.providers.kakao  # noqa: F401

    assert "kakao" in PROVIDERS
    assert PROVIDERS["kakao"].key == "kakao"


def test_kakao_provider_shape():
    import coverage_acquisition.providers.kakao  # noqa: F401

    provider = PROVIDERS["kakao"]
    source = provider.sources[0]

    assert len(provider.sources) == 1
    assert source.kind == "raster"
    assert provider.coordinate_scheme == "kakao_epsg5181"
    assert provider.default_display_zoom == 7
    assert source.display_zoom_min == 7
    assert source.display_zoom_max == 7
    assert source.token_query_param is None
    assert "Authorization" not in source.headers


def test_kakao_tile_url_build():
    import coverage_acquisition.providers.kakao  # noqa: F401

    source = PROVIDERS["kakao"].sources[0]
    url = source.template.format(z=7, x=55, y=124)

    assert url == "https://map0.daumcdn.net/map_roadviewline/3.00/L7/124/55.png"
    assert url.startswith("https://map0.daumcdn.net/")
    assert "/map_roadviewline/3.00/" in url
    assert "/L7/124/55.png" in url


def test_kakao_tilecoord_seoul():
    assert geo.wgs84_to_kakao_epsg5181_tile(126.9779, 37.5663, 7) == (55, 124)


def test_kakao_decode_coverage():
    summary = summarize_png(fixture_bytes("roadviewline_L7_seoul.png"))

    assert summary["width"] == 256
    assert summary["height"] == 256
    assert summary["coverage_pixel_count"] > 40000
    assert summary["coverage_ratio"] > 0.5


def test_kakao_decode_empty():
    for fixture_name in ("roadviewline_L7_empty.png", "roadviewline_L7_empty_land.png"):
        summary = summarize_png(fixture_bytes(fixture_name))

        assert summary["coverage_pixel_count"] == 0


def test_kakao_presence_alpha_not_color():
    transparent = (0, 0, 0, 0)
    one_alpha_pixel = [transparent] * 16
    one_alpha_pixel[5] = (0, 0, 0, 1)

    assert summarize_png(rgba_png(one_alpha_pixel, (4, 4)))["coverage_pixel_count"] == 1
    assert summarize_png(rgba_png([transparent] * 16, (4, 4)))["coverage_pixel_count"] == 0


def test_kakao_tile_range_korea():
    tile_range = geo.tile_range_for_bbox(BoundingBox(124.5, 33.0, 131.9, 38.7), 7, "kakao_epsg5181")

    assert tile_range == TileRange(x_min=-1, x_max=168, y_min=1, y_max=158)
    assert tile_range.count == 26860

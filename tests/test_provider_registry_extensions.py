from __future__ import annotations

import io

import pytest
from PIL import Image

from coverage_acquisition import runners
from coverage_acquisition.models import BoundingBox, FetchAreaRequest
from coverage_acquisition.mvt_decoder import load_vector_tile_message_class
from coverage_acquisition.providers import PROVIDERS, get_provider


def _single_point_bbox(lon: float, lat: float) -> BoundingBox:
    return BoundingBox(min_lon=lon, min_lat=lat, max_lon=lon, max_lat=lat)


def _transparent_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _minimal_mvt(layer_name: str, *, geometry_type: int) -> bytes:
    tile = load_vector_tile_message_class()()
    layer = tile.layers.add()
    layer.name = layer_name
    layer.version = 2
    layer.extent = 4096
    feature = layer.features.add()
    feature.id = 1
    feature.type = geometry_type
    if geometry_type == 1:  # Point: MoveTo(1), (100, 100)
        feature.geometry.extend([9, 200, 200])
    else:  # LineString: MoveTo(1), LineTo(1)
        feature.geometry.extend([9, 200, 200, 10, 20, 20])
    return tile.SerializeToString()


def test_notebook_local_providers_are_registered_in_source():
    assert {"mapilio", "mapy", "barikoi"} <= set(PROVIDERS)


def test_mapilio_source_contract_and_nonstandard_path_order():
    provider = get_provider("mapilio")
    source = provider.sources[0]

    assert provider.coordinate_scheme == "web_mercator"
    assert source.kind == "vector_mvt"
    assert source.layer_names == ("map_roads_line",)
    assert source.vector_decoder == "custom_mvt"
    assert source.token_query_param is None
    assert source.template.format(z=14, x=8802, y=5373) == "https://geo.mapilio.com/map/8802/5373/14"


def test_mapy_source_contract_and_transparent_empty_rule():
    provider = get_provider("mapy")
    source = provider.sources[0]

    assert source.kind == "raster"
    assert source.options["coverage_from"] == "alpha"
    assert source.options["empty_tile_rule"] == "transparent_png"
    assert source.headers["Referer"] == "https://mapy.com/"
    assert source.template.format(z=14, x=8848, y=5550) == (
        "https://mapserver.mapy.cz/panorama_ln_hybrid-m/14-8848-5550"
    )


def test_barikoi_source_contract_and_zoom_guard():
    provider = get_provider("barikoi")
    source = provider.sources[0]

    assert source.kind == "vector_mvt"
    assert source.layer_names == ("ThirdEye360",)
    assert source.display_zoom_min == 7
    assert source.display_zoom_max == 18
    assert source.token_query_param is None
    assert source.template.format(z=14, x=12306, y=7075) == ("https://tiles.bmapsbd.com/ThirdEye360/14/12306/7075")


def test_mapy_transparent_placeholder_is_checked_empty(monkeypatch, tmp_path):
    payload = _transparent_png()
    monkeypatch.setattr(
        runners,
        "_fetch_payload",
        lambda **_kwargs: (payload, "image/png", 200),
    )

    result = runners.fetch_provider_coverage(
        FetchAreaRequest(
            provider="mapy",
            bbox=_single_point_bbox(14.42, 50.085),
            output_root=tmp_path,
            display_zoom=14,
        )
    )["results"][0]

    assert result["manifest"]["tile_count"] == 1
    assert result["manifest"]["empty_tile_count"] == 1
    assert result["manifest"]["nonempty_tile_count"] == 0
    assert result["fetched_tiles"][0]["coverage_pixel_count"] == 0
    assert result["fetched_tiles"][0]["is_empty"] is True
    assert result["fetched_tiles"][0]["output_path"] == ""


@pytest.mark.parametrize(
    ("provider_key", "lon", "lat", "http_status"),
    [
        ("mapilio", 28.98, 41.015, 200),
        ("barikoi", 90.406, 23.815, 204),
    ],
)
def test_empty_vector_responses_are_checked_empty(
    monkeypatch,
    tmp_path,
    provider_key,
    lon,
    lat,
    http_status,
):
    monkeypatch.setattr(
        runners,
        "_fetch_payload",
        lambda **_kwargs: (b"", "application/x-protobuf", http_status),
    )

    result = runners.fetch_provider_coverage(
        FetchAreaRequest(
            provider=provider_key,
            bbox=_single_point_bbox(lon, lat),
            output_root=tmp_path,
            display_zoom=14,
        )
    )["results"][0]

    assert result["manifest"]["tile_count"] == 1
    assert result["manifest"]["empty_tile_count"] == 1
    assert result["manifest"]["nonempty_tile_count"] == 0
    assert result["fetched_tiles"][0]["feature_count"] == 0
    assert result["fetched_tiles"][0]["is_empty"] is True


@pytest.mark.parametrize(
    ("provider_key", "layer_name", "geometry_type", "lon", "lat"),
    [
        ("mapilio", "map_roads_line", 2, 28.98, 41.015),
        ("barikoi", "ThirdEye360", 1, 90.406, 23.815),
    ],
)
def test_present_vector_responses_decode_through_public_runner(
    monkeypatch,
    tmp_path,
    provider_key,
    layer_name,
    geometry_type,
    lon,
    lat,
):
    payload = _minimal_mvt(layer_name, geometry_type=geometry_type)
    monkeypatch.setattr(
        runners,
        "_fetch_payload",
        lambda **_kwargs: (payload, "application/vnd.mapbox-vector-tile", 200),
    )

    result = runners.fetch_provider_coverage(
        FetchAreaRequest(
            provider=provider_key,
            bbox=_single_point_bbox(lon, lat),
            output_root=tmp_path,
            display_zoom=14,
        )
    )["results"][0]

    row = result["fetched_tiles"][0]
    assert result["manifest"]["empty_tile_count"] == 0
    assert result["manifest"]["nonempty_tile_count"] == 1
    assert result["manifest"]["vector_feature_record_count"] == 1
    assert row["feature_count"] == 1
    assert row["is_empty"] is False
    assert row["output_path"].endswith(".mvt")


def test_barikoi_low_zoom_is_rejected_before_fetch(tmp_path):
    with pytest.raises(ValueError, match="No source configured"):
        runners.fetch_provider_coverage(
            FetchAreaRequest(
                provider="barikoi",
                bbox=_single_point_bbox(90.406, 23.815),
                output_root=tmp_path,
                display_zoom=6,
                dry_run=True,
            )
        )

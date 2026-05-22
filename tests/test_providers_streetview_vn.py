from __future__ import annotations

import json
import re
from pathlib import Path

from coverage_acquisition import geo
from coverage_acquisition.models import ProviderDefinition
from coverage_acquisition.mvt_decoder import decode_tile, feature_rows_from_decoded_tile
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "streetview_vn"
HANOI_Z14_X = 13008
HANOI_Z14_Y = 7212


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def streetview_vn_provider() -> ProviderDefinition:
    import coverage_acquisition.providers.streetview_vn  # noqa: F401

    return get_provider("streetview_vn")


def streetview_vn_source():
    return streetview_vn_provider().sources[0]


def decode_streetview_fixture(name: str, make_decode_context, *, x: int = HANOI_Z14_X, y: int = HANOI_Z14_Y):
    source = streetview_vn_source()
    ctx = make_decode_context(
        source,
        payload=fixture_bytes(name),
        content_type="application/octet-stream",
        x=x,
        y=y,
    )
    return get_source_kind_handler("vector_mvt")(ctx)


def targeted_feature_rows(name: str, *, source_zoom: int, tile_x: int, tile_y: int):
    source = streetview_vn_source()
    decoded_tile = decode_tile(fixture_bytes(name))
    targeted_tile = {layer_name: decoded_tile[layer_name] for layer_name in source.layer_names}
    return feature_rows_from_decoded_tile(
        decoded_tile=targeted_tile,
        provider=streetview_vn_provider().key,
        source_id=source.id,
        display_zoom=streetview_vn_provider().default_display_zoom,
        source_zoom=source_zoom,
        tile_x=tile_x,
        tile_y=tile_y,
        tile_url=source.template.format(z=source_zoom, x=tile_x, y=tile_y),
        fetched_at="2026-05-22T00:00:00+00:00",
    )


def first_wkt_point(wkt: str) -> tuple[float, float]:
    match = re.search(r"(-?\d+\.\d+) (-?\d+\.\d+)", wkt)
    assert match is not None
    return float(match.group(1)), float(match.group(2))


def test_streetview_vn_registers():
    import coverage_acquisition.providers.streetview_vn  # noqa: F401

    assert "streetview_vn" in PROVIDERS
    provider = get_provider("streetview_vn")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "streetview_vn"
    assert provider.coordinate_scheme == "web_mercator"
    assert len(provider.sources) == 1


def test_streetview_vn_source_shape():
    source = streetview_vn_source()

    assert source.kind == "vector_mvt"
    assert source.vector_decoder == "custom_mvt"
    assert source.layer_names == ("sequences",)
    assert source.storage_subdir == "vector_mvt"
    assert source.headers["User-Agent"] == "global-svi-coverage-observatory/0.3"
    assert source.headers["Referer"] == "https://view.ndamaps.vn/"
    assert source.token_query_param is None
    assert "Authorization" not in source.headers
    assert source.expect_content_type_prefix is None


def test_streetview_vn_tile_url_build():
    source = streetview_vn_source()
    url = source.template.format(z=14, x=HANOI_Z14_X, y=HANOI_Z14_Y)

    assert url == "https://gpx-view.ndamaps.vn/snap/14/13008/7212.mvt"
    assert "?" not in url
    assert "apiKey" not in url
    assert "access_token" not in url


def test_streetview_vn_decode_present(make_decode_context):
    result = decode_streetview_fixture("snap_hanoi_z14.mvt", make_decode_context)
    layer_counts = json.loads(result.layer_counts_json)

    assert result.feature_count > 0
    assert layer_counts["sequences"] > 0
    sequence_records = [
        record for record in result.vector_feature_records if record["layer_name"] == "sequences"
    ]
    assert sequence_records
    geometry_types = {record["geometry_type"] for record in sequence_records}
    assert "MultiLineString" in geometry_types
    assert geometry_types <= {"LineString", "MultiLineString"}
    lon, lat = first_wkt_point(sequence_records[0]["geometry_wkt"])
    assert 105.7 < lon < 105.95
    assert 20.95 < lat < 21.10


def test_streetview_vn_decode_has_date(make_decode_context):
    result = decode_streetview_fixture("snap_hanoi_z14.mvt", make_decode_context)
    sequence_record = next(record for record in result.vector_feature_records if record["layer_name"] == "sequences")
    properties = json.loads(sequence_record["properties_json"])

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", properties["date"])


def test_streetview_vn_empty_tile_is_404():
    payload = fixture_bytes("snap_empty_404.html")

    assert payload.startswith(b"<html>")
    try:
        decoded_tile = decode_tile(payload)
    except Exception:
        decoded_tile = {}
    assert decoded_tile.get("sequences", {}).get("feature_count", 0) == 0


def test_streetview_vn_targets_sequences_only():
    decoded_tile = decode_tile(fixture_bytes("snap_hanoi_z6.mvt"))
    assert {"sequences", "grid"} <= set(decoded_tile)

    rows, layer_counts = targeted_feature_rows("snap_hanoi_z6.mvt", source_zoom=6, tile_x=50, tile_y=28)

    assert layer_counts == {"sequences": 10}
    assert rows
    assert {row["layer_name"] for row in rows} == {"sequences"}


def test_streetview_vn_web_mercator_scheme():
    provider = streetview_vn_provider()
    hanoi_bbox = provider.area_presets["hanoi_center_bbox"]
    tile_range = geo.tile_range_for_bbox(hanoi_bbox, 14, provider.coordinate_scheme)

    assert tile_range.x_min <= HANOI_Z14_X <= tile_range.x_max
    assert tile_range.y_min <= HANOI_Z14_Y <= tile_range.y_max

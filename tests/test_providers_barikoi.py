from __future__ import annotations

import json
from pathlib import Path

from coverage_acquisition import geo
from coverage_acquisition.models import BoundingBox, ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "barikoi"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def barikoi_source():
    import coverage_acquisition.providers.barikoi  # noqa: F401

    return get_provider("barikoi").sources[0]


def decode_barikoi_fixture(name: str, make_decode_context):
    source = barikoi_source()
    ctx = make_decode_context(
        source,
        payload=fixture_bytes(name),
        content_type="application/x-protobuf",
        http_status=204 if name == "thirdeye360_empty.pbf" else 200,
        x=12306,
        y=7075,
    )
    return get_source_kind_handler("vector_mvt")(ctx)


def test_barikoi_registers():
    import coverage_acquisition.providers.barikoi  # noqa: F401

    assert "barikoi" in PROVIDERS
    provider = get_provider("barikoi")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "barikoi"
    assert len(provider.sources) == 1
    assert provider.sources[0].kind == "vector_mvt"


def test_barikoi_provider_shape():
    import coverage_acquisition.providers.barikoi  # noqa: F401

    provider = get_provider("barikoi")
    source = provider.sources[0]
    bbox = provider.area_presets["dhaka_pilot_bbox"]

    assert provider.coordinate_scheme == "web_mercator"
    assert provider.default_display_zoom == 14
    assert bbox == BoundingBox(min_lon=90.395, min_lat=23.790, max_lon=90.430, max_lat=23.815)
    assert source.id == "barikoi_thirdeye360_mvt"
    assert source.layer_names == ("ThirdEye360",)
    assert source.storage_subdir == "vector_mvt"
    assert source.vector_decoder == "custom_mvt"
    assert source.token_query_param is None
    assert "Authorization" not in source.headers
    assert "Cookie" not in source.headers
    assert ".env" not in source.template
    assert ".env" not in source.notes


def test_barikoi_tile_url_build():
    source = barikoi_source()
    url = source.template.format(z=14, x=12306, y=7075)

    assert url == "https://tiles.bmapsbd.com/ThirdEye360/14/12306/7075"
    assert "tiles.bmapsbd.com" in url
    assert "/ThirdEye360/14/12306/7075" in url
    assert not url.endswith((".pbf", ".mvt"))
    assert "?" not in url


def test_barikoi_decode_present(make_decode_context):
    result = decode_barikoi_fixture("thirdeye360_z14_dhaka.pbf", make_decode_context)
    layer_counts = json.loads(result.layer_counts_json)

    assert result.feature_count > 0
    assert layer_counts["ThirdEye360"] > 0
    assert result.vector_feature_records
    assert {
        record["geometry_type"]
        for record in result.vector_feature_records
        if record["layer_name"] == "ThirdEye360"
    } == {"Point"}


def test_barikoi_decode_empty(make_decode_context):
    result = decode_barikoi_fixture("thirdeye360_empty.pbf", make_decode_context)

    assert result.feature_count == 0
    assert result.stored_payload == b""
    assert result.vector_feature_records == []


def test_barikoi_decode_carries_capture_date(make_decode_context):
    result = decode_barikoi_fixture("thirdeye360_z14_dhaka.pbf", make_decode_context)
    properties = [json.loads(record["properties_json"]) for record in result.vector_feature_records]

    assert any("capture_date" in property_payload for property_payload in properties)
    assert any("capture_date_raw" in property_payload for property_payload in properties)


def test_barikoi_web_mercator_scheme():
    import coverage_acquisition.providers.barikoi  # noqa: F401

    provider = get_provider("barikoi")
    tile_range = geo.tile_range_for_bbox(provider.area_presets["dhaka_pilot_bbox"], 14, "web_mercator")

    assert tile_range.x_min <= 12306 <= tile_range.x_max
    assert tile_range.y_min <= 7075 <= tile_range.y_max

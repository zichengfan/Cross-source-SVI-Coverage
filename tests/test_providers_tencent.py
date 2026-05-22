from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from coverage_acquisition.models import BoundingBox, FetchAreaRequest, ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.runners import _build_tile_url
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tencent"


def tencent_source():
    import coverage_acquisition.providers.tencent  # noqa: F401

    return get_provider("tencent").sources[0]


def test_tencent_registers():
    import coverage_acquisition.providers.tencent  # noqa: F401

    assert "tencent" in PROVIDERS
    provider = get_provider("tencent")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "tencent"
    assert provider.discovery_kind == "tencent_city_bl"
    assert len(provider.sources) == 1
    assert provider.sources[0].kind == "tencent_mobile_street"


def test_tencent_provider_shape():
    import coverage_acquisition.providers.tencent  # noqa: F401

    provider = get_provider("tencent")
    source = provider.sources[0]
    bbox = provider.area_presets["shenzhen_futian_pilot_bbox"]

    assert provider.coordinate_scheme == "tencent_px"
    assert provider.default_display_zoom == 14
    assert bbox == BoundingBox(min_lon=114.04, min_lat=22.52, max_lon=114.08, max_lat=22.56)
    assert source.id == "tencent_mobile_street"
    assert source.storage_subdir == "tiles"
    assert source.token_query_param is None
    assert source.expect_content_type_prefix is None
    assert source.options["data_level"] == "14"
    assert source.options["valid_levels"] == "11,12,13,14,18"
    assert "Authorization" not in source.headers
    assert "Cookie" not in source.headers
    assert ".env" not in source.template
    assert ".env" not in source.notes


def test_tencent_mobile_street_url_build():
    source = tencent_source()
    url = _build_tile_url(
        source,
        13,
        1001,
        200,
        access_token=None,
        runtime_options={"format_values": {"lv": 13}},
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert url == "https://mapvectors.map.qq.com/mobile_street?df=1&idx=1001&lv=13&dth=20&bn=1&bl=200"
    assert parsed.netloc == "mapvectors.map.qq.com"
    assert query["df"] == ["1"]
    assert query["dth"] == ["20"]
    assert query["bn"] == ["1"]
    assert query["idx"] == ["1001"]
    assert query["lv"] == ["13"]
    assert query["bl"] == ["200"]


def test_tencent_discovery_kind_auto_registers_and_emits_city_bl_job(tmp_path):
    import coverage_acquisition.discovery_kinds
    import coverage_acquisition.providers.tencent  # noqa: F401

    provider = get_provider("tencent")
    request = FetchAreaRequest(
        provider="tencent",
        bbox=BoundingBox(min_lon=116.39, min_lat=39.90, max_lon=116.42, max_lat=39.93),
        output_root=tmp_path,
        display_zoom=14,
    )

    handler = coverage_acquisition.discovery_kinds.get_discovery_kind_handler("tencent_city_bl")
    jobs = handler(provider, request)

    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == provider.sources[0]
    assert job["source_zoom"] == 14
    assert job["source_tile_range"]["x_min"] == 1001
    assert job["source_tile_range"]["x_max"] == 1001
    assert job["source_tile_range"]["y_min"] == 0
    assert job["source_tile_range"]["y_max"] == job["source_tile_count"] - 1
    assert job["tile_grid_projection"] == "tencent_px"
    assert job["tencent_region"]["idx"] == "1001"
    assert job["tencent_bl_tiles"][0]["bl"] == 0
    assert {"tile_x", "tile_y", "origin_px_x", "origin_px_y"} <= set(job["tencent_bl_tiles"][0])


def test_tencent_discovery_rejects_invalid_level(tmp_path):
    import coverage_acquisition.discovery_kinds
    import coverage_acquisition.providers.tencent  # noqa: F401

    provider = get_provider("tencent")
    source = provider.sources[0]
    invalid_provider = ProviderDefinition(
        key=provider.key,
        output_namespace=provider.output_namespace,
        run_label_prefix=provider.run_label_prefix,
        default_display_zoom=provider.default_display_zoom,
        coordinate_scheme=provider.coordinate_scheme,
        discovery_kind=provider.discovery_kind,
        sources=(
            type(source)(
                id=source.id,
                kind=source.kind,
                template=source.template,
                headers=source.headers,
                storage_subdir=source.storage_subdir,
                options={**source.options, "data_level": "15"},
            ),
        ),
    )
    request = FetchAreaRequest(
        provider="tencent",
        bbox=BoundingBox(min_lon=116.39, min_lat=39.90, max_lon=116.42, max_lat=39.93),
        output_root=tmp_path,
        display_zoom=14,
    )
    handler = coverage_acquisition.discovery_kinds.get_discovery_kind_handler("tencent_city_bl")

    try:
        handler(invalid_provider, request)
    except ValueError as exc:
        assert "Unsupported Tencent data level" in str(exc)
    else:
        raise AssertionError("invalid Tencent data level was accepted")


def test_tencent_decode_uses_job_bl_origin(make_decode_context):
    source = tencent_source()
    payload = (FIXTURE_DIR / "mobile_street_beijing_lv13_bl100.bin").read_bytes()

    zero_origin_ctx = make_decode_context(source, payload=payload, content_type="text/plain", x=1001, y=100)
    zero_origin_result = get_source_kind_handler("tencent_mobile_street")(zero_origin_ctx)
    zero_origin_first = json.loads(zero_origin_result.vector_feature_records[0]["properties_json"])

    origin_ctx = make_decode_context(source, payload=payload, content_type="text/plain", x=1001, y=100)
    origin_ctx.job["tencent_bl_tiles"] = [
        {
            "bl": 100,
            "tile_x": 6744,
            "tile_y": 3101,
            "origin_px_x": 55246848,
            "origin_px_y": 25403392,
        }
    ]
    origin_result = get_source_kind_handler("tencent_mobile_street")(origin_ctx)
    origin_first = json.loads(origin_result.vector_feature_records[0]["properties_json"])

    assert zero_origin_first["origin_px_x"] == 0
    assert zero_origin_first["origin_px_y"] == 0
    assert origin_first["origin_px_x"] == 55246848
    assert origin_first["origin_px_y"] == 25403392
    assert zero_origin_result.vector_feature_records[0]["geometry_wkt"] != origin_result.vector_feature_records[0][
        "geometry_wkt"
    ]

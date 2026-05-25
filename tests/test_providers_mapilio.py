from __future__ import annotations

import json
from pathlib import Path

from coverage_acquisition.models import ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mapilio"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def mapilio_source():
    import coverage_acquisition.providers.mapilio  # noqa: F401

    return get_provider("mapilio").sources[0]


def decode_mapilio_fixture(name: str, make_decode_context):
    source = mapilio_source()
    ctx = make_decode_context(
        source,
        payload=fixture_bytes(name),
        content_type="application/vnd.mapbox-vector-tile",
        x=9510,
        y=6142,
    )
    return get_source_kind_handler("vector_mvt")(ctx)


def test_mapilio_registers():
    import coverage_acquisition.providers.mapilio  # noqa: F401

    assert "mapilio" in PROVIDERS
    provider = get_provider("mapilio")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "mapilio"
    assert len(provider.sources) == 1


def test_mapilio_source_kind_is_vector_mvt():
    assert mapilio_source().kind == "vector_mvt"


def test_mapilio_coordinate_scheme():
    import coverage_acquisition.providers.mapilio  # noqa: F401

    assert get_provider("mapilio").coordinate_scheme == "web_mercator"


def test_mapilio_tile_url_build():
    source = mapilio_source()
    url = source.template.format(z=14, x=8802, y=5373)

    assert url == "https://geo.mapilio.com/map/8802/5373/14"
    assert "?" not in url
    assert "access_token" not in url


def test_mapilio_decode_present(make_decode_context):
    result = decode_mapilio_fixture("tile_istanbul_z14.mvt", make_decode_context)
    layer_counts = json.loads(result.layer_counts_json)

    assert result.feature_count > 0
    assert layer_counts["map_roads_line"] > 0
    assert result.is_empty in ("", False)
    assert result.tile_path is not None and result.tile_path.exists()


def test_mapilio_decode_empty(make_decode_context):
    result = decode_mapilio_fixture("tile_empty.mvt", make_decode_context)

    assert result.feature_count == 0
    assert result.stored_payload == b""
    assert result.tile_path is not None and result.tile_path.exists()


def test_mapilio_layer_names():
    assert "map_roads_line" in mapilio_source().layer_names


def test_mapilio_no_auth_required():
    source = mapilio_source()

    assert source.token_query_param is None
    assert ".env" not in source.template
    assert ".env" not in source.notes
    assert "Authorization" not in source.headers


def test_mapilio_decode_present_geometry_is_lines(make_decode_context):
    result = decode_mapilio_fixture("tile_istanbul_z14.mvt", make_decode_context)

    assert result.vector_feature_records
    assert {
        record["geometry_type"]
        for record in result.vector_feature_records
        if record["layer_name"] == "map_roads_line"
    } <= {"LineString", "MultiLineString"}

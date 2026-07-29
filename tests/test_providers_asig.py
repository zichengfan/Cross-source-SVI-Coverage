from __future__ import annotations

from pathlib import Path

from coverage_acquisition import geo
from coverage_acquisition.models import BoundingBox, ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.source_kinds import get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "asig"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def asig_source():
    import coverage_acquisition.providers.asig  # noqa: F401

    return get_provider("asig").sources[0]


def decode_asig_fixture(name: str, make_decode_context):
    source = asig_source()
    ctx = make_decode_context(
        source,
        payload=fixture_bytes(name),
        content_type="application/geo+json",
        x=9093,
        y=6123,
    )
    return get_source_kind_handler("vector_geojson")(ctx)


def test_asig_registers():
    import coverage_acquisition.providers.asig  # noqa: F401

    assert "asig" in PROVIDERS
    provider = get_provider("asig")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "asig"


def test_asig_provider_shape():
    import coverage_acquisition.providers.asig  # noqa: F401

    provider = get_provider("asig")
    source = provider.sources[0]
    bbox = provider.area_presets["tirana_center_bbox"]

    assert len(provider.sources) == 1
    assert source.kind == "vector_geojson"
    assert provider.coordinate_scheme == "web_mercator"
    assert provider.default_display_zoom == 14
    assert source.display_zoom_min == 6
    assert source.display_zoom_max == 15
    assert source.options["geojson_lon_property"] == "lon"
    assert source.options["geojson_lat_property"] == "lat"
    assert source.options["geojson_geometry_types"] == "Point"
    assert bbox == BoundingBox(min_lon=19.79, min_lat=41.30, max_lon=19.86, max_lat=41.35)
    assert "Authorization" not in source.headers
    assert "Cookie" not in source.headers


def test_asig_tile_url_build():
    source = asig_source()
    url = source.template.format(z=14, x=9093, y=6123)

    assert (
        url
        == "http://360.asig.gov.al/AlbaniaStreetView/player2/tiles-1674737600/14/9093/6123.geojson"
    )


def test_asig_xyz_tile_indices():
    assert geo.lonlat_to_tile(19.819, 41.327, 14) == (9093, 6123)
    assert geo.lonlat_to_tile(19.819, 41.327, 15) == (18187, 12246)


def test_asig_decode_present(make_decode_context):
    result = decode_asig_fixture("tile_present_z14.geojson", make_decode_context)

    assert result.feature_count == 3
    assert len(result.vector_feature_records) == 3
    assert result.is_empty is False

    first = result.vector_feature_records[0]
    assert first["geometry_type"] == "Point"
    assert first["geometry_wkt"].startswith("POINT")
    assert "19.8059604" in first["geometry_wkt"]
    assert "41.3120913" in first["geometry_wkt"]
    assert "1615" not in first["geometry_wkt"]
    assert "3775" not in first["geometry_wkt"]


def test_asig_decode_empty(make_decode_context):
    result = decode_asig_fixture("tile_empty.geojson", make_decode_context)

    assert result.feature_count == 0
    assert result.vector_feature_records == []
    assert result.is_empty is True


def test_asig_decode_ignores_pixel_lines(make_decode_context):
    result = decode_asig_fixture("tile_present_z14.geojson", make_decode_context)
    wkts = [record["geometry_wkt"] for record in result.vector_feature_records]

    assert {record["geometry_type"] for record in result.vector_feature_records} == {"Point"}
    assert all("LINESTRING" not in wkt for wkt in wkts)
    assert all("2741" not in wkt and "4160" not in wkt for wkt in wkts)

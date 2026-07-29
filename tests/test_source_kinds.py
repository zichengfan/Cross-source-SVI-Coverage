"""Tests for the pluggable source-kind decoders."""

from __future__ import annotations

import json

import mapbox_vector_tile
import pytest
from shapely.geometry import LineString, Point

from coverage_acquisition.source_kinds import SOURCE_KIND_HANDLERS, get_source_kind_handler
from coverage_acquisition.source_kinds.raster import summarize_png
from coverage_acquisition.source_kinds.vector_mvt import guess_geometry_type_from_wkt


def test_core_kinds_registered():
    for kind in ("raster", "vector_mvt", "coverage_json"):
        assert kind in SOURCE_KIND_HANDLERS


def test_get_handler_unknown_kind_raises():
    with pytest.raises(ValueError):
        get_source_kind_handler("not_a_kind")


def test_summarize_png_counts_opaque_pixels(make_png):
    opaque = summarize_png(make_png(opaque=True))
    transparent = summarize_png(make_png(opaque=False))
    assert opaque["coverage_pixel_count"] == opaque["total_pixel_count"]
    assert opaque["coverage_ratio"] == 1.0
    assert transparent["coverage_pixel_count"] == 0


def test_decode_raster_writes_tile(make_source, make_decode_context, make_png):
    source = make_source("raster")
    ctx = make_decode_context(source, payload=make_png(opaque=True), content_type="image/png")
    result = get_source_kind_handler("raster")(ctx)
    assert result.tile_path is not None and result.tile_path.exists()
    assert result.coverage_pixel_count > 0
    assert result.is_empty is False


def test_decode_raster_content_type_mismatch_skipped(make_source, make_decode_context):
    source = make_source("raster", expect_content_type_prefix="image/")
    ctx = make_decode_context(source, payload=b"<html>", content_type="text/html")
    result = get_source_kind_handler("raster")(ctx)
    assert result.skipped is True
    assert result.skip_record is not None


def test_yandex_source_migrated_to_empty_tile_rule():
    # Yandex's empty-tile behaviour is now driven by the provider-agnostic
    # `empty_tile_rule` option, not a hard-coded `config_kind` special case.
    from coverage_acquisition.providers import get_provider

    source = get_provider("yandex").sources[0]
    assert source.options.get("empty_tile_rule") == "transparent_png"


def test_decode_raster_config_kind_alone_does_not_enable_empty_rule(make_source, make_decode_context, make_png):
    source = make_source("raster", options={"config_kind": "yandex_stv_renderer"})
    ctx = make_decode_context(source, payload=make_png(opaque=False), content_type="image/png")

    result = get_source_kind_handler("raster")(ctx)

    assert result.is_empty is False
    assert result.tile_path is not None


def test_decode_raster_transparent_png_empty_rule(make_source, make_decode_context, make_png):
    source = make_source("raster", options={"empty_tile_rule": "transparent_png"})

    transparent = get_source_kind_handler("raster")(
        make_decode_context(source, payload=make_png(opaque=False), content_type="image/png")
    )
    opaque = get_source_kind_handler("raster")(
        make_decode_context(source, payload=make_png(opaque=True), content_type="image/png")
    )

    assert transparent.is_empty is True
    assert transparent.tile_path is None
    assert opaque.is_empty is False
    assert opaque.tile_path is not None


def test_decode_raster_http_204_empty_rule(make_source, make_decode_context):
    source = make_source("raster", options={"empty_tile_rule": "http_204"})
    ctx = make_decode_context(source, payload=b"", content_type="image/png", http_status=204)

    result = get_source_kind_handler("raster")(ctx)

    assert result.is_empty is True
    assert result.tile_path is None


def test_decode_coverage_json_extracts_panos(make_source, make_decode_context):
    source = make_source("coverage_json")
    payload = json.dumps(
        {
            "lastModified": "2026-01-01",
            "panos": [
                {"panoid": "a", "lat": 52.3, "lon": 4.9},
                {"panoid": "b", "lat": 52.4, "lon": 5.0},
            ],
        }
    ).encode("utf-8")
    ctx = make_decode_context(source, payload=payload)
    result = get_source_kind_handler("coverage_json")(ctx)
    assert result.pano_count == 2
    assert len(result.pano_records) == 2
    assert result.pano_records[0]["panoid"] == "a"
    assert result.last_modified == "2026-01-01"


def test_decode_vector_mvt_round_trip(make_source, make_decode_context):
    payload = mapbox_vector_tile.encode(
        [
            {
                "name": "sequence",
                "features": [
                    {"geometry": Point(100, 200), "properties": {"id": 1}},
                    {"geometry": LineString([(0, 0), (10, 10)]), "properties": {"id": 2}},
                ],
            }
        ]
    )
    source = make_source("vector_mvt", vector_decoder="custom_mvt", layer_names=("sequence",))
    ctx = make_decode_context(source, payload=payload, content_type="application/x-protobuf")
    result = get_source_kind_handler("vector_mvt")(ctx)
    assert result.feature_count == 2
    assert len(result.vector_feature_records) == 2
    assert result.tile_path is not None and result.tile_path.exists()


def test_guess_geometry_type_from_wkt():
    assert guess_geometry_type_from_wkt("POINT (1 2)") == "Point"
    assert guess_geometry_type_from_wkt("LINESTRING (0 0, 1 1)") == "LineString"
    assert guess_geometry_type_from_wkt("") == "Unknown"


def test_vector_geojson_registered():
    assert "vector_geojson" in SOURCE_KIND_HANDLERS


def _feature_collection(features: list[dict]) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": features}).encode("utf-8")


def test_decode_vector_geojson_standard_features(make_source, make_decode_context):
    payload = _feature_collection(
        [
            {
                "type": "Feature",
                "id": "p1",
                "geometry": {"type": "Point", "coordinates": [4.9, 52.3]},
                "properties": {"name": "alpha"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [1.0, 1.0]]},
                "properties": {"name": "beta"},
            },
        ]
    )
    source = make_source("vector_geojson", template="https://example.test/{z}/{x}/{y}.geojson")
    ctx = make_decode_context(source, payload=payload, content_type="application/geo+json")

    result = get_source_kind_handler("vector_geojson")(ctx)

    assert result.feature_count == 2
    assert len(result.vector_feature_records) == 2
    assert result.is_empty is False
    assert result.tile_path is not None and result.tile_path.exists()
    assert result.tile_path.suffix == ".geojson"

    point_record = next(r for r in result.vector_feature_records if r["geometry_type"] == "Point")
    assert point_record["geometry_wkt"].startswith("POINT")
    assert "4.9" in point_record["geometry_wkt"] and "52.3" in point_record["geometry_wkt"]
    assert point_record["mvt_id"] == "p1"
    assert json.loads(point_record["properties_json"])["name"] == "alpha"


def test_decode_vector_geojson_empty(make_source, make_decode_context):
    source = make_source("vector_geojson")
    ctx = make_decode_context(source, payload=_feature_collection([]), content_type="application/geo+json")

    result = get_source_kind_handler("vector_geojson")(ctx)

    assert result.feature_count == 0
    assert result.vector_feature_records == []
    assert result.is_empty is True


def test_decode_vector_geojson_lonlat_from_properties(make_source, make_decode_context):
    # ASIG case: the Point geometry is in tile-local pixel space (0-4096), but the
    # true WGS84 location is carried in `lon`/`lat` properties. With the property
    # names configured, the emitted WKT must use the properties, not the geometry.
    payload = _feature_collection(
        [
            {
                "type": "Feature",
                "id": "cam-1",
                "geometry": {"type": "Point", "coordinates": [2048, 2048]},
                "properties": {"lon": 19.819, "lat": 41.327, "heading": 90},
            }
        ]
    )
    source = make_source(
        "vector_geojson",
        options={"geojson_lon_property": "lon", "geojson_lat_property": "lat"},
    )
    ctx = make_decode_context(source, payload=payload, content_type="application/geo+json")

    result = get_source_kind_handler("vector_geojson")(ctx)

    assert result.feature_count == 1
    wkt = result.vector_feature_records[0]["geometry_wkt"]
    assert "19.819" in wkt and "41.327" in wkt
    assert "2048" not in wkt


def test_decode_vector_geojson_geometry_type_filter(make_source, make_decode_context):
    # ASIG's LineString/MultiLineString features are tile-pixel-space decoration and
    # must not be emitted as geographic geometries. A geometry-type allow-list keeps
    # only the Point photo-centers.
    payload = _feature_collection(
        [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [4.9, 52.3]},
                "properties": {"lon": 4.9, "lat": 52.3},
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0, 0], [4096, 4096]]},
                "properties": {"tourName": "trace"},
            },
        ]
    )
    source = make_source(
        "vector_geojson",
        options={
            "geojson_lon_property": "lon",
            "geojson_lat_property": "lat",
            "geojson_geometry_types": "Point",
        },
    )
    ctx = make_decode_context(source, payload=payload, content_type="application/geo+json")

    result = get_source_kind_handler("vector_geojson")(ctx)

    assert result.feature_count == 1
    assert {r["geometry_type"] for r in result.vector_feature_records} == {"Point"}

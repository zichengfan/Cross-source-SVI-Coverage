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

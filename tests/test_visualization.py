from __future__ import annotations

import csv
import json

from coverage_acquisition.visualization import (
    _read_csv_strided,
    geometry_parts_from_wkt,
    load_result_from_manifest,
    result_tile_bbox,
    summarize_result,
)


def test_geometry_parts_support_points_lines_and_collections():
    points, segments = geometry_parts_from_wkt(
        "GEOMETRYCOLLECTION (POINT (90.4 23.8), LINESTRING (90.4 23.8, 90.5 23.9))"
    )
    assert points == [(90.4, 23.8)]
    assert segments == [[(90.4, 23.8), (90.5, 23.9)]]


def test_large_record_tables_are_sampled_deterministically(tmp_path):
    path = tmp_path / "records.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["value"])
        writer.writeheader()
        writer.writerows({"value": value} for value in range(10))

    assert [row["value"] for row in _read_csv_strided(path, 3, total_hint=10)] == ["0", "4", "8"]


def test_result_tile_bbox_uses_native_tile_extent():
    result = {
        "manifest": {
            "bbox": {"min_lon": 90.3956, "min_lat": 23.8193, "max_lon": 90.3964, "max_lat": 23.8201},
            "source_zoom": 7,
            "tile_grid_projection": "web_mercator",
            "source_tile_range": {"x_min": 96, "x_max": 96, "y_min": 55, "y_max": 55},
        }
    }
    bbox = result_tile_bbox(result)
    assert bbox.min_lon < 90.3956 < bbox.max_lon
    assert bbox.min_lat < 23.8193 < bbox.max_lat


def test_manifest_loader_and_summary_resolve_local_outputs(tmp_path):
    tile_summary = tmp_path / "tile_summary.csv"
    feature_records = tmp_path / "feature_records.csv"
    pano_records = tmp_path / "pano_records.csv"
    for path, fields in (
        (tile_summary, ["x", "y", "source_zoom", "output_path"]),
        (feature_records, ["geometry_wkt"]),
        (pano_records, ["lon", "lat"]),
    ):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()

    manifest = {
        "provider": "barikoi",
        "source_id": "barikoi_thirdeye360_mvt",
        "source_kind": "vector_mvt",
        "bbox": {"min_lon": 90.396, "min_lat": 23.806, "max_lon": 90.417, "max_lat": 23.825},
        "display_zoom": 16,
        "source_zoom": 16,
        "tile_count": 1,
        "vector_feature_record_count": 42,
        "error_count": 0,
        "tile_summary_path": str(tile_summary),
        "vector_feature_records_path": str(feature_records),
        "pano_records_path": str(pano_records),
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = load_result_from_manifest(manifest_path)
    summary = summarize_result(result)
    assert result["tile_summary_path"] == str(tile_summary)
    assert summary["provider"] == "barikoi"
    assert summary["feature_count"] == 42

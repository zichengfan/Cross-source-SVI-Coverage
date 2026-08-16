from __future__ import annotations

from pathlib import Path

from coverage_acquisition.io_utils import load_json


def summarize_fetch_bundle(bundle: dict) -> list[dict]:
    rows = []
    for result in bundle.get("results", []):
        manifest = result["manifest"]
        rows.append(
            {
                "provider": manifest["provider"],
                "run_label": manifest["run_label"],
                "source_id": manifest["source_id"],
                "source_kind": manifest["source_kind"],
                "job_index": manifest["job_index"],
                "display_zoom": manifest["display_zoom"],
                "source_zoom": manifest["source_zoom"],
                "tile_count": _manifest_value(manifest, "tile_count", "fetched_tile_count", default=0),
                "skipped_404_count": _manifest_value(manifest, "skipped_404_count", "skipped_tile_count", default=0),
                "error_count": _manifest_value(manifest, "error_count", "error_tile_count", default=0),
                "pano_record_count": manifest.get("pano_record_count", 0),
                "vector_feature_record_count": manifest.get("vector_feature_record_count", 0),
                "total_coverage_pixels": manifest.get("total_coverage_pixels", 0),
                "total_pixels": manifest.get("total_pixels", 0),
                "aggregate_coverage_ratio": manifest.get("aggregate_coverage_ratio"),
                "manifest_path": result["manifest_path"],
            }
        )
    return rows


def summarize_many_bundles(bundles: list[dict]) -> list[dict]:
    rows = []
    for bundle in bundles:
        rows.extend(summarize_fetch_bundle(bundle))
    return rows


def summarize_manifest_paths(manifest_paths: list[str | Path]) -> list[dict]:
    rows = []
    for manifest_path in manifest_paths:
        manifest_path = Path(manifest_path)
        manifest = load_json(manifest_path)
        rows.append(
            {
                "provider": manifest["provider"],
                "run_label": manifest.get("run_label", manifest_path.parent.name),
                "source_id": manifest["source_id"],
                "source_kind": manifest.get("source_kind", infer_source_kind(manifest)),
                "job_index": manifest.get("job_index", -1),
                "display_zoom": manifest["display_zoom"],
                "source_zoom": manifest["source_zoom"],
                "tile_count": _manifest_value(manifest, "tile_count", "fetched_tile_count", default=0),
                "skipped_404_count": _manifest_value(manifest, "skipped_404_count", "skipped_tile_count", default=0),
                "error_count": _manifest_value(manifest, "error_count", "error_tile_count", default=0),
                "pano_record_count": manifest.get("pano_record_count", 0),
                "vector_feature_record_count": _manifest_value(
                    manifest,
                    "vector_feature_record_count",
                    "feature_record_count",
                    default=0,
                ),
                "total_coverage_pixels": manifest.get("total_coverage_pixels", 0),
                "total_pixels": manifest.get("total_pixels", 0),
                "aggregate_coverage_ratio": manifest.get("aggregate_coverage_ratio"),
                "manifest_path": str(manifest_path),
            }
        )
    return rows


def maybe_dataframe(rows: list[dict]):
    try:
        import pandas as pd
    except Exception:
        return rows
    return pd.DataFrame(rows)


def _manifest_value(manifest: dict, *keys: str, default=0):
    for key in keys:
        if key in manifest:
            return manifest[key]
    return default


def infer_source_kind(manifest: dict) -> str:
    if "pano_records_path" in manifest:
        return "coverage_json"
    if "feature_records_path" in manifest or "vector_feature_records_path" in manifest:
        return "vector_mvt"
    return "raster"

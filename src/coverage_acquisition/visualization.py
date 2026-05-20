from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from PIL import Image

from coverage_acquisition.geo import tile_to_lonlat_bounds_for_scheme
from coverage_acquisition.io_utils import load_json, read_csv_rows
from coverage_acquisition.models import BoundingBox


PROVIDER_COLORS = {
    "apple_lookaround": "#1f78b4",
    "apple_lookaround_bluelines_layered": "#1f78b4",
    "svmap_google": "#e66101",
    "svmap_google_mts_raster": "#e66101",
    "kartaview": "#5e3c99",
    "kartaview_coverage_raster": "#5e3c99",
    "panoramax": "#4daf4a",
    "panoramax_mvt_coverage": "#4daf4a",
    "mapillary": "#d01c8b",
    "mapillary_mvt_coverage": "#d01c8b",
    "baidu": "#b15928",
    "baidu_mapsv_raster": "#b15928",
    "yandex": "#1f9d8a",
    "yandex_stv_raster": "#1f9d8a",
}


def load_result_from_manifest(manifest_path: str | Path) -> dict:
    manifest_path = Path(manifest_path)
    manifest = load_json(manifest_path)
    result_dir = manifest_path.parent
    return {
        "output_dir": str(result_dir),
        "manifest_path": str(manifest_path),
        "tile_summary_path": str(_resolve_path(manifest, "tile_summary_path", result_dir / "tile_summary.csv")),
        "pano_records_path": str(_resolve_path(manifest, "pano_records_path", result_dir / "pano_records.csv")),
        "vector_feature_records_path": str(
            _resolve_path(
                manifest,
                "vector_feature_records_path",
                manifest.get("feature_records_path", result_dir / "feature_records.csv"),
            )
        ),
        "manifest": manifest,
        "job": {
            "index": manifest.get("job_index", 0),
            "row": manifest.get("job_row", 0),
            "col": manifest.get("job_col", 0),
            "bbox": manifest["bbox"],
            "display_zoom": manifest["display_zoom"],
            "source_zoom": manifest["source_zoom"],
            "run_label": manifest.get("run_label", result_dir.name),
        },
    }


def load_results_from_manifest_paths(manifest_paths: list[str | Path]) -> list[dict]:
    return [load_result_from_manifest(path) for path in manifest_paths]


def summarize_results(results: list[dict]) -> list[dict]:
    rows = []
    for result in results:
        manifest = result["manifest"]
        rows.append(
            {
                "provider": manifest["provider"],
                "source_id": manifest["source_id"],
                "source_kind": manifest.get("source_kind", _infer_source_kind(manifest)),
                "job_index": manifest.get("job_index", 0),
                "display_zoom": manifest["display_zoom"],
                "source_zoom": manifest["source_zoom"],
                "tile_count": manifest.get("tile_count", manifest.get("fetched_tile_count", 0)),
                "pano_record_count": manifest.get("pano_record_count", 0),
                "vector_feature_record_count": manifest.get(
                    "vector_feature_record_count",
                    manifest.get("feature_record_count", 0),
                ),
                "aggregate_coverage_ratio": manifest.get("aggregate_coverage_ratio"),
                "manifest_path": result["manifest_path"],
            }
        )
    return rows


def plot_multi_provider_comparison(
    results: list[dict],
    *,
    job_index: int | None = None,
    ncols: int = 3,
    figsize_per_panel: tuple[float, float] = (5.2, 5.2),
    show_tile_frames: bool = True,
    show_tile_labels: bool = False,
    bbox_pad_fraction: float = 0.0,
    suptitle: str | None = None,
) -> None:
    filtered = [result for result in results if job_index is None or result["job"]["index"] == job_index]
    if not filtered:
        raise ValueError("No results available for the requested comparison.")

    filtered = sorted(filtered, key=lambda item: (_provider_label(item), item["manifest"]["source_id"]))
    n_panels = len(filtered)
    ncols = max(1, min(ncols, n_panels))
    nrows = (n_panels + ncols - 1) // ncols
    figsize = (figsize_per_panel[0] * ncols, figsize_per_panel[1] * nrows)
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False)
    axes_flat = list(axes.flat)

    bbox = BoundingBox.from_mapping(filtered[0]["job"]["bbox"])
    for ax, result in zip(axes_flat, filtered):
        plot_single_result(
            result,
            ax=ax,
            bbox=bbox,
            show_tile_frames=show_tile_frames,
            show_tile_labels=show_tile_labels,
            bbox_pad_fraction=bbox_pad_fraction,
        )

    for ax in axes_flat[n_panels:]:
        ax.axis("off")

    if suptitle is None:
        job_value = filtered[0]["job"]["index"]
        display_zoom = filtered[0]["job"]["display_zoom"]
        suptitle = f"Coverage comparison | job={job_value} | display z{display_zoom}"
    fig.suptitle(suptitle)
    plt.tight_layout()
    plt.show()


def plot_single_result(
    result: dict,
    *,
    ax,
    bbox: BoundingBox | None = None,
    show_tile_frames: bool = True,
    show_tile_labels: bool = False,
    bbox_pad_fraction: float = 0.0,
) -> None:
    manifest = result["manifest"]
    tile_rows = read_csv_rows(Path(result["tile_summary_path"]))
    pano_rows = read_csv_rows(Path(result["pano_records_path"]))
    feature_rows = read_csv_rows(Path(result["vector_feature_records_path"]))
    bbox = bbox or BoundingBox.from_mapping(result["job"]["bbox"])

    provider_label = _provider_label(result)
    color = PROVIDER_COLORS.get(manifest["provider"], PROVIDER_COLORS.get(provider_label, "#333333"))
    source_kind = manifest.get("source_kind", _infer_source_kind(manifest))
    tile_grid_projection = manifest.get("tile_grid_projection", "web_mercator")

    ax.set_title(
        f"{provider_label}\n{manifest['source_id']} | {source_kind} | "
        f"tiles={len(tile_rows)} feats={len(feature_rows)} panos={len(pano_rows)}",
        fontsize=10,
    )

    bbox_width = bbox.max_lon - bbox.min_lon
    bbox_height = bbox.max_lat - bbox.min_lat
    ax.add_patch(
        Rectangle(
            (bbox.min_lon, bbox.min_lat),
            bbox_width,
            bbox_height,
            fill=False,
            edgecolor="black",
            linewidth=2.0,
            linestyle="--",
        )
    )

    for row in tile_rows:
        x = int(row["x"])
        y = int(row["y"])
        z = int(row["source_zoom"])
        lon_min, lat_min, lon_max, lat_max = tile_to_lonlat_bounds_for_scheme(x, y, z, tile_grid_projection)

        if source_kind == "raster" and row.get("output_path"):
            overlay = _mask_overlay_rgba(Path(row["output_path"]), color)
            ax.imshow(overlay, extent=[lon_min, lon_max, lat_min, lat_max], origin="upper")

        if show_tile_frames:
            ax.add_patch(
                Rectangle(
                    (lon_min, lat_min),
                    lon_max - lon_min,
                    lat_max - lat_min,
                    fill=False,
                    edgecolor=color,
                    linewidth=0.8,
                    alpha=0.5,
                )
            )
        if show_tile_labels:
            ax.text(
                (lon_min + lon_max) / 2,
                (lat_min + lat_max) / 2,
                f"{x},{y}",
                fontsize=7,
                ha="center",
                va="center",
                color=color,
            )

    if feature_rows:
        for row in feature_rows:
            _plot_wkt(ax, row.get("geometry_wkt", ""), color=color)

    if pano_rows:
        lons = [float(row["lon"]) for row in pano_rows if row.get("lon")]
        lats = [float(row["lat"]) for row in pano_rows if row.get("lat")]
        if lons and lats:
            ax.scatter(lons, lats, s=12, c=color, alpha=0.75)

    pad_lon = max(bbox_width * bbox_pad_fraction, 0.0)
    pad_lat = max(bbox_height * bbox_pad_fraction, 0.0)
    ax.set_xlim(bbox.min_lon - pad_lon, bbox.max_lon + pad_lon)
    ax.set_ylim(bbox.min_lat - pad_lat, bbox.max_lat + pad_lat)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(alpha=0.25)
    ax.set_aspect("equal", adjustable="box")


def maybe_dataframe(rows: list[dict]):
    try:
        import pandas as pd
    except Exception:
        return rows
    return pd.DataFrame(rows)


def _provider_label(result: dict) -> str:
    provider = result["manifest"]["provider"]
    mapping = {
        "apple_lookaround_bluelines_layered": "apple_lookaround",
        "svmap_google_mts_raster": "svmap_google",
        "kartaview_coverage_raster": "kartaview",
        "panoramax_mvt_coverage": "panoramax",
        "mapillary_mvt_coverage": "mapillary",
        "baidu_mapsv_raster": "baidu",
        "yandex_stv_raster": "yandex",
    }
    return mapping.get(provider, provider)


def _resolve_path(manifest: dict, key: str, fallback: str | Path) -> Path:
    value = manifest.get(key, fallback)
    return Path(value)


def _infer_source_kind(manifest: dict) -> str:
    if "pano_records_path" in manifest:
        return "coverage_json"
    if "feature_records_path" in manifest or "vector_feature_records_path" in manifest:
        return "vector_mvt"
    return "raster"


def _mask_overlay_rgba(path: Path, color: str) -> np.ndarray:
    rgba_color = np.array(_hex_to_rgba(color), dtype=np.uint8)
    with Image.open(path) as image:
        rgba = np.array(image.convert("RGBA"))
    overlay = np.zeros_like(rgba)
    alpha_mask = rgba[:, :, 3] > 0
    overlay[alpha_mask] = rgba_color
    return overlay


def _hex_to_rgba(hex_color: str, alpha: int = 190) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def _plot_wkt(ax, wkt: str, *, color: str) -> None:
    if not wkt:
        return
    wkt = wkt.strip()
    if wkt.startswith("POINT"):
        point = _parse_point_wkt(wkt)
        if point is not None:
            ax.scatter([point[0]], [point[1]], s=10, c=color, alpha=0.8)
        return
    if wkt.startswith("MULTIPOINT"):
        points = _parse_multipoint_wkt(wkt)
        if points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            ax.scatter(xs, ys, s=10, c=color, alpha=0.8)
        return
    for segment in _parse_linestring_wkt(wkt):
        xs = [point[0] for point in segment]
        ys = [point[1] for point in segment]
        ax.plot(xs, ys, color=color, linewidth=1.0, alpha=0.75)


def _parse_point_wkt(wkt: str) -> tuple[float, float] | None:
    if not wkt.startswith("POINT"):
        return None
    body = wkt[wkt.find("(") + 1 : wkt.rfind(")")]
    values = body.strip().split()
    if len(values) != 2:
        return None
    return float(values[0]), float(values[1])


def _parse_multipoint_wkt(wkt: str) -> list[tuple[float, float]]:
    body = wkt[wkt.find("(") + 1 : wkt.rfind(")")]
    body = body.replace("(", "").replace(")", "")
    points = []
    for chunk in body.split(","):
        values = chunk.strip().split()
        if len(values) == 2:
            points.append((float(values[0]), float(values[1])))
    return points


def _parse_linestring_wkt(wkt: str) -> list[list[tuple[float, float]]]:
    if wkt.startswith("LINESTRING"):
        return [_parse_coordinate_series(wkt[wkt.find("(") + 1 : wkt.rfind(")")])]
    if wkt.startswith("MULTILINESTRING"):
        body = wkt[wkt.find("(") + 1 : wkt.rfind(")")]
        segments = []
        for raw_segment in _split_multilinestring_parts(body):
            segments.append(_parse_coordinate_series(raw_segment))
        return [segment for segment in segments if segment]
    if wkt.startswith("POLYGON"):
        body = wkt[wkt.find("((") + 2 : wkt.rfind("))")]
        rings = body.split("),(")
        return [_parse_coordinate_series(ring) for ring in rings]
    return []


def _split_multilinestring_parts(body: str) -> list[str]:
    cleaned = body.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    return [segment for segment in cleaned.split("),(") if segment]


def _parse_coordinate_series(raw_series: str) -> list[tuple[float, float]]:
    raw_series = raw_series.replace("(", " ").replace(")", " ")
    points = []
    for pair in raw_series.split(","):
        values = pair.strip().split()
        if len(values) >= 2:
            points.append((float(values[0]), float(values[1])))
    return points

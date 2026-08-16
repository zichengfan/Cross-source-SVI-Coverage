from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from shapely import wkt
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, Point, Polygon

from coverage_acquisition.geo import tile_to_lonlat_bounds_for_scheme
from coverage_acquisition.models import BoundingBox

DEFAULT_COVERAGE_COLOR = "#256B8A"


def load_result_from_manifest(manifest_path: str | Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result_dir = manifest_path.parent
    return {
        "manifest": manifest,
        "manifest_path": str(manifest_path),
        "output_dir": str(result_dir),
        "tile_summary_path": str(
            _resolve_recorded_path(manifest.get("tile_summary_path"), result_dir / "tile_summary.csv")
        ),
        "pano_records_path": str(
            _resolve_recorded_path(manifest.get("pano_records_path"), result_dir / "pano_records.csv")
        ),
        "vector_feature_records_path": str(
            _resolve_recorded_path(
                manifest.get("vector_feature_records_path") or manifest.get("feature_records_path"),
                result_dir / "feature_records.csv",
            )
        ),
    }


def summarize_result(result: dict) -> dict:
    manifest = result["manifest"]
    return {
        "provider": manifest["provider"],
        "source_id": manifest.get("source_id", ""),
        "source_kind": manifest.get("source_kind", ""),
        "display_zoom": manifest.get("display_zoom"),
        "source_zoom": manifest.get("source_zoom"),
        "tile_count": manifest.get("tile_count", 0),
        "feature_count": manifest.get("vector_feature_record_count", manifest.get("feature_record_count", 0)),
        "pano_count": manifest.get("pano_record_count", 0),
        "coverage_ratio": manifest.get("aggregate_coverage_ratio"),
        "error_count": manifest.get("error_count", 0),
    }


def plot_result(
    ax,
    result: dict,
    *,
    bbox: BoundingBox,
    label: str,
    level_label: str,
    color: str = DEFAULT_COVERAGE_COLOR,
    max_plot_records: int | None = 100_000,
    show_axis_labels: bool = True,
) -> dict:
    from matplotlib.collections import LineCollection

    manifest = result["manifest"]
    tile_rows = _read_csv(Path(result["tile_summary_path"]))
    feature_count = int(manifest.get("vector_feature_record_count", manifest.get("feature_record_count", 0)) or 0)
    pano_count = int(manifest.get("pano_record_count", 0) or 0)
    feature_rows = _read_csv_strided(
        Path(result["vector_feature_records_path"]), max_plot_records, total_hint=feature_count
    )
    pano_rows = _read_csv_strided(Path(result["pano_records_path"]), max_plot_records, total_hint=pano_count)
    source_kind = manifest.get("source_kind", "unknown")

    if source_kind == "raster":
        scheme = manifest.get("tile_grid_projection", "web_mercator")
        for row in tile_rows:
            if not row.get("output_path"):
                continue
            image_path = _resolve_row_path(row["output_path"], Path(result["manifest_path"]).parent)
            if not image_path.exists():
                continue
            bounds = tile_to_lonlat_bounds_for_scheme(int(row["x"]), int(row["y"]), int(row["source_zoom"]), scheme)
            ax.imshow(
                coverage_overlay_rgba(image_path, color),
                extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
                origin="upper",
            )

    points: list[tuple[float, float]] = []
    segments: list[list[tuple[float, float]]] = []
    for row in feature_rows:
        geometry_points, geometry_segments = geometry_parts_from_wkt(row.get("geometry_wkt", ""))
        points.extend(geometry_points)
        segments.extend(geometry_segments)
    for row in pano_rows:
        if row.get("lon") and row.get("lat"):
            points.append((float(row["lon"]), float(row["lat"])))

    if segments:
        ax.add_collection(LineCollection(segments, colors=color, linewidths=0.7, alpha=0.82))
    if points:
        xy = np.asarray(points)
        ax.scatter(xy[:, 0], xy[:, 1], s=2.2, c=color, alpha=0.68, linewidths=0, rasterized=True)

    count = feature_count + pano_count
    subtitle = f"{level_label}; {source_kind}; n={count:,}; tiles={len(tile_rows):,}"
    title = "\n".join(part for part in (label, subtitle) if part)
    style_geo_axis(ax, bbox, title, show_axis_labels=show_axis_labels)
    return {
        "source_kind": source_kind,
        "tile_count": len(tile_rows),
        "record_count": count,
        "plotted_record_count": len(feature_rows) + len(pano_rows),
        "error_count": int(manifest.get("error_count", 0) or 0),
    }


def plot_mappls_segments(
    ax,
    segments: list[list[tuple[float, float]]],
    *,
    bbox: BoundingBox,
    label: str,
    level_label: str,
    color: str = DEFAULT_COVERAGE_COLOR,
) -> None:
    from matplotlib.collections import LineCollection

    if segments:
        ax.add_collection(LineCollection(segments, colors=color, linewidths=0.7, alpha=0.82))
    style_geo_axis(ax, bbox, f"{label}\n{level_label}; vector lines; n={len(segments):,}")


def load_mappls_segments(summary_path: str | Path) -> tuple[BoundingBox, list[list[tuple[float, float]]]]:
    summary_path = Path(summary_path).resolve()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    bbox = BoundingBox.from_sequence(summary["bbox"])
    tile_root = summary_path.parents[1] / "tiles"
    segments: list[list[tuple[float, float]]] = []
    for tile_path in sorted(tile_root.glob(f"{int(summary['zoom'])}/*/*.geojson.gz")):
        with gzip.open(tile_path, "rt", encoding="utf-8") as handle:
            collection = json.load(handle)
        for feature in collection.get("features", []):
            segments.extend(geometry_segments_from_geojson(feature.get("geometry") or {}))
    return bbox, segments


def result_tile_bbox(result: dict) -> BoundingBox:
    manifest = result["manifest"]
    tile_range = manifest.get("source_tile_range") or {}
    required = {"x_min", "x_max", "y_min", "y_max"}
    if not required.issubset(tile_range):
        return BoundingBox.from_mapping(manifest["bbox"])
    zoom = int(manifest["source_zoom"])
    scheme = manifest.get("tile_grid_projection", "web_mercator")
    northwest = tile_to_lonlat_bounds_for_scheme(
        int(tile_range["x_min"]), int(tile_range["y_min"]), zoom, scheme
    )
    southeast = tile_to_lonlat_bounds_for_scheme(
        int(tile_range["x_max"]), int(tile_range["y_max"]), zoom, scheme
    )
    return BoundingBox(
        min_lon=northwest[0],
        min_lat=southeast[1],
        max_lon=southeast[2],
        max_lat=northwest[3],
    )


def style_geo_axis(ax, bbox: BoundingBox, title: str, *, show_axis_labels: bool = True) -> None:
    from matplotlib.ticker import MaxNLocator, ScalarFormatter

    ax.set_xlim(bbox.min_lon, bbox.max_lon)
    ax.set_ylim(bbox.min_lat, bbox.max_lat)
    ax.set_title(title, fontsize=8, pad=4)
    ax.set_xlabel("Longitude" if show_axis_labels else "")
    ax.set_ylabel("Latitude" if show_axis_labels else "")
    ax.xaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
    ax.tick_params(labelsize=5.0)
    ax.grid(color="#D5DDE5", linewidth=0.45, alpha=0.75)
    mean_lat = 0.5 * (bbox.min_lat + bbox.max_lat)
    ax.set_aspect(1 / max(math.cos(math.radians(mean_lat)), 0.2), adjustable="box")


def coverage_overlay_rgba(path: str | Path, color: str = DEFAULT_COVERAGE_COLOR) -> np.ndarray:
    with Image.open(path) as image:
        rgba = np.asarray(image.convert("RGBA"))
    overlay = np.zeros_like(rgba)
    overlay[rgba[:, :, 3] > 0] = _hex_to_rgba(color)
    return overlay


def geometry_parts_from_wkt(value: str) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    if not value:
        return [], []
    try:
        geometry = wkt.loads(value)
    except Exception:
        return [], []
    return _geometry_parts(geometry)


def geometry_segments_from_geojson(geometry: dict) -> list[list[tuple[float, float]]]:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in coordinates]]
    if kind == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in line] for line in coordinates]
    return []


def _geometry_parts(geometry) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    if isinstance(geometry, Point):
        return [(float(geometry.x), float(geometry.y))], []
    if isinstance(geometry, MultiPoint):
        return [(float(point.x), float(point.y)) for point in geometry.geoms], []
    if isinstance(geometry, LineString):
        return [], [[(float(x), float(y)) for x, y, *_ in geometry.coords]]
    if isinstance(geometry, MultiLineString):
        return [], [[(float(x), float(y)) for x, y, *_ in line.coords] for line in geometry.geoms]
    if isinstance(geometry, Polygon):
        segments = [[(float(x), float(y)) for x, y, *_ in geometry.exterior.coords]]
        segments.extend([[(float(x), float(y)) for x, y, *_ in ring.coords] for ring in geometry.interiors])
        return [], segments
    if isinstance(geometry, GeometryCollection):
        points: list[tuple[float, float]] = []
        segments: list[list[tuple[float, float]]] = []
        for part in geometry.geoms:
            part_points, part_segments = _geometry_parts(part)
            points.extend(part_points)
            segments.extend(part_segments)
        return points, segments
    return [], []


def _resolve_recorded_path(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback.resolve()
    path = Path(value)
    if path.is_absolute():
        return path
    relative_to_manifest = fallback.parent / path
    if relative_to_manifest.exists():
        return relative_to_manifest.resolve()
    return path.resolve()


def _resolve_row_path(value: str, result_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else result_dir / path


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_csv_strided(path: Path, max_rows: int | None, *, total_hint: int = 0) -> list[dict]:
    if not path.exists():
        return []
    if max_rows is None or max_rows <= 0 or total_hint <= max_rows:
        return _read_csv(path)
    stride = max(1, math.ceil(total_hint / max_rows))
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row for index, row in enumerate(csv.DictReader(handle)) if index % stride == 0][:max_rows]


def _hex_to_rgba(color: str, alpha: int = 190) -> tuple[int, int, int, int]:
    value = color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha

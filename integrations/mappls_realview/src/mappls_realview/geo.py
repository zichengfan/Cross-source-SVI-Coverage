from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

from .bbox import BBox


def write_feature_collection(
    features: list[dict],
    path: str | Path,
    *,
    atomic: bool = False,
) -> Path:
    """Write a GeoJSON FeatureCollection, optionally gzip-compressed.

    A ``.gz`` suffix selects deterministic gzip output. Atomic writes keep a
    partially written tile from being mistaken for a completed production
    artifact after an interrupted capture.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = {"type": "FeatureCollection", "features": features}
    payload = json.dumps(fc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    target = path.with_name(f".{path.name}.tmp") if atomic else path
    if path.suffix == ".gz":
        with target.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                compressed.write(payload)
    else:
        target.write_bytes(payload)
    if atomic:
        os.replace(target, path)
    return path


def optimize_tile_features(features: list[dict], coordinate_precision: int = 7) -> list[dict]:
    """Return lean production features without redundant per-feature tile metadata."""

    def round_coordinates(value):
        if isinstance(value, list):
            return [round_coordinates(item) for item in value]
        if isinstance(value, float):
            return round(value, coordinate_precision)
        return value

    optimized: list[dict] = []
    for feature in features:
        properties = dict(feature.get("properties") or {})
        for key in ("_tile_z", "_tile_x", "_tile_y", "_mvt_layer"):
            properties.pop(key, None)
        geometry = dict(feature.get("geometry") or {})
        if "coordinates" in geometry:
            geometry["coordinates"] = round_coordinates(geometry["coordinates"])
        optimized.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": geometry,
            }
        )
    return optimized


def clip_features(features: list[dict], bbox: BBox) -> list[dict]:
    from shapely.geometry import box, mapping, shape

    clipper = box(bbox.west, bbox.south, bbox.east, bbox.north)
    out: list[dict] = []
    for f in features:
        g = f.get("geometry")
        if not g:
            continue
        geom = shape(g)
        if geom.is_empty or not geom.intersects(clipper):
            continue
        clipped = geom.intersection(clipper)
        if clipped.is_empty:
            continue
        ff = {"type": "Feature", "properties": dict(f.get("properties") or {}), "geometry": mapping(clipped)}
        out.append(ff)
    return out

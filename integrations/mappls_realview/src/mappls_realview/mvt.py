from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def _tile_coord_to_lonlat(tx: float, ty: float, z: int, x: int, y: int, extent: float) -> list[float]:
    n = 2**z
    gx = (x + tx / extent) / n
    gy = (y + ty / extent) / n
    lon = gx * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * gy))))
    return [lon, lat]


def _transform_coords(coords: Any, z: int, x: int, y: int, extent: float) -> Any:
    if not isinstance(coords, (list, tuple)):
        return coords
    if len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
        return _tile_coord_to_lonlat(float(coords[0]), float(coords[1]), z, x, y, extent)
    return [_transform_coords(c, z, x, y, extent) for c in coords]


def decode_pbf_to_features(
    pbf_path: str | Path,
    z: int,
    x: int,
    y: int,
    layer_regex: str | None = None,
    geometry_types: set[str] | None = None,
) -> list[dict]:
    import re

    import mapbox_vector_tile

    raw = Path(pbf_path).read_bytes()
    # Keep MVT's original top-left tile coordinate convention so our explicit
    # z/x/y -> WGS84 transform is deterministic.
    try:
        tile = mapbox_vector_tile.decode(raw, default_options={"y_coord_down": True})
    except TypeError:
        # Older package versions may not accept default_options. This fallback
        # can mirror Y; validate visually before using it for analysis.
        tile = mapbox_vector_tile.decode(raw)

    layer_rx = re.compile(layer_regex, re.I) if layer_regex else None
    out: list[dict] = []

    for layer_name, layer in tile.items():
        if layer_rx and not layer_rx.search(layer_name):
            continue
        extent = float(layer.get("extent") or 4096)
        for f in layer.get("features", []):
            geom = f.get("geometry") or {}
            gtype = geom.get("type")
            if geometry_types and gtype not in geometry_types:
                continue
            coords = _transform_coords(geom.get("coordinates"), z, x, y, extent)
            props = dict(f.get("properties") or {})
            props.update(
                {
                    "_mvt_layer": layer_name,
                    "_tile_z": z,
                    "_tile_x": x,
                    "_tile_y": y,
                }
            )
            if f.get("id") is not None:
                props["_mvt_id"] = f.get("id")
            out.append(
                {
                    "type": "Feature",
                    "properties": props,
                    "geometry": {"type": gtype, "coordinates": coords},
                }
            )
    return out


def inspect_pbf(pbf_path: str | Path) -> dict:
    import mapbox_vector_tile

    raw = Path(pbf_path).read_bytes()
    try:
        tile = mapbox_vector_tile.decode(raw, default_options={"y_coord_down": True})
    except TypeError:
        tile = mapbox_vector_tile.decode(raw)

    summary: dict = {"size_bytes": len(raw), "layers": {}}
    for name, layer in tile.items():
        geom: dict[str, int] = {}
        keys: set[str] = set()
        for f in layer.get("features", []):
            gt = (f.get("geometry") or {}).get("type", "UNKNOWN")
            geom[gt] = geom.get(gt, 0) + 1
            keys.update((f.get("properties") or {}).keys())
        summary["layers"][name] = {
            "extent": layer.get("extent"),
            "version": layer.get("version"),
            "feature_count": len(layer.get("features", [])),
            "geometry_types": geom,
            "property_keys": sorted(keys),
            "identifier_fields_present": sorted(keys & {"street_id", "trip_id"}),
        }
    return summary

"""`vector_geojson` source kind — coverage served as per-tile GeoJSON.

Each tile is a GeoJSON ``FeatureCollection``. Every feature becomes a vector
feature record (same shape as ``vector_mvt``), so the rasterize stage consumes
the WKT geometries identically.

Two optional ``source.options`` adapt the kind to sources whose tiles are not
RFC-7946-clean:

- ``geojson_lon_property`` / ``geojson_lat_property``: when both are set, a
  feature's point location is taken from those numeric *properties* instead of
  its geometry coordinates. This is required by sources (e.g. ASIG) that render
  tiles in tile-local pixel space but carry true WGS84 lon/lat as properties.
- ``geojson_geometry_types``: a comma-separated allow-list of GeoJSON geometry
  types to emit; features of other types are dropped. Lets a source keep only
  its ``Point`` photo-centers and ignore pixel-space decoration lines.

With no options set, the kind decodes a standards-compliant GeoJSON tile: every
feature is emitted using its own geometry coordinates.
"""

from __future__ import annotations

import json

from shapely.geometry import Point, shape

from coverage_acquisition.io_utils import ensure_directory, maybe_gzip_decompress
from coverage_acquisition.source_kinds._base import (
    DecodeContext,
    DecodeResult,
    register_source_kind,
    tile_storage_path,
)


def _allowed_geometry_types(options: dict[str, str]) -> set[str] | None:
    raw = options.get("geojson_geometry_types", "").strip()
    if not raw:
        return None
    return {part.strip() for part in raw.split(",") if part.strip()}


def _point_from_properties(properties: dict, lon_key: str, lat_key: str) -> Point | None:
    if lon_key not in properties or lat_key not in properties:
        return None
    try:
        return Point(float(properties[lon_key]), float(properties[lat_key]))
    except (TypeError, ValueError):
        return None


def decode_vector_geojson(ctx: DecodeContext) -> DecodeResult:
    result = DecodeResult()
    stored_payload, was_gzip = maybe_gzip_decompress(ctx.wire_payload)
    result.stored_payload = stored_payload
    result.was_gzip_compressed = was_gzip

    collection = json.loads(stored_payload.decode("utf-8"))
    tile_path = tile_storage_path(ctx, ".geojson")
    ensure_directory(tile_path.parent)
    tile_path.write_text(json.dumps(collection, indent=2, sort_keys=True), encoding="utf-8")
    result.tile_path = tile_path

    options = ctx.source.options
    lon_key = options.get("geojson_lon_property", "").strip()
    lat_key = options.get("geojson_lat_property", "").strip()
    use_properties = bool(lon_key and lat_key)
    allowed_types = _allowed_geometry_types(options)

    records: list[dict] = []
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type", "")
        if allowed_types is not None and geometry_type not in allowed_types:
            continue

        properties = feature.get("properties") or {}
        emitted_geometry = None
        if use_properties:
            emitted_geometry = _point_from_properties(properties, lon_key, lat_key)
        if emitted_geometry is None:
            if not geometry.get("coordinates"):
                continue
            emitted_geometry = shape(geometry)

        records.append(
            {
                "provider": ctx.provider.key,
                "source_id": ctx.source.id,
                "display_zoom": ctx.job["display_zoom"],
                "source_zoom": ctx.job["source_zoom"],
                "tile_x": ctx.x,
                "tile_y": ctx.y,
                "tile_url": ctx.tile_url,
                "layer_name": "",
                "feature_index": len(records),
                "mvt_id": feature.get("id", ""),
                "geometry_type": emitted_geometry.geom_type,
                "properties_json": json.dumps(properties, sort_keys=True),
                "geometry_wkt": emitted_geometry.wkt,
                "fetched_at": ctx.fetched_at,
            }
        )

    result.vector_feature_records = records
    result.feature_count = len(records)
    result.record_count = len(records)
    result.is_empty = len(records) == 0
    return result


register_source_kind("vector_geojson", decode_vector_geojson)

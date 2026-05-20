from __future__ import annotations

import ast
import importlib.metadata
import json
import re
from functools import lru_cache
from pathlib import Path

from google.protobuf import descriptor_pool, message_factory


MVT_CMD_MOVE_TO = 1
MVT_CMD_LINE_TO = 2
MVT_CMD_SEG_END = 7

MVT_POINT = 1
MVT_LINESTRING = 2
MVT_POLYGON = 3


@lru_cache(maxsize=1)
def load_vector_tile_message_class():
    try:
        distribution = importlib.metadata.distribution("mapbox_vector_tile")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("mapbox_vector_tile package is required for locating vector_tile protobuf schema files.") from exc

    source_path = None
    for file in distribution.files or []:
        candidate = Path(str(file))
        if candidate.as_posix().endswith("Mapbox/vector_tile_p3_pb2.py"):
            source_path = distribution.locate_file(file)
            break

    if source_path is None:
        raise RuntimeError("Could not locate Mapbox/vector_tile_p3_pb2.py in mapbox_vector_tile distribution.")

    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()

    match = re.search(r"serialized_pb=(b'.*?')\n\)", source, re.S)
    if not match:
        raise RuntimeError(f"Could not locate serialized_pb descriptor bytes in {source_path}.")

    serialized_pb = ast.literal_eval(match.group(1))
    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(serialized_pb)
    tile_descriptor = pool.FindMessageTypeByName("mapnik.vector.tile")
    if hasattr(message_factory, "GetMessageClass"):
        return message_factory.GetMessageClass(tile_descriptor)
    return message_factory.MessageFactory(pool).GetPrototype(tile_descriptor)


def parse_value(val) -> object:
    for candidate in (
        "bool_value",
        "double_value",
        "float_value",
        "int_value",
        "sint_value",
        "string_value",
        "uint_value",
    ):
        if val.HasField(candidate):
            return getattr(val, candidate)
    return None


def zig_zag_decode(n: int) -> int:
    return (n >> 1) ^ (-(n & 1))


def parse_geometry(geom, ftype: int) -> dict:
    i = 0
    coords = []
    parts = []
    dx = 0
    dy = 0

    def ensure_polygon_closed(points: list[list[int]]) -> None:
        if points and points[0] != points[-1]:
            points.append(points[0])

    while i != len(geom):
        item = geom[i]
        cmd = item & 0x7
        cmd_len = item >> 3
        i += 1

        if cmd == MVT_CMD_SEG_END:
            if ftype == MVT_POLYGON:
                ensure_polygon_closed(coords)
            parts.append(coords)
            coords = []
        elif cmd in (MVT_CMD_MOVE_TO, MVT_CMD_LINE_TO):
            if coords and cmd == MVT_CMD_MOVE_TO and ftype in (MVT_LINESTRING, MVT_POLYGON):
                if ftype == MVT_POLYGON:
                    ensure_polygon_closed(coords)
                parts.append(coords)
                coords = []

            for _ in range(cmd_len):
                x = zig_zag_decode(geom[i])
                y = zig_zag_decode(geom[i + 1])
                i += 2
                x += dx
                y += dy
                dx = x
                dy = y
                coords.append([x, y])
        else:
            raise RuntimeError(f"Unsupported MVT geometry command: {cmd}")

    if ftype == MVT_POINT:
        if len(coords) == 1:
            return {"type": "Point", "coordinates": coords[0]}
        return {"type": "MultiPoint", "coordinates": coords}

    if ftype == MVT_LINESTRING:
        if parts:
            if coords:
                parts.append(coords)
            if len(parts) == 1:
                return {"type": "LineString", "coordinates": parts[0]}
            return {"type": "MultiLineString", "coordinates": parts}
        return {"type": "LineString", "coordinates": coords}

    if ftype == MVT_POLYGON:
        if coords:
            parts.append(coords)
        return {"type": "Polygon", "coordinates": parts}

    return {"type": "Unknown", "coordinates": coords}


def decode_tile(payload: bytes) -> dict:
    tile_cls = load_vector_tile_message_class()
    tile = tile_cls()
    tile.ParseFromString(payload)

    decoded = {}
    for layer in tile.layers:
        features = []
        for feature in layer.features:
            props = {}
            tags = list(feature.tags)
            for key_idx, val_idx in zip(tags[::2], tags[1::2]):
                props[layer.keys[key_idx]] = parse_value(layer.values[val_idx])

            features.append(
                {
                    "id": feature.id,
                    "geometry": parse_geometry(feature.geometry, feature.type),
                    "properties": props,
                }
            )

        decoded[layer.name] = {
            "extent": layer.extent,
            "version": layer.version,
            "feature_count": len(features),
            "features": features,
        }
    return decoded


def tile_point_to_lonlat(tile_x: int, tile_y: int, zoom: int, extent: int, point: list[float]) -> tuple[float, float]:
    world_size = extent * (2**zoom)
    world_x = tile_x * extent + point[0]
    world_y = tile_y * extent + point[1]
    lon = world_x / world_size * 360.0 - 180.0
    lat = _mercator_y_to_lat(world_y / world_size)
    return lon, lat


def transform_geometry_to_lonlat(geometry: dict, tile_x: int, tile_y: int, zoom: int, extent: int) -> dict:
    geometry_type = geometry.get("type", "Unknown")
    coords = geometry.get("coordinates", [])

    if geometry_type == "Point":
        lon, lat = tile_point_to_lonlat(tile_x, tile_y, zoom, extent, coords)
        return {"type": "Point", "coordinates": [lon, lat]}

    if geometry_type == "MultiPoint":
        return {
            "type": "MultiPoint",
            "coordinates": [
                list(tile_point_to_lonlat(tile_x, tile_y, zoom, extent, point))
                for point in coords
            ],
        }

    if geometry_type == "LineString":
        return {
            "type": "LineString",
            "coordinates": [
                list(tile_point_to_lonlat(tile_x, tile_y, zoom, extent, point))
                for point in coords
            ],
        }

    if geometry_type == "MultiLineString":
        return {
            "type": "MultiLineString",
            "coordinates": [
                [
                    list(tile_point_to_lonlat(tile_x, tile_y, zoom, extent, point))
                    for point in line
                ]
                for line in coords
            ],
        }

    if geometry_type == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    list(tile_point_to_lonlat(tile_x, tile_y, zoom, extent, point))
                    for point in ring
                ]
                for ring in coords
            ],
        }

    return {"type": geometry_type, "coordinates": coords}


def geometry_to_wkt(geometry: dict) -> str:
    geometry_type = geometry.get("type", "Unknown")
    coords = geometry.get("coordinates", [])

    def fmt_point(point: list[float]) -> str:
        return f"{point[0]:.8f} {point[1]:.8f}"

    if geometry_type == "Point":
        return f"POINT ({fmt_point(coords)})"
    if geometry_type == "MultiPoint":
        inner = ", ".join(f"({fmt_point(point)})" for point in coords)
        return f"MULTIPOINT ({inner})"
    if geometry_type == "LineString":
        inner = ", ".join(fmt_point(point) for point in coords)
        return f"LINESTRING ({inner})"
    if geometry_type == "MultiLineString":
        inner = ", ".join(
            "(" + ", ".join(fmt_point(point) for point in line) + ")"
            for line in coords
        )
        return f"MULTILINESTRING ({inner})"
    if geometry_type == "Polygon":
        inner = ", ".join(
            "(" + ", ".join(fmt_point(point) for point in ring) + ")"
            for ring in coords
        )
        return f"POLYGON ({inner})"
    return ""


def feature_rows_from_decoded_tile(
    *,
    decoded_tile: dict,
    provider: str,
    source_id: str,
    display_zoom: int,
    source_zoom: int,
    tile_x: int,
    tile_y: int,
    tile_url: str,
    fetched_at: str,
) -> tuple[list[dict], dict[str, int]]:
    feature_records = []
    layer_counts = {
        layer_name: layer_payload.get("feature_count", 0)
        for layer_name, layer_payload in decoded_tile.items()
    }

    for layer_name, layer_payload in decoded_tile.items():
        extent = int(layer_payload.get("extent", 4096) or 4096)
        for feature_index, feature in enumerate(layer_payload.get("features", [])):
            lonlat_geometry = transform_geometry_to_lonlat(
                feature.get("geometry", {}),
                tile_x=tile_x,
                tile_y=tile_y,
                zoom=source_zoom,
                extent=extent,
            )
            feature_records.append(
                {
                    "provider": provider,
                    "source_id": source_id,
                    "display_zoom": display_zoom,
                    "source_zoom": source_zoom,
                    "tile_x": tile_x,
                    "tile_y": tile_y,
                    "tile_url": tile_url,
                    "layer_name": layer_name,
                    "feature_index": feature_index,
                    "mvt_id": feature.get("id", ""),
                    "geometry_type": lonlat_geometry.get("type", "Unknown"),
                    "properties_json": json.dumps(feature.get("properties", {}), sort_keys=True),
                    "geometry_wkt": geometry_to_wkt(lonlat_geometry),
                    "fetched_at": fetched_at,
                }
            )
    return feature_records, layer_counts


def _mercator_y_to_lat(y_fraction: float) -> float:
    import math

    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y_fraction))))

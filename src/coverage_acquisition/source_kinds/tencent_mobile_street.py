"""`tencent_mobile_street` source kind for Tencent Maps TXVN coverage tiles."""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass

from coverage_acquisition.geo import (
    TENCENT_COMPRESS_LEVELS,
    gcj02_to_wgs84,
    tencent_pixel_to_gcj02,
    tencent_point_multiplier,
    tencent_tile_size,
)
from coverage_acquisition.io_utils import ensure_directory
from coverage_acquisition.source_kinds._base import (
    DecodeContext,
    DecodeResult,
    register_source_kind,
    tile_storage_path,
)

TXVN_HEADER_SIZE = 30
TXVN_SIGNATURE = b"TXVN"
_ABSOLUTE_POINT_MARKER = 127


@dataclass(frozen=True)
class TxvnHeader:
    idx: int
    level: int
    tile_index: int
    signature: bytes
    date: int
    file_offset: int
    unknown: int
    body_size: int
    trailer: bytes

    @property
    def body_offset(self) -> int:
        return TXVN_HEADER_SIZE


@dataclass(frozen=True)
class TxvnTile:
    header: TxvnHeader
    inflated_body: bytes
    linestrings: list[list[tuple[float, float]]]

    @property
    def is_empty(self) -> bool:
        return not self.linestrings


def parse_txvn_header(payload: bytes) -> TxvnHeader:
    if len(payload) < TXVN_HEADER_SIZE:
        raise ValueError(f"TXVN payload too short: {len(payload)} bytes")

    idx, level, tile_index, signature, date, file_offset, unknown, body_size = struct.unpack_from(
        "<iBi4siibi",
        payload,
        0,
    )
    trailer = payload[26:30]
    if signature != TXVN_SIGNATURE:
        raise ValueError(f"Unexpected TXVN signature: {signature!r}")
    if body_size < 0:
        raise ValueError(f"Invalid TXVN body size: {body_size}")
    if len(payload) - body_size != TXVN_HEADER_SIZE:
        raise ValueError(
            f"TXVN body size mismatch: payload={len(payload)} body_size={body_size}"
        )
    return TxvnHeader(
        idx=idx,
        level=level,
        tile_index=tile_index,
        signature=signature,
        date=date,
        file_offset=file_offset,
        unknown=unknown,
        body_size=body_size,
        trailer=trailer,
    )


def inflate_txvn_body(payload: bytes, header: TxvnHeader | None = None) -> bytes:
    header = header or parse_txvn_header(payload)
    body = payload[header.body_offset :]
    if header.body_size <= 7:
        return body
    return zlib.decompress(body)


def _read_absolute_point(body: bytes, offset: int, point_size: int) -> tuple[int, int, int]:
    if point_size == 2:
        return body[offset], body[offset + 1], offset + 2
    if point_size == 3:
        value = body[offset] | (body[offset + 1] << 8) | (body[offset + 2] << 16)
        return value & 0x000FFF, (value & 0xFFF000) >> 12, offset + 3
    raise ValueError(f"Unsupported Tencent absolute point size: {point_size}")


def _decode_point_stream(
    body: bytes,
    offset: int,
    point_count: int,
    point_size: int,
) -> tuple[list[tuple[int, int]], int]:
    if point_count <= 0:
        return [], offset

    x, y, offset = _read_absolute_point(body, offset, point_size)
    points = [(x, y)]
    while len(points) < point_count:
        if body[offset] == _ABSOLUTE_POINT_MARKER:
            x, y, offset = _read_absolute_point(body, offset + 1, point_size)
        else:
            x += struct.unpack_from("<b", body, offset)[0]
            y += struct.unpack_from("<b", body, offset + 1)[0]
            offset += 2
        points.append((x, y))
    return points, offset


def parse_txvn_tile(
    payload: bytes,
    *,
    tile_origin_px: tuple[int, int] = (0, 0),
) -> TxvnTile:
    header = parse_txvn_header(payload)
    inflated_body = inflate_txvn_body(payload, header)
    if header.body_size <= 7:
        return TxvnTile(header=header, inflated_body=inflated_body, linestrings=[])

    body_tile_index, body_level, num_layers = struct.unpack_from("<iBH", inflated_body, 0)
    if body_tile_index != header.tile_index or body_level != header.level:
        raise ValueError("TXVN body header does not match tile header")

    offset = 7
    multiplier = tencent_point_multiplier(header.level)
    compress_level = TENCENT_COMPRESS_LEVELS[header.level - 10]
    point_size = (compress_level + 1) // 4
    origin_x, origin_y = tile_origin_px
    linestrings: list[list[tuple[float, float]]] = []

    for _ in range(num_layers):
        _, feature_count = struct.unpack_from("<HH", inflated_body, offset)
        offset += 4
        features = []
        # Recorded mobile_street fixtures store each feature descriptor as a
        # uint16 point count plus a one-byte feature type/flag.
        for _ in range(feature_count):
            point_count = struct.unpack_from("<H", inflated_body, offset)[0]
            feature_type = inflated_body[offset + 2]
            offset += 3
            features.append((point_count, feature_type))

        layer_point_count = sum(point_count for point_count, _feature_type in features)
        layer_points, offset = _decode_point_stream(inflated_body, offset, layer_point_count, point_size)

        point_offset = 0
        for point_count, _feature_type in features:
            points = layer_points[point_offset : point_offset + point_count]
            point_offset += point_count
            if len(points) < 2:
                continue
            line = []
            for point_x, point_y in points:
                px_x = origin_x + point_x * multiplier
                px_y = origin_y + point_y * multiplier
                gcj_lon, gcj_lat = tencent_pixel_to_gcj02(px_x, px_y)
                line.append(gcj02_to_wgs84(gcj_lon, gcj_lat))
            linestrings.append(line)

    return TxvnTile(header=header, inflated_body=inflated_body, linestrings=linestrings)


def _linestring_wkt(line: list[tuple[float, float]]) -> str:
    coords = ", ".join(f"{lon:.8f} {lat:.8f}" for lon, lat in line)
    return f"LINESTRING ({coords})"


def decode_tencent_mobile_street(ctx: DecodeContext) -> DecodeResult:
    result = DecodeResult(stored_payload=ctx.wire_payload)
    header = parse_txvn_header(ctx.wire_payload)
    tile_size = tencent_tile_size(header.level)
    tile = parse_txvn_tile(ctx.wire_payload, tile_origin_px=(ctx.x * tile_size, ctx.y * tile_size))
    result.is_empty = tile.is_empty
    result.feature_count = len(tile.linestrings)
    result.record_count = result.feature_count
    result.layer_counts_json = json.dumps({"street": len(tile.linestrings)}, sort_keys=True)
    result.last_modified = str(tile.header.date)

    if not tile.is_empty:
        tile_path = tile_storage_path(ctx, ".txvn")
        ensure_directory(tile_path.parent)
        tile_path.write_bytes(ctx.wire_payload)
        result.tile_path = tile_path

    for feature_index, line in enumerate(tile.linestrings):
        result.vector_feature_records.append(
            {
                "provider": ctx.provider.key,
                "source_id": ctx.source.id,
                "display_zoom": ctx.job["display_zoom"],
                "source_zoom": ctx.job["source_zoom"],
                "tile_x": ctx.x,
                "tile_y": ctx.y,
                "tile_url": ctx.tile_url,
                "layer_name": "street",
                "feature_index": feature_index,
                "mvt_id": "",
                "geometry_type": "LineString",
                "properties_json": json.dumps(
                    {"idx": tile.header.idx, "date": tile.header.date, "bl": tile.header.tile_index},
                    sort_keys=True,
                ),
                "geometry_wkt": _linestring_wkt(line),
                "fetched_at": ctx.fetched_at,
            }
        )

    return result


register_source_kind("tencent_mobile_street", decode_tencent_mobile_street)

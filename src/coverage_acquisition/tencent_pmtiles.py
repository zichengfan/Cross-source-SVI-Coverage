from __future__ import annotations

import bisect
import gzip
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from coverage_acquisition.geo import bbox_to_tile_range, gcj02_to_wgs84, iter_tile_coords, wgs84_to_gcj02
from coverage_acquisition.io_utils import ensure_directory, load_json, sha256_bytes, utc_now_iso, write_csv, write_json
from coverage_acquisition.models import BoundingBox
from coverage_acquisition.mvt_decoder import decode_tile, geometry_to_wkt, transform_geometry_to_lonlat

DEFAULT_TENCENT_PMTILES_URL = "https://qq-map.netlify.app/lines.pmtiles"
DEFAULT_LAYER = "sv"
PMTILES_HEADER_LENGTH = 127
PMTILES_INITIAL_FETCH_LENGTH = 16_384
PMTILES_MAGIC = b"PMTiles"
PMTILES_SPEC_VERSION = 3

COMPRESSION_NONE = 1
COMPRESSION_GZIP = 2

TILE_SUMMARY_FIELDS = [
    "provider",
    "source_id",
    "source_kind",
    "display_zoom",
    "source_zoom",
    "x",
    "y",
    "tile_url",
    "http_status",
    "content_type",
    "is_empty",
    "wire_byte_length",
    "stored_byte_length",
    "wire_sha256",
    "stored_sha256",
    "was_gzip_compressed",
    "record_count",
    "feature_count",
    "layer_counts_json",
    "output_path",
    "fetched_at",
]

VECTOR_FEATURE_FIELDS = [
    "provider",
    "source_id",
    "display_zoom",
    "source_zoom",
    "tile_x",
    "tile_y",
    "tile_url",
    "layer_name",
    "feature_index",
    "mvt_id",
    "geometry_type",
    "properties_json",
    "geometry_wkt",
    "fetched_at",
]

PANO_RECORD_FIELDS = [
    "provider",
    "source_id",
    "display_zoom",
    "source_zoom",
    "tile_x",
    "tile_y",
    "tile_url",
    "panoid",
    "lat",
    "lon",
    "timestamp",
    "buildId",
    "coverageType",
    "lastModified",
    "fetched_at",
]


@dataclass(frozen=True)
class PMTilesHeader:
    root_directory_offset: int
    root_directory_length: int
    json_metadata_offset: int
    json_metadata_length: int
    leaf_directory_offset: int
    leaf_directory_length: int
    tile_data_offset: int
    tile_data_length: int
    addressed_tiles_count: int
    tile_entries_count: int
    tile_contents_count: int
    clustered: bool
    internal_compression: int
    tile_compression: int
    tile_type: int
    min_zoom: int
    max_zoom: int
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float
    center_zoom: int
    center_lon: float
    center_lat: float

    def as_dict(self) -> dict:
        return {
            "root_directory_offset": self.root_directory_offset,
            "root_directory_length": self.root_directory_length,
            "json_metadata_offset": self.json_metadata_offset,
            "json_metadata_length": self.json_metadata_length,
            "leaf_directory_offset": self.leaf_directory_offset,
            "leaf_directory_length": self.leaf_directory_length,
            "tile_data_offset": self.tile_data_offset,
            "tile_data_length": self.tile_data_length,
            "addressed_tiles_count": self.addressed_tiles_count,
            "tile_entries_count": self.tile_entries_count,
            "tile_contents_count": self.tile_contents_count,
            "clustered": self.clustered,
            "internal_compression": self.internal_compression,
            "tile_compression": self.tile_compression,
            "tile_type": self.tile_type,
            "min_zoom": self.min_zoom,
            "max_zoom": self.max_zoom,
            "bounds": [self.min_lon, self.min_lat, self.max_lon, self.max_lat],
            "center": [self.center_lon, self.center_lat, self.center_zoom],
        }


@dataclass(frozen=True)
class DirectoryEntry:
    tile_id: int
    offset: int
    length: int
    run_length: int


@dataclass(frozen=True)
class RangeResponse:
    payload: bytes
    etag: str
    archive_length: int | None


class HTTPRangeSource:
    """HTTP byte-range reader with an on-disk immutable range cache."""

    def __init__(self, url: str, cache_dir: Path, timeout_seconds: int = 60):
        self.url = url
        self.cache_dir = Path(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.etag = ""
        self.archive_length: int | None = None
        self.identity_path = self.cache_dir / "source_identity.json"
        ensure_directory(self.cache_dir / "ranges")
        if self.identity_path.exists():
            identity = load_json(self.identity_path)
            if identity.get("source_url") == self.url:
                self.etag = str(identity.get("etag", ""))
                self.archive_length = identity.get("archive_length")

    def get_bytes(self, offset: int, length: int) -> bytes:
        if offset < 0 or length < 1:
            raise ValueError(f"Invalid byte range: offset={offset}, length={length}")

        cache_path = self.cache_dir / "ranges" / f"{offset}-{length}.bin"
        if cache_path.exists() and cache_path.stat().st_size == length:
            return cache_path.read_bytes()

        request = Request(
            self.url,
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Range": f"bytes={offset}-{offset + length - 1}",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            status = getattr(response, "status", response.getcode())
            content_range = response.headers.get("Content-Range", "")
            if status != 206 or not content_range.startswith(f"bytes {offset}-"):
                raise RuntimeError(
                    "PMTiles host did not honor the requested byte range "
                    f"{offset}-{offset + length - 1}: status={status}, Content-Range={content_range!r}"
                )
            payload = response.read()
            etag = response.headers.get("ETag", "")

        if len(payload) != length:
            raise RuntimeError(f"Expected {length} PMTiles bytes, received {len(payload)}.")

        archive_length = _archive_length_from_content_range(content_range)
        if etag:
            self.etag = etag
        if archive_length is not None:
            self.archive_length = archive_length
        write_json(
            self.identity_path,
            {
                "source_url": self.url,
                "etag": self.etag,
                "archive_length": self.archive_length,
                "observed_at": utc_now_iso(),
            },
        )
        cache_path.write_bytes(payload)
        return payload


class PMTilesReader:
    """Minimal PMTiles v3 reader for range-based MVT access."""

    def __init__(self, source: HTTPRangeSource):
        self.source = source
        initial = source.get_bytes(0, PMTILES_INITIAL_FETCH_LENGTH)
        self.header = parse_header(initial[:PMTILES_HEADER_LENGTH])
        self._root_entries = deserialize_directory(
            _decompress_internal(
                _slice_or_fetch(
                    initial,
                    source,
                    self.header.root_directory_offset,
                    self.header.root_directory_length,
                ),
                self.header.internal_compression,
            )
        )
        metadata_payload = _slice_or_fetch(
            initial,
            source,
            self.header.json_metadata_offset,
            self.header.json_metadata_length,
        )
        self.metadata = json.loads(
            _decompress_internal(metadata_payload, self.header.internal_compression).decode("utf-8")
        )

    def get_tile(self, zoom: int, x: int, y: int) -> bytes | None:
        if zoom < self.header.min_zoom or zoom > self.header.max_zoom:
            return None

        tile_id = zxy_to_tile_id(zoom, x, y)
        entries = self._root_entries
        for _ in range(4):
            entry = find_directory_entry(entries, tile_id)
            if entry is None:
                return None
            if entry.run_length > 0:
                wire_payload = self.source.get_bytes(
                    self.header.tile_data_offset + entry.offset,
                    entry.length,
                )
                return _decompress_tile(wire_payload, self.header.tile_compression)

            leaf_payload = self.source.get_bytes(
                self.header.leaf_directory_offset + entry.offset,
                entry.length,
            )
            entries = deserialize_directory(_decompress_internal(leaf_payload, self.header.internal_compression))
        raise RuntimeError(f"PMTiles directory nesting exceeded the supported depth for tile {zoom}/{x}/{y}.")


def fetch_tencent_pmtiles_sv_coverage(
    bbox: BoundingBox,
    *,
    output_root: Path,
    cache_dir: Path,
    source_url: str = DEFAULT_TENCENT_PMTILES_URL,
    layer_name: str = DEFAULT_LAYER,
    source_zoom: int | None = None,
    run_label: str = "tencent_pmtiles_sv_subbox_00",
    timeout_seconds: int = 60,
) -> dict:
    """Fetch Tencent ``sv`` coverage from PMTiles and write WGS84 feature records.

    The PMTiles MVT coordinates are GCJ-02 numeric coordinates stored in a
    conventional Web Mercator tile pyramid. Tile selection therefore converts
    the WGS84 request bbox to GCJ-02, while decoded feature coordinates are
    converted back to WGS84 exactly once before they are written.
    """

    provider = "tencent_pmtiles_sv"
    source_id = "qq_map_lines_pmtiles_sv"
    fetched_at = utc_now_iso()
    reader = PMTilesReader(HTTPRangeSource(source_url, cache_dir, timeout_seconds))
    zoom = reader.header.max_zoom if source_zoom is None else source_zoom
    if not reader.header.min_zoom <= zoom <= reader.header.max_zoom:
        raise ValueError(
            f"Requested PMTiles zoom {zoom} is outside {reader.header.min_zoom}..{reader.header.max_zoom}."
        )
    if layer_name not in {layer.get("id") for layer in reader.metadata.get("vector_layers", [])}:
        raise ValueError(f"Layer {layer_name!r} is not present in the PMTiles vector_layers metadata.")

    source_bbox = _wgs84_bbox_to_gcj02(bbox)
    tile_range = bbox_to_tile_range(source_bbox, zoom)
    output_dir = Path(output_root) / provider / run_label
    tile_dir = output_dir / "tiles"
    ensure_directory(tile_dir)

    tile_rows: list[dict] = []
    feature_rows: list[dict] = []
    for tile_x, tile_y in iter_tile_coords(tile_range):
        tile_url = f"pmtiles://{source_url}#/{zoom}/{tile_x}/{tile_y}"
        tile_payload = reader.get_tile(zoom, tile_x, tile_y)
        if tile_payload is None:
            continue

        decoded = decode_tile(tile_payload)
        selected_layer = decoded.get(layer_name)
        if selected_layer is None:
            continue

        tile_path = tile_dir / str(zoom) / str(tile_x) / f"{tile_y}.mvt"
        ensure_directory(tile_path.parent)
        tile_path.write_bytes(tile_payload)

        extent = int(selected_layer.get("extent", 4096) or 4096)
        tile_feature_count = 0
        for feature_index, feature in enumerate(selected_layer.get("features", [])):
            gcj_geometry = transform_geometry_to_lonlat(
                feature.get("geometry", {}),
                tile_x=tile_x,
                tile_y=tile_y,
                zoom=zoom,
                extent=extent,
            )
            wgs84_geometry = geometry_gcj02_to_wgs84(gcj_geometry)
            feature_rows.append(
                {
                    "provider": provider,
                    "source_id": source_id,
                    "display_zoom": zoom,
                    "source_zoom": zoom,
                    "tile_x": tile_x,
                    "tile_y": tile_y,
                    "tile_url": tile_url,
                    "layer_name": layer_name,
                    "feature_index": feature_index,
                    "mvt_id": feature.get("id", ""),
                    "geometry_type": wgs84_geometry.get("type", "Unknown"),
                    "properties_json": json.dumps(feature.get("properties", {}), sort_keys=True),
                    "geometry_wkt": geometry_to_wkt(wgs84_geometry),
                    "fetched_at": fetched_at,
                }
            )
            tile_feature_count += 1

        tile_rows.append(
            {
                "provider": provider,
                "source_id": source_id,
                "source_kind": "vector_mvt",
                "display_zoom": zoom,
                "source_zoom": zoom,
                "x": tile_x,
                "y": tile_y,
                "tile_url": tile_url,
                "http_status": 206,
                "content_type": "application/vnd.mapbox-vector-tile",
                "is_empty": tile_feature_count == 0,
                "wire_byte_length": "",
                "stored_byte_length": len(tile_payload),
                "wire_sha256": "",
                "stored_sha256": sha256_bytes(tile_payload),
                "was_gzip_compressed": reader.header.tile_compression == COMPRESSION_GZIP,
                "record_count": tile_feature_count,
                "feature_count": tile_feature_count,
                "layer_counts_json": json.dumps({layer_name: tile_feature_count}, sort_keys=True),
                "output_path": str(tile_path),
                "fetched_at": fetched_at,
            }
        )

    tile_summary_path = output_dir / "tile_summary.csv"
    feature_records_path = output_dir / "feature_records.csv"
    pano_records_path = output_dir / "pano_records.csv"
    write_csv(tile_summary_path, tile_rows, TILE_SUMMARY_FIELDS)
    write_csv(feature_records_path, feature_rows, VECTOR_FEATURE_FIELDS)
    write_csv(pano_records_path, [], PANO_RECORD_FIELDS)

    manifest = {
        "provider": provider,
        "source_id": source_id,
        "source_kind": "vector_mvt",
        "source_url": source_url,
        "source_coordinate_system": "GCJ-02 numeric coordinates in Web Mercator MVT",
        "output_coordinate_system": "WGS84",
        "coordinate_conversion": "GCJ-02 -> WGS84 exactly once after MVT decoding",
        "layer_name": layer_name,
        "bbox": bbox.as_dict(),
        "source_bbox_gcj02": source_bbox.as_dict(),
        "display_zoom": zoom,
        "source_zoom": zoom,
        "tile_grid_projection": "gcj02_web_mercator",
        "source_tile_range": tile_range.as_dict(),
        "tile_count": len(tile_rows),
        "vector_feature_record_count": len(feature_rows),
        "feature_record_count": len(feature_rows),
        "tile_summary_path": str(tile_summary_path),
        "feature_records_path": str(feature_records_path),
        "vector_feature_records_path": str(feature_records_path),
        "pano_records_path": str(pano_records_path),
        "pmtiles_header": reader.header.as_dict(),
        "pmtiles_metadata": reader.metadata,
        "pmtiles_etag": reader.source.etag,
        "pmtiles_archive_length": reader.source.archive_length
        or reader.header.tile_data_offset + reader.header.tile_data_length,
        "fetched_at": fetched_at,
        "job_index": 0,
        "job_row": 0,
        "job_col": 0,
        "run_label": run_label,
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)

    result = {
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "tile_summary_path": str(tile_summary_path),
        "pano_records_path": str(pano_records_path),
        "vector_feature_records_path": str(feature_records_path),
        "feature_records_path": str(feature_records_path),
        "fetched_tiles": tile_rows,
        "feature_records": feature_rows,
        "manifest": manifest,
    }
    return {
        "provider": provider,
        "output_namespace": provider,
        "dry_run": False,
        "jobs": [
            {
                "index": 0,
                "row": 0,
                "col": 0,
                "bbox": bbox.as_dict(),
                "display_zoom": zoom,
                "source_zoom": zoom,
                "source_tile_range": tile_range.as_dict(),
                "source_tile_count": tile_range.count,
                "run_label": run_label,
            }
        ],
        "results": [result],
    }


def parse_header(payload: bytes) -> PMTilesHeader:
    if len(payload) < PMTILES_HEADER_LENGTH:
        raise ValueError(f"PMTiles header needs {PMTILES_HEADER_LENGTH} bytes.")
    if payload[:7] != PMTILES_MAGIC:
        raise ValueError("Not a PMTiles archive.")
    if payload[7] != PMTILES_SPEC_VERSION:
        raise ValueError(f"Unsupported PMTiles version: {payload[7]}.")

    values = struct.unpack_from("<11Q", payload, 8)
    return PMTilesHeader(
        root_directory_offset=values[0],
        root_directory_length=values[1],
        json_metadata_offset=values[2],
        json_metadata_length=values[3],
        leaf_directory_offset=values[4],
        leaf_directory_length=values[5],
        tile_data_offset=values[6],
        tile_data_length=values[7],
        addressed_tiles_count=values[8],
        tile_entries_count=values[9],
        tile_contents_count=values[10],
        clustered=bool(payload[96]),
        internal_compression=payload[97],
        tile_compression=payload[98],
        tile_type=payload[99],
        min_zoom=payload[100],
        max_zoom=payload[101],
        min_lon=struct.unpack_from("<i", payload, 102)[0] / 10_000_000,
        min_lat=struct.unpack_from("<i", payload, 106)[0] / 10_000_000,
        max_lon=struct.unpack_from("<i", payload, 110)[0] / 10_000_000,
        max_lat=struct.unpack_from("<i", payload, 114)[0] / 10_000_000,
        center_zoom=payload[118],
        center_lon=struct.unpack_from("<i", payload, 119)[0] / 10_000_000,
        center_lat=struct.unpack_from("<i", payload, 123)[0] / 10_000_000,
    )


def deserialize_directory(payload: bytes) -> list[DirectoryEntry]:
    position = 0
    count, position = _read_varint(payload, position)
    tile_ids: list[int] = []
    last_tile_id = 0
    for _ in range(count):
        delta, position = _read_varint(payload, position)
        last_tile_id += delta
        tile_ids.append(last_tile_id)

    run_lengths = []
    for _ in range(count):
        value, position = _read_varint(payload, position)
        run_lengths.append(value)

    lengths = []
    for _ in range(count):
        value, position = _read_varint(payload, position)
        lengths.append(value)

    offsets = []
    for index in range(count):
        value, position = _read_varint(payload, position)
        if value == 0 and index > 0:
            offsets.append(offsets[index - 1] + lengths[index - 1])
        else:
            offsets.append(value - 1)

    return [
        DirectoryEntry(
            tile_id=tile_ids[index],
            offset=offsets[index],
            length=lengths[index],
            run_length=run_lengths[index],
        )
        for index in range(count)
    ]


def find_directory_entry(entries: list[DirectoryEntry], tile_id: int) -> DirectoryEntry | None:
    if not entries:
        return None
    index = bisect.bisect_right([entry.tile_id for entry in entries], tile_id) - 1
    if index < 0:
        return None
    entry = entries[index]
    if entry.run_length == 0 or tile_id - entry.tile_id < entry.run_length:
        return entry
    return None


def zxy_to_tile_id(zoom: int, x: int, y: int) -> int:
    if zoom < 0 or zoom > 26:
        raise ValueError("PMTiles v3 tile IDs support zooms 0..26.")
    if x < 0 or y < 0 or x >= 2**zoom or y >= 2**zoom:
        raise ValueError(f"Tile coordinate out of range for z{zoom}: ({x}, {y}).")
    zoom_offset = ((1 << (2 * zoom)) - 1) // 3
    return zoom_offset + _hilbert_xy_to_index(zoom, x, y)


def geometry_gcj02_to_wgs84(geometry: dict) -> dict:
    geometry_type = geometry.get("type", "Unknown")
    coordinates = geometry.get("coordinates", [])

    def convert_point(point) -> list[float]:
        lon, lat = gcj02_to_wgs84(float(point[0]), float(point[1]))
        return [lon, lat]

    if geometry_type == "Point":
        converted = convert_point(coordinates)
    elif geometry_type in {"MultiPoint", "LineString"}:
        converted = [convert_point(point) for point in coordinates]
    elif geometry_type in {"MultiLineString", "Polygon"}:
        converted = [[convert_point(point) for point in part] for part in coordinates]
    else:
        converted = coordinates
    return {"type": geometry_type, "coordinates": converted}


def _wgs84_bbox_to_gcj02(bbox: BoundingBox) -> BoundingBox:
    corners = [wgs84_to_gcj02(lon, lat) for lon in (bbox.min_lon, bbox.max_lon) for lat in (bbox.min_lat, bbox.max_lat)]
    return BoundingBox(
        min_lon=min(point[0] for point in corners),
        min_lat=min(point[1] for point in corners),
        max_lon=max(point[0] for point in corners),
        max_lat=max(point[1] for point in corners),
    )


def _read_varint(payload: bytes, position: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while position < len(payload):
        byte = payload[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, position
        shift += 7
        if shift > 63:
            raise ValueError("PMTiles varint is too large.")
    raise ValueError("Unexpected end of PMTiles directory varint.")


def _hilbert_xy_to_index(zoom: int, x: int, y: int) -> int:
    distance = 0
    scale = 1 << (zoom - 1) if zoom else 0
    while scale > 0:
        rotate_x = 1 if x & scale else 0
        rotate_y = 1 if y & scale else 0
        distance += scale * scale * ((3 * rotate_x) ^ rotate_y)
        if rotate_y == 0:
            if rotate_x == 1:
                x = scale - 1 - x
                y = scale - 1 - y
            x, y = y, x
        scale //= 2
    return distance


def _slice_or_fetch(initial: bytes, source: HTTPRangeSource, offset: int, length: int) -> bytes:
    if offset >= 0 and offset + length <= len(initial):
        return initial[offset : offset + length]
    return source.get_bytes(offset, length)


def _decompress_internal(payload: bytes, compression: int) -> bytes:
    if compression == COMPRESSION_NONE:
        return payload
    if compression == COMPRESSION_GZIP:
        return gzip.decompress(payload)
    raise RuntimeError(f"Unsupported PMTiles internal compression: {compression}.")


def _decompress_tile(payload: bytes, compression: int) -> bytes:
    if compression == COMPRESSION_NONE:
        return payload
    if compression == COMPRESSION_GZIP:
        return gzip.decompress(payload)
    raise RuntimeError(f"Unsupported PMTiles tile compression: {compression}.")


def _archive_length_from_content_range(content_range: str) -> int | None:
    if "/" not in content_range:
        return None
    total = content_range.rsplit("/", 1)[-1]
    if not total.isdigit():
        return None
    return int(total)

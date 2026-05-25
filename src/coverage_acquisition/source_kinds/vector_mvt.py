"""`vector_mvt` source kind — coverage served as Mapbox Vector Tiles."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from coverage_acquisition.io_utils import ensure_directory, maybe_gzip_decompress
from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.mvt_decoder import decode_tile, feature_rows_from_decoded_tile
from coverage_acquisition.source_kinds._base import (
    DecodeContext,
    DecodeResult,
    register_source_kind,
    tile_storage_path,
)


def guess_geometry_type_from_wkt(wkt: str) -> str:
    if not wkt:
        return "Unknown"
    prefix = wkt.strip().split("(", 1)[0].strip().upper()
    mapping = {
        "POINT": "Point",
        "MULTIPOINT": "MultiPoint",
        "LINESTRING": "LineString",
        "MULTILINESTRING": "MultiLineString",
        "POLYGON": "Polygon",
        "MULTIPOLYGON": "MultiPolygon",
    }
    return mapping.get(prefix, prefix.title())


def inspect_vector_layers(tile_path: Path) -> list[str]:
    ogrinfo_path = shutil.which("ogrinfo")
    if not ogrinfo_path:
        raise RuntimeError("ogrinfo is required when vector layer names are not preconfigured.")

    command = [ogrinfo_path, "-ro", "-so", str(tile_path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    layers = []
    for line in result.stdout.splitlines():
        if ": " in line and line[:1].isdigit():
            _, tail = line.split(": ", 1)
            layers.append(tail.split(" (", 1)[0].strip())
    return layers


def _extract_single_layer_rows(*, ogr2ogr_path: str, tile_path: Path, layer_name: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / f"{layer_name}.csv"
        command = [
            ogr2ogr_path,
            "-f",
            "CSV",
            str(csv_path),
            str(tile_path),
            layer_name,
            "-lco",
            "GEOMETRY=AS_WKT",
            "-t_srs",
            "EPSG:4326",
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip() or (exc.stdout or "").strip() or repr(exc)
            raise RuntimeError(f"ogr2ogr failed for {tile_path.name} layer {layer_name}: {detail}") from exc
        if not csv_path.exists():
            return []
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


def extract_vector_records(
    *,
    tile_path: Path,
    payload: bytes,
    source: SourceDefinition,
    provider: ProviderDefinition,
    job: dict,
    x: int,
    y: int,
    tile_url: str,
    fetched_at: str,
) -> tuple[list[dict], dict[str, int]]:
    if source.vector_decoder == "custom_mvt":
        decoded_tile = decode_tile(payload)
        return feature_rows_from_decoded_tile(
            decoded_tile=decoded_tile,
            provider=provider.key,
            source_id=source.id,
            display_zoom=job["display_zoom"],
            source_zoom=job["source_zoom"],
            tile_x=x,
            tile_y=y,
            tile_url=tile_url,
            fetched_at=fetched_at,
        )

    ogr2ogr_path = shutil.which("ogr2ogr")
    if not ogr2ogr_path:
        raise RuntimeError("ogr2ogr is required to decode vector MVT tiles into feature records.")

    layer_names = source.layer_names or tuple(inspect_vector_layers(tile_path))
    all_records = []
    layer_counts: dict[str, int] = {}

    for layer_name in layer_names:
        rows = _extract_single_layer_rows(ogr2ogr_path=ogr2ogr_path, tile_path=tile_path, layer_name=layer_name)
        layer_counts[layer_name] = len(rows)
        for feature_index, row in enumerate(rows):
            geometry_wkt = row.pop("WKT", "")
            mvt_id = row.get("mvt_id", "")
            all_records.append(
                {
                    "provider": provider.key,
                    "source_id": source.id,
                    "display_zoom": job["display_zoom"],
                    "source_zoom": job["source_zoom"],
                    "tile_x": x,
                    "tile_y": y,
                    "tile_url": tile_url,
                    "layer_name": layer_name,
                    "feature_index": feature_index,
                    "mvt_id": mvt_id,
                    "geometry_type": guess_geometry_type_from_wkt(geometry_wkt),
                    "properties_json": json.dumps(row, sort_keys=True),
                    "geometry_wkt": geometry_wkt,
                    "fetched_at": fetched_at,
                }
            )

    return all_records, layer_counts


def decode_vector_mvt(ctx: DecodeContext) -> DecodeResult:
    result = DecodeResult()
    stored_payload, was_gzip = maybe_gzip_decompress(ctx.wire_payload)
    result.stored_payload = stored_payload
    result.was_gzip_compressed = was_gzip

    tile_path = tile_storage_path(ctx, ".mvt")
    ensure_directory(tile_path.parent)
    tile_path.write_bytes(stored_payload)
    result.tile_path = tile_path

    tile_records, layer_counts = extract_vector_records(
        tile_path=tile_path,
        payload=stored_payload,
        source=ctx.source,
        provider=ctx.provider,
        job=ctx.job,
        x=ctx.x,
        y=ctx.y,
        tile_url=ctx.tile_url,
        fetched_at=ctx.fetched_at,
    )
    result.vector_feature_records = tile_records
    result.feature_count = len(tile_records)
    result.record_count = result.feature_count
    result.layer_counts_json = json.dumps(layer_counts, sort_keys=True)
    return result


register_source_kind("vector_mvt", decode_vector_mvt)

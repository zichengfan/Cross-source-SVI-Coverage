"""`coverage_json` source kind — coverage served as JSON pano listings."""

from __future__ import annotations

import json

from coverage_acquisition.io_utils import ensure_directory, maybe_gzip_decompress
from coverage_acquisition.source_kinds._base import (
    DecodeContext,
    DecodeResult,
    register_source_kind,
    tile_storage_path,
)


def decode_coverage_json(ctx: DecodeContext) -> DecodeResult:
    result = DecodeResult()
    stored_payload, was_gzip = maybe_gzip_decompress(ctx.wire_payload)
    result.stored_payload = stored_payload
    result.was_gzip_compressed = was_gzip

    tile_json = json.loads(stored_payload.decode("utf-8"))
    tile_path = tile_storage_path(ctx, ".json")
    ensure_directory(tile_path.parent)
    tile_path.write_text(json.dumps(tile_json, indent=2, sort_keys=True), encoding="utf-8")
    result.tile_path = tile_path

    last_modified = tile_json.get("lastModified", "")
    result.last_modified = last_modified
    panos = tile_json.get("panos", [])
    result.pano_count = len(panos)
    result.record_count = result.pano_count

    for pano in panos:
        result.pano_records.append(
            {
                "provider": ctx.provider.key,
                "source_id": ctx.source.id,
                "display_zoom": ctx.job["display_zoom"],
                "source_zoom": ctx.job["source_zoom"],
                "tile_x": ctx.x,
                "tile_y": ctx.y,
                "tile_url": ctx.tile_url,
                "panoid": pano.get("panoid", ""),
                "lat": pano.get("lat", ""),
                "lon": pano.get("lon", ""),
                "timestamp": pano.get("timestamp", ""),
                "buildId": pano.get("buildId", ""),
                "coverageType": pano.get("coverageType", ""),
                "lastModified": last_modified,
                "fetched_at": ctx.fetched_at,
            }
        )

    return result


register_source_kind("coverage_json", decode_coverage_json)

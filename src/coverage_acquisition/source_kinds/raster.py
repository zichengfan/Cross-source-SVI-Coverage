"""`raster` source kind — coverage served directly as image tiles."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from coverage_acquisition.io_utils import ensure_directory, suffix_for_content_type
from coverage_acquisition.models import SourceDefinition
from coverage_acquisition.source_kinds._base import (
    DecodeContext,
    DecodeResult,
    register_source_kind,
    tile_storage_path,
)


def empty_tile_rule(source: SourceDefinition) -> str | None:
    rule = source.options.get("empty_tile_rule")
    if rule:
        return rule
    if source.options.get("config_kind") == "yandex_stv_renderer":
        return "transparent_png"
    return None


def summarize_png(payload: bytes) -> dict[str, float | int]:
    with Image.open(io.BytesIO(payload)) as image:
        rgba = np.array(image.convert("RGBA"))

    alpha = rgba[:, :, 3]
    coverage_pixel_count = int(np.count_nonzero(alpha))
    total_pixel_count = int(alpha.size)
    coverage_ratio = coverage_pixel_count / total_pixel_count if total_pixel_count else 0.0

    return {
        "width": int(rgba.shape[1]),
        "height": int(rgba.shape[0]),
        "coverage_pixel_count": coverage_pixel_count,
        "total_pixel_count": total_pixel_count,
        "coverage_ratio": coverage_ratio,
    }


def decode_raster(ctx: DecodeContext) -> DecodeResult:
    source = ctx.source
    payload = ctx.wire_payload
    result = DecodeResult(stored_payload=payload)
    rule = empty_tile_rule(source)

    if rule in {"http_204", "transparent_png"} and (ctx.http_status == 204 or not payload):
        result.is_empty = True
        result.stored_payload = b""
    elif source.expect_content_type_prefix and not ctx.content_type.startswith(
        source.expect_content_type_prefix
    ):
        result.skipped = True
        result.skip_record = {
            "provider": ctx.provider.key,
            "source_id": source.id,
            "source_kind": source.kind,
            "display_zoom": ctx.job["display_zoom"],
            "source_zoom": ctx.job["source_zoom"],
            "x": ctx.x,
            "y": ctx.y,
            "tile_url": ctx.tile_url,
            "fetched_at": ctx.fetched_at,
            "content_type": ctx.content_type,
        }
        return result
    else:
        summary = summarize_png(payload)
        result.width = summary["width"]
        result.height = summary["height"]
        result.coverage_pixel_count = summary["coverage_pixel_count"]
        result.total_pixel_count = summary["total_pixel_count"]
        result.coverage_ratio = summary["coverage_ratio"]
        result.is_empty = bool(rule == "transparent_png" and summary["coverage_pixel_count"] == 0)

    if result.is_empty is not True:
        suffix = suffix_for_content_type(ctx.content_type, ctx.tile_url, default=".png")
        tile_path = tile_storage_path(ctx, suffix)
        ensure_directory(tile_path.parent)
        tile_path.write_bytes(payload)
        result.tile_path = tile_path
    else:
        result.tile_path = None

    return result


register_source_kind("raster", decode_raster)

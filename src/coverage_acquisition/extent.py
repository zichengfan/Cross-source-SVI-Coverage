"""Low-zoom coverage discovery utilities for planning z14 provider fetches."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from coverage_acquisition import geo, polite
from coverage_acquisition.models import BoundingBox, SourceDefinition
from coverage_acquisition.providers import get_provider
from coverage_acquisition.source_kinds.raster import summarize_png

CoveragePredicate = Callable[[bytes, str, SourceDefinition], bool]


def discover_coverage_tiles(
    provider_key: str,
    region_bbox: BoundingBox,
    discovery_zoom: int,
    *,
    output_root: str | Path,
    has_coverage: CoveragePredicate | None = None,
) -> list[tuple[int, int]]:
    """Fetch a low-zoom tile sweep and return discovery tiles containing coverage."""
    Path(output_root).mkdir(parents=True, exist_ok=True)
    provider = get_provider(provider_key)
    if not provider.sources:
        raise ValueError(f"Provider has no sources: {provider_key}")

    source = provider.sources[0]
    predicate = has_coverage or _default_has_coverage
    tile_range = geo.tile_range_for_bbox(region_bbox, discovery_zoom, provider.coordinate_scheme)
    covered: list[tuple[int, int]] = []

    for x, y in geo.iter_tile_coords(tile_range):
        url = source.template.format(z=discovery_zoom, x=x, y=y)
        payload, content_type, _status = polite.polite_fetch(url, headers=source.headers)
        if predicate(payload, content_type, source):
            covered.append((x, y))

    return covered


def child_tiles(tile_xy: tuple[int, int], from_zoom: int, to_zoom: int) -> list[tuple[int, int]]:
    """Expand one tile coordinate to all descendants at `to_zoom`."""
    if to_zoom < from_zoom:
        raise ValueError("to_zoom must be greater than or equal to from_zoom.")
    scale = 2 ** (to_zoom - from_zoom)
    x, y = tile_xy
    return [
        (child_x, child_y)
        for child_x in range(x * scale, (x + 1) * scale)
        for child_y in range(y * scale, (y + 1) * scale)
    ]


def _default_has_coverage(payload: bytes, content_type: str, source: SourceDefinition) -> bool:
    if source.kind == "raster" or content_type.startswith("image/png"):
        return int(summarize_png(payload)["coverage_pixel_count"]) > 0
    if source.kind in {"coverage_json", "json_api"} or "json" in content_type:
        return _json_has_records(payload)
    return bool(payload)


def _json_has_records(payload: bytes) -> bool:
    document = json.loads(payload.decode("utf-8"))
    if isinstance(document, list):
        return bool(document)
    if not isinstance(document, dict):
        return bool(document)
    for key in ("features", "panos", "records", "items", "data"):
        value = document.get(key)
        if isinstance(value, list | dict):
            return bool(value)
    return bool(document)

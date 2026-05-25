"""Tencent city/`bl` discovery over the committed streetcfg region table."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coverage_acquisition.discovery_kinds._base import register_discovery_kind
from coverage_acquisition.discovery_kinds.default import _job_run_label, resolve_source_for_display_zoom
from coverage_acquisition.geo import tencent_bl_tiles_for_gcj02_bbox
from coverage_acquisition.models import BoundingBox, FetchAreaRequest, ProviderDefinition, SourceDefinition


@dataclass(frozen=True)
class TencentStreetRegion:
    idx: str
    name: str
    bbox: BoundingBox


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _streetcfg_path(source: SourceDefinition) -> Path:
    configured = source.options.get("streetcfg_path", "data/external/tencent/streetcfg.json")
    path = Path(configured)
    if path.is_absolute():
        return path
    return _repo_root() / path


def _load_regions(source: SourceDefinition) -> tuple[TencentStreetRegion, ...]:
    payload = json.loads(_streetcfg_path(source).read_text(encoding="utf-8"))
    regions = []
    for item in payload["regions"]:
        regions.append(
            TencentStreetRegion(
                idx=str(item["idx"]),
                name=str(item.get("name") or item["idx"]),
                bbox=BoundingBox.from_sequence(item["bbox"]),
            )
        )
    return tuple(regions)


def _intersects(left: BoundingBox, right: BoundingBox) -> bool:
    return not (
        left.max_lon < right.min_lon
        or left.min_lon > right.max_lon
        or left.max_lat < right.min_lat
        or left.min_lat > right.max_lat
    )


def _tencent_level(source: SourceDefinition) -> int:
    level = int(source.options.get("data_level", "14"))
    valid_levels = {int(value.strip()) for value in source.options.get("valid_levels", "11,12,13,14,18").split(",")}
    if level not in valid_levels:
        raise ValueError(f"Unsupported Tencent data level: {level}")
    return level


def _tile_payloads(region_bbox: BoundingBox, level: int) -> list[dict[str, int]]:
    return [
        {
            "bl": tile.bl,
            "tile_x": tile.tile_x,
            "tile_y": tile.tile_y,
            "origin_px_x": tile.origin_px_x,
            "origin_px_y": tile.origin_px_y,
        }
        for tile in tencent_bl_tiles_for_gcj02_bbox(region_bbox, level)
    ]


def _region_payload(region: TencentStreetRegion) -> dict[str, Any]:
    return {"idx": region.idx, "name": region.name, "bbox": region.bbox.as_dict()}


def tencent_city_bl_discovery(provider: ProviderDefinition, request: FetchAreaRequest) -> list[dict]:
    display_zoom = request.display_zoom or provider.default_display_zoom
    source = resolve_source_for_display_zoom(provider, display_zoom)
    level = _tencent_level(source)
    jobs = []

    for region_index, region in enumerate(_load_regions(source)):
        if not _intersects(region.bbox, request.bbox):
            continue

        bl_tiles = _tile_payloads(region.bbox, level)
        if not bl_tiles:
            continue

        jobs.append(
            {
                "index": len(jobs),
                "row": 0,
                "col": region_index,
                "bbox": region.bbox.as_dict(),
                "display_zoom": display_zoom,
                "source": source,
                "source_zoom": level,
                "source_tile_range": {
                    "x_min": int(region.idx),
                    "x_max": int(region.idx),
                    "y_min": 0,
                    "y_max": len(bl_tiles) - 1,
                },
                "source_tile_count": len(bl_tiles),
                "tile_grid_projection": provider.coordinate_scheme,
                "zoom_candidates": [],
                "run_label": _job_run_label(provider, request, len(jobs)),
                "tencent_region": _region_payload(region),
                "tencent_bl_tiles": bl_tiles,
            }
        )

    return jobs


register_discovery_kind("tencent_city_bl", tencent_city_bl_discovery)

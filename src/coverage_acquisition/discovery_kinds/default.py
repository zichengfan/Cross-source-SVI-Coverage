"""Default discovery kind -- tile sweep over the requested bbox/subboxes."""

from __future__ import annotations

from coverage_acquisition.discovery_kinds._base import register_discovery_kind
from coverage_acquisition.geo import select_subboxes, split_bbox_into_grid, tile_range_for_bbox
from coverage_acquisition.models import FetchAreaRequest, ProviderDefinition, SourceDefinition


def default_discovery(provider: ProviderDefinition, request: FetchAreaRequest) -> list[dict]:
    if request.grid_rows < 1 or request.grid_cols < 1:
        raise ValueError("Grid rows and columns must be positive integers.")

    if request.grid_rows == 1 and request.grid_cols == 1:
        all_subboxes = [{"index": 0, "row": 0, "col": 0, "bbox": request.bbox}]
    else:
        all_subboxes = split_bbox_into_grid(request.bbox, request.grid_rows, request.grid_cols)

    selected_subboxes = select_subboxes(all_subboxes, request.target_subboxes)
    jobs = []
    provider_min_zoom, provider_max_zoom = provider_display_zoom_bounds(provider)

    for subbox in selected_subboxes:
        if request.auto_zoom:
            selected_plan, zoom_candidates = choose_display_zoom_for_bbox(
                provider=provider,
                bbox=subbox["bbox"],
                min_display_zoom=request.min_display_zoom or provider_min_zoom,
                max_display_zoom=request.max_display_zoom or provider_max_zoom,
                max_source_tile_count=request.max_source_tile_count,
            )
        else:
            display_zoom = request.display_zoom or provider.default_display_zoom
            selected_plan = build_zoom_candidate(provider=provider, bbox=subbox["bbox"], display_zoom=display_zoom)
            zoom_candidates = [selected_plan]

        jobs.append(
            {
                "index": subbox["index"],
                "row": subbox["row"],
                "col": subbox["col"],
                "bbox": subbox["bbox"].as_dict(),
                "display_zoom": selected_plan["display_zoom"],
                "source": selected_plan["source"],
                "source_zoom": selected_plan["source_zoom"],
                "source_tile_range": selected_plan["source_tile_range"],
                "source_tile_count": selected_plan["source_tile_count"],
                "tile_grid_projection": provider.coordinate_scheme,
                "zoom_candidates": zoom_candidates,
                "run_label": _job_run_label(provider, request, subbox["index"]),
            }
        )

    return jobs


def resolve_source_for_display_zoom(provider: ProviderDefinition, display_zoom: int) -> SourceDefinition:
    for source in provider.sources:
        if source.display_zoom_min <= display_zoom <= source.display_zoom_max:
            return source
    raise ValueError(f"No source configured for provider {provider.key!r} at display zoom {display_zoom}.")


def build_zoom_candidate(provider: ProviderDefinition, bbox, display_zoom: int) -> dict:
    source = resolve_source_for_display_zoom(provider, display_zoom)
    source_zoom = source.query_zoom or display_zoom
    source_tile_range = tile_range_for_bbox(bbox, source_zoom, provider.coordinate_scheme)
    return {
        "display_zoom": display_zoom,
        "source": source,
        "source_zoom": source_zoom,
        "source_tile_range": source_tile_range.as_dict(),
        "source_tile_count": source_tile_range.count,
    }


def choose_display_zoom_for_bbox(
    provider: ProviderDefinition,
    bbox,
    min_display_zoom: int,
    max_display_zoom: int,
    max_source_tile_count: int,
) -> tuple[dict, list[dict]]:
    candidates = [
        build_zoom_candidate(provider=provider, bbox=bbox, display_zoom=display_zoom)
        for display_zoom in range(min_display_zoom, max_display_zoom + 1)
    ]
    valid = [candidate for candidate in candidates if candidate["source_tile_count"] <= max_source_tile_count]
    selected = valid[-1] if valid else min(
        candidates,
        key=lambda item: (item["source_tile_count"], item["display_zoom"]),
    )
    return selected, candidates


def provider_display_zoom_bounds(provider: ProviderDefinition) -> tuple[int, int]:
    min_zoom = min(source.display_zoom_min for source in provider.sources)
    max_zoom = max(source.display_zoom_max for source in provider.sources)
    return min_zoom, max_zoom


def _job_run_label(provider: ProviderDefinition, request: FetchAreaRequest, subbox_index: int) -> str:
    prefix = request.run_label or provider.run_label_prefix
    return f"{prefix}_subbox_{subbox_index:02d}"


register_discovery_kind("default", default_discovery)

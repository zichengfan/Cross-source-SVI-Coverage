from __future__ import annotations

from pathlib import Path

from coverage_acquisition.compare import maybe_dataframe, summarize_many_bundles
from coverage_acquisition.models import BoundingBox, FetchAreaRequest
from coverage_acquisition.providers import DEFAULT_MULTI_SOURCE_PROVIDERS, get_area_preset
from coverage_acquisition.runners import fetch_provider_coverage


def bbox_from_preset(preset_name: str) -> BoundingBox:
    return get_area_preset(preset_name)


def fetch_single_source(
    *,
    provider: str,
    bbox: BoundingBox | dict[str, float],
    output_root: str | Path,
    display_zoom: int | None = None,
    auto_zoom: bool = False,
    min_display_zoom: int | None = None,
    max_display_zoom: int | None = None,
    max_source_tile_count: int = 16,
    grid_rows: int = 1,
    grid_cols: int = 1,
    target_subboxes: int | list[int] | tuple[int, ...] | None = None,
    run_label: str | None = None,
    access_token: str | None = None,
    dry_run: bool = False,
) -> dict:
    if isinstance(bbox, dict):
        bbox = BoundingBox.from_mapping(bbox)

    request = FetchAreaRequest(
        provider=provider,
        bbox=bbox,
        output_root=Path(output_root),
        display_zoom=display_zoom,
        auto_zoom=auto_zoom,
        min_display_zoom=min_display_zoom,
        max_display_zoom=max_display_zoom,
        max_source_tile_count=max_source_tile_count,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        target_subboxes=_normalize_subboxes(target_subboxes),
        run_label=run_label,
        access_token=access_token,
        dry_run=dry_run,
    )
    return fetch_provider_coverage(request)


def fetch_multi_source_coverage(
    *,
    bbox: BoundingBox | dict[str, float],
    output_root: str | Path,
    providers: list[str] | tuple[str, ...] = DEFAULT_MULTI_SOURCE_PROVIDERS,
    display_zoom_overrides: dict[str, int] | None = None,
    auto_zoom_providers: list[str] | tuple[str, ...] = ("apple_lookaround",),
    access_tokens: dict[str, str] | None = None,
    grid_rows: int = 1,
    grid_cols: int = 1,
    target_subboxes: int | list[int] | tuple[int, ...] | None = None,
    dry_run: bool = False,
) -> dict:
    if isinstance(bbox, dict):
        bbox = BoundingBox.from_mapping(bbox)

    display_zoom_overrides = display_zoom_overrides or {}
    access_tokens = access_tokens or {}
    bundles = []

    for provider in providers:
        bundles.append(
            fetch_single_source(
                provider=provider,
                bbox=bbox,
                output_root=output_root,
                display_zoom=display_zoom_overrides.get(provider),
                auto_zoom=provider in set(auto_zoom_providers),
                grid_rows=grid_rows,
                grid_cols=grid_cols,
                target_subboxes=target_subboxes,
                access_token=access_tokens.get(provider),
                dry_run=dry_run,
            )
        )

    summary_rows = summarize_many_bundles(bundles) if not dry_run else []
    return {
        "bundles": bundles,
        "summary_rows": summary_rows,
        "summary_table": maybe_dataframe(summary_rows),
    }


def _normalize_subboxes(value: int | list[int] | tuple[int, ...] | None) -> tuple[int, ...] | None:
    if value is None:
        return None
    if isinstance(value, int):
        return (value,)
    return tuple(int(item) for item in value)

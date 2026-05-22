from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from coverage_acquisition.compare import summarize_manifest_paths
from coverage_acquisition.downloaders import download_file, fetch_raster_tiles
from coverage_acquisition.models import BoundingBox, FetchAreaRequest, TileFetchRequest
from coverage_acquisition.providers import (
    DEFAULT_MULTI_SOURCE_PROVIDERS,
    DIRECT_DOWNLOADS,
    FRONTEND_NOTES,
    PROVIDERS,
    get_area_preset,
)
from coverage_acquisition.runners import fetch_provider_coverage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquisition helpers for multi-source street-view coverage experiments."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-providers", help="List registered provider fetchers.")

    download_parser = subparsers.add_parser("direct-download", help="Download a known direct source for a provider.")
    download_parser.add_argument("--provider", required=True, choices=sorted(DIRECT_DOWNLOADS.keys()))
    download_parser.add_argument("--output-root", required=True, type=Path)

    raster_parser = subparsers.add_parser(
        "fetch-raster-tiles", help="Fetch a small xyz tile range for a raw raster layer."
    )
    raster_parser.add_argument("--provider", required=True)
    raster_parser.add_argument("--template", required=True)
    raster_parser.add_argument("--zoom", required=True, type=int)
    raster_parser.add_argument("--x-min", required=True, type=int)
    raster_parser.add_argument("--x-max", required=True, type=int)
    raster_parser.add_argument("--y-min", required=True, type=int)
    raster_parser.add_argument("--y-max", required=True, type=int)
    raster_parser.add_argument("--output-root", required=True, type=Path)
    raster_parser.add_argument("--header", action="append", default=[], help="Optional HTTP header in KEY=VALUE form.")

    notes_parser = subparsers.add_parser(
        "provider-notes", help="Print provider notes for restricted frontend acquisition."
    )
    notes_parser.add_argument("--provider", required=True)

    fetch_provider_parser = subparsers.add_parser("fetch-provider", help="Fetch one provider over one bbox.")
    _add_fetch_arguments(fetch_provider_parser)
    fetch_provider_parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS.keys()))

    fetch_multi_parser = subparsers.add_parser("fetch-multi", help="Fetch several providers over the same bbox.")
    _add_fetch_arguments(fetch_multi_parser)
    fetch_multi_parser.add_argument(
        "--provider",
        action="append",
        dest="providers",
        default=[],
        help="Provider key. Repeat to fetch multiple providers. Defaults to the Amsterdam comparison set.",
    )
    fetch_multi_parser.add_argument(
        "--display-zoom-override",
        action="append",
        default=[],
        help="Provider-specific override in PROVIDER=ZOOM form.",
    )
    fetch_multi_parser.add_argument(
        "--access-token",
        action="append",
        default=[],
        help="Provider-specific access token in PROVIDER=TOKEN form.",
    )

    compare_parser = subparsers.add_parser("compare-manifests", help="Summarize one or more manifest.json files.")
    compare_parser.add_argument("manifest_paths", nargs="+", type=Path)

    return parser


def _add_fetch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    parser.add_argument("--preset", help="Named area preset such as amsterdam_city_bbox_approx.")
    parser.add_argument("--display-zoom", type=int)
    parser.add_argument("--auto-zoom", action="store_true")
    parser.add_argument("--min-display-zoom", type=int)
    parser.add_argument("--max-display-zoom", type=int)
    parser.add_argument("--max-source-tile-count", type=int, default=16)
    parser.add_argument("--grid-rows", type=int, default=1)
    parser.add_argument("--grid-cols", type=int, default=1)
    parser.add_argument("--target-subbox", action="append", type=int, default=[])
    parser.add_argument("--run-label")
    parser.add_argument("--header", action="append", default=[], help="Optional HTTP header in KEY=VALUE form.")
    parser.add_argument("--access-token-value", help="Access token for providers that require one.")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--no-skip-404", action="store_true")
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--dry-run", action="store_true")


def parse_headers(entries: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid header format: {entry!r}")
        key, value = entry.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def parse_mapping_entries(entries: list[str], *, value_type=str) -> dict[str, str | int]:
    parsed = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid mapping format: {entry!r}")
        key, value = entry.split("=", 1)
        parsed[key.strip()] = value_type(value.strip())
    return parsed


def resolve_bbox(args) -> BoundingBox:
    if args.bbox:
        return BoundingBox.from_sequence(args.bbox)
    if args.preset:
        return get_area_preset(args.preset)
    raise ValueError("Either --bbox or --preset must be provided.")


def build_fetch_request(
    args,
    provider: str,
    *,
    display_zoom: int | None = None,
    access_token: str | None = None,
    auto_zoom: bool | None = None,
) -> FetchAreaRequest:
    return FetchAreaRequest(
        provider=provider,
        bbox=resolve_bbox(args),
        output_root=args.output_root,
        display_zoom=display_zoom if display_zoom is not None else args.display_zoom,
        auto_zoom=args.auto_zoom if auto_zoom is None else auto_zoom,
        min_display_zoom=args.min_display_zoom,
        max_display_zoom=args.max_display_zoom,
        max_source_tile_count=args.max_source_tile_count,
        grid_rows=args.grid_rows,
        grid_cols=args.grid_cols,
        target_subboxes=tuple(args.target_subbox) or None,
        run_label=args.run_label,
        skip_404=not args.no_skip_404,
        stop_on_error=not args.continue_on_error,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
        access_token=access_token if access_token is not None else args.access_token_value,
        extra_headers=parse_headers(args.header),
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list-providers":
        print(json.dumps(sorted(PROVIDERS.keys()), indent=2))
        return

    if args.command == "direct-download":
        manifest = download_file(DIRECT_DOWNLOADS[args.provider], args.output_root)
        print(json.dumps(manifest, indent=2, sort_keys=True, default=_json_default))
        return

    if args.command == "fetch-raster-tiles":
        request = TileFetchRequest(
            provider=args.provider,
            template=args.template,
            zoom=args.zoom,
            x_min=args.x_min,
            x_max=args.x_max,
            y_min=args.y_min,
            y_max=args.y_max,
            output_dir=args.output_root / args.provider,
            headers=parse_headers(args.header),
        )
        manifest = fetch_raster_tiles(request)
        print(json.dumps(manifest, indent=2, sort_keys=True, default=_json_default))
        return

    if args.command == "provider-notes":
        print(FRONTEND_NOTES.get(args.provider, "No provider notes recorded."))
        return

    if args.command == "fetch-provider":
        result = fetch_provider_coverage(build_fetch_request(args, args.provider))
        print(json.dumps(result, indent=2, sort_keys=True, default=_json_default))
        return

    if args.command == "fetch-multi":
        providers = args.providers or list(DEFAULT_MULTI_SOURCE_PROVIDERS)
        display_zoom_overrides = parse_mapping_entries(args.display_zoom_override, value_type=int)
        access_tokens = parse_mapping_entries(args.access_token, value_type=str)
        results = []
        for provider in providers:
            provider_auto_zoom = args.auto_zoom and PROVIDERS[provider].supports_auto_zoom
            request = build_fetch_request(
                args,
                provider,
                display_zoom=display_zoom_overrides.get(provider),
                access_token=access_tokens.get(provider),
                auto_zoom=provider_auto_zoom,
            )
            results.append(fetch_provider_coverage(request))
        print(json.dumps(results, indent=2, sort_keys=True, default=_json_default))
        return

    if args.command == "compare-manifests":
        rows = summarize_manifest_paths(args.manifest_paths)
        print(json.dumps(rows, indent=2, sort_keys=True, default=_json_default))
        return

    raise RuntimeError(f"Unhandled command: {args.command}")


def _json_default(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from coverage_acquisition.geo import iter_tile_coords, select_subboxes, split_bbox_into_grid, tile_range_for_bbox
from coverage_acquisition.io_utils import (
    ensure_directory,
    read_csv_rows,
    sha256_bytes,
    utc_now_iso,
    write_csv,
    write_json,
)
from coverage_acquisition.models import FetchAreaRequest, ProviderDefinition, SourceDefinition
from coverage_acquisition.polite import PolitePolicy, polite_fetch
from coverage_acquisition.providers import get_provider
from coverage_acquisition.source_kinds import DecodeContext, get_source_kind_handler

# Backwards-compatible re-exports: these decoders moved into source_kinds/.
from coverage_acquisition.source_kinds.raster import summarize_png  # noqa: F401
from coverage_acquisition.source_kinds.vector_mvt import (  # noqa: F401
    extract_vector_records,
    guess_geometry_type_from_wkt,
    inspect_vector_layers,
)

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
    "width",
    "height",
    "coverage_pixel_count",
    "total_pixel_count",
    "coverage_ratio",
    "record_count",
    "pano_count",
    "feature_count",
    "layer_counts_json",
    "last_modified",
    "output_path",
    "metadata_path",
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


def fetch_provider_coverage(request: FetchAreaRequest) -> dict:
    provider = get_provider(request.provider)
    jobs = build_jobs(provider, request)

    if request.dry_run:
        return {
            "provider": provider.key,
            "output_namespace": provider.output_namespace,
            "dry_run": True,
            "jobs": jobs,
            "results": [],
        }

    results = []
    for job in jobs:
        result = _fetch_job(provider=provider, source=job["source"], job=job, request=request)
        results.append(result)

    return {
        "provider": provider.key,
        "output_namespace": provider.output_namespace,
        "dry_run": False,
        "jobs": jobs,
        "results": results,
    }


def build_jobs(provider: ProviderDefinition, request: FetchAreaRequest) -> list[dict]:
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


def _fetch_job(provider: ProviderDefinition, source: SourceDefinition, job: dict, request: FetchAreaRequest) -> dict:
    output_dir = request.output_root / provider.output_namespace / job["run_label"]
    ensure_directory(output_dir)
    runtime_options = _build_runtime_options(source, request)

    fetched_tiles = []
    skipped_tiles = []
    error_tiles = []
    pano_records = []
    vector_feature_records = []

    for x, y in iter_tile_coords(_tile_range_from_dict(job["source_tile_range"])):
        tile_url = _build_tile_url(source, job["source_zoom"], x, y, request.access_token, runtime_options)
        try:
            payload, content_type, http_status = _fetch_payload(
                url=tile_url,
                headers=_merge_headers(source.headers, request.extra_headers),
                timeout_seconds=request.timeout_seconds or provider.request_timeout_seconds,
            )
        except HTTPError as exc:
            error_record = _build_error_record(provider, source, job, tile_url, x, y, exc.code, str(exc.reason))
            if exc.code == 404 and request.skip_404:
                skipped_tiles.append(error_record)
                continue
            error_tiles.append(error_record)
            if request.stop_on_error:
                raise
            continue
        except URLError as exc:
            error_record = _build_error_record(provider, source, job, tile_url, x, y, None, str(exc.reason))
            error_tiles.append(error_record)
            if request.stop_on_error:
                raise
            continue

        fetched_at = utc_now_iso()
        context = DecodeContext(
            source=source,
            provider=provider,
            job=job,
            x=x,
            y=y,
            tile_url=tile_url,
            fetched_at=fetched_at,
            output_dir=output_dir,
            wire_payload=payload,
            content_type=content_type,
            http_status=http_status,
        )

        try:
            decoded = get_source_kind_handler(source.kind)(context)
        except Exception as exc:
            error_record = _build_error_record(provider, source, job, tile_url, x, y, None, str(exc))
            error_tiles.append(error_record)
            if request.stop_on_error:
                raise
            continue

        if decoded.skipped:
            if decoded.skip_record is not None:
                skipped_tiles.append(decoded.skip_record)
            continue

        pano_records.extend(decoded.pano_records)
        vector_feature_records.extend(decoded.vector_feature_records)
        tile_path = decoded.tile_path

        if tile_path is None:
            metadata_path = (
                output_dir
                / source.effective_storage_subdir
                / str(job["source_zoom"])
                / str(x)
                / f"{y}.png.metadata.json"
            )
        else:
            metadata_path = Path(str(tile_path) + ".metadata.json")
        row = {
            "provider": provider.key,
            "source_id": source.id,
            "source_kind": source.kind,
            "display_zoom": job["display_zoom"],
            "source_zoom": job["source_zoom"],
            "x": x,
            "y": y,
            "tile_url": tile_url,
            "http_status": http_status,
            "content_type": content_type,
            "is_empty": decoded.is_empty,
            "wire_byte_length": len(payload),
            "stored_byte_length": len(decoded.stored_payload),
            "wire_sha256": sha256_bytes(payload),
            "stored_sha256": sha256_bytes(decoded.stored_payload),
            "was_gzip_compressed": decoded.was_gzip_compressed,
            "width": decoded.width,
            "height": decoded.height,
            "coverage_pixel_count": decoded.coverage_pixel_count,
            "total_pixel_count": decoded.total_pixel_count,
            "coverage_ratio": decoded.coverage_ratio,
            "record_count": decoded.record_count,
            "pano_count": decoded.pano_count,
            "feature_count": decoded.feature_count,
            "layer_counts_json": decoded.layer_counts_json,
            "last_modified": decoded.last_modified,
            "output_path": str(tile_path) if tile_path is not None else "",
            "metadata_path": str(metadata_path),
            "fetched_at": fetched_at,
        }
        write_json(metadata_path, row)
        fetched_tiles.append(row)

    tile_summary_path = output_dir / "tile_summary.csv"
    pano_records_path = output_dir / "pano_records.csv"
    vector_feature_records_path = output_dir / "feature_records.csv"
    write_csv(tile_summary_path, fetched_tiles, TILE_SUMMARY_FIELDS)
    write_csv(pano_records_path, pano_records, PANO_RECORD_FIELDS)
    write_csv(vector_feature_records_path, vector_feature_records, VECTOR_FEATURE_FIELDS)

    total_coverage_pixels = sum(
        int(row["coverage_pixel_count"]) for row in fetched_tiles if row["coverage_pixel_count"] != ""
    )
    total_pixels = sum(
        int(row["total_pixel_count"]) for row in fetched_tiles if row["total_pixel_count"] != ""
    )
    aggregate_coverage_ratio = total_coverage_pixels / total_pixels if total_pixels else None
    empty_tile_count = sum(1 for row in fetched_tiles if row.get("is_empty") is True)
    nonempty_tile_count = sum(1 for row in fetched_tiles if row.get("is_empty") is False)

    manifest = {
        "provider": provider.key,
        "output_namespace": provider.output_namespace,
        "job_index": job["index"],
        "job_row": job["row"],
        "job_col": job["col"],
        "bbox": job["bbox"],
        "source_id": source.id,
        "source_kind": source.kind,
        "display_zoom": job["display_zoom"],
        "source_zoom": job["source_zoom"],
        "source_tile_range": job["source_tile_range"],
        "source_tile_count": job["source_tile_count"],
        "tile_grid_projection": job.get("tile_grid_projection", provider.coordinate_scheme),
        "run_label": job["run_label"],
        "tile_count": len(fetched_tiles),
        "empty_tile_count": empty_tile_count,
        "nonempty_tile_count": nonempty_tile_count,
        "skipped_404_count": len(skipped_tiles),
        "error_count": len(error_tiles),
        "pano_record_count": len(pano_records),
        "vector_feature_record_count": len(vector_feature_records),
        "total_coverage_pixels": total_coverage_pixels,
        "total_pixels": total_pixels,
        "aggregate_coverage_ratio": aggregate_coverage_ratio,
        "tile_summary_path": str(tile_summary_path),
        "pano_records_path": str(pano_records_path),
        "vector_feature_records_path": str(vector_feature_records_path),
        "runtime_options": runtime_options,
        "fetched_at": utc_now_iso(),
    }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)

    if skipped_tiles:
        write_json(output_dir / "skipped_tiles.json", skipped_tiles)
    if error_tiles:
        write_json(output_dir / "errors.json", error_tiles)

    return {
        "output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "tile_summary_path": str(tile_summary_path),
        "pano_records_path": str(pano_records_path),
        "vector_feature_records_path": str(vector_feature_records_path),
        "fetched_tiles": fetched_tiles,
        "skipped_tiles": skipped_tiles,
        "error_tiles": error_tiles,
        "manifest": manifest,
        "job": job,
    }


def _tile_range_from_dict(payload: dict[str, int]):
    from coverage_acquisition.models import TileRange

    return TileRange(
        x_min=int(payload["x_min"]),
        x_max=int(payload["x_max"]),
        y_min=int(payload["y_min"]),
        y_max=int(payload["y_max"]),
    )


def _merge_headers(base: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    headers = dict(base)
    headers.update(extra)
    return headers


def _build_runtime_options(source: SourceDefinition, request: FetchAreaRequest) -> dict:
    if not _is_yandex_stv_source(source):
        return {}

    fallback_version = source.options.get("version_fallback", "")
    runtime_options = {
        "format_values": {
            "layer": source.options.get("layer", "stv"),
            "version": fallback_version,
        },
        "frontend_config": {
            "config_source": "fallback",
            "stv_version": fallback_version,
            "query_layers": "",
        },
    }

    try:
        frontend_config = _discover_yandex_frontend_config(
            page_url=source.options["frontend_page_url"],
            headers=_merge_headers(source.headers, request.extra_headers),
            timeout_seconds=request.timeout_seconds or 60,
        )
    except Exception as exc:
        runtime_options["frontend_config"]["config_error"] = repr(exc)
        return runtime_options

    runtime_options["frontend_config"].update(frontend_config)
    runtime_options["frontend_config"]["config_source"] = "live_page"
    runtime_options["format_values"]["version"] = frontend_config["stv_version"]
    if frontend_config.get("stv_tiles_template"):
        runtime_options["tile_template"] = _normalize_yandex_stv_tile_template(
            frontend_config["stv_tiles_template"],
            request_layer=runtime_options["format_values"]["layer"],
        )
    return runtime_options


def _is_yandex_stv_source(source: SourceDefinition) -> bool:
    return source.options.get("config_kind") == "yandex_stv_renderer"


def _discover_yandex_frontend_config(page_url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, str]:
    request = Request(page_url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8")

    match = re.search(r'<script type="application/json" class="state-view">(.*?)</script>', html, re.S)
    if not match:
        raise RuntimeError("Could not locate Yandex state-view JSON in the frontend page.")

    state = json.loads(match.group(1))
    config = state["config"]
    return {
        "stv_tiles_template": config["hosts"]["stvTiles"],
        "stv_version": config["layers"]["stv"]["version"],
        "query_layers": state.get("query", {}).get("l", ""),
    }


def _normalize_yandex_stv_tile_template(template: str, request_layer: str) -> str:
    normalized = template.replace("\\u0026", "&")
    normalized = normalized.replace("l=stv&", f"l={request_layer}&")
    normalized = normalized.replace(
        "https://0%d.core-stv-renderer.maps.yandex.net/",
        "https://core-stv-renderer.maps.yandex.net/",
    )
    normalized = normalized.replace("%c", "x={x}&y={y}&z={z}")
    normalized = normalized.replace("%v", "{version}")
    normalized = normalized.replace("%l", "lang=en_US&scale=1")
    return normalized


def _build_tile_url(
    source: SourceDefinition,
    z: int,
    x: int,
    y: int,
    access_token: str | None,
    runtime_options: dict | None = None,
) -> str:
    runtime_options = runtime_options or {}
    template = runtime_options.get("tile_template", source.template)
    format_values = dict(runtime_options.get("format_values", {}))
    format_values.update({"z": z, "x": x, "y": y})
    base_url = template.format(**format_values)
    if not source.token_query_param:
        return base_url
    if not access_token:
        raise ValueError(f"Provider source {source.id!r} requires an access token.")
    query = urlencode({source.token_query_param: access_token})
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query}"


def _fetch_payload(url: str, headers: dict[str, str], timeout_seconds: int) -> tuple[bytes, str, int]:
    """Fetch one tile through the polite scraper (per-host throttle + retry)."""
    return polite_fetch(url, headers=headers, policy=PolitePolicy(timeout_seconds=timeout_seconds))


def _build_error_record(
    provider: ProviderDefinition,
    source: SourceDefinition,
    job: dict,
    tile_url: str,
    x: int,
    y: int,
    http_status: int | None,
    reason: str,
) -> dict:
    return {
        "provider": provider.key,
        "source_id": source.id,
        "source_kind": source.kind,
        "display_zoom": job["display_zoom"],
        "source_zoom": job["source_zoom"],
        "tile_url": tile_url,
        "x": x,
        "y": y,
        "fetched_at": utc_now_iso(),
        "http_status": http_status if http_status is not None else "",
        "reason": reason,
    }


def read_manifest(manifest_path: str | Path) -> dict:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8"))


def read_tile_summary_rows(manifest: dict) -> list[dict]:
    return read_csv_rows(Path(manifest["tile_summary_path"]))

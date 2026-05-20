"""Point-probe coverage acquisition for streetlevel-native providers."""

from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep

from coverage_acquisition.io_utils import ensure_directory, utc_now_iso, write_csv, write_json
from coverage_acquisition.models import BoundingBox, ProbeFetchRequest
from coverage_acquisition.source_kinds.streetlevel import (
    GlobalRateLimiter,
    ProbeBlockedError,
    RateLimitedProbe,
    get_streetlevel_probe,
)

PROBE_PANO_RECORD_FIELDS = [
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
    "date",
    "raw_json",
]


def generate_probe_grid(bbox: BoundingBox, spacing_m: float) -> list[tuple[float, float]]:
    """Generate an inclusive WGS84 point lattice covering `bbox`."""
    if spacing_m <= 0:
        raise ValueError("spacing_m must be positive.")
    mid_lat = (bbox.min_lat + bbox.max_lat) / 2.0
    dlat = spacing_m / 111_320.0
    cos_mid_lat = max(abs(math.cos(math.radians(mid_lat))), 1.0e-12)
    dlon = spacing_m / (111_320.0 * cos_mid_lat)
    lats = _inclusive_axis(bbox.min_lat, bbox.max_lat, dlat)
    lons = _inclusive_axis(bbox.min_lon, bbox.max_lon, dlon)
    return [(lat, lon) for lat in lats for lon in lons]


def coarse_cells_with_hits(
    bbox: BoundingBox,
    coarse_spacing_m: float,
    pano_records: list[dict],
) -> list[BoundingBox]:
    """Return coarse-grid cells to fine-sweep, given the coarse-pass hits.

    A single coarse probe only "sees" coverage within its search radius, so a
    coarse grid point that lands in a courtyard or block interior returns
    nothing even where coverage genuinely exists nearby. Because street-level
    coverage is spatially contiguous, the set of cells that had a direct hit is
    **dilated to its 8-neighbours** — a cell adjacent to a hit is very likely
    covered too. This trades a little extra fine-sweeping for far fewer
    wrongly-skipped cells.
    """
    coarse_lats = sorted({lat for lat, _lon in generate_probe_grid(bbox, coarse_spacing_m)})
    coarse_lons = sorted({lon for _lat, lon in generate_probe_grid(bbox, coarse_spacing_m)})
    if len(coarse_lats) < 2 or len(coarse_lons) < 2:
        return [bbox] if pano_records else []

    hit_cells: set[tuple[int, int]] = set()
    for pano in pano_records:
        lat = float(pano["lat"])
        lon = float(pano["lon"])
        lat_index = _cell_index(coarse_lats, lat)
        lon_index = _cell_index(coarse_lons, lon)
        if lat_index is not None and lon_index is not None:
            hit_cells.add((lat_index, lon_index))

    lat_cell_count = len(coarse_lats) - 1
    lon_cell_count = len(coarse_lons) - 1
    dilated_cells: set[tuple[int, int]] = set()
    for lat_index, lon_index in hit_cells:
        for d_lat in (-1, 0, 1):
            for d_lon in (-1, 0, 1):
                neighbour_lat = lat_index + d_lat
                neighbour_lon = lon_index + d_lon
                if 0 <= neighbour_lat < lat_cell_count and 0 <= neighbour_lon < lon_cell_count:
                    dilated_cells.add((neighbour_lat, neighbour_lon))

    cells = []
    for lat_index, lon_index in sorted(dilated_cells):
        cells.append(
            BoundingBox(
                min_lon=coarse_lons[lon_index],
                min_lat=coarse_lats[lat_index],
                max_lon=coarse_lons[lon_index + 1],
                max_lat=coarse_lats[lat_index + 1],
            )
        )
    return cells


def fetch_probe_coverage(request: ProbeFetchRequest) -> dict:
    """Fetch streetlevel coverage with a two-pass point-probe sweep."""
    if request.concurrency < 1:
        raise ValueError("concurrency must be at least 1.")
    mask = _load_probe_mask(request.mask_path)
    limiter = GlobalRateLimiter(request.requests_per_second)
    probe = RateLimitedProbe(
        get_streetlevel_probe(request.provider),
        requests_per_second=request.requests_per_second,
        limiter=limiter,
    )
    coarse_grid = _filter_points_by_mask(generate_probe_grid(request.bbox, request.coarse_spacing_m), mask)
    fine_grid = _filter_points_by_mask(generate_probe_grid(request.bbox, request.fine_spacing_m), mask)
    run_label = request.run_label or utc_now_iso().replace(":", "").replace("+", "Z")
    output_dir = request.output_root / f"{request.provider}_streetlevel" / run_label

    if request.dry_run:
        return {
            "provider": request.provider,
            "bbox": request.bbox.as_dict(),
            "dry_run": True,
            "two_pass": request.two_pass,
            "coarse_spacing_m": request.coarse_spacing_m,
            "fine_spacing_m": request.fine_spacing_m,
            "radius_m": request.radius_m,
            "requests_per_second": request.requests_per_second,
            "mask_path": str(request.mask_path) if request.mask_path else None,
            "concurrency": request.concurrency,
            "coarse_grid_size": len(coarse_grid),
            "estimated_pass2_grid_size": len(fine_grid),
        }

    started_at = time.monotonic()
    fetched_at = utc_now_iso()
    coarse_probe_count = 0
    fine_probe_count = 0
    hit_count = 0
    blocked_count = 0
    all_panos: list[dict] = []
    current_phase = "coarse"

    try:
        if request.two_pass:
            current_phase = "coarse"
            coarse_result = _probe_points(
                probe=probe,
                points=coarse_grid,
                radius_m=request.radius_m,
                concurrency=request.concurrency,
            )
            coarse_probe_count += coarse_result.probe_count
            hit_count += coarse_result.hit_count
            all_panos.extend(coarse_result.panos)
            hit_cells = coarse_cells_with_hits(request.bbox, request.coarse_spacing_m, all_panos)
            pass2_points = _dedupe_points(
                point
                for cell in hit_cells
                for point in generate_probe_grid(cell, request.fine_spacing_m)
            )
            pass2_points = _filter_points_by_mask(pass2_points, mask)
        else:
            hit_cells = [request.bbox]
            pass2_points = fine_grid

        current_phase = "fine"
        fine_result = _probe_points(
            probe=probe,
            points=pass2_points,
            radius_m=request.radius_m,
            concurrency=request.concurrency,
        )
        fine_probe_count += fine_result.probe_count
        hit_count += fine_result.hit_count
        all_panos.extend(fine_result.panos)
    except _ProbeRunBlocked as exc:
        if current_phase == "coarse":
            coarse_probe_count += exc.probe_count
        else:
            fine_probe_count += exc.probe_count
        hit_count += exc.hit_count
        all_panos.extend(exc.panos)
        blocked_count += 1
        manifest = _base_manifest(
            request=request,
            output_dir=output_dir,
            run_label=run_label,
            coarse_grid_size=len(coarse_grid),
            estimated_pass2_grid_size=len(fine_grid),
            coarse_probe_count=coarse_probe_count,
            fine_probe_count=fine_probe_count,
            hit_cell_count=0,
            hit_count=hit_count,
            blocked_count=blocked_count,
            pano_count=0,
            elapsed_seconds=time.monotonic() - started_at,
        )
        manifest.update({"blocked": True, "block_reason": str(exc.__cause__ or exc)})
        _write_manifest(output_dir, manifest)
        return manifest

    deduped_panos = _dedupe_panos(all_panos)
    rows = [_pano_to_row(request.provider, pano, fetched_at) for pano in deduped_panos]
    ensure_directory(output_dir)
    pano_records_path = output_dir / "pano_records.csv"
    coverage_points_path = output_dir / "coverage_points.parquet"
    manifest_path = output_dir / "manifest.json"
    write_csv(pano_records_path, rows, PROBE_PANO_RECORD_FIELDS)
    _write_coverage_points(coverage_points_path, request.provider, deduped_panos, fetched_at)

    manifest = _base_manifest(
        request=request,
        output_dir=output_dir,
        run_label=run_label,
        coarse_grid_size=len(coarse_grid),
        estimated_pass2_grid_size=len(fine_grid),
        coarse_probe_count=coarse_probe_count,
        fine_probe_count=fine_probe_count,
        hit_cell_count=len(hit_cells),
        hit_count=hit_count,
        blocked_count=blocked_count,
        pano_count=len(deduped_panos),
        elapsed_seconds=time.monotonic() - started_at,
    )
    manifest.update(
        {
            "blocked": False,
            "pano_records_path": str(pano_records_path),
            "coverage_points_path": str(coverage_points_path),
            "manifest_path": str(manifest_path),
        }
    )
    write_json(manifest_path, manifest)
    return manifest


def _inclusive_axis(start: float, stop: float, step: float) -> list[float]:
    if stop < start:
        raise ValueError("Bounding box maximums must be greater than or equal to minimums.")
    span = stop - start
    if span == 0:
        return [start]
    interval_count = max(1, math.ceil((span / step) - 1.0e-6))
    values = [start + (step * index) for index in range(interval_count)]
    if not math.isclose(values[-1], stop, rel_tol=0.0, abs_tol=step * 1.0e-6):
        values.append(stop)
    else:
        values[-1] = stop
    return values


def _cell_index(axis: list[float], value: float) -> int | None:
    if value < axis[0] or value > axis[-1]:
        return None
    for index in range(len(axis) - 1):
        if axis[index] <= value <= axis[index + 1]:
            return index
    return None


def _dedupe_points(points) -> list[tuple[float, float]]:
    seen: set[tuple[float, float]] = set()
    deduped = []
    for point in points:
        if point in seen:
            continue
        seen.add(point)
        deduped.append(point)
    return deduped


def _dedupe_panos(panos: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for pano in panos:
        deduped.setdefault(str(pano["panoid"]), pano)
    return [deduped[panoid] for panoid in sorted(deduped)]


@dataclass(frozen=True)
class _ProbeRunResult:
    probe_count: int
    hit_count: int
    panos: list[dict]


class _ProbeRunBlocked(Exception):
    def __init__(self, cause: ProbeBlockedError, probe_count: int, hit_count: int, panos: list[dict]) -> None:
        super().__init__(str(cause))
        self.__cause__ = cause
        self.probe_count = probe_count
        self.hit_count = hit_count
        self.panos = panos


def _probe_points(
    *,
    probe: RateLimitedProbe,
    points: list[tuple[float, float]],
    radius_m: float,
    concurrency: int,
) -> _ProbeRunResult:
    if not points:
        return _ProbeRunResult(probe_count=0, hit_count=0, panos=[])

    results: dict[int, list[dict]] = {}
    probe_count = 0
    hit_count = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(probe, lat, lon, radius_m): index
            for index, (lat, lon) in enumerate(points)
        }
        for future in as_completed(futures):
            index = futures[future]
            probe_count += 1
            try:
                panos = future.result()
            except ProbeBlockedError as exc:
                for pending in futures:
                    pending.cancel()
                raise _ProbeRunBlocked(exc, probe_count, hit_count, _ordered_panos(results)) from exc
            if panos:
                hit_count += 1
                results[index] = panos

    return _ProbeRunResult(probe_count=probe_count, hit_count=hit_count, panos=_ordered_panos(results))


def _ordered_panos(results: dict[int, list[dict]]) -> list[dict]:
    panos: list[dict] = []
    for index in sorted(results):
        panos.extend(results[index])
    return panos


def _load_probe_mask(mask_path: Path | None):
    if mask_path is None:
        return None
    mask = gpd.read_file(mask_path)
    if mask.crs is None:
        mask = mask.set_crs("EPSG:4326")
    else:
        mask = mask.to_crs("EPSG:4326")
    return prep(mask.geometry.union_all())


def _filter_points_by_mask(points: list[tuple[float, float]], mask) -> list[tuple[float, float]]:
    if mask is None:
        return points
    return [(lat, lon) for lat, lon in points if mask.contains(Point(lon, lat))]


def _pano_to_row(provider: str, pano: dict, fetched_at: str) -> dict:
    raw = pano.get("raw", {})
    date = pano.get("date")
    return {
        "provider": provider,
        "source_id": "streetlevel",
        "display_zoom": "",
        "source_zoom": "",
        "tile_x": "",
        "tile_y": "",
        "tile_url": "",
        "panoid": str(pano["panoid"]),
        "lat": float(pano["lat"]),
        "lon": float(pano["lon"]),
        "timestamp": date or "",
        "buildId": "",
        "coverageType": "streetlevel",
        "lastModified": "",
        "fetched_at": fetched_at,
        "date": date or "",
        "raw_json": json.dumps(raw, sort_keys=True),
    }


def _write_coverage_points(path: Path, provider: str, panos: list[dict], fetched_at: str) -> None:
    ensure_directory(path.parent)
    if not panos:
        gdf = gpd.GeoDataFrame(
            {
                "provider": [],
                "panoid": [],
                "lat": [],
                "lon": [],
                "date": [],
                "fetched_at": [],
                "raw_json": [],
            },
            geometry=[],
            crs="EPSG:4326",
        )
        gdf.to_parquet(path, index=False)
        return

    rows = [
        {
            "provider": provider,
            "panoid": str(pano["panoid"]),
            "lat": float(pano["lat"]),
            "lon": float(pano["lon"]),
            "date": pano.get("date"),
            "fetched_at": fetched_at,
            "raw_json": json.dumps(pano.get("raw", {}), sort_keys=True),
            "geometry": Point(float(pano["lon"]), float(pano["lat"])),
        }
        for pano in panos
    ]
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    gdf.to_parquet(path, index=False)


def _base_manifest(
    *,
    request: ProbeFetchRequest,
    output_dir: Path,
    run_label: str,
    coarse_grid_size: int,
    estimated_pass2_grid_size: int,
    coarse_probe_count: int,
    fine_probe_count: int,
    hit_cell_count: int,
    hit_count: int,
    blocked_count: int,
    pano_count: int,
    elapsed_seconds: float,
) -> dict:
    return {
        "provider": request.provider,
        "source_kind": "streetlevel",
        "bbox": request.bbox.as_dict(),
        "dry_run": False,
        "two_pass": request.two_pass,
        "run_label": run_label,
        "output_dir": str(output_dir),
        "coarse_spacing_m": request.coarse_spacing_m,
        "fine_spacing_m": request.fine_spacing_m,
        "radius_m": request.radius_m,
        "requests_per_second": request.requests_per_second,
        "mask_path": str(request.mask_path) if request.mask_path else None,
        "concurrency": request.concurrency,
        "coarse_grid_size": coarse_grid_size,
        "estimated_pass2_grid_size": estimated_pass2_grid_size,
        "coarse_probe_count": coarse_probe_count,
        "fine_probe_count": fine_probe_count,
        "total_probe_count": coarse_probe_count + fine_probe_count,
        "hit_cell_count": hit_cell_count,
        "hit_count": hit_count,
        "blocked_count": blocked_count,
        "pano_count": pano_count,
        "elapsed_seconds": elapsed_seconds,
        "fetched_at": utc_now_iso(),
    }


def _write_manifest(output_dir: Path, manifest: dict) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    write_json(manifest_path, manifest)

"""Tests for streetlevel point-probe coverage acquisition."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from coverage_acquisition.cli import build_parser
from coverage_acquisition.io_utils import read_csv_rows
from coverage_acquisition.models import BoundingBox, ProbeFetchRequest
from coverage_acquisition.probe import fetch_probe_coverage, generate_probe_grid
from coverage_acquisition.source_kinds.streetlevel import (
    STREETLEVEL_PROBES,
    ProbeBlockedError,
    register_streetlevel_probe,
)


def _register_probe(provider_key: str, probe) -> None:
    STREETLEVEL_PROBES.pop(provider_key, None)
    register_streetlevel_probe(provider_key, probe)


def test_generate_probe_grid_covers_bbox_and_uses_expected_spacing():
    bbox = BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.01, max_lat=0.01)
    grid = generate_probe_grid(bbox, spacing_m=556.6)

    assert len(grid) == 9
    assert grid[0] == (0.0, 0.0)
    assert grid[-1] == (0.01, 0.01)
    assert (0.01, 0.0) in grid
    assert (0.0, 0.01) in grid
    assert abs(grid[1][1] - 0.005) < 0.0001
    assert abs(grid[3][0] - 0.005) < 0.0001


def test_fetch_probe_coverage_two_pass_writes_outputs_and_dedupes(tmp_path):
    provider_key = "probe_two_pass"
    calls = []

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        calls.append((lat, lon, radius_m))
        if lat <= 0.01 and lon <= 0.01:
            return [
                {"panoid": "same", "lat": 0.002, "lon": 0.002, "date": "2024-01", "raw": {"hit": True}},
                {"panoid": "same", "lat": 0.002, "lon": 0.002, "date": "2024-01", "raw": {"hit": True}},
            ]
        return []

    _register_probe(provider_key, probe)
    request = ProbeFetchRequest(
        provider=provider_key,
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.02, max_lat=0.02),
        output_root=tmp_path,
        coarse_spacing_m=1113.2,
        fine_spacing_m=556.6,
        radius_m=80.0,
        requests_per_second=1000.0,
        run_label="case",
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["provider"] == provider_key
    assert manifest["two_pass"] is True
    assert manifest["coarse_probe_count"] == 9
    # The one directly-hit coarse cell is dilated to its 8 neighbours, so all
    # four cells of this bbox are fine-swept (see coarse_cells_with_hits).
    assert manifest["hit_cell_count"] == 4
    assert manifest["fine_probe_count"] == 27
    assert manifest["total_probe_count"] == 36
    assert manifest["pano_count"] == 1
    assert manifest["hit_count"] >= 1
    assert manifest["blocked_count"] == 0

    output_dir = tmp_path / f"{provider_key}_streetlevel" / "case"
    assert Path(manifest["pano_records_path"]) == output_dir / "pano_records.csv"
    assert Path(manifest["coverage_points_path"]) == output_dir / "coverage_points.parquet"
    assert Path(manifest["manifest_path"]) == output_dir / "manifest.json"
    assert (output_dir / "coverage_points.parquet").exists()

    csv_rows = read_csv_rows(output_dir / "pano_records.csv")
    assert len(csv_rows) == 1
    assert csv_rows[0]["panoid"] == "same"
    assert csv_rows[0]["provider"] == provider_key
    assert json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))["pano_count"] == 1


def test_fetch_probe_coverage_concurrent_matches_serial_and_sorts_output(tmp_path):
    def make_probe(call_order: list[tuple[float, float]]) -> object:
        def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
            call_order.append((lat, lon))
            time.sleep(0.01 if lon == 0.0 else 0.0)
            return [
                {"panoid": "z", "lat": lat, "lon": lon, "date": None, "raw": {"lon": lon}},
                {"panoid": "a", "lat": lat, "lon": lon, "date": None, "raw": {"lon": lon}},
                {"panoid": "z", "lat": lat, "lon": lon, "date": None, "raw": {"lon": lon}},
            ]

        return probe

    serial_provider = "probe_serial_sorted"
    concurrent_provider = "probe_concurrent_sorted"
    serial_calls: list[tuple[float, float]] = []
    concurrent_calls: list[tuple[float, float]] = []
    _register_probe(serial_provider, make_probe(serial_calls))
    _register_probe(concurrent_provider, make_probe(concurrent_calls))
    bbox = BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.01, max_lat=0.01)

    serial_manifest = fetch_probe_coverage(
        ProbeFetchRequest(
            provider=serial_provider,
            bbox=bbox,
            output_root=tmp_path,
            fine_spacing_m=1113.2,
            requests_per_second=1000.0,
            two_pass=False,
            run_label="serial",
            concurrency=1,
        )
    )
    concurrent_manifest = fetch_probe_coverage(
        ProbeFetchRequest(
            provider=concurrent_provider,
            bbox=bbox,
            output_root=tmp_path,
            fine_spacing_m=1113.2,
            requests_per_second=1000.0,
            two_pass=False,
            run_label="concurrent",
            concurrency=4,
        )
    )

    assert serial_manifest["pano_count"] == concurrent_manifest["pano_count"] == 2
    assert serial_manifest["fine_probe_count"] == concurrent_manifest["fine_probe_count"] == 4
    serial_rows = read_csv_rows(Path(serial_manifest["pano_records_path"]))
    concurrent_rows = read_csv_rows(Path(concurrent_manifest["pano_records_path"]))
    assert [row["panoid"] for row in serial_rows] == ["a", "z"]
    assert [row["panoid"] for row in concurrent_rows] == ["a", "z"]


def test_fetch_probe_coverage_global_rate_cap_with_multiple_workers(tmp_path):
    provider_key = "probe_global_rate_cap"
    call_times: list[float] = []
    call_lock = threading.Lock()

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        with call_lock:
            call_times.append(time.monotonic())
        time.sleep(0.01)
        return []

    _register_probe(provider_key, probe)
    request = ProbeFetchRequest(
        provider=provider_key,
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.01, max_lat=0.01),
        output_root=tmp_path,
        fine_spacing_m=1113.2,
        requests_per_second=20.0,
        two_pass=False,
        run_label="rate",
        concurrency=4,
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["fine_probe_count"] == 4
    assert len(call_times) == 4
    assert max(call_times) - min(call_times) >= 0.14


def test_fetch_probe_coverage_mask_skips_outside_points_before_probe(tmp_path):
    provider_key = "probe_masked"
    calls: list[tuple[float, float]] = []

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        calls.append((lat, lon))
        return [{"panoid": f"{lat:.2f},{lon:.2f}", "lat": lat, "lon": lon, "date": None, "raw": {}}]

    _register_probe(provider_key, probe)
    request = ProbeFetchRequest(
        provider=provider_key,
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.02, max_lat=0.02),
        output_root=tmp_path,
        fine_spacing_m=1113.2,
        requests_per_second=1000.0,
        two_pass=False,
        run_label="masked",
        mask_path=Path(__file__).parent / "fixtures" / "probe_mask.geojson",
        concurrency=3,
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["fine_probe_count"] == 1
    assert len(calls) == 1
    assert calls[0][0] == 0.01
    assert abs(calls[0][1] - 0.01) < 1.0e-9
    assert manifest["pano_count"] == 1


def test_fetch_probe_cli_wires_mask_and_concurrency(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "fetch-probe",
            "--provider",
            "probe_cli",
            "--output-root",
            str(tmp_path),
            "--bbox",
            "0",
            "0",
            "1",
            "1",
            "--mask",
            str(tmp_path / "mask.geojson"),
            "--concurrency",
            "5",
        ]
    )

    request = ProbeFetchRequest(
        provider=args.provider,
        bbox=BoundingBox.from_sequence(args.bbox),
        output_root=args.output_root,
        mask_path=args.mask,
        concurrency=args.concurrency,
    )

    assert request.mask_path == tmp_path / "mask.geojson"
    assert request.concurrency == 5


def test_fetch_probe_coverage_dry_run_does_not_call_probe(tmp_path):
    provider_key = "probe_dry_run"

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        raise AssertionError("dry-run must not call the probe")

    _register_probe(provider_key, probe)
    request = ProbeFetchRequest(
        provider=provider_key,
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.01, max_lat=0.01),
        output_root=tmp_path,
        coarse_spacing_m=1113.2,
        fine_spacing_m=556.6,
        dry_run=True,
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["dry_run"] is True
    assert manifest["coarse_grid_size"] == 4
    assert manifest["estimated_pass2_grid_size"] == 9
    assert not (tmp_path / f"{provider_key}_streetlevel").exists()


def test_fetch_probe_coverage_blocked_probe_writes_block_manifest(tmp_path):
    provider_key = "probe_blocked"

    def probe(lat: float, lon: float, radius_m: float) -> list[dict]:
        raise ProbeBlockedError("endpoint blocked")

    _register_probe(provider_key, probe)
    request = ProbeFetchRequest(
        provider=provider_key,
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.01, max_lat=0.01),
        output_root=tmp_path,
        coarse_spacing_m=1113.2,
        fine_spacing_m=556.6,
        requests_per_second=1000.0,
        run_label="blocked",
    )

    manifest = fetch_probe_coverage(request)

    assert manifest["blocked"] is True
    assert manifest["blocked_count"] == 1
    assert manifest["block_reason"] == "endpoint blocked"
    assert manifest["pano_count"] == 0
    manifest_path = tmp_path / f"{provider_key}_streetlevel" / "blocked" / "manifest.json"
    assert manifest_path.exists()


def test_coarse_cells_with_hits_dilates_to_neighbours():
    from coverage_acquisition.probe import coarse_cells_with_hits

    # ~0.01 deg coarse spacing over a 0.03 deg bbox -> a 3x3 grid of coarse cells.
    bbox = BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.03, max_lat=0.03)
    centre_hit = [{"panoid": "p", "lat": 0.015, "lon": 0.015}]

    cells = coarse_cells_with_hits(bbox, coarse_spacing_m=1113.2, pano_records=centre_hit)

    # A single hit in the centre cell dilates to all 9 cells.
    assert len(cells) == 9


def test_coarse_cells_with_hits_dilation_clamps_at_edges():
    from coverage_acquisition.probe import coarse_cells_with_hits

    bbox = BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.03, max_lat=0.03)
    corner_hit = [{"panoid": "p", "lat": 0.005, "lon": 0.005}]

    cells = coarse_cells_with_hits(bbox, coarse_spacing_m=1113.2, pano_records=corner_hit)

    # A corner-cell hit dilates only to its 3 in-grid neighbours (4 cells total).
    assert len(cells) == 4


def test_coarse_cells_with_hits_empty_when_no_hits():
    from coverage_acquisition.probe import coarse_cells_with_hits

    bbox = BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=0.03, max_lat=0.03)
    assert coarse_cells_with_hits(bbox, coarse_spacing_m=1113.2, pano_records=[]) == []

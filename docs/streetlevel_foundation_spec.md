# Foundation spec — streetlevel point-probe coverage

Implementation spec for the foundation that lets streetlevel-native providers
(`kakao`, `mapy`, `naver`, later `ja360`) acquire coverage. Build it **TDD**
(red-green-refactor). See `docs/PLAN.md` and `CLAUDE.md` for conventions.

## Background

The 7 existing providers fetch coverage as `{z}/{x}/{y}` **tiles**. The
streetlevel-native providers have **no coverage tile layer** — coverage is found
by **point-probe queries**: call a "find panorama near (lat, lon)" function over
a grid of points and collect the panoramas returned. This foundation adds that
acquisition path. It does **not** implement any provider — provider modules
(built later, one PR each) plug in their own probe function.

## Constraints

- Foundation work: editing shared files (`models.py`, `cli.py`,
  `source_kinds/__init__.py`) **is** allowed here. Do **not** edit existing
  provider modules, the 7 tile providers, `rasterize.py`/`catalog.py`, or
  anything under `docs/providers/`.
- TDD: write tests first. `uv run pytest` must stay fully green (all current 38
  tests still pass) and `uv run ruff check src/ tests/` clean (line length 120).
- Unit tests must not hit the network — monkeypatch/stub all probe functions.
- `from __future__ import annotations`; frozen dataclasses where natural.

## Design overview

A streetlevel provider declares a single `SourceDefinition` with
`kind="streetlevel"`. Its **probe function** — the thing that actually calls the
`streetlevel` library — lives in the *provider's own module* and is registered
into a registry, so each future provider PR touches only its own file. This
foundation builds the **machinery and the registry**, tested with stub probes.

## 1. `source_kinds/streetlevel.py` — probe registry + machinery

The probe contract:

```python
# A pano hit: a dict with at least these keys.
#   {"panoid": str|int, "lat": float, "lon": float, "date": str|None, "raw": dict}
# A StreetlevelProbe is called with one query point and returns the panoramas
# found near it (empty list = checked, nothing there).
StreetlevelProbe = Callable[[float, float, float], list[dict]]   # (lat, lon, radius_m)
```

Provide:

- `class ProbeBlockedError(RuntimeError)` — raised by a probe when the endpoint
  is blocked / returns a non-decodable response (distinct from "no coverage").
- `STREETLEVEL_PROBES: dict[str, StreetlevelProbe]` registry.
- `register_streetlevel_probe(provider_key: str, probe: StreetlevelProbe) -> None`
  — rejects duplicates.
- `get_streetlevel_probe(provider_key: str) -> StreetlevelProbe` — clear error
  if missing.
- `class RateLimitedProbe` (or a `throttle(probe, requests_per_second, max_retries)`
  wrapper) — wraps a probe so calls are spaced to at most `requests_per_second`
  and transient exceptions are retried with exponential backoff;
  `ProbeBlockedError` is **not** retried (it re-raises immediately). Reuse the
  throttle idea from `polite.py` (a monotonic-clock min-interval gate).
- Register `"streetlevel"` in `SOURCE_KIND_HANDLERS` (via `register_source_kind`)
  with a handler that raises a clear error: streetlevel sources are acquired by
  `probe.fetch_probe_coverage`, not the tile decode path.

## 2. `models.py` — `ProbeFetchRequest`

Add a frozen dataclass (mirroring `FetchAreaRequest`'s style):

```python
@dataclass(frozen=True)
class ProbeFetchRequest:
    provider: str
    bbox: BoundingBox
    output_root: Path
    coarse_spacing_m: float = 1500.0   # pass-1 discovery grid spacing
    fine_spacing_m: float = 150.0      # pass-2 fill grid spacing
    radius_m: float = 100.0            # search radius per probe
    requests_per_second: float = 1.0
    two_pass: bool = True              # False = single fine-grid sweep
    run_label: str | None = None
    dry_run: bool = False
```

## 3. `probe.py` — the point-probe runner

- `generate_probe_grid(bbox: BoundingBox, spacing_m: float) -> list[tuple[float, float]]`
  — a regular WGS84 lattice of `(lat, lon)` covering the bbox. Convert metres to
  degrees: `dlat = spacing_m / 111_320`; `dlon = spacing_m / (111_320 *
  cos(mid_lat))`. Deterministic, inclusive of both corners.
- `coarse_cells_with_hits(...)` helper — given coarse probe results, return the
  sub-bboxes (one per coarse grid cell that had ≥1 pano) to refine in pass 2.
- `fetch_probe_coverage(request: ProbeFetchRequest) -> dict`:
  1. Look up the probe via `get_streetlevel_probe(request.provider)`; wrap it
     with the rate limiter (`requests_per_second`).
  2. If `dry_run`: return a plan dict (coarse grid size, est. pass-2 size) — no
     probing.
  3. Pass 1 (if `two_pass`): probe the coarse grid over `bbox`; record which
     coarse cells produced panos.
  4. Pass 2: probe the fine grid, restricted to the hit cells (or the whole bbox
     if `two_pass=False`).
  5. Collect all panos; **dedupe by `panoid`**.
  6. Write outputs under `output_root/<provider>_streetlevel/<run_label>/`:
     - `pano_records.csv` (reuse the `PANO_RECORD_FIELDS`-style columns from
       `runners.py` where sensible: provider, panoid, lat, lon, date,
       fetched_at, ...);
     - `coverage_points.parquet` — a GeoParquet point layer (the
       re-rasterizable source of truth, `docs/PLAN.md` §3); use
       `geopandas`/`shapely`;
     - `manifest.json` — provider, bbox, grid sizes, probe counts, pano count,
       hit count, blocked count, timings.
  7. Return the manifest dict.
- A `ProbeBlockedError` from the probe should abort the run cleanly with a
  manifest noting the block (do not silently treat as empty).

## 4. `cli.py` — `fetch-probe` subcommand

Add a subcommand `fetch-probe` parallel to `fetch-provider`:
`--provider`, `--bbox MIN_LON MIN_LAT MAX_LON MAX_LAT` or `--preset`,
`--output-root`, `--coarse-spacing`, `--fine-spacing`, `--radius`,
`--requests-per-second`, `--single-pass`, `--dry-run`. It builds a
`ProbeFetchRequest` and calls `fetch_probe_coverage`, printing the manifest as
JSON. Keep `fetch-provider` (tile path) unchanged.

## 5. Tests (write FIRST)

`tests/test_probe.py`:
- `generate_probe_grid` — correct point count and spacing for a known bbox;
  covers both corners; spacing within tolerance.
- `fetch_probe_coverage` with a **stub probe** registered via
  `register_streetlevel_probe` (a fake that returns canned panos for points
  inside a sub-region, `[]` elsewhere): two-pass restricts pass-2 to hit cells;
  panos are deduped by `panoid`; `pano_records.csv`, `coverage_points.parquet`,
  `manifest.json` are written; manifest counts are correct.
- `dry_run=True` returns a plan without calling the probe.
- a probe raising `ProbeBlockedError` aborts cleanly with a block-noting manifest.

`tests/test_streetlevel_kind.py`:
- registry: `register_streetlevel_probe` / `get_streetlevel_probe`; duplicate
  rejected; missing key error.
- the rate limiter spaces calls to the configured interval (monotonic-clock
  assertion, like `test_polite.py`); retries a transient error; does **not**
  retry `ProbeBlockedError`.
- the `"streetlevel"` entry in `SOURCE_KIND_HANDLERS` raises the
  "use fetch_probe_coverage" error when invoked.

## Done criteria

`uv run pytest` fully green (38 existing + new), `uv run ruff check src/ tests/`
clean. Each new module has a docstring and meaningful tests. No provider is
implemented here — only the machinery, registry, runner, and CLI.

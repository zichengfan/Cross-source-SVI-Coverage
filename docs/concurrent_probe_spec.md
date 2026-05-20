# Foundation spec — concurrent probing + area mask

Make full-extent point-probe scrapes feasible (days, not months) **while staying
polite**: run probe workers concurrently, but bound the *total* request rate
with one shared global limiter; and add an area mask so ocean / empty wilderness
is never probed. Build it **TDD**. See `docs/PLAN.md` and `CLAUDE.md`.

## Why

A country-scale run is millions of probes; at a single serial ~1 req/s it takes
months. Concurrency with a **shared global rate cap** hides per-request latency
(many in flight) while keeping total load polite and bounded — this is *not*
proxy rotation or ban evasion, just efficient use of one allowed rate.

## Constraints

- Foundation PR into `dev`. Editing `probe.py`, `models.py`, `cli.py`,
  `source_kinds/streetlevel.py` is allowed. Do NOT edit provider modules under
  `providers/` or `docs/providers/`.
- TDD; `uv run`-free in this sandbox — test with
  `PYTHONPATH=src /data2/shared/Cross-source-SVI-Coverage/.venv/bin/python -m pytest`
  and `... ruff check src/ tests/`. Both pass; line length 120. All deps installed.
- Unit tests must not hit the network — use stub probes.

## 1. Shared global rate limiter (`source_kinds/streetlevel.py`)

Add a thread-safe `GlobalRateLimiter` (monotonic-clock, `Lock`-guarded) that
admits at most `requests_per_second` calls/sec **in total** across all threads
(`acquire()` blocks until a slot is free). `RateLimitedProbe` should accept an
optional shared limiter and use it instead of its own per-instance gate when
provided, so every worker thread shares one rate budget.

## 2. Concurrent probe execution (`probe.py`)

- `fetch_probe_coverage` runs the coarse sweep and the fine sweep through a
  `concurrent.futures.ThreadPoolExecutor` with `request.concurrency` workers.
- All workers share ONE `GlobalRateLimiter(request.requests_per_second)` — so
  total throughput is `requests_per_second`, regardless of worker count;
  concurrency only hides latency.
- Results collected thread-safely; dedupe by `panoid` unchanged; manifest and
  outputs unchanged in shape (add `concurrency` to the manifest).
- A `ProbeBlockedError` from any worker still aborts the run cleanly with a
  blocked manifest (cancel remaining work).
- Determinism: final `pano_records`/parquet sorted by `panoid` so output is
  stable regardless of completion order.

## 3. Area mask (`probe.py`, `models.py`, `cli.py`)

- `ProbeFetchRequest` gains `mask_path: Path | None = None` and
  `concurrency: int = 8`.
- When `mask_path` is set, load the polygon(s) with `geopandas` (GeoJSON / GPKG,
  reprojected to EPSG:4326) and **skip every probe grid point not inside the
  mask** — both coarse and fine. A `point_in_mask` helper using a prepared
  shapely geometry for speed.
- `cli.py fetch-probe` gains `--mask <path>` and `--concurrency <n>`.

## 4. Tests (write FIRST)

`tests/test_probe.py` / `tests/test_streetlevel_kind.py`:
- `GlobalRateLimiter` admits N calls in ≈ N / rate seconds (monotonic-clock
  assertion); thread-safe under several threads.
- `fetch_probe_coverage` with `concurrency > 1` and a stub probe returns the
  same deduped result as serial; output ordering is deterministic.
- total request rate stays within the configured cap with multiple workers.
- area mask: probe points outside a supplied mask polygon are skipped; points
  inside are probed (use a small synthetic mask, no files needed — or a tiny
  GeoJSON fixture under `tests/fixtures/`).

## Done criteria

`uv run pytest` green (all prior tests + new), `ruff` clean. `fetch-probe` gains
`--concurrency` and `--mask`. Commit, push `foundation/concurrent-probe`, open a
PR into `dev` titled "feat: concurrent probing + area mask for feasible
full-extent runs".

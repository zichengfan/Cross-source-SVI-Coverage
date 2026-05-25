# Phase 0 foundation spec — rasterize / catalog / extent modules

Implementation spec for three foundation modules. Build them **TDD**
(red-green-refactor): write the listed tests first, then the module.
See `docs/PLAN.md` (§3 data model, §12 testing) and `CLAUDE.md` for conventions.

Constraints:
- Work only in **new files**. Do **not** edit `cli.py`, `runners.py`, `models.py`,
  `providers/`, or `source_kinds/` — CLI wiring is done separately.
- `from __future__ import annotations`; frozen dataclasses where natural.
- `uv run pytest` and `uv run ruff check src/ tests/` must pass (line-length 120).
- Unit tests must not hit the network.

## The z14 analysis grid (shared definition)

Global web-mercator (EPSG:3857) pixel grid at "zoom 14, 256-px tiles":
- Grid is `256 * 2**14 = 4_194_304` pixels square.
- Origin (top-left) = `(-20037508.342789244, 20037508.342789244)` in EPSG:3857.
- Pixel size = `2 * 20037508.342789244 / 4_194_304` ≈ `9.5546` m.
- A per-provider COG is a **window** of this global grid covering the provider's
  data extent, pixel-aligned to the global grid (never re-snapped).

Put this grid definition in a small shared helper inside `rasterize.py`
(`GRID_ZOOM = 14`, origin, pixel size, plus `lonlat_window(...)` /
`pixel_bounds_for_bbox(...)` helpers) so `catalog.py` and tests can import it.

## Module 1 — `src/coverage_acquisition/rasterize.py`

Purpose: turn a provider's coverage (raster tiles **or** vector geometries **or**
points) into a single-band `uint8` binary-presence COG on the z14 grid.
Pixel values: `1` = covered, `0` = checked-empty, `255` = nodata.

Public API:
- `rasterize_geometries_to_cog(geometries, output_path, *, point_buffer_cells=1.0) -> dict`
  — `geometries`: iterable of shapely geometries in EPSG:4326. Reproject to 3857,
  buffer pure Point/MultiPoint geometries by `point_buffer_cells * pixel_size`,
  burn onto the z14 window covering their union extent, write a COG. Returns a
  manifest dict (output_path, bbox, pixel counts, covered_pixel_count, crs).
- `rasterize_raster_tiles_to_cog(tile_paths, output_path, *, coverage_from="alpha") -> dict`
  — `tile_paths`: iterable of (z, x, y, path) for stored PNG coverage tiles.
  A pixel is covered where alpha != 0 (or non-background). Reproject/resample
  each tile onto the z14 window, OR the values. Returns a manifest dict.
- Use `rasterio`, `rasterio.features.rasterize`, `shapely`, `rio-cogeo`
  (`cog_translate` / `cog_validate`).

Tests first (`tests/test_rasterize.py`), no network:
- z14 grid constants: pixel size ≈ 9.5546, grid size 4_194_304.
- `rasterize_geometries_to_cog` on a small LineString → COG exists, is a valid
  COG (`rio_cogeo.cog_validate`), `covered_pixel_count > 0`, CRS is EPSG:3857.
- A lone Point with `point_buffer_cells=1.0` covers ≥ 1 pixel.
- Output dtype is `uint8`; nodata is `255`.
- Two disjoint geometries → covered pixels in two separated regions.

## Module 2 — `src/coverage_acquisition/catalog.py`

Purpose: maintain a STAC catalog indexing the per-provider COGs.

Public API:
- `upsert_provider_item(catalog_root, provider_key, cog_path, *, bbox, scrape_date,
  tier, source_endpoint, tos_notes="") -> pystac.Item`
  — open or create a `pystac.Catalog` rooted at `catalog_root`
  (`data/processed/stac/`), add or replace the Item for `provider_key` with a
  COG asset, geometry/bbox, datetime, and the extra fields as properties, then
  save the catalog (`CatalogType.SELF_CONTAINED`).
- `load_catalog(catalog_root) -> pystac.Catalog`.

Tests first (`tests/test_catalog.py`), no network, use `tmp_path`:
- `upsert_provider_item` creates a catalog + one item; reload finds it.
- Calling it twice for the same `provider_key` replaces, not duplicates.
- Item carries `tier`, `source_endpoint`, `tos_notes` in properties; bbox set.

## Module 3 — `src/coverage_acquisition/extent.py`

Purpose: two-pass extent discovery (PLAN §1, §11). Pass 1 sweeps a low zoom over
a region to find where coverage exists; the caller then z14-fetches only there.

Public API:
- `discover_coverage_tiles(provider_key, region_bbox, discovery_zoom, *,
  output_root, has_coverage=None) -> list[tuple[int, int]]`
  — build the discovery-zoom tile range for `region_bbox` (reuse
  `geo.tile_range_for_bbox` with the provider's `coordinate_scheme`), fetch each
  tile via the provider's first source through `polite.polite_fetch`, decide
  coverage with `has_coverage` (default: raster → any non-transparent pixel
  via `source_kinds.raster.summarize_png`; vector/json → any record), and return
  the discovery-zoom (x, y) tiles that have coverage.
- `child_tiles(tile_xy, from_zoom, to_zoom) -> list[tuple[int, int]]`
  — expand a tile to all descendant tiles at `to_zoom` (for planning the z14 fetch).

Tests first (`tests/test_extent.py`), no network:
- `child_tiles((1, 1), 1, 3)` returns 16 tiles, all within the expected range.
- `discover_coverage_tiles` with a monkeypatched/injected `has_coverage` and a
  monkeypatched `polite.polite_fetch` (return canned bytes) returns exactly the
  tiles the predicate marks covered. (Inject the fetch + predicate so the test
  stays offline.)

## Done criteria
`uv run pytest` green (existing 28 tests still pass), `uv run ruff check` clean,
each new module has a docstring and meaningful tests.

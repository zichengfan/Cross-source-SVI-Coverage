---
name: rasterize-coverage
description: Convert a provider's scraped tiles or vector output into the z14 binary-presence Cloud-Optimized GeoTIFF on the shared grid. Use after a provider's coverage has been fetched.
---

# rasterize-coverage

Turn one provider's fetched coverage into the project's canonical output: a
single-band `uint8` binary-presence COG on the shared **z14 web-mercator grid**
(see `docs/PLAN.md` §3 and `src/coverage_acquisition/rasterize.py`).

## Inputs by source kind
- **raster** providers — stored PNG tiles under `data/raw/<namespace>/.../tiles/`.
  Coverage = non-transparent / non-background pixels. Use
  `rasterize.rasterize_raster_tiles_to_cog`.
- **vector_mvt** providers — `feature_records.csv` (WKT geometries, EPSG:4326).
  Use `rasterize.rasterize_geometries_to_cog`.
- **coverage_json / point** providers — `pano_records.csv` (lat/lon points).
  Use `rasterize.rasterize_geometries_to_cog` with point buffering.

## Steps
1. Locate the provider's fetch output (`manifest.json`, `tile_summary.csv`,
   `feature_records.csv` / `pano_records.csv`) under `data/raw/` or
   `data/intermediate/`.
2. Load the geometries/tiles and call the matching `rasterize.py` function,
   writing the COG to `data/processed/<key>/coverage_z14.tif`.
   For raster providers, call `rasterize_raster_tiles_to_cog` with
   `coordinate_scheme=PROVIDERS[key].coordinate_scheme` so non-web-mercator
   providers (for example, `kakao`) are reprojected correctly.
3. Sanity-check the returned manifest: valid COG, CRS EPSG:3857, dtype `uint8`,
   `covered_pixel_count > 0`, extent matches the fetched area.
4. Register the COG in the STAC catalog with `catalog.upsert_provider_item`
   (`data/processed/stac/`), passing tier, source endpoint, scrape date, and ToS
   notes from `docs/providers/<key>.md`.

## Output
Report the COG path, its extent and covered-pixel count, and confirm the STAC
item was created/updated. Keep the point/vector source data in
`data/intermediate/` — the raster is derived, the records are the source of truth.

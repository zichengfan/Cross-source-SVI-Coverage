---
name: compare-zoom-levels
description: Render a provider's coverage overlay at several source zoom levels over one fixed geographic extent, juxtaposed into a figure for human review. Use to choose or sanity-check a provider's source zoom level.
---

# compare-zoom-levels

Pick — or sanity-check — the **source zoom level** of a coverage-overlay
provider by eye. Given one or more raster or `vector_mvt` providers and a single
fixed extent, this renders each provider's overlay at several zoom levels, every
cell cropped to the *same* geographic box, and lays them out as one figure under
`figures/` for a human to review.

This is the **zoom-calibration** step of the per-provider pipeline: run it once
a provider module exists (so it is registered), before committing to its
`display_zoom`, or whenever revisiting a provider's zoom (e.g. the Kakao L7
question). It is a human-in-the-loop visual aid — the figure is the deliverable,
a person decides.

## The one rule — same extent, always

Comparing tiles at their native per-zoom extents is meaningless: a z9 tile and
a z18 tile cover wildly different areas. **Every cell must show the identical
geographic box.** The script enforces this — you pass one `--center` and one
`--extent-km`, and every cell is mosaicked from its zoom's tiles and cropped to
exactly that box. Likewise, when comparing several providers, give them the same
extent so the only visible difference is real resolution.

## Usage

Run with the project environment:

```
uv run python .claude/skills/compare-zoom-levels/render_zoom_samples.py \
  --provider kakao --provider naver \
  --center 127.0276 37.4979 --extent-km 2 \
  --zooms 13,14,15 \
  --out figures/zoom_compare_seoul.png
```

- `--provider KEY` — a registered provider key; repeat for several (one row each).
- `--center LON LAT` — the centre of the fixed extent (WGS84).
- `--extent-km KM` — the side length of the square extent, in km (same for all cells).
- `--zooms Z,Z,...` — optional source zoom levels (columns). Omitted → a spread
  around each provider's `default_display_zoom`.
- `--out PATH` — output PNG (default `figures/zoom_samples.png`).

Then **Read the output image**, show it to the user, and ask which source zoom
to use. Record the decision in the provider's `docs/providers/<key>.md`.

## Notes

- Works on **raster** coverage-overlay providers (kakao / naver / mapy …) and
  on **`vector_mvt`** providers (mapilio / barikoi / streetview_vn) — vector
  tiles are decoded and their coverage geometry (points / lines / polygons)
  rasterized to the same binary mask; the point/line pen scales with zoom so a
  fixed ground footprint stays consistent across the columns. Other source
  kinds (`coverage_json`, `tencent_mobile_street`) are not `{z}/{x}/{y}` tile
  layers — the script reports and skips them.
- Providers in different countries can still be compared at the same extent
  *size* — run the script once per region with a representative `--center`.
- Coverage is drawn as a binary mask (covered = the provider's colour, empty =
  dark) — the same presence representation as the project's z14 COG output.
- The script reuses `geo.tile_range_for_bbox` / `tile_to_lonlat_bounds_for_scheme`
  for tile maths and the `runtime_config` registry for live `{version}` values,
  so it works for any registered raster provider and any coordinate scheme.

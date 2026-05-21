# Foundation spec — raster-provider prerequisites (kakao / naver / mapy)

Three shared-file changes that the kakao/naver/mapy raster redesign needs.
Build **TDD**. One PR `foundation/raster-provider-prereqs` into `dev`. The exact
endpoint/grid facts are in the rewritten subplans `docs/providers/kakao.md`,
`docs/providers/naver.md`, `docs/providers/mapy.md` — read those first, plus
`CLAUDE.md`, `docs/PLAN.md`, and the files named below.

## 1. `geo.py` — add the `kakao_epsg5181` coordinate scheme

Kakao's roadview-overlay tiles are NOT Web Mercator — they use the Korea-specific
**EPSG:5181** transverse-Mercator grid (see `docs/providers/kakao.md` §2 for the
exact parameters: tile origin, the per-level resolution table, 256-px tiles,
**y-axis up / TMS-style**, served at L7).

- Add the scheme to the two dispatchers in `geo.py`: `tile_range_for_bbox(bbox,
  zoom, coordinate_scheme)` and `tile_to_lonlat_bounds_for_scheme(x, y, zoom,
  coordinate_scheme)` — same pattern as the existing `baidu` /
  `yandex_wgs84_mercator` branches.
- Conversion: WGS84 lon/lat ⇄ EPSG:5181 metres via `pyproj.Transformer`
  (`pyproj` is already a dependency); then metres ⇄ tile index using the origin
  + `resolution(zoom)` + 256-px tile span, with **y increasing northward**.
- TDD: a round-trip test (lon/lat → tile → bounds contains the point) and a
  known-point test — Seoul City Hall (~`126.9779, 37.5663`) must map to the L7
  tile recorded in `docs/providers/kakao.md`.

## 2. `runners.py` — generalize runtime-config discovery for naver

`runners._build_runtime_options` currently only handles Yandex
(`config_kind == "yandex_stv_renderer"`, discovers `stv_version`). naver's tile
template has a volatile `{version}` segment that must be discovered live from its
TileJSON (`https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps` — see
`docs/providers/naver.md` §2).

- Add a branch for `config_kind == "naver_pstatic_tiles"`: fetch the TileJSON
  via `polite.polite_fetch`, parse the live `{version}`, return it in
  `format_values` so `_build_tile_url` fills the template's `{version}`.
- Keep the Yandex path working unchanged. Keep the existing fallback behaviour
  (if discovery fails, use a `version_fallback` from `options`).
- TDD: with `polite_fetch` monkeypatched to return a canned TileJSON, the naver
  runtime options carry the discovered version; on failure it falls back.

## 3. `source_kinds/raster.py` — generalize the empty-tile rule

`raster.py` gates transparent-PNG / HTTP-204 empty-tile detection behind the
Yandex-specific `is_yandex_stv_source` (`config_kind == "yandex_stv_renderer"`).
mapy and naver also serve transparent PNGs for "no coverage" and need the same
treatment.

- Replace the Yandex gate with a provider-agnostic `SourceDefinition.options`
  flag: `empty_tile_rule` — supported values `"transparent_png"` (a decoded tile
  with `coverage_pixel_count == 0` is empty) and `"http_204"` (HTTP 204 / empty
  body is empty); absent → no special empty handling (current default for
  svmap_google etc.).
- Migrate `providers/yandex.py` to set `empty_tile_rule` in its source `options`
  (a foundation PR may edit a provider module). Yandex's behaviour must be
  unchanged — its existing tests in `tests/test_source_kinds.py` must still pass.
- TDD: tests for `empty_tile_rule="transparent_png"` (transparent tile → empty,
  opaque → not), and that yandex still works.

## Done criteria
`uv run pytest` fully green (all existing tests + new), `uv run ruff check src/
tests/` clean. Files touched: `geo.py`, `runners.py`, `source_kinds/raster.py`,
`providers/yandex.py`, and their test files. No new dependency.

# [T1] Provider: Naver Maps Street View (`naver`) — RASTER REDESIGN

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

REDESIGN NOTE (2026-05-21): this subplan supersedes the earlier point-probe /
`streetlevel` design for `naver`. Naver DOES serve a rendered raster overlay
tile layer for its 거리뷰 (Street View) coverage; the previous subplan's "no
tile layer" conclusion referred only to the panorama-point metadata API and was
wrong about coverage tiles. `naver` is redesigned here as a `kind="raster"`
provider, mirroring `svmap_google`.
-->

## 1. Summary

Naver Maps ("네이버 지도", 거리뷰) is South Korea's dominant domestic web-map
provider and ships a first-party street-level panorama product ("거리뷰",
Street View) covering virtually all of South Korea — Seoul, the six metro
cities, secondary towns, rural roads, and offshore islands such as Jeju. It is
**active**, produces its own imagery (car / bicycle / trekker capture; not a
re-hoster), and is in scope for the global SVI coverage database as a **Tier-1**
provider. When the 거리뷰 layer is toggled on, the Naver map viewer draws a
**rendered raster overlay tile layer** of light-purple lines showing exactly
where Street View imagery exists. This subplan redesigns `naver` to fetch that
overlay's `{z}/{x}/{y}` PNG tiles and rasterize them onto the shared z14
coverage grid — exactly like `src/coverage_acquisition/providers/svmap_google.py`.
This replaces the prior point-probe `streetlevel` design.

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:** `https://map.naver.com` — Street View is the
  "거리뷰" layer (`naver.maps.StreetLayer` in the Naver Maps JS API v3, layer
  name `"street"`, label 거리뷰). The overlay is served by Naver's tile CDN
  `map.pstatic.net`.

- **Tier:** T1 — first-party national SVI provider with a public rendered
  coverage overlay.

- **Source kind:** `raster` (existing kind, `source_kinds/raster.py`). No new
  kind is needed. The provider is a near-exact analogue of `svmap_google`: a
  single `SourceDefinition(kind="raster", ...)` whose `template` is a
  `{z}/{x}/{y}` PNG URL and whose coverage decision is "any non-transparent
  pixel" (`summarize_png` already counts non-zero alpha).

- **Coverage endpoint(s):**

  - **Overlay tile template** (the thing to fetch):
    ```
    https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps
    ```
    HTTP `GET`. `mt=ps` selects the 거리뷰 (panorama / Street View) overlay
    layer in isolation — the response is a transparent-background PNG with only
    the coverage lines drawn. `{version}` is a Naver tile-set version code
    (e.g. `1778829614`) that **must be discovered live at fetch time** (see
    below); stale codes return HTTP 400.

  - **Version-discovery endpoint** (call once per run, before fetching tiles):
    ```
    GET https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps
    ```
    Returns a small TileJSON 2.1.0 document:
    ```json
    {"tilejson":"2.1.0","scheme":"xyz","minzoom":0,"maxzoom":21,
     "version":"1778829614","bounds":[-180,-85.0511,180,85.0511],
     "format":"png","center":[127.929498,36.607695,7.0],
     "tiles":["https://map.pstatic.net/nrb/styles/basic/1778829614/{z}/{x}/{y}.png?mt=ps"]}
    ```
    Read `version` and substitute it into the tile template; the TileJSON
    `tiles[0]` value is itself the ready-to-use template.

  - **Headers:** none are strictly required — tiles return HTTP 200 even with no
    `User-Agent` and no `Referer` (verified bare `curl`). For polite scraping the
    `SourceDefinition.headers` should still set a descriptive `User-Agent`, a
    `Referer: https://map.naver.com/`, and `Accept: image/png,image/*;q=0.9,*/*;q=0.1`
    — same posture as `yandex` / `svmap_google`.

  - **Query params:** only `mt=ps` (and `fmt=png` on the `basic.json` call).

- **Coordinate scheme:** **`web_mercator`** — standard Web Mercator XYZ. The
  `basic.json` TileJSON reports `scheme: "xyz"`, the standard
  `bounds: [-180,-85.0511,180,85.0511]`, and tiles align to the
  `lonlat_to_tile` / `tile_to_lonlat_bounds` math in `geo.py` (verified: a tile
  computed for Gangnam, Seoul with the standard slippy-map formula returns the
  Gangnam street grid). **No y-flip (not TMS), no Naver-specific grid.** Note:
  the legacy `onetile{N}.map.naver.net` system in the Naver JS bundle uses a
  Naver-specific `UTMK_NAVER` projection — **do not use the legacy host**; the
  modern `map.pstatic.net/nrb/styles` path is plain Web Mercator XYZ and is the
  one this provider uses.

- **Zoom range / tile size / response format:** Tiles are **256×256 PNG**
  (`image/png`, 8-bit colormap, RGBA when decoded). The TileJSON advertises
  `minzoom:0, maxzoom:21`. The overlay renders meaningfully across roughly
  **z6–z19** (verified non-empty content at z11/z14/z18/z19 over Seoul; z0
  returns a tiny near-empty PNG; z21/z22 return a 145-byte fully transparent
  tile, i.e. above the overlay's native detail). **Use display zoom 13** for
  the pilot raster fetch (same as `svmap_google` / `yandex`) and z11–12 for
  pass-1 discovery; the burn zoom is fixed at z14 per PLAN §3.

- **Auth:** **none.** No token, no cookie, no API key, no login. Tile and
  TileJSON endpoints are public and unauthenticated (verified). **No `.env` key
  is required or added for this provider.** Do not add a `NAVER_*` slot to
  `.env.example`.

- **Presence rule:** "Imagery exists here" = the decoded overlay PNG has **≥ 1
  non-transparent pixel**. The overlay is drawn on a **fully transparent
  background** (alpha = 0) with coverage lines in light purple
  (`(202,201,242,255)` / `(214,213,241,255)` and anti-aliased neighbours);
  every covered pixel is opaque. This is the `coverage_from="alpha"` case —
  `source_kinds/raster.py::summarize_png` already computes
  `coverage_pixel_count = np.count_nonzero(alpha)`, so a Naver overlay tile
  needs **no special decode**; opaque pixels are coverage. A no-coverage tile
  is a small (~145-byte) PNG that is uniformly `alpha == 0` (verified over open
  sea SE of Korea and over an uncovered Jeju tile). **Empty-tile signature is a
  transparent PNG, NOT HTTP 404/204** — every in-bounds tile returns HTTP 200
  `image/png`; emptiness is decided from pixels, not status code.

- **Background vs. line colours:** transparent background (alpha 0) + opaque
  coloured lines → **`coverage_from = "alpha"`**. (Contrast with `mt=bg.ps`,
  which composites the overlay onto an opaque white base — do NOT use a `bg`
  layer; `mt=ps` alone keeps the background transparent so alpha is a clean
  coverage mask.)

- **robots.txt / ToS notes; observed rate limit:**
  - **Tile CDN host `map.pstatic.net`:** `https://map.pstatic.net/robots.txt`
    returns **HTTP 403 with an HTML "Access Denied" body** — there is no
    `robots.txt` file. `polite.robots_allows` treats an unreachable / non-200
    robots.txt as **allowed**, so the overlay tile endpoint on
    `map.pstatic.net` is permitted under the project's robots posture. **All
    fetching for this provider happens on `map.pstatic.net` only.**
  - **Viewer host `map.naver.com`:** `https://map.naver.com/robots.txt` is
    highly restrictive (`User-agent: *` → `Disallow: /`, only `Allow: /$` and
    `/p/$`; `ClaudeBot`, `GPTBot`, `CCBot`, etc. explicitly `Disallow: /`).
    **This provider never fetches from `map.naver.com`** — the viewer URL
    appears only as the `Referer` header value. The restrictive viewer robots
    therefore does not gate this provider, mirroring how the `kakao` module
    keeps all fetches on `rv.map.kakao.com` and never crawls `map.kakao.com`.
  - ToS: Naver Maps content is Naver's; this provider stores only a derived
    binary coverage mask (presence/absence), not Naver imagery or map tiles in
    the published DB. Record the `map.pstatic.net` (no robots) vs
    `map.naver.com` (restrictive, Referer-only) distinction in the module
    docstring.
  - **Observed rate limit:** none hit in light manual probing; no documented
    limit. Use the project polite default via `polite_fetch` (descriptive UA,
    per-host throttle, retry/backoff). A `min_interval_seconds` around the
    0.25 s default is fine for a CDN tile host; keep concurrency modest.

- **Known quirks / gotchas:**
  - **Version code is mandatory and volatile.** The `{version}` path segment
    must be live-discovered from `basic.json?fmt=png&mt=ps` at the start of each
    run — stale codes (e.g. last week's) return HTTP 400 with an empty body
    (verified: `1732841753`, `1700000000` → 400). This is the same live-config
    pattern as `yandex` (which discovers a renderer version from the frontend);
    `naver` discovers a CDN tile-set version from a TileJSON. See §4 for the
    `config_kind` plumbing.
  - **`mt=ps` vs other `mt` mixes.** `mt=ps` = the 거리뷰 overlay alone on a
    transparent background. `mt=bg.ol.ts.ar.lko` is the basic base map; `mt=ps.lko`
    adds Korean labels; `mt=bg.ps` composites onto white. **Use `mt=ps` only** —
    any added base/label layer makes the background opaque and breaks the
    alpha-as-coverage rule.
  - **Empty ≠ 404.** Tiles outside coverage (ocean, uninhabited interior)
    return HTTP 200 with a tiny fully transparent PNG, not 404/204. The
    `raster` kind already handles this: `summarize_png` yields
    `coverage_pixel_count == 0` for such tiles and the rasterizer drops them.
    `skip_404` behaviour is irrelevant here; emptiness is pixel-decided.
  - **Do not use the legacy `onetile{N}.map.naver.net` host.** The Naver JS
    bundle still contains a legacy overlay system (`overlayType:"empty/ol_pn_rd"`,
    projection `UTMK_NAVER`, `maxZoom:14`). It uses a Naver-specific UTMK grid
    not supported by `geo.py`. The modern `map.pstatic.net/nrb/styles/basic`
    path used here is plain Web Mercator XYZ — stick to it.
  - **Higher-zoom tiles are thinner.** Coverage line width is roughly constant
    in screen pixels, so at z18+ the overlay is thin lines on mostly-transparent
    tiles. Burning at z14 from z13–z14 source tiles keeps lines wide enough to
    land on the z14 grid; do not fetch the overlay at very high zoom for the
    coverage burn.
  - **Date layer:** the rendered overlay carries no capture date — it is a
    binary presence mask only. A date (`*_year.tif`) layer for `naver` would
    require the separate panorama-metadata API and is **out of scope** for this
    raster provider (note as a possible future follow-up).

## 3. Test plan (write these FIRST — red before green)

All tests are **offline** — they decode recorded PNG / JSON fixtures and never
hit the network (PLAN §12). Fixtures live under `tests/fixtures/naver/`.

Fixtures to record (small real responses, captured once during scouting-style
manual runs):
- `tests/fixtures/naver/basic_styles_ps.json` — a real
  `basic.json?fmt=png&mt=ps` TileJSON document (contains `version`, `scheme`,
  `minzoom`/`maxzoom`, and the `tiles[0]` template).
- `tests/fixtures/naver/overlay_gangnam_z14.png` — a real `mt=ps` overlay tile
  over Gangnam, Seoul (z14 x=13973 y=6348) — dense coverage, many opaque
  purple-line pixels on a transparent background.
- `tests/fixtures/naver/overlay_empty_ocean_z14.png` — a real `mt=ps` tile over
  open sea SE of Korea (z14 x=14085 y=6544) — a ~145-byte fully transparent PNG.

Tests (`tests/test_providers_naver.py`):

- [ ] `test_naver_registers` — importing `coverage_acquisition.providers`
  registers `"naver"` in `PROVIDERS`; `get_provider("naver")` returns a
  `ProviderDefinition` with `key == "naver"`, `coordinate_scheme == "web_mercator"`,
  and exactly one `SourceDefinition` whose `kind == "raster"`.
- [ ] `test_naver_tile_url_build` — the source `template` (after `{version}`
  substitution) fills correctly for a sample `z/x/y`: e.g. version `1778829614`,
  `z=14,x=13973,y=6348` →
  `https://map.pstatic.net/nrb/styles/basic/1778829614/14/13973/6348.png?mt=ps`.
  Assert host `map.pstatic.net`, the `?mt=ps` query, and `{z}/{x}/{y}` order.
- [ ] `test_naver_source_definition` — the `SourceDefinition` has
  `kind == "raster"`, `expect_content_type_prefix == "image/"`,
  `storage_subdir == "tiles"`, headers carrying a descriptive `User-Agent` and
  `Referer: https://map.naver.com/`, and `options` declaring the live-version
  config (`config_kind`, the `basic.json` URL, `mt`, a `version_fallback`).
- [ ] `test_naver_tilejson_parse` — feeding `basic_styles_ps.json` to the naver
  version-discovery helper yields the `version` string (`"1778829614"`),
  `scheme == "xyz"`, and a tile template string containing `{z}/{x}/{y}` and
  `mt=ps`.
- [ ] `test_naver_decode_present` — feeding `overlay_gangnam_z14.png` through
  `source_kinds.raster.summarize_png` (or the `raster` decode path) yields
  `width == 256`, `height == 256`, and `coverage_pixel_count > 0` (covered
  tile).
- [ ] `test_naver_decode_empty` — feeding `overlay_empty_ocean_z14.png` yields
  `coverage_pixel_count == 0` and `coverage_ratio == 0.0` (checked-but-empty
  tile; transparent PNG, not a 404).
- [ ] `test_naver_coverage_from_alpha` — assert the empty fixture is uniformly
  `alpha == 0` and the Gangnam fixture has opaque (`alpha > 0`) pixels, pinning
  the `coverage_from = "alpha"` rule (regression guard against accidentally
  selecting a `bg`-composited `mt` mix).
- [ ] `test_naver_web_mercator_scheme` — a regression test pinning that
  `geo.tile_range_for_bbox(bbox, zoom, "web_mercator")` for the Gangnam pilot
  bbox produces tile indices that include `(13973, 6348)` at z14 (guards
  against a TMS y-flip or a non-standard grid being introduced).
- Fixtures: small recorded samples under `tests/fixtures/naver/` (above).

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: `raster`** (existing — `source_kinds/raster.py`). No new
  kind. The existing `decode_raster` / `summarize_png` already implement the
  alpha-as-coverage rule the Naver overlay needs.
- [ ] **Live version discovery.** The overlay tile URL needs a `{version}`
  segment that is invalid if stale, so the runner must fetch
  `basic.json?fmt=png&mt=ps` once per run and substitute the `version`.
  Two acceptable approaches — the implementer picks one and documents it:
  - **(Preferred) Generalise the existing Yandex hook.** `runners._build_runtime_options`
    is currently gated on `config_kind == "yandex_stv_renderer"`. Add a sibling
    branch for `config_kind == "naver_pstatic_tiles"` that GETs the configured
    `basic.json` URL via `polite_fetch`, parses the TileJSON, and sets
    `format_values["version"]`. The `naver` `SourceDefinition.template` keeps a
    `{version}` placeholder filled from `runtime_options`, identical in spirit
    to how `yandex` fills `{version}`. **This touches `runners.py`, a shared
    file** — per CLAUDE.md "no shared-file edits", land it as a **small Phase-0
    foundation PR first**, then the `naver` provider PR only adds
    `providers/naver.py`.
  - **(Fallback) Bake discovery into the provider module.** If the foundation
    change cannot land in time, `providers/naver.py` may itself fetch and cache
    `basic.json` via `polite_fetch` at import/first-use and expose a resolved
    template. Less clean (provider does I/O); acceptable only as a stopgap and
    must be noted in the docstring.
  Either way: keep a `version_fallback` in `options` so a transient TileJSON
  fetch failure degrades gracefully (it will still 400 if the fallback is
  stale — log it, do not crash the run).
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/naver.py` defining `PROVIDER` as a
  `ProviderDefinition` and calling `register_provider(PROVIDER)` — mirror
  `svmap_google.py` / `yandex.py`:
  - `key="naver"`, `output_namespace="naver_streetview_raster"`,
    `run_label_prefix="naver_streetview_raster"`, `default_display_zoom=13`,
    `coordinate_scheme="web_mercator"`.
  - `area_presets`: declare the pilot bbox **inside the provider module** (do
    not edit `_presets.py`) — `seoul_gangnam_pilot_bbox`
    `BoundingBox(127.020, 37.490, 127.060, 37.520)`.
  - One `SourceDefinition`:
    - `id="naver_streetview_overlay_png"`, `kind="raster"`.
    - `template="https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps"`.
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3", "Referer":
      "https://map.naver.com/", "Accept": "image/png,image/*;q=0.9,*/*;q=0.1"}`.
    - `storage_subdir="tiles"`, `expect_content_type_prefix="image/"`.
    - `options={"config_kind": "naver_pstatic_tiles",
      "tilejson_url": "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps",
      "mt": "ps", "version_fallback": "1778829614",
      "empty_tile_rule": "transparent_png", "coverage_from": "alpha"}`.
      (`empty_tile_rule="transparent_png"` flags the transparent no-coverage
      tiles as `is_empty` so they are not stored — the same B0 rule `kakao`
      uses; most of mountainous/offshore Korea returns empty tiles.
      `version_fallback` is the version observed live 2026-05-22.)
    - `notes` recording the `mt=ps` transparent-overlay choice and the
      `map.pstatic.net` (no robots) vs `map.naver.com` (restrictive, Referer
      only) distinction.
  - Module docstring records the robots/ToS posture from §2, the live-version
    requirement, and the redesign note (was point-probe, now raster).
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `127.020 37.490 127.060 37.520` (`Seoul — Gangnam`,
  dense guaranteed coverage, ~3.6 × 3.3 km) at display zoom 13. Discover the
  live version, fetch the `mt=ps` overlay tiles, confirm tiles decode and have
  `coverage_pixel_count > 0` on the Gangnam street grid.
- [ ] Rasterize the pilot area to a z14 COG with the standard raster pipeline
  (alpha mask → coverage); sanity-check: covered pixels land on Gangnam's
  street grid (Teheran-ro, Gangnam-daero), not on the Han River or rooftops;
  CRS EPSG:3857, `uint8`.
- [ ] **Two-pass full extent:** pass-1 discovery region bbox
  `124.5 33.0 131.9 38.7` (mainland South Korea + Jeju + offshore islands) at
  discovery zoom **z11–z12**; pass-2 burns covered cells at z14. Korea-only, so
  the tile volume is bounded. Run detached in `tmux` (PLAN §5 / `run-scraper`).
- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T1"`,
  `source_endpoint="https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps"`,
  `tos_notes=<robots posture from §2>`); update the inventory status for `naver`.
- [ ] (Future, out of scope here) optional date layer via the Naver panorama
  metadata API → `naver_streetview_raster_year.tif`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.naver` imports and
  self-registers in `PROVIDERS`; CI import/register/dry-run smoke test passes.
- The single source is `kind="raster"`, `coordinate_scheme="web_mercator"`, and
  its tile URL resolves to a live `map.pstatic.net/nrb/styles/basic/{version}/
  {z}/{x}/{y}.png?mt=ps` (version live-discovered, not hard-coded stale).
- Pilot tiles fetch (HTTP 200 `image/png`) and decode; covered tiles have
  `coverage_pixel_count > 0`, empty tiles (transparent PNG) decode to
  `coverage_pixel_count == 0` and are dropped — coverage lands on Gangnam
  roads/land, not on water.
- z14 COG is valid (`rio_cogeo.cog_validate`), CRS EPSG:3857, `uint8`, covered
  pixels > 0.
- All fetching goes through `polite.polite_fetch` with a descriptive
  `User-Agent`; only `map.pstatic.net` is fetched, `map.naver.com` is never
  crawled (Referer only).
- The robots.txt / ToS posture is documented in the `providers/naver.py`
  docstring and in the STAC item `tos_notes`.
- No `NAVER_*` secret is required or added (provider is unauthenticated).

## 6. Status log

- `2026-05-20` scout: drafted (original point-probe `streetlevel` design).
- `2026-05-21` scout: **REDESIGNED as a `kind="raster"` provider.** Confirmed
  Naver serves a rendered 거리뷰 coverage overlay tile layer — the prior "no
  tile layer" conclusion was about the panorama-point metadata API and was
  wrong about coverage tiles. Findings, all verified live this session:
  - Endpoint: `https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps`
    (extracted from the Naver Maps JS v3 bundle's `StreetLayer` /
    `getStreetLayer` definition and the `nrb/styles` tile builder, then probed
    directly).
  - Fetchable & renders coverage: a z14 Gangnam tile returned HTTP 200
    `image/png` 256×256, a transparent-background PNG whose opaque pixels form
    Gangnam's street grid in light purple — visually confirmed (rendered the
    tile over white). Busan, Seoul City Hall, and Jeju City tiles also returned
    coverage; ocean tiles returned a ~145-byte fully transparent PNG.
  - Scheme: standard Web Mercator XYZ (`basic.json` reports `scheme:"xyz"`,
    standard bounds, no y-flip) → `coordinate_scheme="web_mercator"`.
  - Zoom: TileJSON `minzoom:0/maxzoom:21`; meaningful overlay content z6–z19.
  - Auth: none — tiles return 200 with no UA / no Referer / fully bare.
  - Empty signature: transparent PNG at HTTP 200 (not 404/204).
  - `coverage_from = "alpha"` (transparent background + opaque coloured lines);
    `source_kinds/raster.py::summarize_png` already implements this.
  - Version code is volatile: stale codes 400; must live-discover from
    `https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps` per run.
  - robots: `map.pstatic.net/robots.txt` → 403 / no file → allowed (this is the
    only host fetched). `map.naver.com/robots.txt` is restrictive but is never
    crawled — viewer URL used as `Referer` only.
- `2026-05-21` open questions for the human reviewer:
  1. **Live-version plumbing.** The `{version}` segment must be discovered each
     run. Preferred fix generalises `runners._build_runtime_options` (currently
     Yandex-only) with a `config_kind == "naver_pstatic_tiles"` branch — that
     edits the shared `runners.py`, so per CLAUDE.md it should land as a small
     Phase-0 foundation PR *before* the `naver` provider PR. Confirm this
     sequencing (foundation PR first), or approve the in-module fallback
     discovery as a stopgap.
  2. **Replacing the old `naver` module.** The current `src/coverage_acquisition/
     providers/naver.py` is the point-probe `streetlevel` implementation and the
     `naver` `streetlevel` probe is registered there. The raster redesign
     **replaces that module wholesale** (new `output_namespace`,
     `run_label_prefix`, no `register_streetlevel_probe`). Confirm the redesign
     PR may delete/rewrite the existing module and its tests
     (`tests/test_providers_naver.py`) rather than add a parallel provider key.
  3. **Display/discovery zoom.** Pilot at z13, pass-1 discovery at z11–z12,
     burn at z14 are starting estimates consistent with `svmap_google`/`yandex`;
     reviewer may tune.
- `2026-05-21` approval: approved by the user (raster redesign).
- `2026-05-21` foundation: the `naver_pstatic_tiles` runtime-config branch and
  the generic `empty_tile_rule` option both landed on `dev` via the B0
  foundation PRs (#22, #23) and the rasterizer foundation PR (#25). The
  provider PR can proceed.

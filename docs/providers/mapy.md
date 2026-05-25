# [T1] Provider: Mapy.com / Mapy.cz (`mapy`) — REDESIGN to raster overlay tiles

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

REDESIGN NOTE (2026-05-21): mapy was previously specced as a `streetlevel`
point-probe provider (FRPC `getbest` per point). Scouting the live Mapy.com
viewer found that the Panorama coverage overlay IS a real raster `{z}/{x}/{y}`
PNG tile layer. This file is rewritten as a `kind="raster"` provider mirroring
`svmap_google.py` / `yandex.py`. All streetlevel / FRPC / point-query language
has been removed.
-->

## 1. Summary

Mapy.com (formerly Mapy.cz) is the dominant Czech web-mapping service, operated
by Seznam.cz. It offers a "Panorama" street-level imagery layer with extensive
coverage of the **Czech Republic only** (the entire country was re-imaged
2021–2023, one-third per year west-to-east, plus 21 cities re-shot). It is in
scope as an active, scrapable provider: its public web viewer draws a
**panorama coverage overlay as raster `{z}/{x}/{y}` PNG tiles** served from
`mapserver.mapy.cz`, requiring no authentication. This project fetches that
overlay-tile layer and rasterizes it onto the shared z14 grid — exactly the
`kind="raster"` pattern used by `svmap_google` and `yandex`. Only coverage
presence is stored; no panorama imagery is downloaded.

## 2. Research findings (filled by provider-scout)

### Verdict: Mapy serves a RASTER overlay tile layer

The Panorama coverage overlay is **raster `{z}/{x}/{y}` PNG tiles** — not vector
MVT, and not purely client-side. mapy **can** be redesigned as a `kind="raster"`
provider. Evidence below was gathered from the live viewer JS bundle and by
probing the tile host directly.

- **Homepage / public viewer URL:**
  - Homepage / viewer: `https://mapy.com/` (legacy `https://en.mapy.cz/`
    301-redirects to `https://mapy.com/en/...`).
  - Viewer with the Panorama layer enabled:
    `https://mapy.com/en/zakladni?pano=1&x=14.42158&y=50.08756&z=17`.
  - Tier: **T1**.

- **How the overlay was identified.** The viewer is a JS SPA; the coverage
  overlay is created in the app bundle `https://mapy.com/js/userweb.<ver>.js`
  (`userweb.2.81.6.js` at scout time). The relevant call:

  ```js
  createPanoLayer("pano-layer", {
    pointsUrl: `${mapserver.url}/panorama_pt_hybrid-m/`,
    lineUrl:   `${mapserver.url}/panorama_ln_hybrid-m/`,
    pointsZoom: 19,
  })
  ```

  The pano layer class extends `SMap.Layer.Canvas` with `SMap.LAYER_TILE`: it is
  a **raster tile canvas layer**. It loads each tile as `new Image()`
  (`_drawTile`) — i.e. PNG raster, not MVT. Two sub-layers:
  - **`panorama_ln_hybrid-m/`** — the coverage **lines** layer ("panorama exists
    on this street"). Used at zoom `< pointsZoom (19)`. **This is the layer this
    project scrapes.**
  - **`panorama_pt_hybrid-m/`** — the coverage **points** layer, used only at
    zoom ≥ 19 (individual pano dots). Not needed for z14 coverage.

- **Coverage endpoint(s):**
  - **Line overlay (use this):**
    `https://mapserver.mapy.cz/panorama_ln_hybrid-m/{z}-{x}-{y}`
  - Point overlay (reference only):
    `https://mapserver.mapy.cz/panorama_pt_hybrid-m/{z}-{x}-{y}`
  - **HTTP method:** `GET`.
  - **Tile path format:** the SMap SDK's default tile query is
    `"{zoom}-{x}-{y}"` (`SMap.Layer.Tile.DEFAULT_OPTIONS`), i.e. the path
    segment is a single token `{z}-{x}-{y}` (hyphen-separated, NOT a
    `/{z}/{x}/{y}/` directory tree). The pano layer passes no custom `query`,
    so it uses this default.
  - **Query params:** the viewer appends `?sdk=<token>` (and optionally
    `&apikey=<key>` if a Loader API key is set). **Scouting confirmed these are
    NOT required** — `GET .../panorama_ln_hybrid-m/14-8848-5550` with no query
    string returns `200 image/png`. Do not send `sdk`/`apikey`.
  - **Host shard `#`:** the SMap SDK supports a `#` placeholder in tile URLs
    replaced by a shard digit `1 + ((x + y) & 3)`. The pano layer's
    `lineUrl`/`pointsUrl` contain **no `#`**, so there is a single host
    (`mapserver.mapy.cz`) and no sharding to implement.
  - **Required headers:** `Referer: https://mapy.com/` is **required** — not
    merely polite. Re-verified live 2026-05-22: an empty tile fetched *without*
    a `Referer` returns **HTTP 403** (153-byte `text/html`); *with* the
    `Referer` it returns the documented `302 → ./default` (see Presence rule).
    Covered tiles return `200 image/png` either way. Always send a descriptive
    `User-Agent`, `Referer: https://mapy.com/`, and
    `Accept: image/png, image/*;q=0.9, */*;q=0.1` — the `SourceDefinition.headers`
    in §4 already do. (Earlier scout text "no headers required" was wrong for
    the empty-tile path.)

- **Coordinate scheme:** `web_mercator` (standard EPSG:3857 / WGS84 spherical
  Mercator, 256-px tiles, the same XYZ scheme as OSM and `svmap_google`).
  Verified by probing: Prague centre (50.0875 N, 14.4213 E) →
  `z14 = 14-8848-5550`, returned a filled tile; Atlantic ocean
  (`14-6371-6759`) and Vienna (`14-8937-5681`) returned empty tiles. No custom
  datum shift (unlike Baidu/Yandex).

- **Zoom range / tile size / response format:**
  - **Tile size:** 256 × 256 PNG (`SMap.Layer.Tile.DEFAULT_OPTIONS.tileSize =
    256`). Confirmed: every probed tile is `PNG image data, 256 x 256`.
  - **Native zoom range of the line layer:** renders from **z7 up to ~z20**.
    Probed Prague tiles at z7,8,9,10,11,12,14,16,18 → all filled PNG; z20 → a
    small filled PNG; z21 → empty (redirect to `default`). The line layer is
    fully usable at the project's analysis zoom **z14** and at coarse discovery
    zooms (z8–z9).
  - **Response format:** 8-bit colormap / RGBA PNG. Filled tiles draw
    semi-transparent **red** coverage lines (see colors below). The empty tile
    is a fully-transparent 256×256 PNG (see Presence rule).
  - Content-Type: `image/png`. Filled tiles `cache-control: max-age=86400`.

- **Auth:** **none.** No API key, token, cookie, or `sdk` value is required —
  confirmed by direct probing. **No `.env` key is needed** for `mapy`.

- **Presence rule:** Each fetched tile is decoded as a PNG; **a tile shows
  coverage iff it contains ≥ 1 pixel with alpha > 0** (i.e. any non-transparent
  pixel — the red coverage lines). Two equivalent empty signals were observed:
  1. **HTTP 302 redirect.** An empty tile responds `302 Found` with
     `location: ./default`. `urllib.request.urlopen` (used by
     `polite.polite_fetch`) **follows 302 automatically**, so the fetcher
     transparently receives the redirect target.
  2. **The `default` placeholder PNG.** The redirect target
     `https://mapserver.mapy.cz/panorama_ln_hybrid-m/default` is a **442-byte,
     256×256, fully-transparent PNG** (0 opaque pixels — verified). Every empty
     tile resolves to this exact placeholder.
  Therefore the implementer does **not** need to special-case the 302: just
  decode whatever PNG `polite_fetch` returns and test `coverage_pixel_count`.
  This is the **same empty-tile rule already implemented for Yandex STV** in
  `source_kinds/raster.py` (`is_yandex_stv_source` → `coverage_pixel_count == 0`
  ⇒ `is_empty`). See §4 for the small generalization needed.
  - z14 raster cell mapping: a tile that contains coverage pixels →
    contributing cells **covered (1)**; a probed tile with zero coverage pixels
    → **checked-empty (0)**; never-probed cells → **nodata (255)**. (Standard
    raster-kind → `rasterize.py` flow.)

- **Filled-tile colors (for rasterization / sanity checks):** coverage lines are
  semi-transparent red. Dominant pixel values observed on Prague/Brno z14 tiles:
  - core line `rgba(253, 0, 0, 128)` (by far the most common),
  - antialias / outline shades `rgba(246,0,0,~130)`, `rgba(242,0,0,~133)`,
    `rgba(205,0,0,~233)`, `rgba(205,0,0,~237)`.
  All coverage pixels are pure-ish red (`R` high, `G=0`, `B=0`) with partial
  alpha. The rasterizer should treat **any alpha > 0** as coverage; the
  red-only palette is a useful cross-check but not the presence test.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://mapy.com/robots.txt` and `https://en.mapy.cz/robots.txt` both
    return **HTTP 200 with an empty body** (`content-length: 0`) — no `Disallow`
    rules served, so `robots_allows()` returns `True`. `mapserver.mapy.cz` (the
    tile host) — fetch its `/robots.txt` during implementation and record the
    result in the status log; an empty/absent robots.txt → allowed.
  - The `panorama_ln_hybrid-m` tile endpoint is undocumented (the public
    Developer Mapy REST API exposes only `basic`/`outdoor`/`aerial`/
    `names-overlay`/`winter` map sets — no panorama overlay). Mapy's general
    Terms of Use restrict bulk reuse of map content; this project stores only a
    **binary coverage raster** (presence, not imagery, not the rendered tiles
    themselves long-term). **Record this caveat in the provider module
    docstring** and keep the scrape polite and small.
  - No published rate limit. Tiles are CDN-cached (`envoy` server,
    `cache-control: max-age=86400` on filled tiles). Use a conservative
    per-host throttle (≈ 4–5 req/s; `PolitePolicy(min_interval_seconds≈0.2)`)
    with the shared retry/backoff. Czech Republic is small enough that a full
    z14 scrape is modest (see §4).

- **Known quirks / gotchas:**
  - **Non-standard tile path token.** The path segment is `{z}-{x}-{y}`
    (hyphens), not `/{z}/{x}/{y}`. The `template` in `SourceDefinition` must use
    `panorama_ln_hybrid-m/{z}-{x}-{y}`. The runner's web-mercator tile
    enumeration still produces ordinary integer `z/x/y`; only the URL string
    differs.
  - **Empty tile = 302 → transparent `default` PNG.** Not a 404, not a 204.
    A naive "skip on 404" will never trigger; rely on the transparent-PNG
    presence rule. `polite_fetch` follows the 302 and returns the placeholder
    PNG with `http_status == 200` and `content_type == image/png`.
  - **Two sub-layers — use `panorama_ln_hybrid-m` (lines), not
    `panorama_pt_hybrid-m` (points).** The points layer only renders at z ≥ 19
    and is sparse; the lines layer is the contiguous coverage footprint and
    renders at every zoom the project needs.
  - **Czech-only coverage.** Confirmed: filled tiles over Prague, Brno,
    Ostrava, Tábor; empty (302→default) over Vienna (AT) and ocean. Restrict
    the discovery region to the Czech Republic bbox; do not waste fetches
    outside it.
  - **No dates in the overlay.** The raster tiles encode presence only — no
    per-pixel capture date. A `mapy_year.tif` date layer is **out of scope** for
    this raster redesign (dates would require the separate FRPC `getbest`
    metadata path; defer as a possible follow-up, not part of this provider).
  - **`sdk`/`apikey` query params.** The viewer sends them but the endpoint
    does not require them; omit them. If Mapy ever starts enforcing the `sdk`
    token, the value derives from `SMap.getSDKHeaderValue()` in the SDK bundle —
    flagged here only as a fallback, not implemented now.
  - **No host sharding.** Single host `mapserver.mapy.cz`; the SDK `#`
    shard-placeholder is unused by the pano layer.

## 3. Test plan (write these FIRST — red before green)

Unit tests must not hit the network. Decode small recorded PNG fixtures under
`tests/fixtures/mapy/`.

- [ ] `test_mapy_registers` — importing `coverage_acquisition.providers.mapy`
      registers `"mapy"` in `PROVIDERS`; `get_provider("mapy")` returns a
      `ProviderDefinition` whose `key == "mapy"` with exactly one source.
- [ ] `test_mapy_source_kind_is_raster` — the provider's single
      `SourceDefinition.kind == "raster"`.
- [ ] `test_mapy_coordinate_scheme` — `PROVIDER.coordinate_scheme ==
      "web_mercator"`.
- [ ] `test_mapy_tile_url_build` — formatting the source `template` with
      `z=14, x=8848, y=5550` yields exactly
      `https://mapserver.mapy.cz/panorama_ln_hybrid-m/14-8848-5550`
      (hyphen-joined token, no `/{z}/{x}/{y}/` tree, no `sdk`/`apikey` params).
- [ ] `test_mapy_decode_present` — feeding the `raster` decoder the
      `tile_prague_z14.png` fixture yields a `DecodeResult` with
      `coverage_pixel_count > 0` and `is_empty is False`; the stored payload is
      written.
- [ ] `test_mapy_decode_empty` — feeding the `raster` decoder the
      `tile_empty_default.png` fixture (the 442-byte transparent placeholder)
      yields `DecodeResult` with `coverage_pixel_count == 0` and
      `is_empty is True`; no tile file is written.
- [ ] `test_mapy_empty_tile_rule_wired` — the `mapy` source carries the option
      that activates transparent-PNG empty detection in `source_kinds/raster.py`
      (see §4 — `options["empty_tile_rule"] == "transparent_png"` or the agreed
      key), so a fully-transparent tile is classified `is_empty`.
- [ ] `test_mapy_no_auth_required` — the `SourceDefinition` has no
      `token_query_param`; the module references no `.env` key.
- [ ] `test_mapy_coverage_color_is_red` — (optional, defensive) on
      `tile_prague_z14.png`, every opaque pixel has `R > 0, G == 0, B == 0`
      (the coverage palette is red-only), guarding against a future endpoint
      change that would silently alter the layer.
- Fixtures under `tests/fixtures/mapy/` (record once with a tiny throwaway
  script, then commit small):
  - `tile_prague_z14.png` — `GET
    https://mapserver.mapy.cz/panorama_ln_hybrid-m/14-8848-5550`
    (a dense, filled Prague tile; ~25 KB).
  - `tile_empty_default.png` — `GET
    https://mapserver.mapy.cz/panorama_ln_hybrid-m/default`
    (the 442-byte fully-transparent placeholder).
  - `tile_brno_z14.png` — optional second filled tile (`14-8947-5613`) for a
    rasterization sanity check.
  - NOTE: the old streetlevel fixtures (`getbest_present.json`,
    `getbest_absent.json`) from the previous design are obsolete — delete them.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: existing `raster`.** No new kind. The provider mirrors
      `src/coverage_acquisition/providers/svmap_google.py` and
      `providers/yandex.py`.
- [ ] **One small shared-file generalization (separate foundation PR first).**
      `source_kinds/raster.py` currently gates transparent-PNG empty detection
      behind `is_yandex_stv_source` (`options["config_kind"] ==
      "yandex_stv_renderer"`). mapy needs the *same* "transparent PNG ⇒ empty"
      behaviour but is not Yandex. Generalize the check to a provider-agnostic
      option, e.g. `options.get("empty_tile_rule") == "transparent_png"` (with
      `yandex_stv_renderer` mapped to it for backward compatibility). **This
      edits a shared file (`raster.py`), so per `CLAUDE.md` it must land in its
      own small foundation PR before the `mapy` provider PR** — the `mapy` PR
      then only adds `providers/mapy.py`. If the reviewer prefers, mapy can
      instead reuse `config_kind` semantics, but a clean generic key is better.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/mapy.py` defining `PROVIDER` as a
      `ProviderDefinition` and calling `register_provider(PROVIDER)`. Shape
      (mirror `svmap_google.py` / `yandex.py`):
  - `key="mapy"`, `output_namespace="mapy_panorama_raster"`,
    `run_label_prefix="mapy_panorama"`, `coordinate_scheme="web_mercator"`,
    `default_display_zoom=14`.
  - One `SourceDefinition`:
    - `id="mapy_panorama_lines"`, `kind="raster"`,
    - `template="https://mapserver.mapy.cz/panorama_ln_hybrid-m/{z}-{x}-{y}"`,
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
      "Referer": "https://mapy.com/"}`,
    - `storage_subdir="tiles"`,
    - `expect_content_type_prefix="image/"`,
    - `options={"empty_tile_rule": "transparent_png"}` (the key agreed in the
      foundation PR above),
    - `notes` describing the line overlay, the `{z}-{x}-{y}` hyphen token, and
      the 302→transparent-`default` empty signal.
  - `area_presets`: declare the pilot bbox inline in this module (do **not**
    add to `_presets.py`).
  - Module docstring: record the redesign (was streetlevel, now raster), the ToS
    caveat (undocumented `panorama_ln_hybrid-m` endpoint; only a binary
    coverage raster is published, no imagery), and the Czech-only extent.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `14.40 50.075 14.44 50.095` (**Prague — Old Town /
      city centre**, ~2.8 km × 2.2 km) at display zoom **z14**. Expect dense
      red coverage on the central street network. Scouting confirmed filled
      z14 tiles `14-8848-5550` (Prague centre) and `14-8947-5613` (Brno).
- [ ] Rasterize the pilot area to a z14 COG (EPSG:3857, `uint8`,
      1=covered / 0=checked-empty / 255=nodata) via `rasterize.py`; sanity-check
      that covered pixels land on Prague streets, not ocean.
- [ ] **Two-pass full extent:** pass-1 discovery region = **Czech Republic
      bbox** `12.09 48.55 18.86 51.06`, discovery zoom **z8** (the line layer
      renders fine at z8; ~6×4 tiles cover all of Czechia — cheap). Pass-2:
      fetch z14 tiles only in the discovery cells that showed coverage. The
      whole Czech Republic at z14 is roughly ~200×180 ≈ 36k tiles worst-case
      (most are empty/302); two-pass keeps this well bounded. Do **not** fetch
      outside the Czech bbox.
- [ ] Update / replace the STAC item for `mapy` (extent = discovered coverage
      envelope ≈ Czech Republic, scrape date, tier T1, source endpoint
      `mapserver.mapy.cz/panorama_ln_hybrid-m`, ToS notes). The existing
      `data/processed/stac/mapy` item from the old design must be regenerated
      for the raster output. Update the inventory status for `mapy`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.mapy` imports and
  self-registers (`"mapy"` in `PROVIDERS`); CI smoke test (import + register +
  dry-run) passes.
- The provider's single source is `kind="raster"`,
  `coordinate_scheme="web_mercator"`; the tile `template` builds the
  hyphen-token URL `.../panorama_ln_hybrid-m/{z}-{x}-{y}` with no auth params.
- Pilot z14 fetch over central Prague returns filled PNG tiles that decode to
  `coverage_pixel_count > 0`; the transparent `default` placeholder decodes to
  `is_empty`. Decoded coverage lands on roads/land in the Czech Republic (not
  ocean, not outside CZ).
- z14 COG is valid: CRS EPSG:3857, `uint8`, covered pixels > 0, internal
  overviews present.
- Fetches go through `polite.polite_fetch` with a descriptive User-Agent and a
  conservative throttle; no bare `urllib`/`requests` in the provider path.
- ToS caveats documented in the `mapy.py` module docstring (undocumented
  `panorama_ln_hybrid-m` tile endpoint; only a binary coverage raster is
  published, never imagery; Czech-only extent).

## 6. Status log

- `2026-05-20` scout: drafted (original streetlevel/FRPC design — superseded).
- `2026-05-20` approval: pending.
- `2026-05-21` scout (REDESIGN): rewrote as a `kind="raster"` overlay-tile
  provider. **Confirmed live that Mapy's Panorama coverage overlay is a real
  raster `{z}/{x}/{y}` PNG tile layer**, not vector MVT and not purely
  client-side. Findings:
  - The viewer bundle `mapy.com/js/userweb.2.81.6.js` builds the overlay via
    `createPanoLayer({lineUrl:"${mapserver}/panorama_ln_hybrid-m/",
    pointsUrl:"${mapserver}/panorama_pt_hybrid-m/", pointsZoom:19})`; the layer
    class extends `SMap.Layer.Canvas` / `SMap.LAYER_TILE` and loads tiles as
    `new Image()` → raster PNG.
  - Endpoint (lines layer):
    `https://mapserver.mapy.cz/panorama_ln_hybrid-m/{z}-{x}-{y}` — path token is
    hyphen-joined (`SMap.Layer.Tile.DEFAULT_OPTIONS.query = "{zoom}-{x}-{y}"`),
    256-px PNG, standard web-mercator XYZ.
  - Probed live: Prague `14-8848-5550` → `200 image/png` 25 KB filled; Brno
    `14-8947-5613` → filled; line layer renders z7–~z20; Vienna `14-8937-5681`
    and Atlantic `14-6371-6759` → `302 → ./default` (442-byte fully-transparent
    PNG, 0 opaque pixels). No `sdk`/`apikey` needed (200 without them).
  - Coverage lines are semi-transparent red (`rgba(253,0,0,128)` core).
    Presence rule = any pixel with alpha > 0 — identical to the existing Yandex
    STV transparent-PNG empty-tile rule in `source_kinds/raster.py`.
  - `mapy.com` / `en.mapy.cz` `robots.txt` = HTTP 200 empty body (no Disallow).
    Coverage confirmed Czech-only. No auth / no `.env` key.
  - Old streetlevel fixtures (`getbest_*.json`) are obsolete and should be
    deleted; the existing `data/processed/stac/mapy` item must be regenerated.
- `2026-05-21` approval: approved by the user (raster redesign).
- `2026-05-22` foundation: the generic `empty_tile_rule` option landed on `dev`
  (B0 PRs #22/#23) and the rasterizer is coordinate-scheme aware (#25). The
  provider PR can proceed.
- `2026-05-22` implement: rebuilt `providers/mapy.py` as a `kind="raster"`
  provider on branch `provider/mapy`. Re-verified the endpoint live: covered
  tiles (Prague 14-8848-5550, Brno 14-8947-5613) → `200 image/png`; the
  `default` placeholder → 442-byte fully-transparent PNG. **Correction:** the
  `Referer: https://mapy.com/` header is *required* — without it empty tiles
  return HTTP 403 instead of `302 → ./default` (see §2). Fixtures recorded:
  `tile_{prague,brno}_z14.png`, `tile_empty_default.png`.
- `YYYY-MM-DD` verify: notes appended here.

---

### Open questions for the reviewer

1. **Shared-file edit for the empty-tile rule.** `source_kinds/raster.py` gates
   transparent-PNG empty detection behind a Yandex-specific flag. mapy needs the
   same behaviour. Recommended: a small foundation PR generalizing it to
   `options["empty_tile_rule"] == "transparent_png"` (back-compat alias for
   `yandex_stv_renderer`), merged before the `mapy` provider PR. Confirm this
   approach, or approve reusing `config_kind` directly.
2. **Discovery zoom.** Proposed two-pass discovery at z8 (the line layer renders
   at z7+). Confirm z8, or prefer z9 for a finer pass-1 footprint.
3. **Date layer out of scope.** The raster overlay encodes presence only, no
   capture dates. A `mapy_year.tif` date layer would require the separate FRPC
   `getbest` metadata path and is deferred. Confirm the raster coverage scrape
   ships without a date layer.
4. **Tile retention.** Filled overlay tiles are Mapy-rendered map content. The
   project keeps raw tiles only in gitignored `data/raw/` and publishes a
   derived binary COG. Confirm this satisfies the ToS posture, or require
   deleting `data/raw/mapy/` after rasterization.

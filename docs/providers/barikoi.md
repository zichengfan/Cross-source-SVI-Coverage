# [T2] Provider: Barikoi ThirdEye360 (`barikoi`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Barikoi is the leading Bangladeshi mapping / location-data company
(`https://barikoi.com/`), a B2B/B2G provider of maps, geocoding and routing
APIs for Bangladesh and other emerging markets. Its street-level imagery
product — historically pitched as a "Google Street View alternative" and
referred to in press as *Drishty* — ships today as **ThirdEye360**, a public
360° street-view viewer at `https://streetview.bmapsbd.com/`. Coverage is
Bangladesh only (currently the Dhaka region and a corridor extending west,
roughly the bbox `88.53,23.69 → 90.51,25.87`). Barikoi is in scope as an
**active, first-party** SVI provider whose coverage map is **publicly and
programmatically reachable**: the ThirdEye360 viewer draws every captured
panorama as a point in a **Mapbox Vector Tile (MVT) layer** served
unauthenticated from `tiles.bmapsbd.com`. This subplan scrapes that vector tile
layer and rasterizes it onto the shared z14 coverage grid. Only coverage
presence is stored; no panorama imagery is downloaded.

**Verdict: cleanly scrapable.** Barikoi is a commercial company, but its
street-view *coverage* layer is a public, key-free vector tile endpoint — the
"commercial" inventory note applies to Barikoi's geocoding/maps APIs, not to
this coverage layer. `barikoi` is specced here as a `kind="vector_mvt"`
provider, mirroring `panoramax` / `mapillary` / `ja360`.

## 2. Research findings (filled by provider-scout)

### Verdict: ThirdEye360 serves a VECTOR (MVT) coverage tile layer

The scouting priority (look for a rendered raster overlay first, then MVT, then
JSON) resolved to **MVT**. There is **no rendered raster `{z}/{x}/{y}` PNG
coverage overlay** for ThirdEye360. The viewer is a MapLibre GL map that adds a
single **vector** source whose points are the panorama capture locations; the
coverage footprint is "wherever that point layer has features". All evidence
below was gathered from the live viewer assets and by probing the tile host
directly (probes done 2026-05-22).

- **Homepage / public viewer URL:**
  - Company homepage: `https://barikoi.com/` (a Vite/React SPA; its product
    nav links the street-view product, labelled **"ThirdEye360"**, to
    `https://streetview.bmapsbd.com/`).
  - Street-view viewer: **`https://streetview.bmapsbd.com/`** — a Next.js app
    titled "ThirdEye360", description "Interactive 360° street view
    experience". This is the viewer this provider scrapes the coverage from.

- **Tier:** **T2** (per the inventory note; a single-country first-party SVI
  provider with a public coverage layer).

- **Source kind:** `vector_mvt` (existing kind — `source_kinds/vector_mvt.py`).
  **No new source kind, no foundation prerequisite.** The provider mirrors
  `src/coverage_acquisition/providers/panoramax.py` and
  `src/coverage_acquisition/providers/mapillary.py` (but, unlike `mapillary`,
  needs **no token**).

- **How the overlay was identified.** The `streetview.bmapsbd.com` Next.js app
  bundle (`/_next/static/chunks/app/page-*.js`) builds a MapLibre GL map and,
  in its `onLoad` handler, adds a vector tile source:
  ```js
  e.target.getSource("thirdEye") || (
    e.target.addSource("thirdEye", {
      url: "https://tiles.bmapsbd.com/ThirdEye360",
      type: "vector"
    }), eo(!0))
  ```
  The `addSource(..., {type:"vector", url:...})` form means `url` points at a
  **TileJSON** document, not a tile template. Fetching it
  (`GET https://tiles.bmapsbd.com/ThirdEye360`) returns the TileJSON below.
  (The basemap is a separate Barikoi style — `map.barikoi.com/styles/...` — and
  is not relevant; the panorama *imagery* itself is served from S3-style
  `driveUrl_*` / `imageUrl_*` URLs carried as feature properties, and is **not**
  fetched by this provider.)

- **TileJSON (`GET https://tiles.bmapsbd.com/ThirdEye360`, verified live):**
  ```json
  {
    "tilejson": "3.0.0",
    "tiles": ["https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}"],
    "vector_layers": [{
      "id": "ThirdEye360",
      "fields": { "capture_date":"String", "capture_date_raw":"String",
        "capture_date_timestamp":"Number", "id":"String",
        "latitude_snapped":"Number", "longitude_snapped":"Number",
        "next_id":"String", "previous_id":"String",
        "driveUrl_Comp":"String","driveUrl_High":"String",
        "imageUrl_Comp":"String","imageUrl_High":"String",
        "initialHfov":"Number","initialPitch":"Number","initialYaw":"Number",
        "showCompass":"Boolean" },
      "minzoom": 7, "maxzoom": 18
    }],
    "bounds": [88.5286, 23.693883, 90.506048, 25.871249],
    "center": [90.363235, 23.814873, 18],
    "minzoom": 7, "maxzoom": 18,
    "format": "pbf",
    "generator": "tippecanoe v2.80.0"
  }
  ```

- **Coverage endpoint:**
  - **URL template:**
    `https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}`
  - **HTTP method:** `GET`. No query string. **Note: no `.pbf`/`.mvt`
    extension** — the path ends at `{y}` (the TileJSON `tiles` entry has no
    suffix). Verified: `GET .../ThirdEye360/14/12306/7075` → `200`,
    `Content-Type: application/x-protobuf`.
  - **Single source-layer:** `ThirdEye360` (the `vector_layers[0].id`). Set
    `SourceDefinition.layer_names=("ThirdEye360",)` so the decoder targets
    exactly that layer.
  - **Required headers:** **none required.** The tile fetched `200` with a
    plain `GET` and no `Referer`, no API key, no cookie. For a polite scrape
    set `headers` to a descriptive `User-Agent`,
    `Referer: https://streetview.bmapsbd.com/`, and
    `Accept: application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1`
    (same posture as `panoramax` / `mapillary`).
  - **Query params:** none.
  - **No path version segment / no token.** The path is a static
    `ThirdEye360/{z}/{x}/{y}` — there is no `vNN` tileset-version segment and no
    per-request token. **No `runtime_config/` handler is needed** for
    `barikoi`. A future endpoint change is a re-scrape trigger, not a
    live-discovery step.

- **Coordinate scheme:** **`web_mercator`** — standard EPSG:3857 / WGS84
  spherical-Mercator XYZ slippy tiles. The tileset was generated by
  **tippecanoe** (TileJSON `generator: "tippecanoe v2.80.0"`), which always
  emits standard web-mercator XYZ `{z}/{x}/{y}` tiles, and the source is added
  to a MapLibre GL map (MapLibre vector sources are always web-mercator XYZ).
  Verified by probing: Dhaka centre (`23.8103 N, 90.4125 E`) → z14 tile
  `14/12306/7075` returned a dense filled tile; Bay of Bengal
  (`14/12306/7189`) and rural India NW of the bounds (`14/12242/6940`)
  returned empty (HTTP 204) tiles. **No custom grid, no new
  `coordinate_scheme`, no foundation prerequisite** — `geo.py`'s existing
  `web_mercator` branch covers tile-range and tile-bounds as-is.

- **Zoom range / tile size / response format:**
  - The tileset advertises **`minzoom: 7`, `maxzoom: 18`** (both in the
    top-level TileJSON and in `vector_layers[0]`). z14 — the project's analysis
    zoom — is well within range and is the recommended fetch zoom.
  - Response format: a **Mapbox Vector Tile** (protobuf). `Content-Type:
    application/x-protobuf`. The tiles are served **uncompressed** (no
    `Content-Encoding: gzip` header observed) — `vector_mvt`'s
    `maybe_gzip_decompress` is a no-op on them, which is fine and needs no
    special handling.
  - There is no raster "tile size" — MVT tiles carry geometry. The MVT
    `extent` is `4096`.
  - **The single `ThirdEye360` layer contains `Point` features — one point per
    captured 360° panorama.** Verified: the Dhaka z14 tile `14/12306/7075`
    decoded to **3 156 `Point` features** in the `ThirdEye360` layer, each with
    the full property set (`id`, `capture_date`, `latitude_snapped`,
    `longitude_snapped`, `next_id`, `previous_id`, `driveUrl_*`, …).
  - **Capture-date attribute IS present.** Every feature carries
    `capture_date` (e.g. `"April 03, 2026"`), `capture_date_raw`
    (ISO-8601, e.g. `"2026-04-03T08:54:25+00:00"`) and a numeric
    `capture_date_timestamp`. A `barikoi_year.tif` date layer is therefore
    *feasible* as a follow-up, but is **out of scope for this provider PR**
    (the initial deliverable is the binary presence raster). Record the
    available date field in §6 so a date-layer follow-up can use it.

- **Auth:** **none.** No token, no cookie, no API key, no signed URL — the
  `tiles.bmapsbd.com/ThirdEye360` TileJSON and `.pbf` tiles are public and
  unauthenticated (verified: `200` with a plain `GET`, no `Referer`, no key).
  **No `.env` key is required or added** for `barikoi`. Neither
  `token_query_param` nor a `runtime_config/` handler applies here. (Barikoi's
  *other* products — geocoding, the `map.barikoi.com` basemap styles — do need
  a `bkoi_…` API key; the ThirdEye360 coverage tile endpoint does not.)

- **Presence rule:** "Barikoi ThirdEye360 imagery exists here" = the decoded
  MVT tile's **`ThirdEye360` layer contains ≥ 1 feature**. The `vector_mvt`
  source kind decodes each tile into feature records and sets `feature_count`;
  a tile with `feature_count > 0` is **covered**, a tile that decodes to
  **zero** features is **checked-empty**. The decoded `Point` geometries are
  written to `data/intermediate/barikoi/` as the re-rasterizable source of
  truth and burned onto the z14 grid by `rasterize.py` (point → covered cell;
  isolated points buffered by ~1 cell per `docs/PLAN.md` §1).
  - **Empty-tile signature — HTTP 204, zero-byte body.** Verified: an
    out-of-coverage tile returns **`204 No Content`** with an **empty body**
    (`size 0`), *not* a 404 and *not* a 200-with-empty-`.pbf`. The runner's
    `_fetch_payload` returns the empty payload with `http_status == 204`; the
    custom MVT decoder (`mvt_decoder.decode_tile`) decodes empty bytes to `{}`
    (zero features) **without raising** — confirmed locally against
    `coverage_acquisition.mvt_decoder.decode_tile(b"")`. So a 204 tile flows
    through as `feature_count == 0` ⇒ checked-empty, with no special-casing
    needed. **Do not** rely on `skip_404` (the empty status is 204, not 404)
    and do not treat 204 as an error.
  - z14 raster cell mapping: a tile with ≥1 feature → contributing cells
    **covered (1)**; a probed tile with zero features → **checked-empty (0)**;
    never-probed cells → **nodata (255)**. (Standard `vector_mvt` →
    `rasterize.py` flow.)

- **robots.txt / ToS notes; observed rate limit:**
  - **`https://tiles.bmapsbd.com/robots.txt` → HTTP 404** (no robots.txt
    served). The project's `polite.robots_allows` treats an absent / non-200
    robots.txt as **allowed**. The tile host therefore imposes no crawl
    restriction. (`streetview.bmapsbd.com/robots.txt` resolves to the Next.js
    SPA 404 page, also non-restrictive; `bmapsbd.com` apex did not resolve to a
    robots.txt either.)
  - **ToS:** Barikoi is a commercial company and ThirdEye360 / the
    `tiles.bmapsbd.com` endpoint is **undocumented** (it is not part of the
    public `docs.barikoi.com` developer API, which covers only
    geocoding/maps/routing). This project stores only a **derived binary
    coverage raster** (presence/absence) — not Barikoi panorama imagery and not
    Barikoi's rendered map tiles. Treat as **polite-scrape default**:
    descriptive `User-Agent`, low concurrency, conservative throttle. Record
    the ToS caveat (undocumented `tiles.bmapsbd.com/ThirdEye360` endpoint;
    © Barikoi; only a binary presence raster is published, never imagery;
    Bangladesh-only extent) in the provider module docstring and the STAC item
    `tos_notes`. The scrape is small (see §4) and is for availability research
    only.
  - **Observed rate limit:** none observed — single-tile probes returned `200`
    immediately with no throttling. **Important caveat — large tiles:** the
    tileset was built by tippecanoe with `--no-feature-limit
    --no-tile-size-limit -r1` (no point dropping at any zoom). Low-zoom tiles
    are therefore **huge**: the z8 tile `8/192/110` over Dhaka is **~126 MB**;
    a z14 tile in central Dhaka is **~1.4–12.6 MB**. Use a conservative
    per-host throttle (`polite.polite_fetch`, ≈ 1–2 req/s, single connection),
    a generous request timeout (≈ 120 s), exponential backoff on 429/5xx, and
    — crucially — **do the two-pass discovery at z11–z12, not z7–z8** (see §4
    "Known quirks" and the §4 two-pass step) so the coarse pass does not pull
    100 MB tiles.

- **Known quirks / gotchas:**
  - **Vector, not raster.** Unlike the kakao/naver/mapy raster redesigns, the
    ThirdEye360 coverage is a **vector MVT point layer**, not a rendered PNG
    overlay. The `vector_mvt` kind decodes geometry; `rasterize.py` burns the
    points onto the z14 grid. There is no `alpha>0` PNG rule here.
  - **Tile URL has NO file extension.** The endpoint is
    `.../ThirdEye360/{z}/{x}/{y}` (no `.pbf` / `.mvt`), per the TileJSON
    `tiles` entry. Do not append an extension to the `template`.
  - **Layer is `Point` features, one per panorama** (not `LineString`
    sequences like `panoramax`/`ja360`). The presence test is still
    feature-count-based; `rasterize.py` burns points (with the standard
    isolated-point ~1-cell buffer) rather than lines. Note this for the
    rasterization step.
  - **Empty tile = HTTP 204, empty body** — not 404, not a 200 with an empty
    `.pbf`. Feature-count-based presence handles it; the decoder tolerates
    empty bytes. Do not rely on `skip_404`.
  - **Tiles are large (no tippecanoe feature/size limits).** z8 ≈ 126 MB;
    z14 central-Dhaka ≈ 1.4–12.6 MB. Discover at z11–z12 (not z7–z8); fetch at
    z14; use a long timeout and a polite throttle. The full coverage extent is
    small (Dhaka region only), so even at z14 the tile count is modest.
  - **Single source-layer named `ThirdEye360`** (same string as the tileset
    name). Decode exactly that layer; there is only one.
  - **Coverage is Bangladesh only**, currently concentrated on Dhaka and a
    corridor extending west — the TileJSON `bounds`
    `[88.5286, 23.693883, 90.506048, 25.871249]`. Restrict the discovery
    region to that bbox; do not sweep outside it.
  - **Tiles are uncompressed protobuf.** No `Content-Encoding: gzip`;
    `maybe_gzip_decompress` is a harmless no-op. `Content-Type` is
    `application/x-protobuf` (not the `application/vnd.mapbox-vector-tile`
    MIME) — fine for the decoder, which works on bytes.
  - **Product naming.** Press historically called the product "Drishty"; the
    live viewer and the Barikoi product nav now label it **"ThirdEye360"**.
    Use `ThirdEye360` for the source-layer and endpoint; the provider `key`
    stays the company name `barikoi`.

## 3. Test plan (write these FIRST — red before green)

All tests are **offline** — they decode recorded MVT fixtures and never hit the
network (`docs/PLAN.md` §12). Mirror the `vector_mvt` decode tests used for
`panoramax` / `mapillary` / `ja360`.

Fixtures under `tests/fixtures/barikoi/` (record once with a tiny throwaway
script, then commit small samples):
- `thirdeye360_z14_dhaka.pbf` — a real ThirdEye360 tile over central Dhaka
  (`GET https://tiles.bmapsbd.com/ThirdEye360/14/12306/7075`); a covered tile
  with ~3 156 `Point` features in the `ThirdEye360` layer. **This raw tile is
  ~1.4 MB** — acceptable as a fixture, but if a smaller sample is preferred,
  record instead a deeper tile, e.g. a z16 tile within Dhaka
  (`16/x/y` for a single block), which carries far fewer features.
  *Recommended:* record a z16 Dhaka tile as `thirdeye360_z16_dhaka.pbf`
  (small, still ≥1 feature) for the "present" test and keep the z14 tile only
  if a rasterization sanity fixture is wanted.
- `thirdeye360_empty.pbf` — the HTTP 204 empty-body response captured as
  zero bytes (`GET https://tiles.bmapsbd.com/ThirdEye360/14/12306/7189`, Bay
  of Bengal). Store it as a 0-byte file; the test asserts it decodes to zero
  features without raising.

Tests (`tests/test_providers_barikoi.py`):

- [ ] `test_barikoi_registers` — importing `coverage_acquisition.providers`
      auto-registers `barikoi` in `PROVIDERS`; `get_provider("barikoi")`
      returns a `ProviderDefinition` with `key == "barikoi"` and exactly one
      `SourceDefinition` whose `kind == "vector_mvt"`.
- [ ] `test_barikoi_provider_shape` — `coordinate_scheme == "web_mercator"`;
      `default_display_zoom == 14`; the source's
      `layer_names == ("ThirdEye360",)`; `vector_decoder == "custom_mvt"`; no
      `token_query_param`, no cookie/auth fields; the module references no
      `.env` key; `area_presets` contains the Dhaka pilot bbox.
- [ ] `test_barikoi_tile_url_build` — formatting the source `template` with
      `z=14, x=12306, y=7075` yields exactly
      `https://tiles.bmapsbd.com/ThirdEye360/14/12306/7075` (assert host
      `tiles.bmapsbd.com`, the `ThirdEye360` path segment, `{z}/{x}/{y}`
      order, **no file extension**, no query string).
- [ ] `test_barikoi_decode_present` — decoding the covered Dhaka fixture
      (`thirdeye360_z16_dhaka.pbf` or `thirdeye360_z14_dhaka.pbf`) through the
      `vector_mvt` decode path yields a `DecodeResult` with
      `feature_count > 0` and feature records whose `layer_name`
      (or `mvt_id`/`layer` field used by `mvt_decoder`) is `ThirdEye360` and
      whose `geometry_type == "Point"`.
- [ ] `test_barikoi_decode_empty` — decoding `thirdeye360_empty.pbf` (the
      0-byte HTTP-204 body) yields `feature_count == 0` ⇒ checked-empty, and
      does **not** raise. (Pins the empty-tile rule for the 204 response.)
- [ ] `test_barikoi_decode_carries_capture_date` — at least one decoded
      feature's `properties_json` contains a `capture_date` /
      `capture_date_raw` key (guards the date attribute for a future
      `barikoi_year.tif` follow-up; presence test itself does not depend on
      it).
- [ ] `test_barikoi_web_mercator_scheme` — a regression test pinning that
      `geo.tile_range_for_bbox(dhaka_pilot_bbox, 14, "web_mercator")` produces
      a tile range that includes `(x=12306, y=7075)` (guards against a TMS
      y-flip or a non-standard grid being introduced).
- Fixtures: small recorded `.pbf` samples under `tests/fixtures/barikoi/`
  (above). Keep them small — prefer a z16 tile for the "present" fixture.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind:** `vector_mvt` — **existing**, no new source kind, no
      foundation prerequisite. `coordinate_scheme="web_mercator"` is already
      supported by `geo.py`. The provider is a straight `kind="vector_mvt"`
      provider mirroring `src/coverage_acquisition/providers/panoramax.py`
      (no token — unlike `mapillary`).
- [ ] Write the §3 tests first; confirm they fail (red). Record the §3
      fixtures by fetching a couple of tiles once from `tiles.bmapsbd.com`
      (no auth needed) and saving the raw bytes (the 204 fixture is a 0-byte
      file).
- [ ] Add `src/coverage_acquisition/providers/barikoi.py` defining `PROVIDER`
      as a `ProviderDefinition` and calling `register_provider(PROVIDER)`.
      Shape (mirror `panoramax.py`):
  - `key="barikoi"`, `output_namespace="barikoi_mvt_coverage"`,
    `run_label_prefix="barikoi_coverage"`, `default_display_zoom=14`,
    `coordinate_scheme="web_mercator"`.
  - `area_presets` declared **inline in this module** (do not edit
    `_presets.py`, per its conflict-free docstring): `dhaka_pilot_bbox`
    (see pilot bbox below).
  - One `SourceDefinition`:
    - `id="barikoi_thirdeye360_mvt"`, `kind="vector_mvt"`.
    - `template="https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}"`
      (no file extension).
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Referer": "https://streetview.bmapsbd.com/",
      "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1"}`.
    - `layer_names=("ThirdEye360",)`.
    - `storage_subdir="vector_mvt"`.
    - `vector_decoder="custom_mvt"` (the pure-Python `mvt_decoder`, as used by
      `panoramax`/`mapillary`).
    - `display_zoom_min`/`display_zoom_max`: leave at the defaults that yield
      a z14 fetch (mirror `panoramax`); the tileset supports z7–z18.
    - `notes`: "Barikoi ThirdEye360 street-view coverage — the `ThirdEye360`
      source-layer of the public `tiles.bmapsbd.com/ThirdEye360` MVT tileset
      (the vector source the streetview.bmapsbd.com viewer adds). Web Mercator
      XYZ; one `Point` feature per captured 360° panorama; presence = ≥1
      feature. Empty tiles return HTTP 204."
  - Module docstring: record (a) this is the **vector MVT coverage layer**
    (`ThirdEye360`), the panorama point layer of the ThirdEye360 viewer — not
    a raster overlay and not a per-point JSON API; (b) the endpoint is
    undocumented and `© Barikoi`; only a binary presence raster is published;
    (c) no auth / no `.env` key; (d) coverage is Bangladesh only (Dhaka
    region); (e) tiles are large (tippecanoe with no feature/size limit) —
    discover at z11–z12, fetch at z14; (f) the date layer
    (`capture_date_raw`) is deferred to a follow-up.
- [ ] Implement until the §3 tests pass (green); refactor. Route all HTTP
      through `polite.polite_fetch` (descriptive UA, per-host throttle,
      retry/backoff, generous timeout) — never bare `urllib`/`requests`.
- [ ] **Pilot fetch:** bbox `90.395 23.790 90.430 23.815`
      (**Dhaka — Gulshan / Banani / Tejgaon area**, ~3.6 km × 2.8 km, a
      densely covered central area). At z14 this is a handful of `.pbf` tiles
      around `(x≈12306, y≈7075)`. Expect thousands of `Point` features tracing
      the Dhaka street network. During the pilot, confirm the decoded feature
      properties carry `capture_date_raw` and record the observed date range
      in §6.
- [ ] Rasterize the pilot area to a z14 COG via `rasterize.py` (EPSG:3857,
      `uint8`, 1=covered / 0=checked-empty / 255=nodata); burn the
      `ThirdEye360` `Point` geometry onto the grid (point burn with the
      standard ~1-cell isolated-point buffer per `docs/PLAN.md` §1).
      Sanity-check that covered pixels land on Dhaka streets/land, not the
      Buriganga / Turag rivers or open water.
- [ ] **Two-pass full extent:** pass-1 discovery region = the ThirdEye360
      tileset `bounds` — bbox `88.5286 23.693883 90.506048 25.871249`
      (Dhaka region + the western corridor). Discovery zoom **z11**
      (recommended) or **z12** — **NOT z7/z8**: low-zoom tiles are 100+ MB
      (no tippecanoe feature/size limit), so the coarse pass must be at z11–z12
      where tiles are manageable while still cheaply skipping empty interior
      tiles. Keep discovery tiles whose `ThirdEye360` layer decodes to
      `feature_count > 0`. Pass-2 fetches z14 tiles only inside the discovery
      cells that showed coverage; decode `Point` features →
      `data/intermediate/barikoi/` → z14 COG. The coverage extent is small
      (Dhaka region only), so the z14 tile count is modest. Run detached in
      `tmux` (`docs/PLAN.md` §5 / the `run-scraper` skill).
- [ ] Update / create the STAC item for `barikoi`
      (`catalog.upsert_provider_item`, `tier="T2"`, extent = discovered
      coverage envelope ≈ Dhaka region, scrape date,
      `source_endpoint="https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}"`,
      `tos_notes` per §2). Update the provider inventory status for `barikoi`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.barikoi` imports and
  self-registers in `PROVIDERS`; CI import/register/dry-run smoke test passes.
- The provider's single source is `kind="vector_mvt"`,
  `coordinate_scheme="web_mercator"`, `layer_names=("ThirdEye360",)`,
  `vector_decoder="custom_mvt"`; no token/cookie/auth fields; no `.env` key.
- The tile `template` builds
  `https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}` (no file extension, no
  query string).
- Pilot `.pbf` tiles fetch over central Dhaka and decode; covered tiles yield
  `ThirdEye360` `Point` features (`feature_count > 0`), and an
  out-of-coverage tile (HTTP 204, empty body) decodes to `feature_count == 0`
  (checked-empty) **without error**.
- Decoded coverage burns onto Dhaka streets/land, not the Buriganga/Turag
  rivers or open water.
- z14 COG is valid (`rio_cogeo.cog_validate`), CRS EPSG:3857, `uint8`,
  covered pixels > 0, extent within the Bangladesh / ThirdEye360 `bounds`
  bbox.
- All fetching goes through `polite.polite_fetch` with a descriptive
  `User-Agent` and a conservative throttle + generous timeout; no bare
  `urllib`/`requests` in the provider path.
- ToS caveats (undocumented `tiles.bmapsbd.com/ThirdEye360` endpoint;
  © Barikoi; only a binary coverage raster published, never imagery;
  Bangladesh-only extent; large low-zoom tiles) documented in the
  `providers/barikoi.py` module docstring and the STAC item `tos_notes`.

## 6. Status log

- `2026-05-22` scout: drafted. Findings, all verified live:
  - Barikoi's street-view product (press name "Drishty") ships today as
    **ThirdEye360**, public viewer `https://streetview.bmapsbd.com/`, linked
    from the Barikoi product nav.
  - The viewer is a Next.js + MapLibre GL app; its `onLoad` adds a vector
    source `addSource("thirdEye", {type:"vector",
    url:"https://tiles.bmapsbd.com/ThirdEye360"})`.
  - `GET https://tiles.bmapsbd.com/ThirdEye360` returns a TileJSON 3.0.0:
    `tiles:["https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}"]`, single
    `vector_layers` id `ThirdEye360`, `minzoom 7` / `maxzoom 18`, `bounds
    [88.5286,23.693883,90.506048,25.871249]`, `format pbf`, tippecanoe
    v2.80.0.
  - Probed live: Dhaka z14 `14/12306/7075` → `200 application/x-protobuf`
    (~1.4 MB), decoded with the project's `mvt_decoder` to **3 156 `Point`
    features** in layer `ThirdEye360`, each with `id`, `capture_date`,
    `capture_date_raw` (ISO-8601), `capture_date_timestamp`, `next_id`,
    `previous_id`, `latitude_snapped`/`longitude_snapped`, `driveUrl_*`,
    `imageUrl_*`. Bay of Bengal `14/12306/7189` and rural-India
    `14/12242/6940` → **HTTP 204, empty body**. z8 `8/192/110` → ~126 MB
    (tippecanoe built with `--no-feature-limit --no-tile-size-limit -r1`).
  - Scheme: standard Web Mercator XYZ (tippecanoe + MapLibre) →
    `coordinate_scheme="web_mercator"`; **no new coordinate scheme, no
    foundation prerequisite.**
  - Auth: **none** — `200` with a plain `GET`, no `Referer`, no API key, no
    cookie. No `.env` key; no `runtime_config/` handler; no
    `token_query_param`. (Barikoi's geocoding / `map.barikoi.com` basemap
    products do need a `bkoi_…` key — the ThirdEye360 coverage endpoint does
    not.)
  - robots.txt: `tiles.bmapsbd.com/robots.txt` → HTTP 404 (absent ⇒ allowed).
  - Verdict: **cleanly scrapable** as a `kind="vector_mvt"` provider mirroring
    `panoramax` — no token, no foundation work, no paywall. The only
    implementation caveat is the very large low-zoom tiles → discover at
    z11–z12 and use a generous timeout.
- `2026-05-22` approval: **pending** — awaiting user review.

---

### Open questions for the reviewer

1. **Discovery zoom z11/z12 vs. the usual coarse pass.** The ThirdEye360
   tileset has **no tippecanoe feature/size limit**, so low-zoom tiles are
   enormous (z8 ≈ 126 MB). This subplan recommends running pass-1 discovery at
   **z11–z12** instead of the more typical z7–z9. Confirm the two-pass runner
   can use z11/z12 as the discovery zoom for this provider, or whether the
   coverage extent is small enough to simply skip two-pass and do a single z14
   sweep of the (small) Dhaka-region `bounds` bbox.
2. **Date layer deferred.** The `ThirdEye360` features carry a per-panorama
   `capture_date_raw` (ISO-8601) and `capture_date_timestamp`, so a
   `barikoi_year.tif` date layer is feasible. This subplan ships only the
   binary presence raster; confirm deferring the date layer to a follow-up is
   acceptable.
3. **Fixture size.** The covered Dhaka z14 tile is ~1.4 MB raw — large for a
   committed test fixture. This subplan recommends recording a smaller z16
   Dhaka tile as the "present" fixture instead. Confirm that is acceptable, or
   whether a trimmed/truncated z14 sample is preferred.
4. **Tile retention.** Decoded ThirdEye360 point geometry is Barikoi map
   content. The project keeps raw `.pbf` tiles only in gitignored `data/raw/`
   and publishes a derived binary COG + the decoded points in
   `data/intermediate/`. Confirm this satisfies the ToS posture for an
   undocumented commercial endpoint, or require deleting `data/raw/barikoi/`
   after rasterization.

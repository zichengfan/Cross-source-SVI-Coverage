# [T2] Provider: Streetview.vn / NDAVIEW (`streetview_vn`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Streetview.vn is a Vietnamese street-level imagery service — a 360° panorama /
"explore the streets of Vietnam" product. The public site `www.streetview.vn`
**301-redirects to `https://view.ndamaps.vn/`**, the live viewer, branded
**NDAVIEW** and operated by "44+ Technologies" on the `ndamaps.vn` map platform.
Coverage is **Vietnam only** (dense in Hanoi, Ho Chi Minh City, Da Nang, Hue,
Nha Trang and along inter-city roads). It is in scope as a Tier-2 provider: it
is **active**, **self-hosted** (its own imagery, captured with Insta360 rigs —
not a re-hoster), is not defunct, and is not paid-B2B-without-a-viewer. The
viewer is a React/MapLibre-GL SPA whose panorama-coverage layer is a public,
unauthenticated **vector MVT tile layer** (`{z}/{x}/{y}.mvt`) of capture
sequences — directly analogous to the existing `panoramax` provider. This
project fetches that MVT coverage layer and rasterizes it onto the shared z14
grid; no panorama imagery is downloaded.

## 2. Research findings (filled by provider-scout)

### Verdict: Streetview.vn serves a VECTOR MVT coverage layer

There is **no rendered raster `{z}/{x}/{y}` PNG overlay** for this provider
(unlike kakao/naver/mapy). The NDAVIEW viewer uses **MapLibre GL** and draws the
panorama-coverage layer as **Mapbox Vector Tiles**. The coverage layer was
identified from the viewer JS bundles and confirmed by probing the tile host
directly. Source kind is the existing **`vector_mvt`** — `streetview_vn` is a
near-exact analogue of `src/coverage_acquisition/providers/panoramax.py`.

- **Homepage / public viewer URL:**
  - Homepage: `https://www.streetview.vn/` → **HTTP 301** →
    `https://view.ndamaps.vn/` (the live viewer; `<title>NDAVIEW</title>`).
  - Deep-link form (a single panorama): `https://view.ndamaps.vn/?picId=<uuid>&yaw=<deg>&pitch=<deg>`.
  - Tier: **T2** (inventory note: "Reachable (self-hosted); custom scraper").

- **How the coverage layer was identified.** The viewer is a Vike/React SPA
  (`view.ndamaps.vn/assets/entries/...` + `assets/chunks/chunk-*.js`). The
  basemap is a MapLibre style from `tiles.openmap.vn` (irrelevant — that is the
  road basemap, not coverage). The **panorama-coverage layer** is created in the
  app bundle (`chunk-RYrMKEBx.js`) which configures a MapLibre source via a
  plugin call `getPlugin(qe).updateSource([...])`:

  ```js
  // chunk-RYrMKEBx.js  (de-minified)
  P.updateSource(
    A?.accountId
      ? [`https://api-view.ndamaps.vn/v1/map/user/${A.accountId}/{z}/{x}/{y}?format=mvt`]
      : ["https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt"]
  )
  ```

  - The **default** (whole-of-provider) coverage source is
    `https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt` — **this is the layer
    this project scrapes.**
  - The `api-view.ndamaps.vn/v1/map/user/{accountId}/...` variant is only used
    when the viewer is filtered to a single contributor account; it is **not**
    needed for total provider coverage. Ignore it.
  - Other `api-view.ndamaps.vn/v1/...` endpoints in the bundle
    (`/points/outstanding`, `/search`, `/statics`, `/feedback`, `/devices`) are
    the featured-POI / dashboard / search APIs — **not** the coverage layer.
    Do not use them.

- **Coverage endpoint (use this):**
  - **URL template:** `https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt`
  - **HTTP method:** `GET`.
  - **Path order:** standard slippy-map `{z}/{x}/{y}` (verified — see
    coordinate scheme).
  - **Query params:** **none.** No `apiKey`, no token — verified (bare GET
    returns the tile).
  - **Required headers:** **none are required.** Verified: a bare `GET` with no
    `Referer`, no `User-Agent`, no auth returns `HTTP 200` with the MVT body.
    For polite scraping the `SourceDefinition.headers` should still set a
    descriptive `User-Agent`, an `Accept` of
    `application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1`,
    and a `Referer: https://view.ndamaps.vn/` — same posture as `panoramax`.
  - Response `Content-Type: application/octet-stream` (raw protobuf MVT; **not**
    `application/vnd.mapbox-vector-tile`, and **not** gzip-encoded — no
    `Content-Encoding` header). CORS is wide open (`access-control-allow-origin: *`).
  - Single host `gpx-view.ndamaps.vn` (nginx); no host sharding.

- **Coordinate scheme:** **`web_mercator`** — standard EPSG:3857 / WGS84
  spherical Mercator XYZ, 256-unit slippy-map tiles, **no y-flip**, no custom
  datum. Verified: tiles computed for Hanoi (105.8342, 21.0278), Ho Chi Minh
  City (106.6297, 10.8231), Da Nang and Hue with the standard slippy-map
  formula all returned populated MVT tiles whose decoded WGS84 geometry lands on
  the correct city streets. The MVT internal tile extent is the standard
  **4096** units. No `geo.py` change is needed — this is the same
  `coordinate_scheme="web_mercator"` used by `panoramax` / `mapillary`.

- **Zoom range / tile size / response format:**
  - **Native zoom range:** the layer renders **z4–z18 inclusive**. Probed live:
    z4, z5, z6, z7, z10, z12, z14, z15, z16, z17, z18 all return `HTTP 200`
    with MVT bodies; **z19, z20, z21, z22 return `HTTP 404`** (the layer's
    max-zoom is 18; the viewer overzooms client-side above that).
  - **Response format:** Mapbox Vector Tile (protobuf), `application/octet-stream`,
    standard 4096-unit MVT extent, **uncompressed** (no gzip).
  - **Layers inside the tile (verified with `ogrinfo`):**
    - **`sequences`** — `MultiLineString`. **This is the coverage layer.** Each
      feature is one panorama capture sequence (a road trace where imagery
      exists). Present at **z6–z18**. Fields:
      `id` (uuid string), `view_mode` (string, observed value `"street"`),
      `date` (string `YYYY-MM-DD`, the capture date), `account_id` (uuid
      string, the contributor), `model` (camera model, e.g.
      `"Insta360 Insta360"`), `type` (string, e.g. `"equirectangular"`),
      `mvt_id` (integer feature id).
    - **`grid`** — `Point`, a clustered panorama-density layer used only at low
      zoom (present at **z4–z7**, absent at z10+). Fields: `id` (int),
      `nb_pictures` (int — picture count in the cluster), `coef` (real).
      Useful as a **fast pass-1 discovery layer** but **not** the layer to burn
      at z14 (it is sparse cluster centroids, not road traces).
  - **Use the `sequences` layer for the z14 coverage burn.** Its
    `MultiLineString` traces are the panorama footprint; the rasterizer burns
    the lines onto the z14 grid (and buffers, per PLAN §3).

- **Auth:** **none.** No token, no cookie, no API key, no `apiKey` query param,
  no login. The `gpx-view.ndamaps.vn/snap/*.mvt` endpoint is fully public and
  unauthenticated (verified by bare `curl`). **No `.env` key is required or
  added for this provider.** (The `Authorization: Bearer` header seen elsewhere
  in the bundle belongs to the `points/outstanding` dashboard API, not to the
  coverage tile layer.)

- **Presence rule:** "panorama imagery exists in this tile" ⇔ the decoded MVT
  tile's **`sequences` layer contains ≥ 1 feature**. The `vector_mvt` source
  kind (`source_kinds/vector_mvt.py`) already decodes the tile to feature rows
  and reports `feature_count` / `layer_counts`; a tile with
  `layer_counts["sequences"] > 0` is **covered**, a successfully fetched tile
  with zero `sequences` features is **checked-empty**, and a `404` tile is
  **never-imaged** (see empty signature). The decoded line geometry (WGS84
  coordinates) is what `rasterize.py` burns onto the z14 grid.
  - **Empty-tile signature: HTTP 404.** A tile outside coverage (ocean, or
    Vietnamese terrain with no panoramas) returns **`HTTP 404`** with a
    153-byte `text/html` nginx "404 Not Found" body — **not** an empty
    `200` MVT. Verified for open ocean (`snap/10/700/500.mvt → 404`) and for a
    remote VN mountain tile (`snap/14/12893/7145.mvt → 404`). The runner's
    existing `skip_404` path (`runners.py`, default `skip_404=True`) handles
    this: a 404 tile is recorded as skipped → treated as **never-imaged
    (nodata)** for that cell. (A populated tile that genuinely contains no
    `sequences` features is the rarer "checked-empty" case; in practice every
    in-coverage tile has features and every out-of-coverage tile 404s.)

- **robots.txt / ToS notes; observed rate limit:**
  - **Tile host `gpx-view.ndamaps.vn`:** `https://gpx-view.ndamaps.vn/robots.txt`
    → **HTTP 404** (no robots.txt). `polite.robots_allows` treats an
    absent/non-200 robots.txt as **allowed** — the coverage tile endpoint is
    permitted under the project's robots posture. **All fetching for this
    provider happens on `gpx-view.ndamaps.vn` only.**
  - **Viewer host `view.ndamaps.vn`:** `https://view.ndamaps.vn/robots.txt`
    → `HTTP 200`, `User-agent: *` / `Allow: /` / `Disallow: /catalogue`
    (only the `/catalogue` path is disallowed; the viewer is otherwise
    crawl-allowed). This provider never fetches from `view.ndamaps.vn` anyway —
    that host appears only as the `Referer` header value.
  - **`www.streetview.vn`** is a thin 301-redirect shell to `view.ndamaps.vn`;
    it is not crawled.
  - ToS: NDAVIEW / Streetview.vn imagery is the operator's ("44+ Technologies").
    This project stores only a **derived binary coverage raster** (presence /
    absence), not NDAVIEW panoramas and not the raw MVT tiles in the published
    DB. No public ToS page enumerating an automation prohibition was found; the
    `snap` MVT endpoint is undocumented. Keep the scrape polite and small and
    record the "derived coverage raster only; undocumented endpoint" caveat in
    the module docstring.
  - **Observed rate limit:** none hit during probing; no documented limit. Use
    the project polite default (`polite.polite_fetch`, per-host throttle,
    retry/backoff) with a descriptive `User-Agent`. A conservative
    `min_interval_seconds ≈ 0.25 s` is fine for this single nginx host.

- **Known quirks / gotchas:**
  - **MVT, not raster.** Unlike `kakao` / `naver` / `mapy`, there is no PNG
    coverage overlay — the layer is vector MVT. Source kind is `vector_mvt`
    with `vector_decoder="custom_mvt"` (the project's pure-Python MVT decoder,
    no `ogr2ogr` needed — confirmed below).
  - **Two layers in the tile; use `sequences`.** The `sequences`
    (MultiLineString) layer is the road-trace coverage footprint and is present
    z6–z18. The `grid` (Point) layer is a low-zoom density-cluster layer
    (z4–z7 only); it is handy for fast discovery but must **not** be the layer
    burned at z14. Set `layer_names=("sequences",)` so the decoder targets the
    coverage layer.
  - **Empty tiles are HTTP 404, not an empty 200 MVT.** Rely on the runner's
    `skip_404` path; do not expect a 200 empty body. Decode-based emptiness
    (`sequences` feature count == 0) is the secondary, rarely-hit case.
  - **Max zoom 18.** Do not fetch z19+ (always 404). The project's z14 analysis
    zoom and any coarse discovery zoom (z6–z9) are all well within range.
  - **`Content-Type` is `application/octet-stream`** (not the canonical MVT
    media type). Do not set a strict `expect_content_type_prefix` that would
    reject `application/octet-stream` — leave it unset, or set it to
    `application/` to match both `octet-stream` and the MVT media type.
  - **Capture dates are available.** Every `sequences` feature carries a
    `date` field (`YYYY-MM-DD`). A `streetview_vn_year.tif` date layer is
    therefore **possible** from this same source (unlike the rendered-overlay
    raster providers). It is **out of scope for this provider PR** (the binary
    coverage raster ships first) but should be noted as a viable future
    follow-up — no separate API would be needed.
  - **Vietnam-only coverage.** Restrict the discovery region to the Vietnam
    bbox; do not sweep globally (out-of-VN tiles 404 anyway, but bounding the
    sweep avoids wasted requests).
  - **No host sharding, no `apiKey`.** Single host, no query string. The
    per-account `api-view.ndamaps.vn/v1/map/user/{accountId}` variant is a
    filtered view and is intentionally not used.

## 3. Test plan (write these FIRST — red before green)

All tests are **offline** — they decode recorded MVT/HTML fixtures and never hit
the network (PLAN §12). Mirror the `vector_mvt` / `panoramax` decode tests.

Fixtures recorded live under `tests/fixtures/streetview_vn/` (capture once with
a tiny throwaway script, then commit small):
- `snap_hanoi_z14.mvt` — `GET https://gpx-view.ndamaps.vn/snap/14/13008/7212.mvt`
  (central Hanoi; a populated tile, ~63 KB, `sequences` layer with ~372
  `MultiLineString` features). The canonical "coverage present" fixture.
- `snap_hcmc_z14.mvt` — `GET https://gpx-view.ndamaps.vn/snap/14/13044/7696.mvt`
  (Ho Chi Minh City; a second populated tile, ~25 KB) — for a rasterization
  sanity check and a second-city decode test.
- `snap_empty_404.html` — the 153-byte nginx `text/html` "404 Not Found" body
  returned for an out-of-coverage tile (e.g. ocean `snap/10/700/500.mvt`).
  Documents the empty-tile signature for the skip_404 test.
- (optional) `snap_hanoi_z6.mvt` — a low-zoom tile that also contains the
  `grid` Point layer, to pin that the decoder targets only `sequences`.

Tests (`tests/test_providers_streetview_vn.py`):

- [ ] `test_streetview_vn_registers` — importing
  `coverage_acquisition.providers.streetview_vn` registers `"streetview_vn"` in
  `PROVIDERS`; `get_provider("streetview_vn")` returns a `ProviderDefinition`
  with `key == "streetview_vn"`, `coordinate_scheme == "web_mercator"`, and
  exactly one `SourceDefinition`.
- [ ] `test_streetview_vn_source_shape` — the single `SourceDefinition` has
  `kind == "vector_mvt"`, `vector_decoder == "custom_mvt"`,
  `layer_names == ("sequences",)`, `storage_subdir == "vector_mvt"`, headers
  carrying a descriptive `User-Agent` and a `Referer` of
  `https://view.ndamaps.vn/`, and **no** `token_query_param` / no auth field.
- [ ] `test_streetview_vn_tile_url_build` — formatting the source `template`
  with `z=14, x=13008, y=7212` yields exactly
  `https://gpx-view.ndamaps.vn/snap/14/13008/7212.mvt` (assert host, the
  `/snap/` path, `{z}/{x}/{y}` order, the `.mvt` suffix, and that there is no
  query string).
- [ ] `test_streetview_vn_decode_present` — decoding `snap_hanoi_z14.mvt` via the
  `vector_mvt` kind's `custom_mvt` path
  (`mvt_decoder.decode_tile` → `feature_rows_from_decoded_tile`) yields
  `layer_counts["sequences"] > 0` (≈ 372) and `feature_count > 0`; the produced
  feature rows have `geometry_type == "MultiLineString"` and
  `geometry_wkt` strings containing WGS84 lon/lat coordinates inside the Hanoi
  bbox (`105.7 < lon < 105.95`, `20.95 < lat < 21.10`).
- [ ] `test_streetview_vn_decode_has_date` — a decoded `sequences` feature
  exposes the `date` property (a `YYYY-MM-DD` string) in its
  `properties_json`, pinning that the capture-date field survives decoding (for
  a future date layer).
- [ ] `test_streetview_vn_empty_tile_is_404` — assert the provider relies on the
  runner's `skip_404` behaviour: the empty-tile signature is `HTTP 404`
  (documented by `snap_empty_404.html` being a non-MVT `text/html` body). A
  unit test asserts that the recorded 404 body is **not** decodable as MVT
  (i.e. `decode_tile` raises / yields no `sequences` layer) so it can never be
  mistaken for coverage.
- [ ] `test_streetview_vn_targets_sequences_only` — decoding the low-zoom
  fixture (`snap_hanoi_z6.mvt`, which also has a `grid` layer) with
  `layer_names=("sequences",)` produces feature rows **only** from the
  `sequences` layer — the `grid` Point cluster layer is excluded from the
  coverage burn.
- [ ] `test_streetview_vn_web_mercator_scheme` — a regression test pinning that
  `geo.tile_range_for_bbox(<Hanoi pilot bbox>, 14, "web_mercator")` produces a
  tile range that includes `(x=13008, y=7212)` (guards against a TMS y-flip or
  a non-standard grid being introduced).
- Fixtures: small recorded samples under `tests/fixtures/streetview_vn/`
  (above).

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: `vector_mvt`** — **existing**, no new source kind and **no
  foundation prerequisite**. The `vector_mvt` kind
  (`src/coverage_acquisition/source_kinds/vector_mvt.py`) with
  `vector_decoder="custom_mvt"` already decodes `{z}/{x}/{y}.mvt` protobuf
  tiles into WGS84 feature rows — verified live against a real
  `gpx-view.ndamaps.vn/snap/...` tile (the project's `decode_tile` +
  `feature_rows_from_decoded_tile` produced 372 `sequences` MultiLineString
  rows with correct Hanoi WGS84 coordinates). `streetview_vn` is a straight
  analogue of `src/coverage_acquisition/providers/panoramax.py`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/streetview_vn.py` defining
  `PROVIDER` as a `ProviderDefinition` and calling `register_provider(PROVIDER)`
  — mirror `providers/panoramax.py` in shape:
  - `key="streetview_vn"`, `output_namespace="streetview_vn_mvt_coverage"`,
    `run_label_prefix="streetview_vn_coverage"`, `default_display_zoom=13`,
    `coordinate_scheme="web_mercator"`.
  - `area_presets`: declare the pilot bbox **inline in this module** (do **not**
    edit `providers/_presets.py`, per its conflict-free docstring) —
    `hanoi_center_bbox = BoundingBox(105.820, 21.015, 105.860, 21.045)`.
  - One `SourceDefinition`:
    - `id="streetview_vn_snap_mvt"`, `kind="vector_mvt"`,
    - `template="https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt"`,
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
      "Referer": "https://view.ndamaps.vn/"}`,
    - `layer_names=("sequences",)`,
    - `storage_subdir="vector_mvt"`,
    - `vector_decoder="custom_mvt"`,
    - `display_zoom_min=6`, `display_zoom_max=18` (the `sequences` layer's
      native zoom range; z19+ 404s),
    - **do not** set a strict `expect_content_type_prefix` (the host returns
      `application/octet-stream`; leave unset or use `application/`),
    - `notes`: "NDAVIEW / Streetview.vn panorama-coverage MVT — `sequences`
      MultiLineString capture traces. Empty tiles return HTTP 404. Vietnam
      only; carries a per-feature `date`."
  - Module docstring records: (a) `www.streetview.vn` 301-redirects to the
    `view.ndamaps.vn` NDAVIEW viewer; (b) the coverage layer is the
    `gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt` vector layer (`sequences`); the
    per-account `api-view.ndamaps.vn/v1/map/user/...` variant and the
    `points/outstanding` / `search` APIs are intentionally not used;
    (c) empty tiles are HTTP 404; (d) no auth; Vietnam-only; (e) ToS caveat —
    undocumented endpoint, only a derived binary coverage raster is published,
    never NDAVIEW imagery; (f) all fetching is on `gpx-view.ndamaps.vn` only
    (no robots.txt → allowed); `view.ndamaps.vn` is used only as `Referer`.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `105.820 21.015 105.860 21.045`
  (**Hanoi — Hoan Kiem / Old Quarter centre**, ~4.1 km × 3.3 km) at display
  zoom 13/14. Expect populated MVT tiles whose decoded `sequences` lines trace
  the central Hanoi street network. Scouting confirmed the z14 tile
  `14/13008/7212` returns ~372 `sequences` features.
- [ ] Rasterize the pilot area to a z14 COG with the standard `vector_mvt` →
  `rasterize.py` pipeline (burn the `sequences` LineString geometry; buffer per
  PLAN §3); sanity-check that covered pixels land on Hanoi streets/land (not
  Hoan Kiem lake, not the Red River, not ocean); CRS EPSG:3857, `uint8`.
- [ ] **Two-pass full extent:** pass-1 discovery region = the **Vietnam bbox**
  `102.1 8.4 109.5 23.4` at discovery zoom **z7–z8** (the `sequences` layer
  renders fine at z6+; ~16×16 tiles cover all of Vietnam at z7 — cheap). Pass-2
  fetches z14 `.mvt` tiles only in the discovery cells that returned `HTTP 200`
  with `sequences` features. 404 tiles are skipped → never-imaged. Run detached
  in `tmux` (PLAN §5 / `run-scraper`); do not fetch outside the Vietnam bbox.
  (Optional optimisation: the low-zoom `grid` Point layer gives an even
  cheaper pass-1 density screen, but a plain `sequences` z7 sweep is simplest.)
- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T2"`,
  `source_endpoint="https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt"`,
  `tos_notes` per §2); update the inventory status for `streetview_vn`.
- [ ] (Future, out of scope here) optional date layer
  `streetview_vn_mvt_coverage_year.tif` from the same `sequences` `date` field.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.streetview_vn` imports and
  self-registers (`"streetview_vn"` in `PROVIDERS`); CI smoke test
  (import + register + dry-run) passes.
- The provider's single source is `kind="vector_mvt"`,
  `vector_decoder="custom_mvt"`, `coordinate_scheme="web_mercator"`,
  `layer_names=("sequences",)`; the tile `template` builds
  `https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt` with no auth params.
- Pilot z14 tiles over central Hanoi fetch (`HTTP 200`) and decode to
  `sequences` features with `feature_count > 0`; an out-of-coverage tile
  returns `HTTP 404` and is skipped (never-imaged) without error.
- Decoded coverage geometry is WGS84 and lands on Vietnamese roads/land
  (Hanoi street grid), not water and not outside Vietnam.
- z14 COG is valid (`rio_cogeo.cog_validate`), CRS EPSG:3857, `uint8`, covered
  pixels > 0, extent within the Vietnam bbox.
- All fetching goes through `polite.polite_fetch` with a descriptive
  `User-Agent`; only `gpx-view.ndamaps.vn` is fetched; `view.ndamaps.vn` is
  never crawled (Referer only).
- ToS / robots posture documented in the `streetview_vn.py` module docstring
  and the STAC item `tos_notes`.
- No `STREETVIEW_VN_*` (or any) secret is required or added — provider is
  unauthenticated.

## 6. Status log

- `2026-05-22` scout: drafted. Findings, all verified live this session:
  - `www.streetview.vn` → **HTTP 301** → `https://view.ndamaps.vn/` (NDAVIEW,
    a React/MapLibre-GL SPA by "44+ Technologies" on the `ndamaps.vn`
    platform).
  - The panorama-coverage layer is a **vector MVT** layer, not a rendered PNG
    overlay. Extracted from the viewer bundle `chunk-RYrMKEBx.js`
    (`updateSource([...])`): default source
    `https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt`.
  - Probed live: populated MVT for Hanoi (`14/13008/7212`, ~63 KB), HCMC
    (`14/13044/7696`), Da Nang, Hue; the layer renders **z4–z18** (z19+ →
    404). Out-of-coverage tiles (ocean, remote VN mountains) return
    **HTTP 404** (153-byte nginx HTML) — that is the empty-tile signature.
  - The MVT tile has two layers: **`sequences`** (`MultiLineString`, the
    coverage road-traces, z6–z18; fields `id, view_mode, date, account_id,
    model, type`) and **`grid`** (`Point`, low-zoom density clusters, z4–z7).
    Use `sequences` for the z14 burn.
  - The project's own `custom_mvt` decoder (`mvt_decoder.decode_tile` +
    `feature_rows_from_decoded_tile`) was run against the real Hanoi tile and
    produced **372 `sequences` MultiLineString rows with correct WGS84 Hanoi
    coordinates** — no new decoder or foundation work is needed.
  - Coordinate scheme: standard `web_mercator` XYZ, 4096-unit MVT extent, no
    y-flip. Auth: **none** (bare GET returns 200; no `apiKey`, no token).
  - robots.txt: tile host `gpx-view.ndamaps.vn` → 404 (no robots → allowed);
    viewer host `view.ndamaps.vn` → `Allow: /` (only `/catalogue` disallowed,
    irrelevant). Only `gpx-view.ndamaps.vn` is fetched.
  - **Verdict: cleanly scrapable.** Source kind `vector_mvt`, near-identical
    to `panoramax`. No foundation prerequisite. No `.env` key.
- `YYYY-MM-DD` approval: < pending >
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **No foundation prerequisite — confirm.** Unlike `kakao` (needed
   `kakao_epsg5181`), `streetview_vn` reuses the existing `vector_mvt` source
   kind, the existing `custom_mvt` decoder, and the existing `web_mercator`
   coordinate scheme unchanged. The provider PR adds exactly one file
   (`providers/streetview_vn.py` + its tests + this subplan) and edits no
   shared file. Confirm the provider PR can proceed directly with no preceding
   foundation PR.
2. **Discovery zoom.** Proposed two-pass discovery at z7–z8 over the Vietnam
   bbox (`102.1 8.4 109.5 23.4`). The `sequences` layer renders at z6+; z7 is
   ~256 tiles for all of Vietnam — cheap. Confirm z7, or prefer z8 for a finer
   pass-1 footprint. (The low-zoom `grid` Point layer could give an even
   cheaper density screen — flagged as an optional optimisation, not required.)
3. **Date layer out of scope for this PR.** Every `sequences` feature carries a
   `date` (`YYYY-MM-DD`) field, so a `streetview_vn_..._year.tif` date layer is
   feasible from the *same* source with no extra API. This subplan ships the
   binary coverage raster only and defers the date layer. Confirm that is
   acceptable as a follow-up.
4. **Per-account vs. global coverage.** The viewer can filter coverage to one
   contributor via `api-view.ndamaps.vn/v1/map/user/{accountId}/{z}/{x}/{y}`.
   This subplan deliberately uses the **unfiltered** `gpx-view.ndamaps.vn/snap`
   layer (all contributors = total provider coverage). Confirm the unfiltered
   layer is the intended target.
5. **Tile retention.** Raw `.mvt` tiles are kept only in gitignored
   `data/raw/streetview_vn/` (and decoded features in
   `data/intermediate/streetview_vn/`); the published artefact is the derived
   binary z14 COG. Confirm this satisfies the ToS posture for an undocumented
   third-party endpoint, or require deleting `data/raw/streetview_vn/` after
   rasterization.

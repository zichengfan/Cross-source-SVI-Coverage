# [T3] Provider: ASIG Albania StreetView 360 (`asig`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): SCRAPABLE — RECOMMEND APPROVE. ASIG (Albania's
State Authority for Geospatial Information) runs a national first-party
"StreetView 360" program and publishes its photo-center coverage as an
unauthenticated XYZ-tiled GeoJSON layer. The viewer's CAS SSO runs in
`gateway=true` mode, so the `/map/` viewer and the coverage tiles load
anonymously (no login). Each coverage tile is a GeoJSON FeatureCollection whose
Point features carry real WGS84 `lat`/`lon`, a panorama `id`, `heading`,
`height`, and an ISO `date`. Coverage is Albania-only, web-mercator XYZ at
z6–z15, no token/cookie required. Empty tiles return HTTP 404.

ONE CAVEAT: the project has no GeoJSON-per-tile source kind yet. The existing
`coverage_json` kind expects a `{"panos": [...]}` payload, which does NOT match
ASIG's FeatureCollection shape, and `vector_mvt` expects binary MVT decoded via
ogr2ogr. ASIG needs the `vector_geojson` seed kind named in PLAN §4.3 — that is
a small **separate foundation PR** that must merge before the provider PR. See
§4. This is the only thing standing between scout and a clean implementation.
-->

## 1. Summary

ASIG — *Autoriteti Shtetëror për Informacionin Gjeohapësinor* (State Authority
for Geospatial Information), `asig.gov.al` — is Albania's national geospatial
agency. It administers the National Geoportal (`geoportal.asig.gov.al`) under
Law 72/2012, an INSPIRE-aligned national SDI offering ~40 free public services.
Since ~2019 ASIG has run a **first-party "StreetView 360"** program: it drives
360° georeferenced panorama cameras over the national road network and urban
areas (Tirana Great Ring Road, the Thumanë–Kashar axis, the Vorë–Kepi i Rodonit
axis, plus city centres) and publishes the imagery on the National Geoportal.
The panoramas play in a Krpano-style viewer at
`http://360.asig.gov.al/AlbaniaStreetView/player2/`, and the geoportal map
shows the **photo-center coverage** ("photo centers placed on an online
map/orthophoto") as a clickable overlay. This is a government-run, first-party
SVI source for an entire country — in scope (active, scrapable, not a re-hoster,
not paid-B2B). It is the only national-government street-view program in the
T3 batch and one of the few with a clean, unauthenticated coverage feed.

## 2. Research findings (filled by provider-scout)

### Verdict: scrapable coverage layer found — XYZ-tiled GeoJSON, no auth

The geoportal viewer (`https://geoportal.asig.gov.al/map/`) is an Italian "iGEO"
/ `IGVT` GIS platform (OpenLayers + Cesium + Drupal 8 shell). Its env config
(`/map/assets/scripts/env_9c5e095.js`) and the AOT app bundle
(`/map/assets/scripts/igeo.aot_*.js`) reveal exactly how the StreetView 360
overlay works:

- `IGVT.ENV.base360Url =`
  `https://geoportal.asig.gov.al/map/uritemplateproxy?protocol=http&host=360.asig.gov.al&port=80&path=/AlbaniaStreetView/player2/tiles-1674737600/`
- `MapService.prototype.setStreetViewerLayerInMap` / `streetViewerOverlay`:
  on map move the app calls `restService.get360Points(url)` for tiles in the
  viewport and adds the returned Point features to an OpenLayers overlay.
- The tile URL is built as `IGVT.ENV.base360Url + '{z}/{x}/{y}.geojson'` where
  the tile indices are computed from **WGS84 lon/lat with the standard slippy
  XYZ formula** (`x = floor((lon+180)/360 · 2^z)`,
  `y = floor((1 − ln(tan φ + sec φ)/π)/2 · 2^z)`) — i.e. ordinary Web Mercator
  XYZ (the OL map itself is in EPSG:6870 / KRGJSH-2010, but the tile grid is
  WGS84 web-mercator).
- Clicking a feature opens the panorama at
  `http://360.asig.gov.al/AlbaniaStreetView/player2/?sv_startup_pano=<id>&sv_startup_heading=<heading>&...&v_lat=<lat>&v_lng=<lon>`
  — confirming each coverage Point maps 1:1 to a playable panorama.

- **Homepage / public viewer URL:**
  - Agency: `https://asig.gov.al/en/` ; Geoportal: `https://geoportal.asig.gov.al/en`
  - Map viewer: `https://geoportal.asig.gov.al/map/` (loads anonymously)
  - Panorama player: `http://360.asig.gov.al/AlbaniaStreetView/player2/`
  - Tier: **T3** ("likely / unverified / gated") per `docs/PLAN.md` §2. Scout
    re-classifies the *mechanism* as a clean unauthenticated tiled-GeoJSON feed.

- **Coverage endpoint(s):** XYZ-tiled GeoJSON FeatureCollection, `GET`.
  Two equivalent ways to reach it (both verified live, both anonymous):
  - **Direct origin (preferred for scraping):**
    `http://360.asig.gov.al/AlbaniaStreetView/player2/tiles-1674737600/{z}/{x}/{y}.geojson`
    (Microsoft-IIS/10.0 static host; `Content-Type: application/geo+json`).
  - **Via geoportal proxy (what the viewer uses):**
    `https://geoportal.asig.gov.al/map/uritemplateproxy?protocol=http&host=360.asig.gov.al&port=80&path=/AlbaniaStreetView/player2/tiles-1674737600/{z}/{x}/{y}.geojson`
    (returns byte-identical payload).
  - **Recommendation:** use the **direct origin** (HTTPS-upgrade is auto by
    `polite_fetch`; if 360.asig.gov.al has no valid HTTPS cert, keep `http://`
    and document it). It avoids the geoportal's nginx/CAS layer entirely.
  - Headers: none required. Send a descriptive `User-Agent` and
    `Accept: application/geo+json, application/json;q=0.9, */*;q=0.1`. A
    `Referer: http://360.asig.gov.al/AlbaniaStreetView/player2/` is polite but
    not required (verified: fresh requests with no cookie return 200).
  - The `tiles-1674737600` path segment is a **build/version stamp** (Unix epoch
    2023-01-26, matching the IIS `Last-Modified`). It is currently fixed in the
    live env config. Treat it as a configurable constant in the provider module;
    if it ever changes, re-read `env_*.js` (`base360Url`) to refresh it. (This is
    the one piece of the URL that can drift between coverage refreshes.)

- **Coordinate scheme:** `web_mercator` (standard XYZ slippy tiles, EPSG:3857
  grid; tile indices derived from WGS84 lon/lat). Reuse `geo.py` web-mercator
  helpers. The **Point feature `lat`/`lon` are true WGS84** (verified inside
  the Tirana bbox), so the intermediate/rasterization stage can burn exact
  point locations rather than relying on tile centroids.

- **Zoom range / tile size / response format:**
  - Source zoom range: **z6 … z15** (the viewer's `ZOOMLEVELS` map is
    `{0:6,1:7,2:8,3:9,4:11,5:12,6:13,7:14,8:14,9:15,10:15,11:15}` — OL zoom →
    GeoJSON tile zoom; the highest served tile zoom is **z15**).
  - Response: GeoJSON `FeatureCollection`, `Content-Type: application/geo+json`.
    A Tirana z14 tile (`14/9093/6123`) is ~600 kB with **2475 features**:
    2329 `Point` (photo centers), 137 `LineString` + 9 `MultiLineString`
    (capture-sequence traces and labels).
  - **`Point` feature properties:** `id` (panorama id, e.g.
    `camera-20190925-110930-000007677`), `lat`, `lon` (WGS84 decimal degrees),
    `heading` (deg), `height` (m), `date` (ISO 8601, e.g.
    `2019-09-25T11:43:32+02:00`). Observed date span across one tile:
    **2019-08-28 … 2024-12-31** → a per-feature capture date is available, so an
    optional `*_year.tif` date layer is feasible.
  - **`LineString`/`MultiLineString` features:** geometry is in **tile-local
    pixel coordinates** (0–4096 extent, like an MVT geometry — NOT lon/lat) and
    carries `tourName` / `label`. These are the capture-path traces; the
    rasterizer should **use the Point features (real lon/lat) for presence** and
    may ignore the pixel-space lines (or treat them only as decoration).

- **Auth:** **none.** The CAS SSO at `/cas/login?...&gateway=true` is in
  *gateway* mode: an unauthenticated request is bounced straight back to the app
  (no credential prompt), so the viewer and the tiles are public. Direct
  requests to `360.asig.gov.al/.../*.geojson` with no cookie return HTTP 200.
  No `.env` key is required. (For symmetry with the registry, no
  `ASIG_*` secret is needed; if a future build ever gates the proxy, prefer the
  direct origin which is unauthenticated.)

- **Presence rule:** fetch the tile; if HTTP 200 and the parsed
  `FeatureCollection` contains **at least one `Point` feature** (i.e. a photo
  center), imagery is present in that tile. HTTP **404** (IIS "resource not
  found" HTML, ~103 bytes) ⇒ no coverage / empty tile. An empty
  `{"type":"FeatureCollection","features":[]}` (if ever returned) also ⇒ empty.
  For the date layer, take `min`/`max` of the Point `date` years.

- **robots.txt / ToS notes; observed rate limit:**
  - `http://360.asig.gov.al/robots.txt` → **HTTP 404** (no robots file ⇒ no
    declared crawl restrictions on the imagery/coverage host).
  - `https://geoportal.asig.gov.al/robots.txt` → **HTTP 403** (nginx; no
    crawlable robots policy published). Neither host declares a `Disallow`.
  - **Licensing:** ASIG is the National Geoportal administrator under **Law
    72/2012** ("Organization and Operation of National Geospatial Information
    Infrastructure"), an **INSPIRE**-aligned SDI that "guarantees public access"
    and offers ~40 services **free of charge** to the public. ASIG's own pages
    state users "access the photo database through the Internet at the National
    Geoportal." **There is no explicit open-data license** (no CC-BY / ODbL
    statement found) — access is granted by the public-SDI statute rather than a
    named license. We publish only a **derived binary coverage raster + point
    metadata in `data/intermediate`**, never ASIG's panorama imagery; this is a
    coverage-availability use, consistent with the public-access mandate.
    Document this in the module docstring and the STAC item. **Open question for
    the user:** whether to email ASIG for an explicit reuse confirmation before a
    full-extent scrape (recommended but not blocking; see §7 below).
  - **Observed rate limit:** none enforced in scout probes; tiles are static
    files on IIS. Be polite: `polite_fetch` per-host throttle (suggest ≤2 rps,
    one host), retry/backoff, descriptive UA. Albania is a small extent so the
    full z15 scrape over discovered tiles is light.

- **Known quirks / gotchas:**
  - **Mixed geometry types in one tile.** Use `Point` features only for
    presence + the intermediate point store; the `LineString`/`MultiLineString`
    geometries are in **tile-pixel space (0–4096), not lon/lat** — do NOT feed
    them to the rasterizer as geographic coordinates.
  - **`tiles-1674737600` is a build stamp** baked into `base360Url`. Keep it a
    named constant; if a future coverage refresh bumps it, re-read `env_*.js`.
  - **`zoom360` is the GeoJSON tile zoom, not the OL map zoom** (see
    `ZOOMLEVELS`). Max served tile zoom is **z15**; there is no z16+.
  - **CAS gateway mode** can change. Today it lets anonymous traffic through; if
    ASIG ever flips it to enforced login, the **direct origin host stays
    anonymous** — prefer it.
  - **EPSG:6870 (KRGJSH-2010)** is the viewer's display CRS; ignore it for
    scraping — the tile grid is plain WGS84 web-mercator and the feature
    `lat`/`lon` are WGS84.
  - **`http://` origin.** `360.asig.gov.al` is served over HTTP by IIS; confirm
    whether HTTPS is available. If not, document the http-only fetch in the
    module docstring (polite_fetch's auto HTTPS-upgrade may need an opt-out for
    this host).

## 3. Test plan (write these FIRST — red before green)

Fixtures: capture small recorded GeoJSON samples under `tests/fixtures/asig/`:
- `tile_present_z14.geojson` — a trimmed Tirana tile (keep ~3 Point features +
  1 LineString to exercise mixed-geometry handling; strip the rest to keep the
  fixture small).
- `tile_empty.geojson` — `{"type":"FeatureCollection","features":[]}`.
- `tile_404.txt` — the IIS 404 HTML body (to assert 404 ⇒ empty/no-coverage).

- [ ] `test_asig_tile_url_build` — URL template fills correctly for a sample
      `(z, x, y)`: asserts the built URL is
      `…/AlbaniaStreetView/player2/tiles-1674737600/14/9093/6123.geojson` and
      that the `tiles-<stamp>` constant is interpolated as configured.
- [ ] `test_asig_xyz_tile_indices` — Tirana centre (`lon=19.819, lat=41.327`)
      maps to `(z14 → x=9093, y=6123)` and `(z15 → 18187, 12246)` via the shared
      `geo.py` web-mercator helper (pins the coordinate scheme).
- [ ] `test_asig_decode_present` — `tile_present_z14.geojson` decodes to
      `presence = True`, `point_count == 3`, and yields point records with
      `panoid`/`lat`/`lon`/`heading`/`date` populated and lat/lon inside the
      Tirana bbox.
- [ ] `test_asig_decode_empty` — `tile_empty.geojson` decodes to
      `presence = False`, `point_count == 0`.
- [ ] `test_asig_decode_ignores_pixel_lines` — the LineString feature in the
      present fixture does NOT contribute a geographic point record (its
      0–4096 pixel coords are not treated as lon/lat).
- [ ] `test_asig_404_is_empty` — a 404 response (use `tile_404.txt`) is treated
      as "no coverage", not an error that aborts the sweep.
- [ ] `test_asig_date_extraction` — point `date` fields parse to years for the
      optional date layer (e.g. `2019`, `2024`).
- [ ] `test_asig_registers` — module self-registers in `PROVIDERS` after the
      registry imports `providers.asig`.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: NEW kind `vector_geojson`** — a small **separate
      foundation PR first** (it is already a named seed kind in `docs/PLAN.md`
      §4.3 but is not yet implemented). Spec: fetch a GeoJSON tile, parse the
      `FeatureCollection`, derive presence from the count of `Point` features,
      and emit per-Point records `{provider, source_id, z, x, y, tile_url,
      panoid(=id), lat, lon, heading, height, date, fetched_at}` into
      `data/intermediate` (the re-rasterizable source of truth). Treat HTTP 404
      as an empty tile. Register via `register_source_kind("vector_geojson", …)`.
      The existing `coverage_json` kind does **not** fit (it expects a top-level
      `{"panos":[...]}`), and `vector_mvt` expects binary MVT via ogr2ogr — so a
      new kind is genuinely needed, not a tweak. **Do not start the provider PR
      until this kind is merged to `dev`.**
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/asig.py` (`ProviderDefinition`,
      frozen dataclass, `from __future__ import annotations`), one
      `SourceDefinition` with `kind="vector_geojson"`,
      `coordinate_scheme="web_mercator"`, template
      `http://360.asig.gov.al/AlbaniaStreetView/player2/tiles-1674737600/{z}/{x}/{y}.geojson`,
      `display_zoom_min=6`, `display_zoom_max=15`, an `area_presets`
      `tirana_center_bbox`, and a docstring documenting the build-stamp,
      mixed-geometry, http-only, and licensing caveats. Call
      `register_provider(PROVIDER)`. Route all fetches through
      `polite.polite_fetch` with a descriptive UA.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `19.79 41.30 19.86 41.35` (**central Tirana**, around
      the Great Ring Road / Skanderbeg Square — confirmed dense coverage).
- [ ] Rasterize the pilot area to a z14 binary COG (burn the Point lon/lat,
      buffer isolated points by ~1 cell); sanity-check coverage lands on Tirana
      streets, not the Adriatic.
- [ ] Two-pass full extent: pass-1 discovery over Albania
      bbox `19.20 39.60 21.10 42.70` at **discovery zoom z9** (≈40 km tiles —
      Albania spans ~1.9° lon × ~3.1° lat, so a handful of z9 tiles cover the
      country; z6 also works but z9 localizes coverage better for the pass-2
      refine). Pass-2 fetch hit tiles up to the source zoom **z15**.
- [ ] Optional: emit `*_year.tif` date layer from the Point `date` years.
- [ ] Update the STAC item (endpoint, tier T3, scrape date, Law 72/2012
      public-access note); update the inventory status to active/scrapable.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- The new `vector_geojson` source kind is merged (foundation PR) before the
  provider PR; the provider PR adds exactly one `providers/asig.py` (+ tests +
  this doc) and edits no shared file.
- Pilot tiles fetch & decode; presence derived from `Point` count; coverage
  lands on Tirana roads/land (not the Adriatic).
- z14 COG is valid, CRS `EPSG:3857`, `uint8`, covered pixels > 0 over Tirana.
- Fetches via `polite.polite_fetch`; descriptive User-Agent; http-only origin,
  build-stamp, mixed-geometry, and Law 72/2012 / no-explicit-license caveats
  documented in the module docstring and STAC item.

## 6. Status log

- `2026-05-28` scout: drafted. Verdict: **SCRAPABLE — RECOMMEND APPROVE.**
  Reverse-engineered the geoportal `IGVT` app: coverage is an unauthenticated
  XYZ-tiled GeoJSON FeatureCollection at
  `http://360.asig.gov.al/AlbaniaStreetView/player2/tiles-1674737600/{z}/{x}/{y}.geojson`
  (z6–z15, web-mercator XYZ), Point features carry WGS84 `lat`/`lon` + pano
  `id` + `heading` + `date`. Verified live (Tirana z6/z13/z14/z15 = 200 with
  features; ocean tile + missing tile = 404; works with and without the
  geoportal proxy and with no cookies). CAS SSO is `gateway=true` (anonymous).
  No robots.txt restrictions; data is public under Law 72/2012 (INSPIRE SDI),
  no explicit named open-data license. **One prerequisite:** the project needs
  the not-yet-built `vector_geojson` source kind (a small separate foundation
  PR) — `coverage_json` and `vector_mvt` do not fit ASIG's FeatureCollection.
- `2026-05-28` approval: **pending user decision.** Open questions for the user
  in §7.
- `YYYY-MM-DD` implement / verify: notes appended here.

## 7. Open questions for the user (approval gate)

1. **Foundation prerequisite.** Approve building the `vector_geojson` source
   kind as a separate foundation PR first (PLAN §4.3 already lists it as a seed
   kind)? The ASIG provider PR depends on it. If you'd rather not add a kind
   now, an alternative is to shoehorn ASIG into a provider-local decoder, but
   that violates the "thin source-kind dispatcher" design — not recommended.
2. **Licensing confirmation.** ASIG data is publicly accessible under Law
   72/2012 (INSPIRE) but carries **no explicit open-data license**. Do you want
   to (a) proceed on the public-SDI basis and document it, or (b) email ASIG for
   an explicit reuse confirmation before the full-extent scrape? Coverage-only
   (we never re-host imagery) makes (a) low-risk, but (b) is the cautious path.
3. **http-only origin.** `360.asig.gov.al` is HTTP (IIS). Confirm it's
   acceptable to fetch over HTTP (polite_fetch auto-upgrades to HTTPS by
   default; this host may need an opt-out). The geoportal HTTPS proxy is an
   alternative but routes through CAS/nginx.

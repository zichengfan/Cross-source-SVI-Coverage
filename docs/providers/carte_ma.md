# [T2] Provider: Carte.ma (`carte_ma`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Carte.ma is a 100%-Moroccan street-level imagery service ("le Google Street
View marocain"), launched in 2014 by Marouane Lamharzi Alaoui. It produced its
own car-mounted panoramic imagery — reportedly >1 million panoramas covering
~104,000 km of roads at ~5 m spacing — across roughly ten Moroccan cities:
Agadir, Asilah, Casablanca, Errachidia, Essaouira, Fès, Ifrane, Marrakech,
Meknès and Rabat. It is a first-party SVI provider (not a re-hoster, not
paid-B2B), which is why it appears in the inventory as a T2 candidate.

**Scouting verdict: RECOMMEND DEFER (not skip permanently).** Carte.ma *had* a
cleanly scrapable street-view coverage API and tile layer, but as of the scout
date (2026-05-22) **the service is down**: the apex `carte.ma` returns a hard
`HTTP 500` on every path and the per-city content subdomains
(`casablanca.carte.ma`, `agadir.carte.ma`, …) do not respond to HTTP at all
(TCP 80/443 closed/filtered). The coverage endpoints documented below are
**verified-correct from Wayback captures up to April 2025** but **cannot be
fetched live today**. This subplan is written so the provider can be
implemented immediately *if and when* Carte.ma comes back online — it is a
deferred provider, blocked only by the upstream outage, not by any design or
ToS problem. Do not open an implementation issue while the site is down; re-probe
periodically (see §6).

## 2. Research findings (filled by provider-scout)

### Verdict detail — current outage

- **Apex `carte.ma`** resolves to `35.180.52.134` (AWS eu-west-3, nginx) and
  returns **`HTTP 500 Internal Server Error`** (170-byte nginx error page) on
  **every** path probed: `/`, `/robots.txt`, `/index.html`, `/map`, `/api`,
  `/tiles/agadir/16/31016/26948.png`, etc. Verified live 2026-05-22 (three
  retries, all 500). Wayback confirms the apex last served `HTTP 200` on
  **2025-06-02**, then flipped to a persistent `HTTP 500` — Wayback shows 500 on
  2025-12-31, 2026-01-31, matching the live probe. The site has been broken for
  ~11 months.
- **Per-city content subdomains** (`casablanca.carte.ma`, `agadir.carte.ma`,
  `marrakech.carte.ma`, `rabat.carte.ma`, …) resolve to a *different* host,
  `37.187.114.153` (OVH, France). That host **does not accept connections** —
  TCP ports 80 and 443 are closed/filtered, every HTTP(S) request times out.
  These subdomains hosted the actual street-view viewer and the coverage API
  (see below) and are completely unreachable.
- The Carte.ma street-view content (the per-city viewer, the `mapspots.php`
  coverage API, the `view/floorplan` and `tiles/<city>` tile layers) was last
  archived **alive** in the Wayback Machine between **2024-12-29 and
  2025-04-28**. So the service was healthy ~13 months ago and has since gone
  dark on both the apex and the content host.

### What the coverage layer is (verified from Wayback, April-2025 captures)

Carte.ma serves street-view coverage two ways. **The primary, recommended
coverage source is a JSON point API**, not a raster overlay.

- **Homepage / public viewer URL:**
  - Apex / landing page: `https://carte.ma/` (historically just a teaser /
    coming-soon page; the real viewer is on the subdomains).
  - Per-city street-view viewer: `https://<city>.carte.ma/view/<city>.php`
    (e.g. `https://casablanca.carte.ma/view/casablanca.php`). A specific
    panorama opens via `?sv=<panoid>&heading=<deg>&tilt=<deg>&zoom=<n>`
    (e.g. `…/view/casablanca.php?sv=1000985&heading=92&tilt=0&zoom=50`).
- **Tier:** T2.

- **Source kind: `coverage_json`** — a bbox-query JSON API returning panorama
  points. (NOT `raster`: the `/tiles/<city>/{z}/{x}/{y}.png` layer that exists
  is a *fully-opaque rendered basemap* of the city, not a transparent
  "panorama-exists-here" overlay — see "Why not the tile layer" below.)

- **Coverage endpoint — the `mapspots.php` JSON point API (use this):**
  - **URL template:**
    ```
    https://<city>.carte.ma/view/ajax/mapspots.php?curSpotID={any}&zoom={z}&lat1={lat_min}&lat2={lat_max}&lng1={lon_min}&lng2={lon_max}
    ```
  - **HTTP method:** `GET`.
  - **Query params:**
    - `lat1`/`lat2` — south/north latitude bounds (WGS84 degrees).
    - `lng1`/`lng2` — west/east longitude bounds (WGS84 degrees).
    - `zoom` — a Leaflet-style integer zoom (observed `10`–`18`); the server
      **density-thins** the returned points by zoom (coarse zoom → sparse
      sample, fine zoom → every panorama). For a complete coverage extent fetch
      use the **highest zoom** (`zoom=18`), which returns the full point set in
      a bbox.
    - `curSpotID` — the currently-open panorama id in the viewer; it does **not**
      filter the result set (the same bbox returns the same points regardless).
      Pass any valid id (e.g. the city's default spot) or omit it — confirm
      during implementation whether the param can be dropped entirely.
  - **Response format:** `application/json` — a flat JSON **array** of panorama
    objects, each `{"id": "<panoid>", "lat": "<wgs84>", "lng": "<wgs84>",
    "heading": "<deg>"}`. All values are JSON strings. Example (real, from the
    2025-04-28 Casablanca capture):
    ```json
    [{"id":"000001","lat":"33.59679722","lng":"-7.62718333","heading":"7"},
     {"id":"000106","lat":"33.59903333","lng":"-7.64362222","heading":"244"},
     {"id":"1000985","lat":"33.58688056","lng":"-7.63286389","heading":"82"}, ...]
    ```
  - **Headers:** none observed as required in the Wayback captures. For polite
    scraping the `SourceDefinition.headers` should set a descriptive
    `User-Agent`, `Accept: application/json`, and a `Referer:
    https://<city>.carte.ma/` — re-verify header requirements live once the
    site is back.

- **Per-city subdomains / extent.** Each city is a separate subdomain with its
  own `mapspots.php`. Confirmed-existing subdomains from Wayback:
  `casablanca`, `agadir`, `errachidia`, `asilah` (and per press coverage also
  `essaouira`, `fes`, `ifrane`, `marrakech`, `meknes`, `rabat` — the apex
  `/tiles/` layer has directories for `agadir`, `casablanca`, `errachidia`,
  `marrakech`, `rabat`, confirming those at minimum). The implementer should
  treat the **city list as a config table** (one `mapspots.php` query region per
  city) — see §4. There is no single global endpoint; coverage is the union of
  the per-city queries.

- **Coordinate scheme:** `web_mercator`. The `mapspots.php` API takes and
  returns **plain WGS84 lat/lon** (`EPSG:4326`) — the `lat1/lat2/lng1/lng2`
  bbox params and the response `lat`/`lng` are degrees. The project's z14
  coverage grid is standard Web Mercator XYZ, so `coordinate_scheme =
  "web_mercator"`; the discovery "grid" for a `coverage_json` provider is a
  set of bbox queries the implementer constructs in WGS84. The companion
  `/tiles/<city>/{z}/{x}/{y}.png` basemap layer also uses standard
  web-mercator XYZ (verified: a probed `z16/z17` tile decoded as a 256×256
  city basemap tile in the right place) — but that layer is **not** the
  coverage source (see below).

- **Zoom range / tile size / response format:** Not tile-based for coverage.
  `mapspots.php` is a JSON API; the `zoom` param is `10`–`18` and only controls
  server-side density thinning. Use `zoom=18` for a complete fetch. Response is
  a JSON array (no pagination observed — each bbox query returns its full point
  set; keep bbox queries city-sized or smaller to bound response size).

- **Auth:** **none.** No token, no cookie, no API key, no login — the
  `mapspots.php` captures are plain unauthenticated `GET`s and the viewer is
  public. **No `.env` key is needed.** (Re-confirm live once the site is back.)
  This provider does **not** need the `runtime_config/` registry — there is no
  live token/version to discover.

- **Presence rule:** "Imagery exists here" ⇔ the `mapspots.php` response for a
  bbox contains **≥ 1 panorama object**. Each object is a presence point at its
  own `lat`/`lng` (WGS84). A z14 grid cell that contains ≥ 1 returned panorama
  point is **covered (1)**; a probed bbox/cell that returns an **empty array
  `[]`** is **checked-empty (0)**; never-probed cells are **nodata (255)**.
  Burn the real panorama `lat`/`lng` into the raster (not the query-bbox
  centre); isolated points are buffered ~1 cell at rasterization per
  `docs/PLAN.md` §1, the same as other point-based providers.

- **Empty signature:** an empty JSON array `[]` (HTTP 200, `application/json`).
  No 404/204 for an in-extent empty bbox is expected — re-verify live (a bbox
  fully outside a city's data may instead return `[]` or possibly an error;
  treat any non-JSON / non-200 as a hard fetch error distinct from a clean
  empty `[]`, mirroring the `ja360` blocked-vs-empty distinction).

- **Why NOT the `/tiles/` raster layer.** The apex serves
  `https://carte.ma/tiles/<city>/{z}/{x}/{y}.png` (and the subdomains a similar
  `view/floorplan/{z}/{x}/{y}.png`). A live-equivalent Wayback tile
  (`tiles/agadir/16/31016/26948.png`, 2025-04-05) decodes to a **256×256,
  fully-opaque** PNG: every pixel has `alpha == 255`; the dominant colours are
  beige land `(241,238,232)`, green parks `(150,210,150)`, and white roads
  `(255,255,255)`. It is a **rendered city basemap**, not a transparent
  "coverage-exists-here" overlay — so the kakao/naver/mapy alpha-as-coverage
  trick does **not** apply here. There is no separate transparent
  coverage-overlay tile layer. The `mapspots.php` JSON point API is the only
  clean machine-readable coverage source. (`/tiles/` is just the viewer's
  background map; ignore it.)

- **Capture date.** `mapspots.php` returns only `id`/`lat`/`lng`/`heading` — no
  capture date. Press reporting says the original fleet captured in 2014 and the
  imagery may be largely a single 2014 vintage; per-panorama dates, if any, are
  not in the coverage API. A `carte_ma_year.tif` date layer is **out of scope**
  for this provider (note as a possible future follow-up if a dated metadata
  endpoint is found).

- **robots.txt / ToS notes; observed rate limit:**
  - **robots.txt — investigate the inventory flag.** The inventory note says
    "robots.txt error but site exists". Confirmed: `https://carte.ma/robots.txt`
    returns **`HTTP 500`** (the same nginx error as every other path — it is the
    *whole site* that is 500ing, there is no real `robots.txt` served right
    now). Wayback has no captured `robots.txt` body for the apex or the
    subdomains with retrievable content. Under the project's robots posture
    (`polite.robots_allows` treats an unreachable / non-200 `robots.txt` as
    **allowed**), a 500 `robots.txt` ⇒ allowed — there is **no `Disallow`
    rule blocking this provider**. The "robots.txt error" the inventory flags
    is simply a symptom of the site-wide outage, not a crawl prohibition.
    **Action for the implementer:** once the site is back, re-fetch
    `https://<city>.carte.ma/robots.txt` and `https://carte.ma/robots.txt` and
    record the real contents in §6 before scraping.
  - **ToS:** Carte.ma has no published machine-readable crawl policy. The
    `mapspots.php` endpoint is a public, unauthenticated viewer API. This
    project stores only a **derived binary coverage raster** (presence/absence),
    not Carte.ma panorama imagery and not its rendered tiles. Record this caveat
    in the module docstring. Keep the scrape polite and modest — coverage is
    only ~10 cities, so the total query volume is small.
  - **Observed rate limit:** unknown — the site is down, so no live probing was
    possible. Be conservative when it returns: `polite.polite_fetch` default
    per-host throttle, low concurrency, exponential backoff on 429/5xx, and
    **stop the run on a sustained 500/timeout streak** (the current failure
    mode). Record the real limit in §6 after the first successful pilot.

- **Known quirks / gotchas:**
  - **The whole service is currently down** (apex `HTTP 500`; content
    subdomains TCP-unreachable). This is the single blocking issue — see the §1
    verdict and §6. Everything below assumes the site returns to the
    April-2025 behaviour.
  - **Per-city subdomains, not one host.** Coverage is the union of ~10
    independent `<city>.carte.ma/view/ajax/mapspots.php` endpoints. The
    provider module must carry a **city table** (subdomain + a city bounding
    box) and the discovery loop iterates cities. There is no global endpoint.
  - **`coverage_json`, not tiles.** Coverage discovery is bbox JSON queries,
    not XYZ tile fetches. The two-pass extent runner must drive *bbox queries
    per city*, not a global tile sweep, for this provider (similar in spirit to
    how `ja360` drives point probes rather than tiles).
  - **JSON values are strings.** `lat`, `lng`, `heading`, `id` all come back as
    JSON strings — cast `lat`/`lng` to float, keep `id` as a string (ids have
    leading zeros, e.g. `"000001"` — do not parse them as ints).
  - **`zoom` thins the result.** A low `zoom` returns a decimated sample, not
    the full set — never use a low zoom for the final extent fetch. Use
    `zoom=18`. (A coarse zoom is only useful as a cheap pass-1 "does this city
    have any coverage at all" check.)
  - **The apex `/tiles/` URLs have a doubled slash in Wayback**
    (`/tiles/agadir//16/...`). That is a Wayback-normalisation artifact of the
    original relative URL join, not part of the real path. Irrelevant anyway —
    the `/tiles/` layer is not used (see "Why NOT the `/tiles/` raster layer").
  - **`curSpotID` param.** Present in every captured `mapspots.php` URL but does
    not change the result for a given bbox. Confirm it can be omitted; if the
    server requires *some* value, pass a known city default spot id.
  - **Apex vs. content host split.** `carte.ma` (AWS) and `*.carte.ma` (OVH)
    are different machines with independent uptime. The `mapspots.php` API
    lives only on the OVH content subdomains; do not expect the apex to serve
    it.

## 3. Test plan (write these FIRST — red before green)

All tests are **offline** — they decode recorded JSON fixtures and never hit the
network (`docs/PLAN.md` §12). Fixtures are the **Wayback-captured**
`mapspots.php` responses (the live site is down); record them by fetching the
Wayback `…id_/` raw-content URLs and saving the JSON. Fixtures live under
`tests/fixtures/carte_ma/`.

Fixtures to record:
- `tests/fixtures/carte_ma/mapspots_casablanca_z14.json` — a real `mapspots.php`
  response containing panorama points (from the 2025-04-28 Casablanca capture,
  `…/mapspots.php?…&zoom=10&lat1=33.3798…` — any covered Casablanca bbox); a
  JSON array of `{id,lat,lng,heading}` objects.
- `tests/fixtures/carte_ma/mapspots_empty.json` — a `mapspots.php` response that
  is an empty array `[]` (a bbox with no panoramas). If no empty capture is
  available from Wayback, synthesize a minimal `[]` fixture and note it.
- (optional) `tests/fixtures/carte_ma/mapspots_blocked.html` — a non-JSON error
  body (e.g. the current nginx `HTTP 500` page) so the blocked-vs-empty test has
  a realistic payload.

Tests (`tests/test_providers_carte_ma.py`):

- [ ] `test_carte_ma_registers` — importing
  `coverage_acquisition.providers.carte_ma` registers `"carte_ma"` in
  `PROVIDERS`; `get_provider("carte_ma")` returns a `ProviderDefinition` with
  `key == "carte_ma"` and at least one source whose `kind == "coverage_json"`.
- [ ] `test_carte_ma_provider_shape` — `coordinate_scheme == "web_mercator"`;
  the source has no token/cookie/auth fields; `options` carry the per-city
  table (subdomain + bbox) and the `zoom` value used for the extent fetch;
  `area_presets` contains the Casablanca pilot bbox.
- [ ] `test_carte_ma_query_url_build` — the source `template` fills correctly
  for a sample city + bbox + zoom: city `casablanca`, `zoom=18`,
  `lat1/lat2/lng1/lng2` for the pilot bbox →
  `https://casablanca.carte.ma/view/ajax/mapspots.php?…zoom=18&lat1=…&lat2=…&lng1=…&lng2=…`
  (assert host `casablanca.carte.ma`, path `/view/ajax/mapspots.php`, and that
  the four bbox params and `zoom` are present and correctly ordered).
- [ ] `test_carte_ma_decode_present` — decoding
  `mapspots_casablanca_z14.json` through the `coverage_json` decode path yields
  N > 0 presence records; each record has a string `id`, a float `lat`, a float
  `lng` (cast from the JSON strings) within the Casablanca bbox.
- [ ] `test_carte_ma_decode_empty` — decoding `mapspots_empty.json` (`[]`)
  yields **zero** presence records / `is_empty` true, and is **not** an error
  (checked-empty, not a failure).
- [ ] `test_carte_ma_decode_blocked_is_error` — feeding a non-JSON / HTML body
  (the `HTTP 500` page) to the decoder raises/flags a distinct "blocked" /
  fetch error, **not** a clean empty result (so a site outage is never silently
  recorded as "no coverage").
- [ ] `test_carte_ma_ids_keep_leading_zeros` — a panorama whose JSON `id` is
  `"000001"` decodes to the string `"000001"` (not the int `1`) — guards
  against losing the leading-zero id format.
- [ ] `test_carte_ma_presence_uses_pano_location` — a decoded presence point
  uses the panorama's own `lat`/`lng`, not the query-bbox centre.
- Fixtures: small recorded JSON samples under `tests/fixtures/carte_ma/` (above).

## 4. Implementation subplan (steps for the implementer — TDD)

> **Gate:** do not start implementation while Carte.ma is down (apex `HTTP 500`,
> subdomains unreachable). The pilot fetch (and live fixture re-verification)
> cannot run. See §6 — re-probe first; implement only once the site is back.

- [ ] **Source kind: `coverage_json`** — a bbox-query JSON API returning
  presence points. Confirm this kind already exists in
  `src/coverage_acquisition/source_kinds/` (the project lists `coverage_json`
  among its source kinds). If `coverage_json` does **not** yet exist, that is a
  **separate `foundation`-labelled PR** that must merge before the `carte_ma`
  provider PR (per `CLAUDE.md`: a new source kind is a foundation change, not
  part of a provider module). The `coverage_json` kind must: fetch a JSON URL
  via `polite.polite_fetch`, parse a JSON array of point objects, map each to a
  presence record (`provider`, `panoid=id`, `lat`, `lng`, `heading`,
  `fetched_at`), map an empty array `[]` to checked-empty, and map a non-JSON /
  non-200 body to a hard "blocked" error.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/carte_ma.py` defining `PROVIDER`
  as a `ProviderDefinition` and calling `register_provider(PROVIDER)`. Shape
  (mirror `ja360.py` for a point/JSON provider):
  - `key="carte_ma"`, `output_namespace="carte_ma_streetview_coverage"`,
    `run_label_prefix="carte_ma_mapspots"`, `default_display_zoom=14`,
    `coordinate_scheme="web_mercator"`.
  - `area_presets` declared **in this module** (do not edit `_presets.py`):
    a Casablanca pilot bbox — see pilot below.
  - One `SourceDefinition`:
    - `id="carte_ma_mapspots"`, `kind="coverage_json"`.
    - `template="https://{city}.carte.ma/view/ajax/mapspots.php?zoom={z}&lat1={lat_min}&lat2={lat_max}&lng1={lon_min}&lng2={lon_max}"`
      (decide whether `curSpotID` is needed — omit if the server accepts the
      query without it; otherwise add `&curSpotID={spot}` with a per-city
      default).
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "application/json", "Referer": "https://casablanca.carte.ma/"}`
      (set `Referer` per-city if simple; otherwise a single representative
      value is fine).
    - `expect_content_type_prefix="application/json"`.
    - `storage_subdir="mapspots"`.
    - `options`: a per-city table — e.g. `{"cities": "agadir,asilah,casablanca,
      errachidia,essaouira,fes,ifrane,marrakech,meknes,rabat", "extent_zoom":
      "18", "discovery_zoom": "12"}` — plus per-city bounding boxes (declare the
      city bboxes inline in the module as a dict of `BoundingBox`). The exact
      city list must be confirmed live (some subdomains may 404); start from the
      `/tiles/` directories (`agadir, casablanca, errachidia, marrakech, rabat`)
      which are definitely-real, and add the others after live verification.
    - `notes`: record that this is a `coverage_json` point API
      (`mapspots.php`), one endpoint per city subdomain, no auth, and the
      April-2025 outage caveat.
  - Module docstring: record (a) `coverage_json` point API, not a tile layer;
    (b) the per-city subdomain split and the city table; (c) the outage caveat
    and that the `/tiles/` layer is an opaque basemap, deliberately not used;
    (d) the ToS posture (public unauthenticated API; only a binary coverage
    raster is published, never imagery); (e) coverage = ~10 Moroccan cities.
- [ ] Implement until the §3 tests pass (green); refactor. Route all HTTP
  through `polite.polite_fetch` (descriptive UA, per-host throttle,
  retry/backoff) — never bare `urllib`/`requests`.
- [ ] **Pilot fetch:** city `casablanca`, bbox
  `-7.65 33.575 -7.60 33.605` (`Casablanca — city centre / Maârif`, a small
  area with confirmed dense Carte.ma coverage in the 2025-04-28 capture). Query
  `mapspots.php?zoom=18&lat1=33.575&lat2=33.605&lng1=-7.65&lng2=-7.60`; expect a
  non-empty JSON array of panorama points falling on the central Casablanca
  street network (e.g. around `33.5868,-7.6328`, a confirmed real spot id
  `1000985`). **Requires the site to be back up.**
- [ ] Rasterize the pilot area to a z14 COG (EPSG:3857, `uint8`,
  1=covered / 0=checked-empty / 255=nodata) via `rasterize.py`; buffer isolated
  points by ~1 cell (`docs/PLAN.md` §1); sanity-check that covered pixels land
  on Casablanca streets, not the Atlantic.
- [ ] **Two-pass full extent:** pass-1 = per city, one coarse `mapspots.php`
  query (`zoom=12`) over the city bounding box to decide whether the city has
  any coverage and to get a rough footprint; pass-2 = per city, `zoom=18`
  queries over the covered area, tiled into city-sized-or-smaller bboxes so each
  response stays bounded. The discovery "region" is the **union of the ~10
  city bounding boxes** (all inside Morocco) — there is no country-wide sweep;
  Carte.ma coverage is city-only. Run detached in `tmux` per `run-scraper`.
- [ ] Update / create the STAC item (`catalog.upsert_provider_item`,
  `tier="T2"`, extent = the union of discovered city coverage,
  `source_endpoint="https://<city>.carte.ma/view/ajax/mapspots.php"`,
  `tos_notes` per §2). Update the inventory status for `carte_ma`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.carte_ma` imports and
  self-registers in `PROVIDERS`; CI smoke test (import / register / dry-run)
  passes.
- The provider's source is `kind="coverage_json"`,
  `coordinate_scheme="web_mercator"`, no auth fields; the query `template`
  builds the per-city `mapspots.php` URL with the four bbox params and `zoom`.
- Pilot `mapspots.php` query over central Casablanca returns a non-empty JSON
  array; decoded panorama points fall on Casablanca roads/land (not the
  Atlantic, not outside Morocco). An empty bbox decodes to `[]` ⇒ checked-empty
  without error; a non-JSON error body is flagged as blocked, not empty.
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0, extent within
  the Moroccan city bounding boxes; isolated points buffered ~1 cell.
- All fetching goes through `polite.polite_fetch` with a descriptive
  `User-Agent` and a conservative throttle; ToS caveats and the per-city
  subdomain structure documented in the `carte_ma.py` module docstring and the
  STAC `tos_notes`.

## 6. Status log

- `2026-05-22` scout: drafted. **Verdict: RECOMMEND DEFER — provider design is
  sound and cleanly scrapable, but the upstream service is currently down.**
  Findings:
  - Carte.ma's street-view coverage is exposed as a **`coverage_json` point
    API**: `https://<city>.carte.ma/view/ajax/mapspots.php?zoom=&lat1=&lat2=
    &lng1=&lng2=` returning a JSON array of `{id,lat,lng,heading}` panorama
    points in the bbox, density-thinned by `zoom`. Verified from Wayback
    captures of `casablanca.carte.ma` up to **2025-04-28**.
  - One endpoint per city subdomain (~10 Moroccan cities: agadir, asilah,
    casablanca, errachidia, essaouira, fes, ifrane, marrakech, meknes, rabat).
    Coordinate scheme = `web_mercator` (API is plain WGS84 lat/lon). No auth,
    no `.env` key, no `runtime_config/` needed.
  - The `https://carte.ma/tiles/<city>/{z}/{x}/{y}.png` raster layer exists but
    is a **fully-opaque rendered city basemap** (a 2025-04 Wayback tile decoded
    100% `alpha==255`, beige/green/white basemap colours) — **not** a
    transparent coverage overlay. The kakao/naver/mapy raster-overlay pattern
    does **not** apply; `mapspots.php` is the coverage source.
  - **Blocker — upstream outage.** Live 2026-05-22: apex `carte.ma`
    (`35.180.52.134`, AWS) returns `HTTP 500` on every path including
    `robots.txt`; content subdomains (`*.carte.ma` → `37.187.114.153`, OVH)
    have TCP 80/443 closed and time out. Wayback shows the apex last `HTTP 200`
    on 2025-06-02 then persistent `HTTP 500` through 2026-01-31; the
    `mapspots.php` API and `/tiles/` layer last archived alive ~Apr 2025. The
    service has been broken ~11 months.
  - **robots.txt — inventory flag explained.** The inventory's "robots.txt
    error" is just a symptom of the site-wide `HTTP 500`: there is no real
    `robots.txt` served and no `Disallow` rule. Under the project's posture an
    unreachable `robots.txt` ⇒ allowed; re-fetch the real `robots.txt` once the
    site is back.
  - **Recommendation:** do **not** open an implementation issue or branch now.
    Treat `carte_ma` as **deferred**, blocked solely by the upstream outage.
    Re-probe periodically (suggest monthly): if `carte.ma` and at least one
    `<city>.carte.ma` start serving `HTTP 200` again and `mapspots.php` returns
    JSON, this subplan is implementation-ready as written — only the live
    fixture re-verification (§3) and the pilot (§4) need to be run. If the site
    is still dead after a reasonable window (e.g. 6–12 months), reclassify
    `carte_ma` as **defunct** and drop it from the inventory.
- `2026-05-22` approval: < pending — awaiting user review >.
- `YYYY-MM-DD` re-probe: < record whether carte.ma is back; if so, the real
  robots.txt contents, the confirmed live city subdomain list, and any
  observed rate limit >.
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **Defer vs. drop.** The provider is technically sound (clean
   `coverage_json` point API, no auth, ~10 cities), but the upstream service
   has been down ~11 months. Recommendation: **defer** and re-probe monthly,
   with a hard deadline (e.g. reclassify as defunct if still down in 6–12
   months). Confirm this disposition, or decide to drop `carte_ma` now as
   defunct.
2. **`coverage_json` source kind.** This subplan assumes a `coverage_json`
   source kind exists (it is listed among the project's source kinds). The
   implementer must confirm it is present in
   `src/coverage_acquisition/source_kinds/`; if not, it is a **foundation PR**
   that must precede the provider PR. Confirm the `coverage_json` kind supports
   a bbox-query API returning a JSON point array, with empty-array =
   checked-empty and non-JSON = blocked-error semantics (the same three-way
   present / empty / blocked distinction `ja360` needs).
3. **Per-city config.** Coverage is ~10 independent city subdomains, each with
   its own `mapspots.php`. The provider module carries a city table
   (subdomain + bounding box). Confirm the two-pass extent runner can iterate a
   per-city query list (rather than a single global tile/bbox sweep) for a
   `coverage_json` provider — same machinery `ja360`'s point-probe mode needs.
4. **`curSpotID` parameter.** Every captured `mapspots.php` URL carries a
   `curSpotID`, but it does not appear to filter results. The implementer must
   verify live whether it can be omitted; if the server requires a value, the
   module needs a per-city default spot id. Cannot be confirmed while the site
   is down.
5. **Live re-verification needed before implementation.** All endpoint
   findings come from Wayback (the live site is down): the exact header
   requirements, the empty-bbox response shape, the rate limit, the full live
   city list, and `robots.txt` must all be re-confirmed against the live site
   once it returns, before the pilot scrape.

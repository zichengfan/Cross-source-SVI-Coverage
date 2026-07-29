# [T2] Provider: Mappy (`mappy`) — RECOMMEND DEFER / SKIP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-22): DEFER / SKIP. Mappy still ships a panorama feature
in its viewer, but its street-level coverage is effectively unavailable: the
viewer's own coverage probe returns HTTP 404 across the entire densest area of
the country, and Mappy's own FAQ tags the panoramic-photo feature "obsolète".
There is no rendered coverage raster tile layer and no coverage MVT layer.
This subplan documents the full investigation and the conditional plan that
would apply *if* coverage ever becomes reachable again. No issue/branch/code
should be created now.
-->

## 1. Summary

Mappy (`https://fr.mappy.com/`) is a long-running French web-mapping service
(routing, maps, POIs), operated in France with data hosted in Europe. From March
2010 it offered an "immersive view" / 360° panoramic street-level imagery
product covering the centres and main suburban roads of major French cities.
The provider is French, in-scope by region, and the SVI feature is first-party
(Mappy photographed the cities itself, with face/plate blurring) — it is **not**
a re-hoster.

**However, scouting concludes Mappy should be DEFERRED / SKIPPED for now.** The
modern WebGL/Leaflet viewer no longer renders a panorama coverage overlay of any
kind (no `{z}/{x}/{y}` raster tile layer, no coverage MVT layer). The only
coverage signal is a per-view point-probe JSON API (`api-poi.mappy.net/data/
pano/1.10/panoramics/...`), and that endpoint returns **HTTP 404 for every
coordinate tested**, including the densest part of central Paris (Rue de Rivoli,
Châtelet, Champs-Élysées, the Louvre) at radii up to 2 km — i.e. the viewer's
own coverage probe finds nothing where Mappy historically had the densest
imagery. Mappy's own support FAQ tags the panoramic-photo articles as
**"obsolète" / "obsolete"**. With no coverage layer to scrape and no coverage
data returned by the only coverage API, there is nothing to harvest into the
coverage database. See §2 for the full evidence and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: no scrapable coverage layer — DEFER / SKIP

Applying the kakao/naver/mapy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.**
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON API (`kind="coverage_json"` / `json_api`)? — Technically a
   point-probe API exists, but it returns no coverage anywhere tested.**

- **Homepage / public viewer URL:**
  - Homepage / viewer: `https://fr.mappy.com/` (the map viewer is at
    `https://fr.mappy.com/plan`).
  - The viewer is a React SPA. Main bundle:
    `https://fr.mappy.com/assets/js/app.<hash>.js` (`app.8be18c5e…js` at scout
    time). The map is rendered with a MapLibre/Mapbox-GL-style vector renderer
    (the bundle history confirms Mappy migrated from a "maison" API → Leaflet →
    the current GL vector stack; custom 384-px tiles in the old Leaflet era are
    no longer used by the live `standard_v2` vector tiles).
  - Tier: **T2** (the inventory note "Custom scraper (WebGL-based viewer)").

- **How the viewer was investigated.** The static HTML exposes nothing useful
  (SPA). Scouting drove the live viewer in headless Google Chrome via the
  DevTools Protocol (`--remote-debugging-port`), loaded
  `https://fr.mappy.com/plan` centred on multiple French city centres, zoomed
  in, and captured every network request. The web API key is injected into the
  page as `window.__MAPPY_API_KEY__` (value observed:
  `f2wjQp1eFdTe26YcAP3K92m7d9cV8x1Z`) and is sent to `api-*.mappy.net` either as
  an `apikey` **query param** (map/tile hosts) or an `apikey` **request header**
  (the POI / panorama host).

- **What the live viewer actually fetches** (captured 2026-05-22):
  - **Base map (vector):** `https://api-map.mappy.net/map/1.0/vector/
    standard_v2/{z}/{x}/{y}` (MVT), styled by `maplight_v2.8.json` /
    `mappy_map.json`. Coordinate scheme: standard Web Mercator XYZ.
  - **POI vector tiles:** `…/map/1.0/vector/pois_v9/{z}/{x}/{y}`.
  - **Raster slabs:** `…/map/1.0/slab/standard/256/{z}/{x}/{y}` (basemap),
    `…/slab/standard_hd/…`, `…/slab/photo/256/{z}/{x}/{y}` (**aerial/satellite
    photography — IGN 2016 — NOT street-level**), `…/slab/hillshade/…`,
    `…/slab/bicycle/…`, `…/slab/public_transport_hd/…`.
  - **The full MapLibre style** (`full_style_web_v1.json`, `mappy_map.json`,
    `maplight_v2.8.json`) was fetched and every `source` enumerated. The only
    sources are: standard basemap (vector + raster), `photo` (aerial), traffic,
    bicycle, public transport, hillshade, ZTL/LEZ, and copyright overlays.
    **There is no panorama / street-view / immersive coverage source of any
    kind** — no raster overlay and no MVT layer for "panorama exists here".
  - **The panorama probe:** on every map view change the viewer fires exactly
    one request to the panorama service:
    ```
    GET https://api-poi.mappy.net/data/pano/1.10/panoramics/{lng},{lat},100/tiles/geodetic/{lng},{lat}.json?preview=false
    ```
    Method `GET`; auth via an `apikey` request header. `{lng},{lat}` is the
    current map centre (WGS84), `100` is a radius in metres. This is a
    point-radius coverage probe: it asks "is there a Mappy panorama within ~100 m
    of here?" and the viewer uses the answer to decide whether to surface the
    immersive entry point.

- **Coverage endpoint (the panorama probe) — and why it yields nothing:**
  - URL template (the only candidate coverage endpoint):
    `https://api-poi.mappy.net/data/pano/1.10/panoramics/{lng},{lat},{radius_m}/tiles/geodetic/{lng},{lat}.json?preview=false`
  - Auth: `apikey` **request header** = `window.__MAPPY_API_KEY__` scraped from
    the viewer HTML. (Sent as a query param it 404s; the header form is what the
    live viewer uses.)
  - **Result: HTTP 404 (Apache Tomcat "Status 404 – Not Found") for every
    coordinate probed**, with the API key correctly attached. Tested:
    - Central Paris — Rue de Rivoli `(2.3499,48.859)` (the exact URL the live
      viewer itself issued), Châtelet, the Louvre `(2.3376,48.8606)`, the
      Champs-Élysées, the Eiffel Tower `(2.2945,48.8584)` — radii 100 m, 500 m,
      1000 m, 2000 m → **all 404**.
    - Other major historically-covered cities: Marseille, Lyon, Toulouse,
      Nantes, Lille, Strasbourg, Rennes, Reims — radii 100 m and 1000 m →
      **all 404**.
  - The sibling path `…/panoramics/{lng},{lat},{radius}.json` returns HTTP 400
    (the route is *recognised* but the request is rejected), confirming the
    `pano/1.10` service is alive but exposes no working coverage query for an
    automated sweep. The `tiles/geodetic/…` form is a per-panorama tile manifest
    that only resolves when a panorama actually exists at the point.
  - **Conclusion:** the viewer's own coverage probe finds zero panoramas in the
    densest possible part of France. Either Mappy's street-level dataset has been
    withdrawn from this API, or it is so sparse that no automated coverage sweep
    can find it. Both outcomes mean there is no coverage map to harvest.

- **Coordinate scheme:** the basemap/tiles are standard **`web_mercator`**
  (EPSG:3857 XYZ). The panorama probe is **not tile-based at all** — it is a
  lat/lng point-radius query, so no tile/coordinate scheme applies to it.

- **Zoom range / tile size / response format:** N/A for coverage — there is no
  coverage tile layer. The panorama probe returns JSON (when a panorama exists)
  or a Tomcat HTML 404 (when none does).

- **Auth:** the panorama API requires the `apikey` header
  (`window.__MAPPY_API_KEY__`, scraped from `https://fr.mappy.com/plan`). The
  key is a public web-client key embedded in page HTML, not a secret; if Mappy
  were ever implemented it would need a `runtime_config` helper to re-scrape the
  current key per run (the key can rotate). **`.env` key name (only if revived):
  not needed — the key is public and discovered at runtime, not stored.**

- **Presence rule (hypothetical, only if coverage ever returns):** "imagery
  exists near (lng,lat)" ⇔ the `pano/1.10/panoramics/…json` probe returns
  HTTP 200 with a non-empty JSON panorama manifest; HTTP 404 ⇔ no imagery. As of
  this scout **every** probe is 404, so the rule currently classifies all of
  France as "no coverage".

- **robots.txt / ToS notes; observed rate limit:**
  - `https://fr.mappy.com/robots.txt` → HTTP 200. It `Disallow:`s
    `/utilisateur/`, `/roadbook`, `/geoentity/`, `/*/1000$`, and blocks AI
    crawlers (`ClaudeBot`, `GPTBot`, `CCBot`, `Anthropic`, `PerplexityBot`,
    etc.) from `/poi/` and `/activite/`. The map/panorama API hosts
    (`api-map.mappy.net`, `api-poi.mappy.net`) are **separate hosts**;
    `api-poi.mappy.net/robots.txt` → HTTP 404 (no file → permitted under the
    project's robots posture). Note that `ClaudeBot` is explicitly disallowed
    from parts of `fr.mappy.com` — any future scrape must use a descriptive
    project User-Agent (not an AI-crawler UA) and must not crawl the disallowed
    viewer paths.
  - **ToS:** Mappy's Terms of Use restrict reuse of Mappy map content; the
    panorama imagery and the `pano` API are undocumented and not part of Mappy's
    commercial API offering (which lists only Cartography, Multimodal Route,
    Suggestion, and Geocoding APIs — no panorama API). Mappy's own FAQ marks the
    panoramic-photo feature **"obsolète"**. Reverse-engineering and sweeping an
    undocumented, vendor-deprecated endpoint with a scraped web key is a weak ToS
    posture even if the data existed.
  - Observed rate limit: not reached — every probe 404'd immediately.

- **Known quirks / gotchas:**
  - **No coverage layer exists.** Unlike kakao/naver/mapy (which each turned out
    to have a real rendered overlay tile layer), Mappy's modern viewer has *no*
    panorama coverage overlay — not raster, not MVT. The base GL style contains
    no panorama source. Coverage is decided purely by the per-view point probe.
  - **The point probe returns nothing.** The single coverage endpoint
    (`pano/1.10/panoramics/…`) 404s everywhere in France, including where the
    viewer itself probes. There is no coverage to harvest.
  - **Feature is vendor-flagged "obsolète".** Mappy's support FAQ tags the
    panoramic-photo articles "obsolète / obsolete". The 360 fullscreen route
    (`/#/360-plein-ecran/:panoramicId`) still exists in the SPA router, but with
    no reachable panoramas it cannot be entered.
  - **Web API key is public but volatile.** `window.__MAPPY_API_KEY__` is in the
    page HTML; it can rotate. Any revival would need runtime re-discovery.
  - **No date layer.** Even if coverage were reachable, the panorama probe is a
    presence JSON, not a dated tile layer; a `*_year.tif` would require per-
    panorama metadata and is out of scope.

## 3. Test plan (write these FIRST — red before green)

**Not applicable while the verdict is DEFER / SKIP** — no provider module is to
be created, so there are no tests to write. This section is retained per the
template; it would only be filled if the user rejects the defer recommendation
and asks for a re-scout (see §4 / §7).

If, on a future re-scout, Mappy's `pano/1.10/panoramics/…` endpoint is found to
return real coverage, the test plan would be (offline, fixtures only):

- [ ] `test_mappy_registers` — module self-registers `"mappy"` in `PROVIDERS`.
- [ ] `test_mappy_probe_url_build` — the `coverage_json`/`json_api` probe URL
  template fills correctly for a sample `(lng, lat, radius)`.
- [ ] `test_mappy_decode_present` — a recorded HTTP-200 panorama-manifest JSON
  fixture decodes to "coverage present" at the probed point.
- [ ] `test_mappy_decode_absent` — a recorded HTTP-404 Tomcat response decodes
  to "no coverage" (checked-empty), without raising.
- [ ] `test_mappy_apikey_runtime_config` — the runtime-config helper extracts
  `__MAPPY_API_KEY__` from a recorded `plan` page HTML fixture.
- Fixtures under `tests/fixtures/mappy/`: `pano_present.json`,
  `pano_absent_404.html`, `plan_page_with_apikey.html`.

## 4. Implementation subplan (steps for the implementer — TDD)

**No implementation now — the verdict is DEFER / SKIP.** Do not create an issue,
branch, or `providers/mappy.py`.

For completeness, the *conditional* plan that would apply only if a future
re-scout finds the `pano/1.10` API returning real coverage:

- [ ] Source kind: **`coverage_json`** (existing) or `json_api` — Mappy would be
  a point-probe JSON provider, NOT a raster/MVT provider. It would sample a grid
  of lat/lng points (a discovery grid over the French city extents) and call the
  `pano/1.10/panoramics/…` probe at each, recording HTTP-200 vs HTTP-404. The
  per-point results would be rasterized onto the z14 grid (buffer isolated hits
  by ~1 cell, per PLAN §3). This is the heaviest kind of provider (one request
  per grid cell, no tile batching) and is only worth building if coverage is
  confirmed dense enough to justify the request volume.
- [ ] Foundation prerequisite: a `runtime_config/mappy_apikey.py` helper to
  re-scrape `window.__MAPPY_API_KEY__` from `https://fr.mappy.com/plan` per run
  (separate foundation PR, mirroring `runtime_config/naver_pstatic_tiles.py`).
- [ ] Pilot bbox (if revived): central Paris `2.30 48.85 2.40 48.88`.
- [ ] Pass-1 discovery: the French major-city extents only (not all of France) —
  Paris, Lyon, Marseille, Toulouse, Lille, etc. — since coverage was always
  city-centre + main-road only.

## 5. Acceptance criteria (checked by provider-verifier)

Not applicable — no provider is being built. The acceptance criterion for this
subplan is simply that the **DEFER / SKIP verdict and its evidence are reviewed
and accepted by the user**, and the inventory status for `mappy` is updated to
`deferred — no scrapable coverage layer; pano API returns no coverage; feature
vendor-flagged "obsolète"` with a re-scout trigger.

## 6. Status log

- `2026-05-22` scout: investigated Mappy. Drove the live `fr.mappy.com/plan`
  viewer in headless Chrome via the DevTools Protocol and captured all network
  traffic; fetched and enumerated the MapLibre styles
  (`full_style_web_v1.json`, `mappy_map.json`, `maplight_v2.8.json`); probed the
  `pano/1.10` panorama API directly.
  - **No panorama coverage overlay exists** — neither a `{z}/{x}/{y}` raster
    tile layer nor a coverage MVT layer. The GL style has only basemap, aerial
    `photo` (IGN), traffic, bicycle, transport, hillshade and copyright sources.
  - The viewer decides "panorama here?" via a per-view point probe:
    `GET api-poi.mappy.net/data/pano/1.10/panoramics/{lng},{lat},100/tiles/
    geodetic/{lng},{lat}.json?preview=false` (`apikey` header).
  - **That probe returns HTTP 404 for every coordinate tested**, including the
    exact URL the live viewer issued, across central Paris and 7 other major
    French cities, at radii 100 m–2000 m. The viewer's own coverage probe finds
    nothing in the densest part of France.
  - Mappy's support FAQ tags the panoramic-photo feature **"obsolète"**.
  - **Verdict: DEFER / SKIP** — there is no coverage layer to scrape and the
    only coverage API returns no data. Recommend marking `mappy` deferred in the
    inventory with a periodic re-scout trigger, and not spending a provider PR
    on it now.
- `2026-05-22` approval: **pending** — user to confirm the DEFER / SKIP verdict.

---

### Open questions for the reviewer

1. **Accept DEFER / SKIP?** Scouting found no scrapable coverage layer and an
   `obsolète`-flagged feature whose only API returns 404 everywhere. Recommend
   marking `mappy` deferred (not "confirmed dead" — the `pano/1.10` service host
   still responds, so the dataset *could* return). Confirm this verdict, or ask
   for a deeper re-scout.
2. **Re-scout trigger.** Suggested: re-check the `pano/1.10/panoramics/…` probe
   over central Paris once per phase; if it ever returns HTTP 200 with panorama
   manifests, revisit this subplan as a `coverage_json` point-probe provider
   (§4). Confirm a phase-boundary re-check is enough, or set a different cadence.
3. **Point-probe provider appetite.** Even if Mappy coverage returns, it would
   be a request-per-grid-cell `coverage_json` provider (no tile batching) — the
   most expensive provider shape in the project. Confirm whether a revived
   Mappy would be worth that cost, or should stay skipped regardless.

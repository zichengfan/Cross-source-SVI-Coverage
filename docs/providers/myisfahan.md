# [T3] Provider: Isfahan Shahrnama / myIsfahan (`myisfahan`) — RECOMMEND DEFER (blocked + unverifiable)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER — blocked + unverifiable. A first-party
municipal street-level panorama service for Isfahan DOES exist — the Isfahan
Municipality "Shahrnama" (شهرنما, "city view") panorama viewer at
`http://pano.isfahan.ir/shahrnama/` — so this is NOT a "no product" drop like
tuttocitta/eniro. BUT it cannot be implemented from our infra right now for two
independent, compounding reasons:

  1. IP BLOCK (like ja360). Every `*.isfahan.ir` host — apex `isfahan.ir`
     (188.191.176.172), the GIS map `map.isfahan.ir` (.70), the citizen portal
     `my.isfahan.ir` (.109), and the panorama host `pano.isfahan.ir` (.127) —
     resolves in DNS but TCP-times-out / is filtered on both :80 and :443 from
     the project's scraping host. This is a geo / IP-reputation block at the
     Isfahan municipal network (188.191.176.0/24, an Iranian ISP block), not an
     auth or path problem. We could not fetch a single live byte; all evidence
     below is from the Wayback Machine.

  2. UNVERIFIABLE COVERAGE WIRE FORMAT. Shahrnama is a legacy ~2015 viewer built
     on the proprietary "Safa Panorama" platform (Safa.Panorama v2.0.19, a
     Silverlight/Flash/WebGL panorama stack). Its coverage/find-nearest logic
     lives in two AJAX-loaded provider modules — `safa.map.ol.min.js` and
     `safa.pano.webgl.min.js`/`safa.pano.flash.min.js` — that the Wayback
     Machine NEVER captured (they are loaded by `$.ajax(...)` and contain no
     crawlable hyperlinks). The two backend services they call,
     `http://pano.isfahan.ir/GisProxy/PanoService/` and
     `http://pano.isfahan.ir/PanoServer2/`, were likewise never archived. So
     while the service URLs, the architecture, the projection and the capture
     vintage are all known (see §2), the exact coverage request/response wire
     format — the one thing needed to write a decoder and a presence rule — is
     NOT observable without live access from an Iran-accepting egress.

This subplan documents the full investigation and specs the provider as
completely as the evidence allows (a `coverage_json` point-probe sampler,
mirroring `dprk360`), so it can be promoted the moment an Iran egress is
available. No issue/branch/code should be created now.
-->

## 1. Summary

`myisfahan` is the street-level panorama service operated by the **Municipality
of Isfahan** (شهرداری اصفهان), Iran. The inventory lists it as a T3 candidate
("myIsfahan — Isfahan municipality service; Custom scraper if reachable"). The
"myIsfahan / اصفهان من" brand on the open web (Instagram `@myisfahan_com`, a
`myisfahan.com` domain that has since lapsed into a parked click-tracker, and a
citizen e-services portal at `my.isfahan.ir`) is **not** the panorama product.
The actual first-party street-level panorama viewer is the municipality's
**"Shahrnama"** (شهرنما, literally "city-view/cityscape") application at
`http://pano.isfahan.ir/shahrnama/` — a click-a-point-on-the-map → open-the-
nearest-360°-panorama viewer covering the city of Isfahan, captured in the
Persian year **1394 (≈ 2015/2016)** and labelled `© isfahan Municipality`. It is
a genuine first-party municipal SVI source (not a re-hoster, not paid-B2B), so
it is in scope on paper as a **Tier-3** provider confined to one city.

**However, scouting concludes `myisfahan` should be DEFERRED for now.** Two
independent blockers compound: (1) every `*.isfahan.ir` host is **IP-filtered
from our scraping infra** (DNS resolves; TCP to :80/:443 times out — an
Iran-network geo/reputation block, exactly the ja360 failure mode but harder:
silent drop, not 403), so not one live byte could be fetched; and (2) the
viewer's coverage/find-nearest backend (`/GisProxy/PanoService/`, `/PanoServer2/`)
and the JS that drives it (`safa.map.ol.min.js`, `safa.pano.webgl.min.js`) were
**never captured by the Wayback Machine**, so the exact coverage request/response
**wire format is unverifiable** without live access. The architecture, service
URLs, projection and capture vintage are all recovered below; only the live
endpoint contract and the live tiles are out of reach. See §2 for evidence and
§7 for the recommendation and the conditions to revive.

## 2. Research findings (filled by provider-scout)

### Verdict: real first-party panorama service exists, but IP-blocked from our infra AND its coverage wire format is unobservable from archives → DEFER

Applying the kakao/naver/mapy/ja360 scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.** The
   `pano.isfahan.ir/shahrnama` viewer draws its 2D locator map with an
   **OpenLayers** provider (`Safa.Maps.OpenLayersProvider`) and a basemap, not a
   `{z}/{x}/{y}` panorama-coverage PNG overlay.
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.** No MVT / `.pbf`
   tileset anywhere in the recovered assets; the stack predates MVT.
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / sampler)? —
   YES, in principle.** The viewer is a classic *click → find nearest panorama*
   model: clicking the OpenLayers map fires `changePano(lng, lat)`, which the
   loaded pano provider resolves against the **`GisProxy/PanoService/`** backend.
   That is a point-probe / nearest-pano service in the same family as
   `dprk360` / Apple's `coverage_json`. **But its exact request/response shape
   was never archived** (see "What could NOT be recovered"), so the decoder and
   presence rule below are a *spec to confirm live*, not an observed contract.

- **Homepage / public viewer URL:**
  - **Panorama viewer (the in-scope product):** `http://pano.isfahan.ir/shahrnama/`
    (HTTP only in the archived captures; the host is `pano.isfahan.ir` →
    `188.191.176.127`). The root `http://pano.isfahan.ir/` 301-redirects to
    `/shahrnama`. Page `<title>` is empty; the app shell references "Shahrnama"
    and `logo-isfahan.jpg`.
  - **Sibling municipal sites (NOT the panorama product, documented to prevent
    a future scout chasing the wrong host):**
    - `http://map.isfahan.ir/` (→ `188.191.176.70`) — the Isfahan city **2D GIS
      map portal** (ASP.NET MVC; districts `home/portal?district_no=1..15` +
      `nazhvan`; `Map/...`; GeoServer **WMS** layers `saee_spatial...`,
      satellite/hybrid/overview; OpenLayers 2; projections **EPSG:32639**
      (UTM 39N, Isfahan's local CRS), **EPSG:900913/3857**, **EPSG:4326**). It
      has **no panorama / 360 / street-view layer** (a full keyword scan of its
      97 kB `MapScriptMVC.js` found only OpenLayers/WMS layer machinery; the two
      "360"/"tour" substrings were incidental). It is a POI/parcels map, out of
      scope for SVI.
    - `http://my.isfahan.ir/` (→ `188.191.176.109`) — the **"myIsfahan / اصفهان
      من" citizen e-services portal** (ASP.NET WebForms; `Home/Services`,
      `Request/Add/{id}`, `Home/ServicesInZone/{zone}`, `Account/Login`). A
      municipal service-request system; **no imagery / panorama layer**. The
      inventory's "myIsfahan" label most likely points here, but the panorama
      product is Shahrnama on `pano.isfahan.ir`.
    - `myisfahan.com` / `www.myisfahan.com` — **lapsed**: now 200-redirects to a
      `netun-oum.com` click-tracker (parked domain, IP `52.44.60.217`). Not
      municipal, ignore.
  - **Tier:** **T3** ("likely / unverified / gated") per `docs/PLAN.md` §2 —
    confirmed first-party but unverifiable live.

- **How the service was identified.** Direct fetches of every `*.isfahan.ir`
  host **TCP-time-out from the project host** (see robots/ToS below), so all
  evidence is from the **Internet Archive Wayback Machine**. The CDX index for
  `pano.isfahan.ir*` reveals the `shahrnama` app and its `Safa.*` script suite.
  The decisive file is the app config
  `http://pano.isfahan.ir/shahrnama/Scripts/safa.config.js` (captured
  2019-12-22 and again 2021-12-31), which sets, verbatim:
  ```js
  Safa.Panorama.GisProxyService = 'http://pano.isfahan.ir/GisProxy/PanoService/';
  Safa.Panorama.PanoServer      = 'http://pano.isfahan.ir/PanoServer2/';
  Safa.Panorama.copyrightText   = '© isfahan Municipality';
  Safa.Panorama.panoLayerSets   = { '1394': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15] };
  Safa.Panorama.panoLayerSet    = '1394';
  Safa.Panorama.silverProvider  = 'SpinningGlobe2';   // Silverlight .xap fallback
  Safa.Maps.defaultLocation.longitude = 51.66;        // Isfahan, WGS84
  Safa.Maps.defaultLocation.latitude  = 32.65;
  ```
  The bootstrap `program.min.js` confirms the interaction model: it builds a
  `Safa.Maps.Map` with a provider chosen by `?map=` (`safa` → OpenLayers via
  `safa.map.ol.min.js`, or `google`/`bing`); on a map `"selection"` it
  instantiates `Safa.Panorama.Pano(...)` and calls
  `panoInstance.changePano(lng, lat)` — i.e. **resolve the nearest panorama to a
  clicked WGS84 lng/lat**. `safa.pano.min.js` (the loader, v2.0.19) then loads
  the rendering provider by `?pano=` (`webgl` → `safa.pano.webgl.min.js`,
  `flash` → `safa.pano.flash.min.js`, `sl` → Silverlight). The Persian UI string
  in `safa.pano.min.js` — "شهرنما توسط این مرورگر پشتیبانی نمی گردد." ("Shahrnama
  is not supported by this browser") — confirms the product name is **Shahrnama**.

- **Coverage endpoint(s):**
  - **Find-nearest / coverage backend:**
    `http://pano.isfahan.ir/GisProxy/PanoService/` — the "GisProxy" service the
    pano provider queries to turn a clicked `(lng, lat)` into the nearest
    panorama (and, candidate, to list panoramas within an extent). **This is the
    coverage-bearing endpoint.** Its exact path suffix (a method like
    `…/GetNearestPano`, `…/Find`, or a REST/`.svc`/`.asmx` operation), HTTP
    method, params and response body **could not be observed** (the calling JS
    was never archived; see below). Almost certainly returns **JSON** (the
    `GisProxy` proxies a GIS query service), keyed on panorama id + WGS84
    lng/lat + heading. **TO BE CONFIRMED LIVE.**
  - **Panorama-imagery server (NOT used by this provider):**
    `http://pano.isfahan.ir/PanoServer2/` — serves the actual 360° image cube
    faces / tiles for a given panorama id. We store **coverage only**, never
    imagery, so this is out of scope except as a cross-check that a pano id is
    real.
  - **HTTP method / headers / query params:** unobservable from archives. The
    scheme is plain HTTP (no HTTPS in any capture); no auth header is set
    anywhere in the recovered JS. **TO BE CONFIRMED LIVE.**

- **Coordinate scheme:** **`web_mercator`** for the locator-map tile grid (the
  default `?map=safa` provider is OpenLayers; the sibling `map.isfahan.ir`
  explicitly uses EPSG:900913/3857). **The find-nearest service speaks WGS84
  lng/lat** — `changePano(lng, lat)`, `Safa.Maps.defaultLocation.longitude/
  latitude = 51.66 / 32.65`, and the `wkt` handler parses `POINT(lng lat)` in
  decimal degrees. So a sampler would tile the city in `web_mercator`, convert
  each probe-point tile centre to WGS84 lng/lat, and call `GisProxyService`.
  (Isfahan's GIS authoritative CRS is **EPSG:32639 / UTM 39N**, seen in the map
  portal; the panorama service's public surface is WGS84, so no custom scheme is
  needed.) **No new `coordinate_scheme`; `geo.py`'s `web_mercator` branch
  suffices.** — TO BE CONFIRMED that the GisProxy I/O is WGS84 and not UTM 39N.

- **Zoom range / tile size / response format:**
  - The `panoLayerSets['1394'] = [1..15]` array is the **set of 15 zoom/tile
    levels of each panorama image** (Safa's image pyramid), **not** a coverage
    grid — it is irrelevant to coverage. There is one capture vintage: **1394**
    (Persian calendar ≈ March 2015 – March 2016).
  - **Coverage response format:** expected **JSON** from `GisProxyService` (so
    `kind="coverage_json"`); not tiles. Unobserved — TO BE CONFIRMED LIVE.
  - For the locator basemap (irrelevant to coverage) the tiles are standard
    256-px web-mercator OpenLayers tiles.

- **Auth:** **none observed.** No token, cookie, API key or signed URL appears
  in `safa.config.js`, `program.min.js`, `safa.pano.min.js` or `safa.map.min.js`.
  The viewer is a public, anonymous municipal page. **No `.env` key anticipated.**
  If a live probe reveals a session/anti-forgery token on `GisProxyService`,
  record it and add a `.env` key `MYISFAHAN_*` then. — TO BE CONFIRMED LIVE.

- **Presence rule (PROPOSED — confirm live):** "Isfahan panorama imagery exists
  here" = a `GisProxyService` find-nearest probe at the tile-centre WGS84
  `(lng, lat)` returns **≥ 1 panorama whose distance to the probe point is below
  a threshold** (e.g. ≤ the grid cell half-diagonal, or Safa's own 15 m
  `showDistanceWarning` heuristic — `checkDistance` warns when the nearest pano
  is > 15 m from the click). A probe that returns no pano, or a nearest pano
  beyond the threshold, ⇒ checked-empty. This mirrors the `dprk360`
  `coverage_json` sampler. The decoded pano points (id, lng, lat, heading,
  vintage `1394`) are written to `data/intermediate/myisfahan/` and burned onto
  the z14 grid. **The exact JSON keys are unverified** — implement the decoder
  against the first live response. (`source_kinds/coverage_json.py` currently
  reads `panos[].{panoid,lat,lon,timestamp,...}`; the GisProxy keys will differ
  and the decoder must be adapted — likely a thin `myisfahan`-specific decode.)

- **robots.txt / ToS notes; observed rate limit:**
  - **BLOCKER — IP block / unreachable from our infra.** All `*.isfahan.ir`
    hosts resolve in DNS but **TCP-time-out on :80 and :443** from the project's
    scraping host:
    - `isfahan.ir` → `188.191.176.172` — :443 filtered, :80 filtered
    - `www.isfahan.ir` → `188.191.176.172`
    - `map.isfahan.ir` → `188.191.176.70`
    - `my.isfahan.ir` → `188.191.176.109`
    - `pano.isfahan.ir` → `188.191.176.127` — :443 filtered, :80 filtered
    The block is at the network edge of the Isfahan municipal range
    (`188.191.176.0/24`, an Iranian ISP allocation) — a **silent drop**, harder
    than ja360's `awselb` 403. This is an IP/geo block, **not** an auth or
    endpoint error: the URLs, scheme and architecture are confirmed from the
    archived `safa.config.js`. The implementer **must run any probe and record
    the §3 fixtures from an Iran-based or Iran-accepting egress** (Iranian VPN /
    residential / proxy). See §7 open questions.
  - **robots.txt:** `http://pano.isfahan.ir/robots.txt` returned **HTTP 404** in
    the 2017 Wayback capture (no robots file) — under the project's
    `polite.robots_allows`, a non-200 robots.txt is treated as **allowed**.
    `map.isfahan.ir/robots.txt` likewise 404. Re-fetch from an accepted IP at
    implementation time and record the live rule in §6.
  - **ToS:** the panorama tiles carry `© isfahan Municipality`. No public
    developer API or scraping policy is documented. The site is a public,
    auth-free Iranian municipal service. **Treat as polite-scrape default**
    (descriptive UA, low concurrency, hard throttle) AND flag the broader
    consideration that this is an **Iranian government site** — confirm there is
    no sanctions/access policy concern for the project before scraping (see §7).
    Record the `© isfahan Municipality` attribution and the ToS posture in the
    module docstring and the STAC `tos_notes`.
  - **Observed rate limit:** unknown — could not probe. Be conservative
    (≈ 1 req/s, single connection, backoff on 5xx, **stop on a sustained
    timeout/connection-refused streak** since that signals the IP block, not
    emptiness). Record the real limit once a live probe runs.

- **Known quirks / gotchas:**
  - **IP block from non-Iran infra** (above) — the single biggest blocker; the
    live probe and fixture recording cannot be done from the project's host.
  - **What could NOT be recovered (the second, independent blocker).** The
    Wayback Machine archived only the static shell of `shahrnama` — the page,
    the `Safa.*` *loader* scripts (`safa.config.js`, `program.min.js`,
    `safa.pano.min.js`, `safa.map.min.js`, `safa.math/utils.min.js`), CSS and
    images. It did **NOT** archive (a) the AJAX-loaded provider modules
    `safa.map.ol.min.js`, `safa.pano.webgl.min.js`, `safa.pano.flash.min.js`,
    `safa.pano.sl.min.js` — they are pulled by `$.ajax(..., {dataType:'script'})`
    and have no crawlable links; nor (b) **any** `GisProxy/PanoService/` or
    `PanoServer2/` response. Therefore the exact coverage request/response
    contract is **unknown**; §3/§4 below are a spec to confirm against the first
    live response, not an observed format.
  - **Legacy Silverlight/Flash stack.** Safa Panorama v2.0.19 prefers WebGL but
    falls back to **Flash** and **Silverlight** (`.xap`, `SpinningGlobe2`). Flash
    and Silverlight are dead in modern browsers — the *imagery* viewer may be
    broken even where reachable. This does NOT affect coverage scraping (we only
    query `GisProxyService` for pano *locations*), but it means the product may
    be effectively abandoned (see "stale data" and §7).
  - **Single, stale vintage.** Only one capture set exists: **1394 (≈ 2015)**.
    No date layer to model; if revived, store vintage as a constant `2015`
    (Gregorian approximation of Persian 1394) on every covered cell. A decade-old
    single-pass capture has low marginal value for the coverage DB — weigh this
    in the keep/drop decision.
  - **Point-probe sampler, not a tile layer.** Coverage must be *discovered* by
    sampling a grid of WGS84 points over the city and asking GisProxy for the
    nearest pano at each — there is no extent/coverage layer to read directly
    (unless a live probe reveals a bbox-list operation, which would be cheaper —
    confirm). Mirror `dprk360`'s `coverage_json` sampler shape.
  - **Three sibling hosts, only one is the SVI product.** `pano.isfahan.ir`
    (Shahrnama panorama) is the in-scope host; `map.isfahan.ir` (2D GIS) and
    `my.isfahan.ir` (e-services) are not. Don't be misled by the "myIsfahan"
    inventory label pointing at `my.isfahan.ir`.
  - **Iranian-government-site policy.** Beyond robots/ToS, confirm there is no
    organizational policy concern about scraping an Iranian municipal government
    host before proceeding (§7).

## 3. Test plan (write these FIRST — red before green)

**Not applicable while the verdict stands.** No tests, fixtures, or provider
module should be written until §7's revival conditions are met (an Iran-accepting
egress yields at least one real `GisProxyService` response to pin the wire
format, and the policy question is cleared). The plan below is the **conditional**
plan that would apply once a live coverage response is captured. It mirrors the
`dprk360` / `coverage_json` sampler tests and is **offline** (decode recorded
JSON fixtures; never hit the network — `docs/PLAN.md` §12).

Fixtures under `tests/fixtures/myisfahan/` (recorded ONCE from an Iran-accepting
egress, raw bytes):
- `panoservice_present.json` — a real `GisProxyService` find-nearest response at
  a Naqsh-e Jahan Square probe point that returns ≥ 1 nearby panorama.
- `panoservice_empty.json` — a real response at a probe point outside coverage
  (or returning a nearest pano beyond the distance threshold) ⇒ checked-empty.

Tests (`tests/test_providers_myisfahan.py`):

- [ ] *(conditional)* `test_myisfahan_registers` — importing
      `coverage_acquisition.providers` auto-registers `myisfahan` in `PROVIDERS`;
      `get_provider("myisfahan")` returns a `ProviderDefinition` with
      `key == "myisfahan"` and exactly one `SourceDefinition` whose
      `kind == "coverage_json"`.
- [ ] *(conditional)* `test_myisfahan_provider_shape` —
      `coordinate_scheme == "web_mercator"`; `default_display_zoom == 14`; no
      token/cookie/auth fields (unless a live probe reveals one); `area_presets`
      contains the Naqsh-e Jahan pilot bbox.
- [ ] *(conditional)* `test_myisfahan_probe_url_build` — the source `template`
      builds the correct `GisProxyService` find-nearest URL for a sample
      tile-centre `(lng, lat)` once the live operation path/params are known.
- [ ] *(conditional)* `test_myisfahan_decode_present` — decoding
      `panoservice_present.json` yields a `DecodeResult` with `pano_count > 0`
      and pano records carrying `(panoid, lon, lat)` in plausible Isfahan ranges
      (lng ≈ 51.5–51.8, lat ≈ 32.5–32.8) and vintage 1394/2015.
- [ ] *(conditional)* `test_myisfahan_decode_empty` — decoding
      `panoservice_empty.json` yields `pano_count == 0` (checked-empty), not an
      error.
- [ ] *(conditional)* `test_myisfahan_distance_threshold` — the presence rule
      treats a nearest pano beyond the cell threshold as checked-empty (guards
      against the GisProxy always returning *some* far-away pano).
- [ ] *(conditional)* Fixtures recorded from an Iran-accepting egress under
      `tests/fixtures/myisfahan/`.

## 4. Implementation subplan (steps for the implementer — TDD)

**Do not implement.** This subplan is a deferred recommendation. The implementer
should **not** create a branch, an issue, or
`src/coverage_acquisition/providers/myisfahan.py` until §7's revival conditions
are met. The conditional plan below applies only once a live `GisProxyService`
response has been captured and the wire format pinned.

- [ ] *(conditional)* **Source kind:** **`coverage_json`** — existing kind
      (`source_kinds/coverage_json.py`), the same family as `dprk360` /
      `apple_lookaround`. **No new source kind and no foundation PR** are needed
      *if* the GisProxy returns JSON pano listings as expected. The
      `coverage_json` decoder currently reads `panos[].{panoid,lat,lon,...}`;
      adapt it (or add a thin `myisfahan` decode) to the real GisProxy keys once
      observed. If — and only if — a live probe shows the service is genuinely
      novel (e.g. a SOAP/`.asmx` envelope or UTM-39N geometry that doesn't fit
      `coverage_json`), that adapter is a **separate foundation PR first**.
- [ ] *(conditional)* Re-run the §2 probe from an Iran-accepting egress to
      capture the real `GisProxyService` operation, params and JSON; fill §3 with
      concrete URL/keys; record fixtures.
- [ ] *(conditional)* Write the §3 tests first; confirm they fail (red).
- [ ] *(conditional)* Add `src/coverage_acquisition/providers/myisfahan.py`
      (`ProviderDefinition` named `PROVIDER`, calling `register_provider`),
      mirroring `dprk360.py`: `key="myisfahan"`,
      `output_namespace="myisfahan_coverage"`, `default_display_zoom=14`,
      `coordinate_scheme="web_mercator"`; one `SourceDefinition`
      `kind="coverage_json"` pointing at the GisProxy find-nearest operation;
      `area_presets` declared inline (Naqsh-e Jahan pilot below). Route all HTTP
      through `polite.polite_fetch` (descriptive UA, per-host throttle, backoff).
      Module docstring records: Shahrnama / `© isfahan Municipality`; IP-block
      caveat; legacy Safa/Silverlight stack; single 1394/≈2015 vintage; the
      Iranian-gov-site policy note.
- [ ] *(conditional)* Implement until §3 tests pass (green); refactor.
- [ ] *(conditional)* **Pilot probe:** bbox `51.670 32.654 51.685 32.662`
      (**Naqsh-e Jahan / Imam Square**, Isfahan's central UNESCO core — the
      highest-probability dense-coverage area). Sample a fine point grid inside
      it, query GisProxy per point, keep points with a nearby pano. Confirm the
      empty-vs-present signature and the distance threshold here; record in §6.
- [ ] *(conditional)* Rasterize the pilot area to a z14 COG (EPSG:3857, `uint8`,
      1=covered / 0=checked-empty / 255=nodata); sanity-check that covered cells
      land on Isfahan streets/the square, not desert.
- [ ] *(conditional)* **Two-pass full extent:** pass-1 coarse point-grid sweep
      over the city of Isfahan — region bbox `51.55 32.55 51.80 32.78` (Isfahan
      municipal area) at a coarse probe spacing; pass-2 densifies the grid only
      where pass-1 found panos. Decode pano points → `data/intermediate/myisfahan/`
      → z14 COG. Stamp vintage `2015`. Run detached in `tmux`.
- [ ] *(conditional)* Update / create the STAC item (`tier="T3"`, extent = the
      discovered Isfahan envelope, vintage 2015,
      `source_endpoint="http://pano.isfahan.ir/GisProxy/PanoService/"`,
      `tos_notes` per §2). Update the inventory status for `myisfahan`.

## 5. Acceptance criteria (checked by provider-verifier)

**Not applicable** while deferred. If §7's revival conditions are met, the
standard criteria apply: all §3 tests pass; `coverage_acquisition.providers.
myisfahan` imports and self-registers; CI smoke passes; the single source is
`kind="coverage_json"`, `coordinate_scheme="web_mercator"`, no auth (unless a
live probe required one); pilot probes fetch (from an Iran-accepting egress) and
decode; covered cells land on Isfahan streets/land (not desert), within the
Isfahan bbox; the z14 COG is valid (`rio_cogeo.cog_validate`), CRS EPSG:3857,
`uint8`, covered pixels > 0; all fetching goes through `polite.polite_fetch`
with a descriptive User-Agent and conservative throttle; the `© isfahan
Municipality` attribution, IP-block, legacy-stack, 2015-vintage and
Iranian-gov-site caveats are documented in the module docstring and STAC
`tos_notes`.

## 6. Status log

- `2026-05-28` scout: drafted. Verdict: **DEFER — blocked + unverifiable.**
  A real first-party municipal SVI service exists: the Isfahan Municipality
  **"Shahrnama"** panorama viewer at `http://pano.isfahan.ir/shahrnama/`, built
  on the proprietary **Safa Panorama v2.0.19** stack, capture vintage **1394
  (≈2015)**, `© isfahan Municipality`. The coverage backend is
  `http://pano.isfahan.ir/GisProxy/PanoService/` (find-nearest, point-probe,
  WGS84 lng/lat — a `coverage_json`-family sampler like `dprk360`); the imagery
  server is `http://pano.isfahan.ir/PanoServer2/`. **Two compounding blockers:**
  (1) every `*.isfahan.ir` host (`isfahan.ir` 188.191.176.172, `map.` .70,
  `my.` .109, `pano.` .127, in the Iranian block 188.191.176.0/24) **resolves in
  DNS but TCP-times-out on :80/:443 from our infra** — a silent geo/IP block,
  the ja360 failure mode but harder; (2) the AJAX-loaded provider JS
  (`safa.map.ol.min.js`, `safa.pano.webgl/flash/sl.min.js`) and every
  `GisProxy`/`PanoServer2` response were **never archived** by the Wayback
  Machine, so the exact coverage **wire format is unobservable** without live
  access. Evidence: Wayback CDX for `pano.isfahan.ir*`; the archived
  `safa.config.js` (2019-12-22 & 2021-12-31), `program.min.js`,
  `safa.pano.min.js`, `safa.map.min.js`; the `map.isfahan.ir` `MapScriptMVC.js`
  (2017, confirmed WMS/OpenLayers POI map with no panorama layer); DNS + TCP
  probes from the project host. Sibling hosts ruled out: `map.isfahan.ir` (2D
  GIS, no pano), `my.isfahan.ir` ("myIsfahan/اصفهان من" citizen e-services, no
  pano), `myisfahan.com` (lapsed → parked click-tracker).
- `2026-05-28` approval: **pending user decision.**

## 7. Recommendation and revival conditions

**Recommendation:** **DEFER** `myisfahan` for Phase 3. Unlike a clean drop, the
product is **real and first-party** (Isfahan Municipality "Shahrnama"), so it
should be kept on the watch-list rather than removed outright. But it cannot be
built from the project's infra today: the host is **IP-blocked from non-Iran
networks**, and even the archive does not reveal the **coverage wire format**
needed to write a decoder. On top of that the data is a **single ~2015 vintage**
on a **dead Silverlight/Flash stack**, so its marginal value to the global
coverage DB is modest and possibly decaying.

**Re-open / promote this subplan to an active scout only when all of these hold:**

1. **An Iran-accepting egress is available** (Iran-based, residential, or a
   commercial VPN/proxy that `pano.isfahan.ir` answers) for both the live probe
   that pins the wire format AND for the production scrape + CI verification.
   Without it, neither fixtures nor pilot can be produced.
2. **A live `GisProxyService` response is captured** — confirming the operation
   path/params, that it returns JSON (so `kind="coverage_json"` fits), the geometry
   CRS (WGS84 vs UTM-39N), the presence/empty signature, and any session/CSRF
   token. This is the gate that turns §3/§4 from "spec" into "observed".
3. **The Iranian-government-site policy question is cleared** — confirm with the
   user/maintainers that scraping an Iranian municipal government host raises no
   sanctions/organizational concern, and that the resulting coverage layer is
   wanted given its single ≈2015 vintage.
4. **The service is still live** when revived (check `pano.isfahan.ir/shahrnama`
   responds from the egress; the GisProxy still answers find-nearest). If the
   Silverlight/Flash product has been fully retired with no working coverage
   backend, drop instead.

If those are met, fill §3/§4/§5 with the observed endpoint contract and proceed
via the standard `add-provider` → `tdd` flow, mirroring `dprk360`.

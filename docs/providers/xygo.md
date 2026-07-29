# [T3] Provider: XYGO Street View (`xygo`) — RECOMMEND DEFER / SKIP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-25): DEFER / SKIP. XYGO's public Street View viewer is
a 2011/2013-era OpenLayers page that depends entirely on `mapas.neonline.cl`,
`t0.neonline.cl` and `ws.mapas.neonline.cl` for its mapping library, tile CDN,
and the JSON coverage API (`carga_servicios_fast2.php?catego=streetview`),
plus a KRPANO panorama host at `204.236.231.44`. Every one of those backends
is dead today — the `*.neonline.cl` subdomains are NXDOMAIN and the KRPANO
host refuses TCP. Wayback last saw `mapas.neonline.cl` alive in 2019-08 and
`ws.mapas.neonline.cl` in 2019-05 (already 403). The viewer HTML still loads
at `http://mapas.xygo.cl/`, but no scripts load and no API call returns
anything — there is no scrapable coverage signal. XYGO the company is alive
(Esri Gold Partner) but has pivoted to GIS consulting; the public Street View
product is gone. There is no second, modern viewer to scrape. This subplan
documents the full investigation so the provider can be revived *if and only
if* XYGO ever republishes a public coverage layer. No issue/branch/code
should be created now.
-->

## 1. Summary

XYGO (Mapas Digitales S.A., Santiago de Chile; formerly Dmapas, est. 1993) is
a Chilean digital cartography / GIS / address-database company. In 2009 they
began capturing 360° panoramic street-level imagery from a roof-mounted
camera car at ~50 m spacing across Chile, and in April 2011 launched
**XYGO Street View** as a free public viewer — initially Arica, Iquique,
Santiago, Viña del Mar, Valparaíso, Rancagua, Talca and Temuco, eventually
covering 240 of Chile's ~350 communes. The product was advertised as the
first first-party street-view product in Chile / LATAM and was hosted both on
XYGO's own `mapas.xygo.cl` and embedded into El Mercurio Online's
`mapas.emol.com`. XYGO is in scope by region (South American street-view
providers are rare in the inventory) and is a first-party SVI provider, not
a re-hoster — which is why it is flagged as a T3 candidate.

**However, scouting concludes XYGO Street View should be DEFERRED / SKIPPED
for now.** The original viewer is still online at `http://mapas.xygo.cl/` (and
its mirror `http://mapas.emol.com/`), but its **entire backend infrastructure
is dead**: the OpenLayers library is loaded from `t0.neonline.cl`, the map JS
helpers from `mapas.neonline.cl`, and the only coverage endpoint is a JSON-P
call to `ws.mapas.neonline.cl/carga_servicios_fast2.php?catego=streetview` —
all three hosts are NXDOMAIN today. The panorama viewer host
(`204.236.231.44/KRPANO/dmapas/imagenes.php`) refuses TCP. There is no
"new XYGO viewer" — the only other live XYGO subdomain (`streetview.xygo.cl`)
turns out to be an unrelated Vue.js **subscription/login admin app for
`mediosregionales.cl`**, not a panorama viewer. XYGO the company has pivoted
to being an Esri Gold Partner doing GIS consulting (Utility Network, ArcGIS
Portal) and no longer publishes a public street-view viewer. There is no
scrapable coverage layer to harvest. See §2 for full evidence and §7 for
the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: no scrapable coverage layer — DEFER / SKIP

Applying the kakao/naver/mapy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO** (no
   tile layer is reachable; the only tile CDN referenced, `t0.neonline.cl`,
   is NXDOMAIN).
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO** (the viewer
   uses 2011-era OpenLayers 2.x; no MVT involved).
3. **Coverage JSON API (`kind="coverage_json"` / `json_api`)? — A JSON-P-style
   endpoint exists in the page source
   (`ws.mapas.neonline.cl/carga_servicios_fast2.php?catego=streetview&...`),
   but its host is NXDOMAIN and has been unreachable since at least 2019-05.**

### Live infrastructure probe (2026-05-25)

DNS resolution for XYGO-related hosts:

| Host | Status | Notes |
|---|---|---|
| `xygo.cl` (apex) | NXDOMAIN | no A record |
| `www.xygo.cl` | `18.229.242.145` | AWS sa-east-1; **HTTPS not served** (TCP 443 refused), HTTP returns Apache static portal |
| `xygo.com` (apex) | NXDOMAIN | |
| `www.xygo.com` | `54.207.29.219` (AWS sa-east-1 ELB `stress-710169538`) | HTTP 200, static "Prontus 11.2" marketing site, last news article 2015 |
| `mapas.xygo.cl` / `mapas.xygo.com` | `200.12.26.79` | HTTP 200 — the old viewer HTML (Apache 2.2.3 / PHP 5.2.6, server header reveals an unpatched RHEL5-era host) |
| `streetview.xygo.cl` / `streetview.xygo.com` | `200.12.26.80` | HTTPS 200 — **NOT a street-view viewer**; the SPA bundle is a Vue.js login/admin app for `mediosregionales.cl` (`https://vma.mediosregionales.cl/`) with routes `/login`, `/suscripciones`, `/beneficiarios`, `/empresas` etc. No panorama or map code. |
| `mapa.xygo.com` | `200.12.26.116` | HTTPS 200 — an unrelated `universo.cl` content page (a different El Mercurio brand). |
| `maps.xygo.cl` / `maps.xygo.com` | resolves but 301-redirects to `http://www.pabellon.cl/` (also unrelated). |
| `mapas.neonline.cl` | **NXDOMAIN** | the JS helper host |
| `t0.neonline.cl` … `t3.neonline.cl` | **NXDOMAIN** | the tile CDN |
| `ws.mapas.neonline.cl` | **NXDOMAIN** | the streetview coverage JSON API |
| `204.236.231.44` | TCP 80 **connection refused** | the legacy KRPANO panorama host |
| `neonline.cl` (apex) | resolves to `200.14.114.41`, but has no street-view subdomain; `www.neonline.cl` is a generic page |

So the viewer HTML loads, but every script source and every API target inside
it is unreachable.

### The old viewer (`http://mapas.xygo.cl/` and its `mapas.emol.com` mirror)

- **Homepage / public viewer URL.** `http://mapas.xygo.cl/` (HTTPS is **not
  served** — `Connection refused` on port 443; the entire 2011 viewer is HTTP-
  only). A perfect mirror lives at `http://mapas.emol.com/` (El Mercurio
  Online), which uses the identical code base and the identical NEONLINE
  backend; everything written below about endpoints applies equally to either
  host.
- **Tier:** T3 (likely / unverified / gated — confirmed gated by infra death).
- **What the page is.** A 2013-era jQuery + OpenLayers 2.x map of Chile,
  centred on Santiago (`init('map',-33.5540003,-70.6363598,...)`), with a
  bottom-right `#streetview` button (`<a id="serv_05" class="serv_05"
  href="javascript:streetviewON_OFF('serv_05');">`). The button fires
  `streetviewON_OFF(...)` defined in
  `http://mapas.neonline.cl/api_mapas/js/funciones_java_mapa_v2.js?05102012`
  (and `..._NCODE_v2.js`). The base map tiles, the streetview helper code
  and the streetview JSON API all live under `*.neonline.cl`.
- **The script sources the viewer references** (verbatim from `view-source:
  http://mapas.xygo.cl/`):
  - `http://t0.neonline.cl/openlayers/OpenLayers.js` — the OpenLayers 2.x
    bundle. **NXDOMAIN today**, so the viewer **cannot even render its base
    map** in a fresh browser session.
  - `http://mapas.neonline.cl/api_mapas/js/funciones_java_mapa_v2.js?05102012`
    — the helper that defines `init()`, `streetviewON_OFF()`,
    `loadStreetview()`, `cargaStreetview()`, `drawSegmentos()`,
    `selectLinea()`, etc. **NXDOMAIN today.** (A Wayback capture
    from 2017-11-09 is the only way to read its source.)
  - Self-hosted `js/funciones.js?21032013` etc. — local viewer glue, harmless.

### The (former) coverage API — verified from a 2017 Wayback capture

The `funciones_java_mapa_v2.js` bundle is packed with `eval(function(p,a,c,k,
e,r){…}(…,62,…))`. Unpacking it (base-62) reveals exactly how XYGO's coverage
is fetched. The relevant declarations and functions:

```js
var URL_servicioFast2 = "http://ws.mapas.neonline.cl/carga_servicios_fast2.php";
var path_link_street  = "http://204.236.231.44/KRPANO/dmapas/imagenes.php?archivoxml=";
var AM_streetview_min_zoom = 16;

function streetviewHabilitado()  { return getZoomActual() >= AM_streetview_min_zoom; }
function loadStreetview() {
  if (!streetviewHabilitado()) return false;
  ME_street_est = true;
  AM_exten   = map.getExtent();
  AM_lonI    = AM_exten.left;  AM_latI = AM_exten.bottom;
  AM_lonD    = AM_exten.right; AM_latS = AM_exten.top;
  AM_coord1  = "" + AM_latI + "," + AM_lonI + "";   // SW lat,lon
  AM_coord2  = "" + AM_latS + "," + AM_lonD + "";   // NE lat,lon
  AM_center  = map.getCenter().lat + "," + map.getCenter().lon;
  // JSONP-style: <script src="…carga_servicios_fast2.php?catego=streetview&…&tipo=5">
  var b = document.createElement("script");
  b.setAttribute("src",
    URL_servicioFast2
      + "?catego=streetview"
      + "&icono=img/mono_streetview.png"
      + "&coord1=" + AM_coord1     // "lat_min,lon_min"
      + "&coord2=" + AM_coord2     // "lat_max,lon_max"
      + "&center=" + AM_center     // "lat_centre,lon_centre"
      + "&tipo=5");
  b.setAttribute("id", "scriptTemporal");
  document.getElementsByTagName("body")[0].appendChild(b);
}

function cargaStreetview(a, b, c, d, e, f, g, h, i, j) {
  // JSONP callback the server invokes. Argument `i` is a "|"-joined list of
  // segment records; each record is "lat:lon:archXml" triples joined by ":".
  // The function splits `i` on "|" then on ":" and calls drawSegmentos(u, v,
  // w, map) — i.e. it draws line/point overlays at (lat=u[i], lon=v[i]) tagged
  // with archXml=w[i].
}

function selectLinea(a) {
  for (var b in a.attributes) {
    if (b == "archXml") {
      // archXml is a panorama set identifier; the panorama itself opens a
      // KRPANO HTML page:
      //   http://204.236.231.44/KRPANO/dmapas/imagenes.php?archivoxml=<archXml>
      window.open(path_link_street + a.attributes[b], "StreetView", …);
    }
  }
}
```

In other words, the (former) XYGO coverage signal was a **bbox-query JSON-P
endpoint** that returned the *segments* (lat/lon polylines, one per drivelet)
where panoramas exist, plus a per-segment KRPANO XML id. The presence rule
would have been "≥ 1 non-NULO segment in the response ⇒ coverage in this
bbox; burn the `(lat, lon)` segments into the raster". That maps cleanly onto
the project's existing **`coverage_json`** source kind. **None of this is
reachable today** — `ws.mapas.neonline.cl` is NXDOMAIN, so no probe can
verify the live response shape, no fixtures can be recorded, and no scrape
can run.

### Wayback evidence — when did it break?

CDX search for the live backends:

- `mapas.neonline.cl/` — last `text/html 200` capture **2019-08-17**;
  earlier captures 2018-03, 2019-05 were `warc/revisit`.
- `ws.mapas.neonline.cl/` — only capture **2019-05-06**, returning
  **HTTP 403** (so even in 2019 the bare host was already rejecting probes
  without the `carga_servicios_fast2.php` path).
- `ws.mapas.neonline.cl/carga_servicios_fast2.php*` — **no Wayback captures
  at all** (the API was never crawled with a usable query).
- `mapas.xygo.cl/` — Wayback has many captures of the viewer page itself
  through ~2017; the page content still references the same NEONLINE backend
  in those captures.

So the **API has been gone for ≥ 7 years** and there is no recorded JSON
fixture anywhere on the public internet for the `catego=streetview` response
shape. Any future implementation would have to *guess* the response shape
from the JS unpacker output above and validate it only if the backend ever
returns.

### Auth, robots, ToS

- **Auth.** The 2013-era API used **no auth** — plain unauthenticated JSON-P
  by URL params. No cookie, no token, no `.env` key would be needed. (Not
  re-verifiable while the API is down.)
- **robots.txt.**
  - `http://www.xygo.com/robots.txt` → returns the apex HTML (`HTTP 200` but
    it's the same redirect-to-prehome HTML, not a real robots file).
  - `https://streetview.xygo.cl/robots.txt` and `…xygo.com/robots.txt` → both
    `HTTP 404` (nginx). Note this is the unrelated subscription SPA, not the
    street-view viewer.
  - `http://mapas.xygo.cl/robots.txt` was not separately checked because the
    viewer's relevant backends are NXDOMAIN. Under the project's robots
    posture (`polite.robots_allows` treats a missing / non-200 `robots.txt`
    as **allowed**), there is no `Disallow` rule blocking this provider.
  - `http://mapas.emol.com/robots.txt` → `HTTP 200`, `User-agent: * / Allow:
    /` (no restrictions; this is the mirror host).
- **ToS.** XYGO has no published machine-readable crawl policy. The viewer
  was a free public service; this project would only store a **derived
  binary-presence coverage raster**, not XYGO panoramas. Polite scraping
  (descriptive UA, low concurrency, throttle, backoff on 429/5xx, stop on
  sustained outage) would be expected, identical to other point-API
  providers. Record this caveat in the module docstring if/when revived.
- **Observed rate limit.** Not measurable — the API is offline. (When alive
  in 2017 the viewer was advertised as free, no plan/quota documentation.)

### Why the modern `streetview.xygo.cl` is a red herring

`https://streetview.xygo.cl/` returns a Vue.js SPA (`<div id="app"></div>` +
`js/app.e7468e85.js` + `js/chunk-vendors.95d0af23.js`). Inspecting the bundle
the only external API host it talks to is `https://vma.mediosregionales.cl/`,
and its visible routes are `/login`, `/suscripciones`, `/empresas`,
`/beneficiarios`, `/contactos`, `/pendientes`, `/renovaciones`,
`/desbloquearusuario`. There is no map code (no MapLibre, no Leaflet, no
OpenLayers, no panorama widget) and no tile/coverage URL anywhere in the
bundle. This is a **subscription/admin app for an unrelated Chilean regional-
media company** that happens to be hosted on an XYGO-owned subdomain — it is
NOT the modern Street View viewer. Searching `xygo.com` / `xygo.cl`, LinkedIn,
and the Esri Partner catalog finds no other public XYGO Street View URL.

### Known quirks / gotchas (only relevant if the API is ever revived)

- **Pure HTTP, no HTTPS.** Every URL is `http://`; the relevant hosts do not
  even accept TCP on 443. A revival would still need a `verify=False` /
  `http://` posture in `polite.polite_fetch`.
- **JSONP-style API.** The endpoint is fetched as a `<script>` injection and
  the server replies by *calling* a global JS function
  (`cargaStreetview(...)`) — it does not return JSON. The `coverage_json`
  source kind would need a tiny JSONP-shim (strip a leading
  `cargaStreetview(` and trailing `);`, parse the argument list as a JS
  literal) before the response is decodable. An alternative is to treat the
  raw response as text and regex out the `|`-separated `(lat:lon:archXml)`
  triples. This is **a foundation-level decoder change**, not a per-provider
  one, and would need a separate PR before this provider could land.
- **Min zoom = 16.** The viewer only displays coverage at z ≥ 16; lower
  zooms simply return nothing. For two-pass discovery a pass-1 sweep would
  have to be done at z16+ — far denser than the project's typical low-zoom
  discovery — making this a heavier provider than its small per-city extent
  suggests.
- **bbox-bounded.** Each call needs a bbox query; coverage discovery is a
  bbox-tile sweep across Chile (≈ 240 communes). The natural unit is per-
  commune queries (the inventory says 240 communes covered).
- **Date layer.** The API returns `lat:lon:archXml` triples — no capture
  date. The KRPANO XML *may* contain a date, but the KRPANO host
  (`204.236.231.44`) is also dead. A `xygo_year.tif` date layer is **out
  of scope**.
- **Old PHP host.** Even when alive the host ran Apache 2.2.3 + PHP 5.2.6
  (server header on `mapas.xygo.cl` today) — a 2008 stack. Any revival
  should expect slow, fragile responses and a sustained-outage stop rule.

## 3. Test plan (write these FIRST — red before green)

**Not applicable while the verdict is DEFER / SKIP** — no provider module is
to be created, so there are no tests to write. This section is retained per
the template; it would only be filled if the user rejects the defer
recommendation and asks for a re-scout (see §4 / §7).

If, on a future re-scout, `ws.mapas.neonline.cl/carga_servicios_fast2.php`
(or its successor) is found to return real coverage, the test plan would be
(offline, fixtures only):

- [ ] `test_xygo_registers` — module self-registers `"xygo"` in `PROVIDERS`.
- [ ] `test_xygo_jsonp_url_build` — the `coverage_json` URL template fills
  `coord1=<lat_min,lon_min>`, `coord2=<lat_max,lon_max>`,
  `center=<lat_c,lon_c>`, `catego=streetview`, `tipo=5`, `icono=img/
  mono_streetview.png` for a sample bbox.
- [ ] `test_xygo_decode_present` — a recorded `cargaStreetview(...)` JSONP
  response fixture decodes to a non-empty list of `(lat, lon, archXml)`
  triples, treated as coverage segments to burn into the raster.
- [ ] `test_xygo_decode_empty` — a `cargaStreetview('streetview','NULO',...)`
  response (the empty-response sentinel hinted at by
  `if(s!="NULO"){...}`) decodes to "checked-empty (0)", not nodata.
- [ ] `test_xygo_decode_malformed` — a non-200 / non-JSONP response (HTTP
  404/500/HTML) is classified as a hard fetch error distinct from a clean
  empty response.
- [ ] `test_xygo_min_zoom_guard` — the discovery sweep never issues queries
  at z < 16 (the viewer's `AM_streetview_min_zoom` floor).
- Fixtures: recorded JSONP responses under `tests/fixtures/xygo/` —
  **none of which exist today**; they cannot be recorded until the API
  is revived.

## 4. Implementation subplan (steps for the implementer — TDD)

**Not applicable while the verdict is DEFER / SKIP.** No provider module
should be added under `src/coverage_acquisition/providers/xygo.py` at this
time, and no `xygo` issue / branch / worktree should be created.

**If the verdict is ever overturned** (live API confirmed during a future
re-probe — see §7), the steps would be:

- [ ] Source kind: **`coverage_json`** (existing) — **but** the JSONP
  wrapper (`cargaStreetview(...)` → argument list) is not how today's
  `coverage_json` decoder works. Add a tiny **JSONP decoder helper** in
  `source_kinds/coverage_json.py` (or a new sibling kind
  `coverage_jsonp`) that strips the leading callback name and trailing
  `);`, parses the argument list, and returns a list of records. This
  is a **shared foundation change** and must land in its own
  `foundation/jsonp-decoder` PR *before* an `xygo` PR.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/xygo.py` (`ProviderDefinition`),
  with `runtime_config = None` (no auth), `headers = {"User-Agent":
  "<project UA>", "Accept": "*/*", "Referer": "http://mapas.xygo.cl/"}`,
  and a per-commune bbox config table (see Chile commune list — 240
  entries from the inventory).
- [ ] Implement the JSONP decoder until §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `-70.70 -33.49 -70.55 -33.40` (**Santiago centre**:
  Plaza de Armas + Providencia + Las Condes — historically the densest
  XYGO city). Expect ≥ 100 segments returned at z16.
- [ ] Rasterize pilot area to a z14 binary-presence COG; sanity-check that
  coverage lands on actual Santiago streets, not Andean slopes.
- [ ] Two-pass full extent: pass-1 region bbox **Chile mainland**
  `-75.7 -56.0 -66.4 -17.5` at discovery zoom **z16** (the API's
  minimum). Even bounded to 240 communes, this is a sizable sweep —
  budget time generously and run detached in tmux per the `run-scraper`
  skill.
- [ ] Update the STAC item; update the inventory status from "deferred"
  to "live".

## 5. Acceptance criteria (checked by provider-verifier)

**Not applicable** while the verdict is DEFER / SKIP. The standard criteria
(all §3 tests pass, module imports & self-registers, pilot tiles fetch &
decode, coverage lands on roads/land, COG valid, throttling + descriptive
UA present, ToS caveats documented) would apply only after revival.

## 6. Status log

- `2026-05-25` scout (provider-scout): **drafted — recommend DEFER / SKIP.**
  Evidence summary:
  - Live HTTP probes 2026-05-25: `mapas.xygo.cl/` serves the 2013 viewer
    HTML (`http://200.12.26.79/`, Apache 2.2.3 / PHP 5.2.6, HTTPS not
    served).
  - Every backend the viewer needs is NXDOMAIN today:
    `t0.neonline.cl` (tile CDN), `mapas.neonline.cl` (JS helpers),
    `ws.mapas.neonline.cl` (coverage JSONP API). The KRPANO panorama host
    `204.236.231.44` refuses TCP.
  - Wayback CDX confirms `mapas.neonline.cl` last responded 200 on
    **2019-08-17** and `ws.mapas.neonline.cl` last responded (403) on
    **2019-05-06**. The actual `…carga_servicios_fast2.php` API has
    **zero** Wayback captures — there is no recorded fixture.
  - The "modern" `https://streetview.xygo.cl/` is **not** a street-view
    viewer; its SPA bundle is a Vue.js subscription/login admin app for
    `mediosregionales.cl` (routes `/login`, `/suscripciones`, etc.) with
    no map code at all.
  - XYGO the company is alive (Esri Gold Partner — see Esri Partners
    catalog "XYGO TECHNICAL CONSULTING by Mapas Digitales SA", LinkedIn
    activity 2026-05) but has pivoted to GIS consulting; the public
    street-view product is no longer offered.
  - Coverage-API URL template, presence rule and JSONP decoder were
    nonetheless reverse-engineered from the unpacked 2017 Wayback copy
    of `funciones_java_mapa_v2.js` (see §2) so that, if XYGO ever
    revives a public viewer, the implementer has a starting point.
- `2026-05-25` approval: < pending — human approval gate >
- **Future re-probe cadence:** re-run `getent hosts ws.mapas.neonline.cl`
  and `curl -sS http://mapas.xygo.cl/` quarterly. The provider becomes
  implementable again only when **both** the viewer HTML loads its JS
  successfully *and* the `carga_servicios_fast2.php?catego=streetview&...`
  endpoint returns a non-empty JSONP body (or XYGO publishes a wholly
  new public viewer, in which case re-scout from scratch).

## 7. Recommendation

**Defer (do not skip permanently).** XYGO had a clean, well-structured
coverage API and a substantial first-party SVI footprint (240 communes
across Chile in 2009–2017), and South American street-view providers are
under-represented in the inventory — if the company ever republishes a
public viewer, the provider is worth picking up. But there is **no scrapable
coverage layer today**, the backend has been dark for ≥ 7 years, the company
has visibly pivoted to GIS consulting, and re-implementing now would
produce a provider that registers but fetches nothing. Mark the inventory
row as `deferred_infra_dead` (mirroring the `carte_ma` and `mappy` status
on `chore/deferred-t2-subplans`) and revisit on a quarterly re-probe.

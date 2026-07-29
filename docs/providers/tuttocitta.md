# [T3] Provider: Tuttocittà (`tuttocitta`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-25): DEFER / DROP. Tuttocittà historically hosted the
first car-mounted spherical "Visual" street view in Italy (2006, Carraro Lab
for Seat Pagine Gialle), but the modern site relaunched in April 2025 as a
Nuxt SPA built on top of OpenStreetMap + TomTom satellite + a traffic overlay,
and it no longer ships a first-party panorama / 360° / "Foto 360" product of
any kind. The live viewer exposes exactly two layer toggles ("Mappa",
"Traffico"); the application bundle (`/_nuxt/entry.*.js`) and the in-page
mapping library (`/iolmap/1.1.7/IOLMap.js`) contain zero references to
`pano*`, `street*`, `sferic*`, `360*`, `immers*`, or any equivalent layer.
The only `streetview-italia` URL on the domain is a legacy SEO landing page
that links to category indexes (`citta`, `mare`, `montagna`, `arte-e-monumenti`)
and does not host or embed any imagery; in the post-April-2025 SPA those
category pages no longer resolve to a viewer either. The site is geo-fenced
to Italy/EU at the CloudFront edge (returns HTTP 403 to traffic from outside
that region) and `robots.txt` explicitly bans `ClaudeBot`, `anthropic-ai`,
`Google-Extended`, `Cohere`, `Apple-Extended`, with `Crawl-delay: 10` for
`GPTBot`, `OAI-SearchBot`, `CCBot`, `Grok`, `Applebot`, `facebookexternalhit`.
There is no coverage layer to scrape and no coverage API to probe.

This subplan documents the full investigation and the conditional plan that
would apply *if* Tuttocittà ever revives a first-party panorama coverage
layer. No issue/branch/code should be created now.
-->

## 1. Summary

Tuttocittà (`https://www.tuttocitta.it/`) is a long-running Italian web-mapping
and yellow-pages property, currently operated by Italiaonline S.p.A. (the
successor of Seat Pagine Gialle). The product started in 1981 as a paper street
atlas bundled with the Pagine Gialle directory, moved fully online in 2014, and
was re-launched on 1 April 2025 as a "dynamic digital ecosystem" built on
OpenStreetMap (announced by Italiaonline; reported by Primaonline). In its
2006–2010s heyday it shipped **Tuttocittà Visual** — a first-party,
car-mounted spherical "Street View" produced by Carraro Lab for Seat Pagine
Gialle that pre-dated Google Street View by a year and covered the centres of
Italy's 8 main cities, with later extensions to Venice on foot, ski slopes,
boats, and bicycles. That feature is in scope on paper (Italian provider,
first-party imagery, not a re-hoster) and is why the inventory lists it as a
T3 candidate.

**However, scouting concludes Tuttocittà should be DEFERRED / DROPPED for now.**
The April 2025 SPA has no panorama / 360 / street-view layer in any form: not
as a rendered raster coverage overlay, not as a vector-MVT layer, not as a
JSON coverage API, and not as a hidden tile path. The legacy "Visual" product
has been retired without replacement, and the Italiaonline relaunch
announcement that describes the new feature set (OSM base map, traffic, on-duty
pharmacies, gas stations, parking, green spaces, cultural sites) does not
mention immersive imagery at all. With no coverage layer to scrape, there is
nothing to harvest into the coverage database. See §2 for the full evidence
and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: no scrapable coverage layer — DEFER / DROP

Applying the kakao/naver/mapy/mappy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.**
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — NO endpoint exists on any subdomain (`www.`, `services.`, `tiles-osm.tcol.it`,
   `osm.italiaonline.it`, `img.tcol.it`).**

- **Homepage / public viewer URL:**
  - Homepage / viewer: `https://www.tuttocitta.it/` (the map viewer is at
    `https://www.tuttocitta.it/mappa`, and per-city deep links at
    `https://www.tuttocitta.it/mappa/{city}`, e.g. `…/mappa/milano`,
    `…/mappa/roma`, `…/mappa/torino`, `…/mappa/firenze`, `…/mappa/napoli`,
    `…/mappa/genova`, `…/mappa/bologna`, `…/mappa/cagliari`).
  - The viewer is a **Nuxt 3 SPA**. The Nuxt asset manifest at scout time
    shipped exactly nine chunks under `/_nuxt/`:
    `entry.ar7uUkYA.js` (690 kB, main bundle), `entry.Fvdn6kaa.css`,
    `default.SyXrB2Wc.js`, `default.d-XVg8eY.css`, `index.1dSrIji7.js`,
    `index.NMYihhW0.js`, `tab-map.yxUeJubn.js`, `client-db.Xe6_0oni.js`,
    `useCanonicalMeta.L4KNrp75.js`. None of them mention a panorama / 360
    feature (see "What the live viewer fetches" below).
  - The Nuxt app also loads an Italiaonline-internal mapping library:
    `https://www.tuttocitta.it/iolmap/1.1.7/IOLMap.js` (1.1 MB; Leaflet +
    MapLibre wrapper) and `IolAutocompleteDoveUnico.js`. A v1.1.8 of the
    same library is referenced from per-place detail pages — same shape.
  - Tier: **T3** ("likely / unverified / gated") per `docs/PLAN.md` §2.

- **How the viewer was investigated.** Direct fetches from the scout
  environment hit `HTTP 403 from CloudFront` with the message *"The Amazon
  CloudFront distribution is configured to block access from your country."*
  (X-Cache: `Error from cloudfront`, X-Amz-Cf-Pop: `TLV55-P1` — i.e. the
  request was geo-blocked at the Tel-Aviv edge). The site is therefore
  **fenced to Italian/EU traffic** at the CDN. All scouting was instead
  performed against the Internet Archive's Wayback Machine captures
  (`web.archive.org/web/2025*/`), using a recent good snapshot taken
  `2025-12-25 21:39 UTC` of the homepage and `/mappa/milano`, and the
  legacy desktop site `services.tuttocitta.it` for comparison. All asset
  URLs (`/_nuxt/*.js`, `/iolmap/1.1.7/IOLMap.js`, etc.) were fetched from
  the same Wayback capture so the JS analysed matches the page snapshot.

- **What the live viewer actually fetches** (captured 2025-12-25 via Wayback):
  - **Preconnect hints in the homepage `<head>`:**
    `https://tiles-osm.tcol.it/` (the only map-tile host),
    `https://www.iolam.it/` (ad / consent platform — `iolam` = "IOL Adv
    Manager"), plus ad networks (`c.amazon-adsystem.com`,
    `adservice.google.com`, …). **No panorama / 360 / streetview host is
    referenced.**
  - **Base map tile sources** (from `entry.ar7uUkYA.js` and `IOLMap.js`):
    - `https://tiles-osm.tcol.it/photo/{z}/{x}/{y}.jpg` — aerial / satellite
      raster (NOT street-level).
    - `https://tiles-osm.tcol.it/WM/512/WST/{z}/{x}/{z}_{x}_{y}.webp` — the
      Italiaonline OSM-derived "WST" base raster (512-px web-mercator tiles).
    - `https://tiles-osm.tcol.it/vector/iolmap-style.json` and
      `tiles-osm.tcol.it/vector/iolmap-style-*` — MapLibre-style vector
      basemap style.
    - `https://api.tomtom.com/map/1/tile/sat/main/{z}/{x}/{y}.jpg` — TomTom
      satellite tiles (alternative aerial basemap; uses `satelliteApiKey`).
    - `https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.png`
      — TomTom traffic flow overlay.
    - `/api/layerTraffic?z={z}&x={x}&y={y}` — same-origin proxy for the
      traffic overlay used by the Nuxt app.
  - **Routing API:** `https://osm.italiaonline.it/routing/route_px` (used by
    `/percorso/*` itineraries).
  - **The full set of map-control labels rendered on `/mappa/milano`** —
    exactly two: **`Mappa`** and **`Traffico`**. There is no "Foto 360",
    "Visual", "Street View", "Panorama", "Sferica", "Immersiva", "Vista",
    "3D", or any equivalent toggle. The `hasStreetNumbers` key seen in the
    embedded JSON for the city of Milan is a per-city **address-number
    availability flag**, not a panorama indicator.
  - **Keyword scan of all loaded JS bundles.** Across `entry.ar7uUkYA.js`
    (690 kB), `tab-map.yxUeJubn.js`, `default.SyXrB2Wc.js`, both `index.*.js`,
    and the full 1.1 MB `iolmap/1.1.7/IOLMap.js`, a case-insensitive scan
    for the regex `(panorama|pano[A-Z]|street.?view|sferic|immers|360°|_360|
    360_|foto.?360|visual[A-Z])` returns **zero matches**. The only hits in
    the entire bundle for `pano|street|visual` are the unrelated Leaflet
    APIs `_panOnFocus`, `autoPanOnFocus`, `StreetNumbers` (address attribute),
    `visualizePitch` (MapLibre 3D camera helper), and Italian UI labels
    (`Visualizza`, `visualizzazione`).
  - **`iol-streets` is a basemap-style id, not a street-view product.** The
    identifier appears once in `IOLMap.js`:
    `{minZoom:…, maxZoom:…, maxNativeZoom:18, id:"iol-streets"}` and again
    on the vector path, sourced from `tiles-osm.tcol.it/vector/iolmap-style.json`.
    Its sibling style id is `iol-photo` (aerial). Both are conventional
    Leaflet/MapLibre **base-map layer ids**, used to switch between "street
    map" and "satellite" — they have nothing to do with street-level
    panoramas.

- **The `services.tuttocitta.it` legacy desktop site and the
  `/streetview-italia` SEO landing** (the only paths on the entire domain
  that contain the substring "streetview"):
  - `services.tuttocitta.it` (legacy desktop viewer, still served, title
    *"Mappe, itinerari e percorsi stradali | Tuttocittà"*) renders a footer
    SEO-link block with `Street View` pointing at
    `https://www.tuttocitta.it/streetview-italia`.
  - `https://www.tuttocitta.it/streetview-italia` (Wayback capture
    2023-04-08) is an **SEO landing page** titled *"Street View 3d: vista
    dell'Italia a livello strada"* with meta description
    *"Visualizza le strade delle città italiane a 360 gradi con Street View
    Italia: passeggia per le vie del centro, visita monumenti…"*. The page
    body links only to four category indexes:
    `/streetview-italia/citta`, `/streetview-italia/arte-e-monumenti`,
    `/streetview-italia/mare`, `/streetview-italia/montagna`. **There is no
    embedded viewer of any kind** (no `<iframe>` pointing at
    `maps.google.com/maps/embed`, `streetviewpixels-pa.googleapis.com`,
    Mapillary, Bing Streetside, or a first-party panorama service — the
    only `<iframe>` on the page is the Google Tag Manager `<noscript>`
    tracking pixel). The deeper subpages (e.g. `/streetview-italia/citta`)
    return a directory of internal links and contain the same Italian
    marketing copy but again **no first-party panorama URLs**.
  - In the **April 2025 Nuxt SPA**, fetching
    `https://www.tuttocitta.it/streetview-italia/citta/roma` (Wayback
    2025-12) **302/SPA-redirects to the new homepage** (title becomes
    *"TuttoCittà: Mappe, Percorsi, Ristoranti, Farmacie, Hotel e Negozi"*)
    — i.e. those legacy SEO subpaths no longer resolve to a viewer in the
    relaunched site.
  - **Interpretation:** the `streetview-italia` slug is a historical SEO
    surface that referenced the long-retired Tuttocittà Visual product
    (and traded on the generic-noun phrase "street view" for Italian
    search traffic). It was already an empty SEO shell on the legacy site
    and has been removed entirely from the new SPA.

- **Coverage endpoint:** **none exists**.
  - No raster `{z}/{x}/{y}` coverage layer is served from
    `tiles-osm.tcol.it`, `services.tuttocitta.it`, `www.tuttocitta.it`,
    `osm.italiaonline.it`, or `img.tcol.it`. The only tile paths advertised
    are `/photo/…`, `/WM/512/WST/…`, `/vector/iolmap-style*`, plus TomTom's
    `tile/sat/…` and `tile/flow/…`.
  - No vector-MVT layer references panoramas in the MapLibre style
    (`iolmap-style.json` only declares OSM-derived base layers).
  - No coverage / point-probe JSON API is referenced from the SPA or
    `IOLMap.js`. The only first-party API endpoints called by the live app
    are `osm.italiaonline.it/routing/route_px` (routing) and `/api/layerTraffic`
    (same-origin traffic proxy).

- **Coordinate scheme:** standard Web Mercator XYZ (EPSG:3857) for every
  tile source on the site (`{z}/{x}/{y}`). The vector style is MapLibre-GL
  conventional WGS84/Web-Mercator. — Moot, since there is no coverage layer.

- **Zoom range / tile size / response format:** Moot. (For reference: the
  base raster is 512-px WebP at `z=0..~18`, photo is 256-px JPEG at
  `z=0..~19`, TomTom satellite is 256-px JPEG to `z=22`.)

- **Auth:** No auth on the publicly observed base-map and aerial tile
  hosts; TomTom is auth'd via an `apikey` query param embedded in the SPA
  config (`satelliteApiKey`). — Moot for coverage scraping, since there is
  no coverage endpoint.

- **Presence rule:** N/A — no candidate response to read.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://www.tuttocitta.it/robots.txt` (fetched via Wayback) explicitly
    sets `Disallow: /` for: **`ClaudeBot`** (our project's bot family),
    **`anthropic-ai`**, **`Google-Extended`**, **`cohere-ai`**,
    **`Applebot-Extended`**, **`Meta-ExternalAgent`**, **`MegaIndex.ru`**.
    It sets `Crawl-delay: 10` for: `GPTBot`, `OAI-SearchBot`, `Grok`,
    `CCBot`, `Applebot`, `facebookexternalhit`. (`Sitemap` is
    `https://www.tuttocitta.it/sitemap.xml`.)
  - `https://services.tuttocitta.it/robots.txt` is `User-agent: *
    Disallow: /` — i.e. the legacy desktop subdomain forbids all
    automated crawling.
  - **CloudFront geo-fencing:** the entire site returns `HTTP 403` to
    non-Italy/EU source IPs. A scraper running from outside the EU would
    need to route through an Italian egress, which complicates the
    "polite scraper" story even before considering robots.txt.
  - **No public ToS / scraping policy** is linked from the site beyond
    `https://privacy.italiaonline.it/common/cookie/privacy_tuttocitta.html`
    (cookie / privacy notice) — that is a privacy policy, not a scraping
    permission grant.
  - **Verdict for `polite_fetch`:** even if a coverage layer existed,
    the project's default `User-Agent` (which advertises `ClaudeBot` /
    `anthropic-ai` heritage) is explicitly disallowed, and the legacy
    subdomain bans `*`. We must not crawl this domain under our default
    policy.

- **Known quirks / gotchas:**
  - Site is **CloudFront-geo-fenced to IT/EU**. Most foreign egress IPs
    return `403`; this also means provider-verifier CI runs from outside
    the EU would always fail to reach the origin.
  - The string "Street View" on `tuttocitta.it` always refers to either
    (a) the long-retired 2006 **Tuttocittà Visual** product (now only
    described on Carraro Lab's portfolio page,
    `https://www.carraro-lab.com/portfolio-item/tuttocitta-visual-il-primo-streetview/`),
    or (b) the dead SEO surface `/streetview-italia` that survived from
    the pre-2025 site. Neither implies a current data layer.
  - `iol-streets` is **not** a street-view layer — it's the basemap
    layer id for the "street map" (as opposed to `iol-photo` = aerial).
    Future scouts must not be misled.

## 3. Test plan (write these FIRST — red before green)

**Not applicable while the verdict stands.** No tests, fixtures, or
provider module should be written until/unless §7's revival conditions are
met. The plan below is the **conditional** plan that would apply if and
only if Tuttocittà reintroduces a first-party panorama coverage layer.

- [ ] *(conditional)* `test_tuttocitta_tile_url_build` — URL template fills
      correctly for sample `(z, x, y)` once the new coverage endpoint URL
      is known.
- [ ] *(conditional)* `test_tuttocitta_decode_present` /
      `test_tuttocitta_decode_empty` — recorded response fixture decodes
      to expected presence flag.
- [ ] *(conditional)* `test_tuttocitta_registers` — module self-registers
      in `PROVIDERS` after the registry imports `providers.tuttocitta`.
- [ ] *(conditional)* `test_tuttocitta_user_agent_respects_robots` — fixture
      asserts the request `User-Agent` is one that is **not** in the live
      `robots.txt` Disallow list (i.e. neither `ClaudeBot` nor
      `anthropic-ai` family). If only those UAs are available, the test
      should fail loudly and the scrape should not proceed.
- [ ] *(conditional)* Fixtures: small recorded response samples under
      `tests/fixtures/tuttocitta/` captured from an Italian egress IP.

## 4. Implementation subplan (steps for the implementer — TDD)

**Do not implement.** This subplan is a deferred / drop recommendation.
The implementer should **not** create a branch, an issue, or
`src/coverage_acquisition/providers/tuttocitta.py`. The Phase-3 batch can
proceed without Tuttocittà; promote it from this `deferred` state to an
active scout only if §7's revival conditions are observed.

- [ ] *(conditional, if revived)* Source kind: most likely `raster` (web
      mercator coverage overlay) or `coverage_json` (point-probe). NEW kind
      only if Tuttocittà ships something genuinely novel; that would be a
      separate foundation PR first.
- [ ] *(conditional)* Re-run the §2 scouting steps to capture the new
      endpoint, then fill §3 with concrete tests.
- [ ] *(conditional)* Write the §3 tests first; confirm they fail (red).
- [ ] *(conditional)* Add `src/coverage_acquisition/providers/tuttocitta.py`
      (`ProviderDefinition`), routed through `polite.polite_fetch` with a
      **non-Anthropic User-Agent** (the default project UA is robots-banned).
- [ ] *(conditional)* Implement until §3 tests pass; refactor.
- [ ] *(conditional)* Pilot fetch: bbox `9.150 45.450 9.220 45.490`
      (Milan city centre, ~5×4 km around the Duomo — Italy's densest urban
      core and the highest-probability area for any revived first-party
      imagery). Fallback pilot if Milan is dry: `12.470 41.880 12.510 41.910`
      (Rome historic centre / Piazza Venezia–Pantheon).
- [ ] *(conditional)* Rasterize the pilot area to a z14 COG; sanity-check.
- [ ] *(conditional)* Two-pass full extent: pass-1 region bbox
      `6.6 36.6 18.6 47.1` (mainland Italy + Sicily + Sardinia) at
      discovery zoom **z=9** (≈55 km tiles — small enough to skip empty
      ocean, large enough that a country-wide sweep completes in minutes;
      Italy spans ~12° of longitude × ~10.5° of latitude). Pass-2 refines
      hit tiles to the source-zoom range observed in pass-1.

## 5. Acceptance criteria (checked by provider-verifier)

**Not applicable.** No acceptance criteria can be met because there is no
coverage layer to fetch and no module to import. If §7's revival
conditions are ever met, the standard provider acceptance criteria apply
(§3 tests pass; module imports and self-registers; CI smoke passes;
pilot tiles fetch and decode; coverage lands on Italian roads/land, not
the Tyrrhenian/Adriatic; z14 COG is valid, CRS `EPSG:3857`, `uint8`,
`covered_pixels > 0`; fetches via `polite.polite_fetch`; descriptive
User-Agent that is **not** robots-banned; ToS / robots / geo-fence
caveats documented in the module docstring).

## 6. Status log

- `2026-05-25` scout: drafted. Verdict: **DEFER / DROP — no first-party
  panorama coverage layer exists in the post-April-2025 Tuttocittà SPA;
  domain is CloudFront-geo-fenced to IT/EU; `robots.txt` explicitly
  bans the project's default `ClaudeBot` / `anthropic-ai` user agents.**
  Evidence captured from Wayback snapshots
  (`web.archive.org/web/20251225213903/…` for the homepage and assets;
  `…/20251219000658/services.tuttocitta.it/` for the legacy desktop site;
  2023-04-08 capture for the legacy `/streetview-italia` SEO landing).
- `2026-05-25` approval: **pending user decision.** Options for the
  user: (a) accept this deferred subplan and remove `tuttocitta` from the
  Phase-3 T3 batch; (b) keep it on a watch-list to re-scout if
  Italiaonline announces revived immersive imagery; (c) override and
  attempt a scrape anyway despite robots.txt (the project's CLAUDE.md
  prohibits this — "respect `robots.txt` and provider ToS").

## 7. Recommendation and revival conditions

**Recommendation:** **DEFER / DROP** Tuttocittà for Phase 3. The project's
goal is to harvest *where imagery exists*. Tuttocittà serves no
panorama / 360 / street-level coverage layer in any form on the current
production site, so there is nothing to harvest. The combination of
(a) no coverage endpoint, (b) CloudFront geo-fencing, and (c) explicit
`Disallow: /` for `ClaudeBot` and `anthropic-ai` in `robots.txt` means
the polite-scraper-friendly path is closed.

**Re-open this subplan only if all of the following become true:**

1. **A first-party panorama UI re-appears on `https://www.tuttocitta.it/`**
   — e.g. a "Foto 360" / "Visual" / "Vista a livello strada" toggle on
   the `/mappa/{city}` viewer, or an Italiaonline corporate announcement
   describing revived immersive imagery. (Worth monitoring
   `https://www.italiaonline.it/corporate/en/iol/brand-en/tuttocitta/`
   and Carraro Lab's news feed.)
2. **A scrapable coverage signal is shipped** — a raster overlay, a vector
   MVT layer, or a point-probe / bbox JSON API — observable in the live
   DevTools network panel of the viewer.
3. **`robots.txt` either drops the `ClaudeBot` / `anthropic-ai` Disallow,
   or the project switches to a non-Anthropic User-Agent for this
   provider that is not banned.**
4. **A practical IT/EU egress** is available for both production fetches
   and CI verification (Tuttocittà's CloudFront 403s most non-EU IPs).

If those conditions are met, fill §3, §4, §5 with the concrete endpoint
details and proceed via the standard `add-provider` → `tdd` flow.

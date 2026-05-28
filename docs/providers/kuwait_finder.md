# [T3] Provider: Kuwait Finder / PACI Street View (`kuwait_finder`) — RECOMMEND DEFER

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER (not a clean DROP, not purely app-only).
A real, web-accessible coverage endpoint DOES exist and was reverse-engineered
from the public Kuwait Finder 3.0 web SPA — it is a Mapillary-v3-compatible
point-probe ("closeto") served from PACI's own host. The blocker is NOT
"app-only with no web endpoint"; it is that ALL *.paci.gov.kw hosts are
network-unreachable from this environment (TCP connect times out / HTTP 000)
while every control host succeeds, i.e. the services are geo-fenced /
WAF-blocked to Kuwaiti (or otherwise allow-listed) IPs. On top of that the
coverage probe requires a runtime `token` + `organization_keys` + `client_id`
loaded from `https://gis.paci.gov.kw/config.json`, which is itself behind the
same network block and was never captured by the Internet Archive, so the
auth material could not be obtained either. Recommendation: DEFER until the
endpoint is reachable (Kuwait-egress proxy / collaborator in-country, or a
relaxed WAF) and the config token can be captured. The endpoint shape, presence
rule, coordinate scheme, and a conditional implementation plan are fully
documented below so that an implementer with network access can build the
provider from this file alone. No issue / branch / code should be created now.
-->

## 1. Summary

Kuwait Finder is the official national mapping application of **Kuwait's Public
Authority for Civil Information (PACI)** — a government address/parcel/navigation
service for the State of Kuwait, distributed as iOS/Android apps **and** a public
web app ("Kuwait Finder 3.0") at `https://gis.paci.gov.kw/Client/`. In March 2018
PACI added a **street-view / 360° panorama** feature covering "most areas in
Kuwait," captured with a vehicle-mounted **RIEGL VZ-400i** mobile-mapping LiDAR
rig and processed/published with the **Orbit GT 3DM** software suite (vendor:
Mena3D); the panoramas are exposed to the web SPA through a **self-hosted,
Mapillary-API-compatible** street-view service on PACI's own infrastructure
(`streetview.paci.gov.kw`). It is in scope as a **first-party, government-owned**
SVI source (not a re-hoster, not paid-B2B) for an otherwise data-sparse region
(the Arabian Gulf). The inventory flagged it "mobile app only / app-gated"; this
scout finds that label only partly correct — there is a genuine web coverage
endpoint, but it is currently **unreachable from outside Kuwait and token-gated**,
so the verdict is **DEFER** (see §7), not DROP.

## 2. Research findings (filled by provider-scout)

### Verdict: real web coverage endpoint exists, but geo-fenced + token-gated — DEFER

Applying the kakao/naver/mapy/eniro scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO** (no
   precomputed "where-panoramas-exist" raster tile layer was found).
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — YES (this is the target).** The web SPA discovers panoramas with a
   Mapillary-v3-style "closeto" point-probe returning GeoJSON features; presence
   = non-empty `features` array. There is also a self-hosted Mapillary `v3/model`
   API on `streetview.paci.gov.kw`.
4. **A panorama viewer with an embeddable iframe one could discovery-probe? — YES**
   (`/streetview.html?key=...&X=...&Y=...` and `/thumbnail.html?key=...`), but the
   point-probe in (3) is the cleaner coverage signal.

- **Homepage / public viewer URL:**
  - Web app (SPA): `https://gis.paci.gov.kw/Client/` (also `…/Client/EN/Default.aspx`);
    page title "Kuwait Finder 3.0" / "كويت فايندر".
  - Street-view data host (self-hosted, Mapillary-compatible): `https://streetview.paci.gov.kw/`.
  - ArcGIS basemap/portal backend: `https://kuwaitportal.paci.gov.kw/arcgisportal/rest/services/Hosted/KuwaitBasemap/MapServer` (and `…/PACIBasemap/MapServer`).
  - PACI marketing page: `https://www.paci.gov.kw/KuwaitFinder.aspx`.
  - Apps: Google Play `kw.gov.paci.kuwaitfinderandroid`; App Store id `593476960`.
  - **Tier:** **T3** ("likely / unverified / gated" per `docs/PLAN.md` §2).

- **How the viewer was investigated.** The live `*.paci.gov.kw` hosts are
  **TCP-unreachable from this environment** — `curl` to
  `gis.paci.gov.kw`, `streetview.paci.gov.kw`, and `kuwaitportal.paci.gov.kw`
  on :443 all hang and return **HTTP 000 (connection timeout)**, both inside and
  outside the sandbox, and the `WebFetch` tool times out the same way. DNS
  resolves fine (`gis.paci.gov.kw → 91.102.145.61`, `kuwaitportal.paci.gov.kw →
  91.102.145.80`, `streetview.paci.gov.kw → 52.157.218.202` (Azure)). Control
  hosts succeed from the same shell — `www.arcgis.com` (200/301),
  `gis.dep.pa.gov/depgisprd/rest/services` (200), `orbitgt.com` (200) — so this
  is **provider-side geo-fencing / WAF**, not a local network fault. The SPA
  shell and its JavaScript bundles were therefore read from the **Internet
  Archive (Wayback)** `…js_/` raw snapshots (snapshot `20251002120548`,
  React build `main.6adb5ba6.chunk.js` / `2.7cb34489.chunk.js`), which preserve
  the exact served code. The coverage endpoint, presence rule, and config-loading
  behaviour below were read directly out of that minified React source.
  Corroboration: PACI/KUNA/Esri/GeoInformatics press on the 2018 launch and the
  Orbit-3DM/Mena3D/RIEGL capture stack; the `arcgis.com` "PACI Kuwait Basemap"
  webmap item (`4f2468bb19a144f792f61e5b86244840`, public) whose only basemap
  layer is the `kuwaitportal.paci.gov.kw/arcgisportal/.../KuwaitBasemap` tiled
  service; and Wayback CDX history of `*.paci.gov.kw`, which first surfaced the
  `streetview.paci.gov.kw` host.

- **What the SPA fetches (from the React bundle, snapshot `20251002120548`):**
  - **Runtime config** is loaded from `GET https://gis.paci.gov.kw/config.json`
    (also `GET /firebase.json`). This config object (`M.config`) supplies the
    street-view settings under `config.streetView`:
    `config.streetView.mapillaryAPIURL`, and `config.streetView.api.clientID`,
    `config.streetView.api.organizationKey`, `config.streetView.api.token`.
    **These values were not obtainable** (host unreachable; `config.json` not in
    Wayback). They must be captured at implementation time (see §3/§4).
  - **Coverage point-probe (THE TARGET).** On a map click / address selection
    the SPA issues:

    ```
    GET {config.streetView.mapillaryAPIURL}
        ?closeto={X},{Y}
        &radius=1000
        &per_page=1
        &client_id={config.streetView.api.clientID}
        &organization_keys={config.streetView.api.organizationKey}
        &token={config.streetView.api.token}
    ```

    and reads the response as GeoJSON: it uses `features[0].properties.key` to
    build the panorama thumbnail URL `…/{key}/thumb-2048.jpg`. The
    `closeto` / `radius` / `per_page` / `organization_keys` / `token` parameter
    vocabulary is the **Mapillary v3 (legacy) API** — PACI runs a Mapillary-
    compatible service on its own host rather than calling public Mapillary
    (no `*.mapillary.com` host appears anywhere in the bundle). For coverage we
    will raise `per_page` and drop the `closeto`-single-result behaviour, or use
    a bbox query (see §4) to enumerate presence within a tile.
  - **Self-hosted Mapillary model API.** The bundle also calls
    `https://streetview.paci.gov.kw/v3/model.json?method=get&paths=…` — the
    classic Mapillary v3 `model.json` graph endpoint, confirming the street-view
    backend is a self-hosted Mapillary (v3-era) deployment fronting the Orbit
    3DM data, served from `streetview.paci.gov.kw`.
  - **Panorama viewer (not needed for coverage):** the SPA opens an `<iframe>`
    to `window.location.origin + "/streetview.html?key={key}&theme=…&language=…&X={X}&Y={Y}"`
    and a thumbnail helper `"/thumbnail.html?key={key}&X={X}&Y={Y}"`.
  - **Basemap (not street view):** Esri ArcGIS JS API renders the tiled basemap
    `kuwaitportal.paci.gov.kw/arcgisportal/rest/services/Hosted/KuwaitBasemap/MapServer`
    in EPSG:3857. (The SPA shell CSS is full of `.esri-*` classes; the street-
    view container is `<div id="mly">`, Mapillary's standard viewer mount.)

- **Coverage endpoint(s):**
  - Primary: `GET {mapillaryAPIURL}?closeto={X},{Y}&radius={m}&per_page={n}&client_id=…&organization_keys=…&token=…`
    → GeoJSON; presence = non-empty `features`.
  - Secondary (graph): `GET https://streetview.paci.gov.kw/v3/model.json?method=get&paths=…`.
  - `mapillaryAPIURL` host/path is in `config.json` (unobtained); strongly
    expected to be on `streetview.paci.gov.kw` (e.g. a Mapillary v3
    `…/v3/images` style path), consistent with the `v3/model.json` host.

- **Coordinate scheme:** the probe takes a **point `X,Y`** that the SPA computes
  from the selected feature (`M.document.X`, `M.document.Y`). The Kuwait Finder
  app and basemap operate in **web mercator EPSG:3857** (the `arcgis.com` webmap
  item declares `wkid:102100 / latestWkid:3857`, and the Wayback deep-link query
  strings carry 3857-magnitude coordinates, e.g. `5340988, 3420228`). So `X,Y`
  are most likely **EPSG:3857 metres**, NOT lon/lat — **this must be confirmed at
  implementation time** by reading `config.json` / live network capture (Mapillary
  `closeto` is normally lon/lat, but PACI's coordinate column here looks 3857).
  For our discovery grid we will iterate web-mercator tiles and convert tile
  centres to whatever unit the live probe expects.
- **Zoom range / tile size / response format:** N/A as a tile pyramid — coverage
  is a **point/bbox JSON probe**, not a tile layer. Response is GeoJSON
  (`features[]` with `properties.key`, capture date, etc.). Nothing live to
  characterise for tile size/zoom.
- **Auth:** **token-gated.** The probe requires `client_id` + `organization_keys`
  + `token` from `config.json`. There is no interactive login for the *coverage*
  probe (the `token` is a static app/service token embedded in `config.json`,
  fetched anonymously by the SPA), but some app features show a Firebase
  login dialog (`/firebase.json`, `showLoginDialog`, `authorized`, `userProfil`
  state) — coverage probing should not need it, but verify. `.env` key proposal:
  `KUWAIT_FINDER_TOKEN` (plus `KUWAIT_FINDER_CLIENT_ID`, `KUWAIT_FINDER_ORG_KEY`,
  `KUWAIT_FINDER_API_URL`) — populated from a captured `config.json`.
- **Presence rule:** issue the probe for a grid point (or bbox); **non-empty
  `features` array ⇒ a PACI panorama exists at/near that point**; empty ⇒ none.
  (The SPA itself treats `features[0].properties.key` truthy as "panorama here.")
- **robots.txt / ToS notes; observed rate limit:**
  - `robots.txt` could not be read live (host unreachable). The Wayback "snapshot"
    of `gis.paci.gov.kw/robots.txt` actually returns the SPA `index.html` shell
    (the React app's catch-all route), i.e. there is effectively **no real
    robots.txt** distinct from the app — **re-fetch and re-check at implementation
    time** once the host is reachable.
  - PACI services are **geo-fenced** (foreign IPs are dropped at the network/WAF
    layer); this strongly signals that PACI restricts who may consume the service,
    so honour their throttle and `User-Agent` policy and keep request volume low
    (the probe is per-point, so a coarse discovery grid is mandatory — see §4).
  - It is Kuwaiti **government** data; before publishing coverage, confirm reuse
    terms (PACI site / app ToS). Record any caveat in the module docstring.
- **Known quirks / gotchas (for the implementer / future re-scout):**
  - **Geo-fence is the primary blocker.** Implementation needs egress from
    Kuwait (in-country collaborator, Kuwaiti VPN/proxy, or a relaxed WAF). Without
    it, every fetch is HTTP 000. Confirm reachability as Step 0 (§4).
  - **`config.json` carries the auth.** The coverage probe is useless without
    `mapillaryAPIURL` + `client_id` + `organization_keys` + `token`. First action
    once reachable: `GET https://gis.paci.gov.kw/config.json`, read `streetView`,
    and copy the values into `.env`. Tokens may rotate — treat as config, not code.
  - **Self-hosted Mapillary v3, not public Mapillary.** Do not point the provider
    at `graph.mapillary.com` — PACI serves its own Mapillary-compatible API on
    `streetview.paci.gov.kw`. We already have a `mapillary` provider module
    (`providers/mapillary.py`); the decode logic (GeoJSON `features` → presence)
    can likely be reused, but the host/auth differ.
  - **Coordinate unit ambiguity** (3857 metres vs lon/lat for `closeto`) — resolve
    by live capture before the pilot; a wrong unit silently returns empty coverage.
  - **`closeto` returns nearest only** (`per_page=1` in the SPA). For coverage,
    prefer a **bbox / many-results** query (raise `per_page`, or use the
    `v3/model.json` graph / a Mapillary `bbox=` parameter) so one request covers a
    whole discovery tile rather than a single point.
  - The Azure IP for `streetview.paci.gov.kw` (52.157.218.202) vs the
    `91.102.145.x` block for the other PACI hosts suggests the street-view tier is
    cloud-hosted but still WAF/geo-gated.

## 3. Test plan (write these FIRST — red before green)

> No tests should be written until §7 unblocks (host reachable + `config.json`
> token captured). The list below is the **conditional** plan an implementer
> adopts once unblocked. Source kind is `coverage_json` / `json_api` (point/bbox
> JSON probe, presence = non-empty `features`), NOT `raster`.

- [ ] `test_kuwait_finder_probe_url_build` — the probe URL fills correctly for a
      sample `(X, Y)` and config, producing
      `{mapillaryAPIURL}?closeto={X},{Y}&radius={r}&per_page={n}&client_id={cid}&organization_keys={org}&token={tok}`
      (and the bbox variant used for discovery).
- [ ] `test_kuwait_finder_decode_present` — recorded GeoJSON fixture for a known
      panorama-bearing point in Kuwait City decodes to `present`
      (rule: non-empty `features`, `features[0].properties.key` truthy).
- [ ] `test_kuwait_finder_decode_empty` — recorded GeoJSON fixture for an
      empty point (e.g. offshore in the Gulf, or empty desert) decodes to `empty`.
- [ ] `test_kuwait_finder_auth_header` — probe includes the configured
      `token` / `client_id` / `organization_keys` from `.env`; missing token
      raises a clear config error (no silent empty coverage).
- [ ] `test_kuwait_finder_coord_unit` — the discovery-grid tile centre is
      converted to the unit the live probe expects (EPSG:3857 metres vs lon/lat),
      pinned by a recorded fixture so a future unit regression is caught.
- [ ] `test_kuwait_finder_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_kuwait_finder_user_agent` — fetch helper sends our descriptive
      `User-Agent` and honours the `polite.polite_fetch` per-host throttle.
- [ ] Fixtures: small recorded GeoJSON samples under
      `tests/fixtures/kuwait_finder/` (a present case + an empty case + the
      `config.json` `streetView` block with the live token redacted) — captured
      once the host is reachable.

## 4. Implementation subplan (steps for the implementer — TDD)

> **Status: blocked at Step 0.** Do not start; see §7. The plan below applies
> once the host is reachable and the config token is captured.

- [ ] **Step 0 (precondition):** From a **Kuwait-egress** network, confirm
      `https://gis.paci.gov.kw/config.json` returns JSON (HTTP 200) and that
      `https://streetview.paci.gov.kw/v3/model.json?...` and the
      `mapillaryAPIURL` `closeto` probe return real `features` for a Kuwait-City
      point. Capture `mapillaryAPIURL`, `client_id`, `organization_keys`, `token`
      into `.env` (`KUWAIT_FINDER_*`). Resolve the **coordinate unit** of
      `closeto` (3857 metres vs lon/lat) by inspecting a live request. If the host
      remains unreachable, keep this subplan deferred.
- [ ] Source kind: **`coverage_json`** / `json_api` (point/bbox GeoJSON probe;
      presence = non-empty `features`). Reuse the `mapillary` provider's GeoJSON
      decode where it fits; do NOT introduce a new source kind (if one is somehow
      needed, that is a separate foundation PR per `CLAUDE.md`).
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/kuwait_finder.py`
      (`ProviderDefinition`), auto-discovered by the registry. Build the probe URL
      from `.env` config; for discovery, prefer a **bbox / high-`per_page`** query
      per tile over the single-result `closeto` to cut request count; convert
      web-mercator discovery-tile centres/bboxes to the resolved coordinate unit
      via `geo.py`.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `47.96 29.36 48.00 29.39` (central **Kuwait City** —
      around 29.37N, 47.98E: the Sharq / Mubarakiya / city-centre core). Confirm
      non-empty coverage on the street grid.
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on
      Kuwait City roads/land, not on Kuwait Bay or the open Gulf.
- [ ] **Two-pass full extent:** pass-1 region bbox `46.5 28.5 48.5 30.1` (State of
      Kuwait mainland incl. Kuwait City, Hawalli, Farwaniya, Ahmadi, Jahra; the
      arcgis.com PACI webmap extent is `[45.66,28.28]–[49.72,30.28]`) at discovery
      zoom `z=12` (urban-dense country; refine after seeing point density and the
      provider's tolerated request rate — the probe is per-request, so do not over-
      probe empty desert). Pass-2 at the chosen source resolution.
- [ ] Keep decoded points (key, date, geometry) in `data/intermediate/kuwait_finder/`
      as the re-rasterizable source of truth; publish the COG only.
- [ ] Update the STAC item; update the inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> Only meaningful once §7 unblocks.

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- Pilot probes fetch & decode; coverage lands on Kuwait City roads (not Kuwait
  Bay / the Gulf, not uniformly across empty desert).
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0.
- Fetches via `polite.polite_fetch`; descriptive `User-Agent`; per-host throttle
  respected; `gis.paci.gov.kw` crawl policy re-checked at implementation time;
  PACI/government ToS reuse caveat documented in the module docstring; auth token
  sourced from `.env`, never committed.

## 6. Status log

- `2026-05-28` scout: drafted as **DEFER**. A genuine web coverage endpoint was
  reverse-engineered from the public Kuwait Finder 3.0 React SPA
  (Wayback snapshot `20251002120548`): a Mapillary-v3-compatible point-probe
  `{mapillaryAPIURL}?closeto={X},{Y}&radius=1000&per_page=1&client_id=…&organization_keys=…&token=…`
  returning GeoJSON `features` (presence = non-empty / `features[0].properties.key`),
  backed by a self-hosted Mapillary on `streetview.paci.gov.kw` (`/v3/model.json`),
  with config + auth token loaded from `gis.paci.gov.kw/config.json`. Imagery is
  first-party PACI data (RIEGL VZ-400i + Orbit 3DM, vendor Mena3D) — in scope,
  not a re-host, not paid-B2B. **Blockers:** (1) all `*.paci.gov.kw` hosts are
  network-unreachable from this environment (HTTP 000 / TCP timeout) while all
  control hosts succeed → geo-fence/WAF, NOT app-only; (2) the probe needs a
  `token`/`organization_keys`/`client_id` from `config.json`, which is itself
  behind the block and absent from Wayback → auth material unobtainable here.
  Not a DROP (endpoint is real and first-party); deferred pending Kuwait-egress
  access + token capture.
- `2026-05-28` approval: < pending >

## 7. Recommendation

**DEFER** — do not implement now, but keep on the roadmap as a tractable target
(this is materially better than the app-only labelling implied; there IS a web
coverage API).

1. **Do not create a GitHub issue, branch, or PR for `kuwait_finder` now.** It
   cannot be built or tested from this environment: every `*.paci.gov.kw` fetch
   returns HTTP 000, and the coverage probe's auth token is unobtainable.
2. **Mark `kuwait_finder` as `deferred / gated` in
   `data/external/street_view_providers.xlsx`**, with a note pointing at this
   subplan, the geo-fence evidence (HTTP 000 vs working controls), and the
   `config.json`-token requirement. Correct the "mobile app only" note to
   "web coverage endpoint exists but geo-fenced + token-gated."
3. **Unblock conditions (re-scout / hand off):** obtain **egress from Kuwait**
   (in-country collaborator, Kuwaiti VPN/residential proxy, or a relaxed WAF) AND
   capture `https://gis.paci.gov.kw/config.json` to read
   `streetView.mapillaryAPIURL` + `api.{clientID,organizationKey,token}`. Once
   both hold, this subplan is directly implementable: re-confirm the `closeto`
   coordinate unit, fill `.env`, and proceed from §4 Step 1. Re-submit for the
   human-approval gate per `CLAUDE.md` before coding.
4. **Reuse, don't reinvent.** PACI's street view is a self-hosted **Mapillary v3**
   deployment; the existing `providers/mapillary.py` GeoJSON-`features` decode and
   the `coverage_json`/`json_api` source kind should cover most of the work — only
   the host, auth, and (possibly) coordinate unit differ. No new source kind.
5. **ToS check before publishing.** This is Kuwaiti government data; verify reuse
   terms and keep request volume modest given the explicit geo-fencing.

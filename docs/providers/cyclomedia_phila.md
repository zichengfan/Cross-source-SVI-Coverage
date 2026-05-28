# [T3] Provider: CycloMedia — Philadelphia public viewer (`cyclomedia_phila`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

`cyclomedia_phila` is the **City of Philadelphia public street-level imagery
viewer** at `https://cyclomedia.phila.gov/` (also embedded inside the Atlas
property viewer `https://atlas.phila.gov/`). The street-level imagery is
**CycloMedia's** "GeoCyclorama" panoramas — CycloMedia is a commercial,
paid-B2B imagery vendor; the City of Philadelphia is a *licensed customer* and
exposes a thin public viewer over CycloMedia's **Street Smart** product.
Coverage is the City of Philadelphia, USA (Philadelphia County, ~3,000 miles of
public streets; rough bbox **-75.29 W .. -74.95 W, 39.86 N .. 40.14 N**). It
sits in `docs/PLAN.md` §2 as a **T3 candidate** with the explicit note
"CycloMedia limited to the public Philadelphia viewer only".

**Scouting verdict: RECOMMEND DEFER / DROP (do not implement now).** This is the
*same architecture* as the sibling `istanbul_ibb` scout (a public city viewer
embedding CycloMedia Street Smart), and the same dispositive blocker applies —
**only more so**, because Philadelphia ships its CycloMedia credentials in
*plaintext*. Live probing (2026-05-28) establishes:

1. **The coverage layer is CycloMedia's own gated WFS.** The viewer's
   "where panoramas exist" layer (the recordings layer) is fetched directly from
   **`https://atlasapi.cyclomedia.com/api/recording/wfs`** — CycloMedia's
   commercial Recording Locations / Coverage service — via WFS `GetFeature`
   over a map-bounds `bbox`, authenticated with HTTP Basic auth using the
   City's **licensed B2B CycloMedia credentials**. Those credentials are
   embedded *in plaintext* in the viewer's JS bundle
   (`username:"APIBasicForPhilly"`, `password:"Philly@Basic215"`,
   `apiKey:"GfElS3oRuroNivgtibsZqDkpCvItyPUNuv0NmXglen8puXoJanEVarsZyns9ynkJ"`).
   Driving that WFS from outside the viewer to bulk-extract coverage means
   **replaying Philadelphia's licensed commercial CycloMedia credentials
   against CycloMedia's own servers to enumerate CycloMedia's coverage** — an
   explicit CycloMedia Street Smart ToS violation and a hard project guardrail.
   The WFS returns **HTTP 401** to any unauthenticated request (verified live).
2. **There is NO City-published open-data street-imagery coverage layer.** The
   investigation specifically asked: does the *City of Philadelphia itself*
   publish a "where street-level imagery exists" layer under an open license
   (OpenDataPhilly / ArcGIS / DataBridge / Carto / PASDA)? Answer: **no.**
   - The OpenDataPhilly dataset titled **"StreetSmartPHL"** is a **false friend**
     — it is a *street-operations* app (street closures, trash/recycling days,
     street sweeping, snow plowing, paving), **not** the CycloMedia street
     imagery. It exposes no recording-locations / panorama-coverage feed.
   - Philadelphia's DataBridge GeoServer (`citygeo-geoserver.databridge.phila.gov
     /geoserver/wms`) is referenced by the viewer **only** for basemap/overlay
     raster layers (e.g. `atlas_zoning_grouped`), not for street-imagery
     coverage.
   - No City-hosted ArcGIS Feature/Map service or open-data dataset publishes
     CycloMedia recording points / capture extent. The coverage signal lives
     **only** inside CycloMedia's gated commercial WFS.
3. **The only "public" path is the credential-replay path, which is off-limits.**
   Unlike `istanbul_ibb` (which at least had a public, unauthenticated
   `GetRandomWithCoordinates` sampler), Philadelphia has **no** city-side
   unauthenticated coverage endpoint at all — the recordings WFS is the single
   coverage source and it is CycloMedia's, behind Basic auth. There is no
   legitimate public bulk-coverage feed to scrape.

The provider is **not defunct and not login-gated for humans** (the viewer works
in a normal browser). It is **out of scope** for this project because the only
coverage signal is a third-party commercial vendor's gated API, and
`CLAUDE.md`/`docs/PLAN.md` §13 explicitly limit CycloMedia to "the public
Philadelphia viewer only" and direct us to "drop any [provider] that explicitly
forbid[s] automation". **Defer / drop; do not open an implementation issue.**
Re-probe at the next provider sweep (see §6) to check whether the City ever
publishes a recording-locations layer on OpenDataPhilly / PASDA under an open
license. Cross-reference: the sibling `istanbul_ibb` subplan
(`git show chore/deferred-t3-batch1-subplans:docs/providers/istanbul_ibb.md`)
reached the same verdict on the identical pattern.

## 2. Research findings (filled by provider-scout)

### Verdict detail — why defer/drop

- **Public viewer host:** `https://cyclomedia.phila.gov/` — a Vite/React +
  OpenLayers SPA (`#app`, bundle `/assets/index-DnGsBUXr.js`, ~1.2 MB) that
  loads CycloMedia's Street Smart SDK from
  `https://streetsmart.cyclomedia.com/api/v24.5/StreetSmartApi.js` (HTTP 200,
  verified live 2026-05-28).
- **Atlas embed:** `https://atlas.phila.gov/` is a separate Vite/React SPA
  (bundle `/assets/index-D7TnOGjA.js`). It embeds EagleView (oblique/aerial)
  via `https://embedded-explorer.eagleview.com/static/embedded-explorer-widget.js`
  and links/embeds the CycloMedia street-view panel (`cyclomedia.phila.gov`).
  Atlas itself adds no street-imagery coverage feed beyond what
  `cyclomedia.phila.gov` provides.
- **The Street Smart init (verbatim from the bundle, 2026-05-28):**

  ```js
  await StreetSmartApi.init({
    targetElement: cycloviewer,
    username: "APIBasicForPhilly",
    password: "Philly@Basic215",
    apiKey:   "GfElS3oRuroNivgtibsZqDkpCvItyPUNuv0NmXglen8puXoJanEVarsZyns9ynkJ",
    srs: "EPSG:4326",
    locale: "en-us",
    addressSettings: { locale: "en-us", database: "CMDatabase" }
  })
  ```

  These are the City's **licensed CycloMedia B2B credentials**, shipped in
  plaintext (no AES wrapper, unlike Istanbul's `gak/gal/gam` labels). After
  `init`, the Street Smart SDK fetches panorama imagery and the recordings
  coverage layer directly from CycloMedia's infrastructure
  (`*.cyclomedia.com`), not from any phila.gov host.
- **The coverage (recordings) layer — CycloMedia's gated WFS:** the bundle
  constructs a recordings client
  `new GR("https://atlasapi.cyclomedia.com/api/recording/wfs",
  "APIBasicForPhilly", "Philly@Basic215", 4326)` and calls
  `getRecordings(bounds, cb)`, which builds a WFS `GetFeature` request
  (`service="WFS" version="1.1.0" outputFormat="text/xml; subtype=gml/3.1.1"`)
  filtered to the current map `bbox` (SW/NE corners), POSTs it to the
  CycloMedia WFS with HTTP Basic auth (the embedded credentials), parses the
  GML `<Feature>`s into `{imageId, lng, lat}`, and renders them as an
  OpenLayers point layer. **This is the only "where imagery exists" signal in
  the entire viewer, and it is CycloMedia's commercial endpoint.**
- **Live auth probe (2026-05-28):**
  `GET https://atlasapi.cyclomedia.com/api/recording/wfs?service=WFS&request=GetCapabilities`
  → **HTTP 401** (unauthenticated). The WFS is reachable only with the City's
  CycloMedia Basic-auth credentials.
- **Why the credential-replay path is off-limits (the single hard blocker).**
  The credentials are trivially extractable (plaintext in the JS). A scraper
  *could* POST WFS `GetFeature` requests over a Philadelphia tile grid to
  enumerate every recording point. **Doing so would (a) use the City of
  Philadelphia's licensed commercial credentials against the third-party owner
  of the imagery (CycloMedia), and (b) violate CycloMedia's Street Smart /
  Recording Locations / Coverage Service commercial ToS, which restricts use to
  the licensed customer's embed/viewer context.** This project is a polite,
  public-coverage scraper; it does not impersonate a B2B client of a
  third-party imagery vendor. Per `CLAUDE.md` ("skip paid-B2B-only providers")
  and `docs/PLAN.md` §13 ("CycloMedia limited to the public Philadelphia viewer
  only"; "drop any that explicitly forbid automation"), this path is
  **non-negotiably out of scope** — exactly as ruled in the `istanbul_ibb`
  subplan.
- **No City open-data fallback exists.** Verified there is no legitimately
  public, City-published coverage layer:
  - **OpenDataPhilly "StreetSmartPHL"** (`opendataphilly.org/datasets/
    street-smart-phl/`) is a street-operations web app (closures / sweeping /
    snow / paving), **not** CycloMedia street imagery. No coverage/extent feed.
  - **DataBridge GeoServer** (`citygeo-geoserver.databridge.phila.gov/
    geoserver/wms`) is used by the viewer only for basemap/zoning raster
    tiles — not street-imagery coverage.
  - No City ArcGIS Online Feature Service / Map Service, OpenDataPhilly
    dataset, or PASDA layer publishes CycloMedia recording points or capture
    extent under an open license. The "Recording Locations Service" and
    "Coverage Service" named in CycloMedia/Esri marketing are CycloMedia's own
    *paid API products*, not City open data.

### Provider properties (the slots the template expects)

- **Homepage / public viewer URL:**
  - Standalone viewer: `https://cyclomedia.phila.gov/`
  - Embedded in the property viewer: `https://atlas.phila.gov/` (street-view
    panel).
- **Tier:** **T3** (matches `docs/PLAN.md` §2).
- **Coverage endpoint(s):**
  - The only coverage-shaped endpoint is **CycloMedia's gated commercial WFS**:
    ```
    POST https://atlasapi.cyclomedia.com/api/recording/wfs
    ```
    - **HTTP method:** `POST`, body = WFS 1.1.0 `GetFeature` XML for the
      recordings type, filtered to a `bbox` (map SW/NE corners). The viewer
      requests it per current map extent.
    - **Auth required:** **HTTP Basic auth** with the City's licensed
      CycloMedia credentials (`APIBasicForPhilly` / `Philly@Basic215`).
      Unauthenticated requests return **HTTP 401**.
    - **Response:** GML 3.1.1 `FeatureCollection`; each feature carries an
      `imageId` and a point geometry; the viewer reduces it to
      `{imageId, lng, lat}` in EPSG:4326.
  - There is **no City-hosted, unauthenticated coverage endpoint** (no
    OpenDataPhilly recording-locations dataset, no public ArcGIS Feature
    Service, no public extent feed). Unlike `istanbul_ibb`, there is not even a
    public random-sampler endpoint.
- **Coordinate scheme:** the WFS payload is EPSG:4326 (`[lng, lat]`); the viewer
  SRS is `EPSG:4326`; the project coverage grid would be `web_mercator`
  (EPSG:3857) as usual. **Not relevant** given the defer verdict.
- **Zoom range / tile size / response format:** **not applicable** — coverage is
  a WFS feature query, not a tile scheme. (Were this ever scraped via the
  forbidden path, it would be a bbox-windowed WFS, gridding Philadelphia into
  small bbox windows; this is documented only to be explicit that it is not
  permitted.)
- **Auth:** **gated** — HTTP Basic with embedded CycloMedia B2B credentials.
  **No `.env` key is proposed**, because the only endpoint requiring auth is
  CycloMedia's commercial WFS and we will not drive it. (Do *not* add an
  `.env` key holding the extracted CycloMedia password — that would institutionalize
  the ToS violation.)
- **Presence rule:** "imagery exists here" ⇔ a recording feature is returned by
  CycloMedia's WFS for that bbox. Because that signal is only obtainable via the
  gated commercial endpoint, there is **no permissible presence rule** for this
  provider today.
- **robots.txt / ToS notes; observed rate limit:**
  - `https://cyclomedia.phila.gov/robots.txt` → **HTTP 404** (no robots file;
    the SPA serves HTML for unknown paths). `https://atlas.phila.gov/robots.txt`
    → returns the SPA HTML (HTTP 200, not a real robots file). Neither host's
    robots.txt forbids anything — but robots permission on the *City* host is
    moot, because the coverage data is fetched from CycloMedia's host, not from
    a phila.gov host.
  - `https://atlasapi.cyclomedia.com/robots.txt` → **HTTP 404** (`{"statusCode":
    404,"message":"Resource not found"}`). The dispositive constraint is
    **CycloMedia's commercial Street Smart / Recording Locations / Coverage
    Service license**, which restricts automated access to the licensed
    customer's viewer context — it forbids exactly the bulk-coverage scrape we
    would otherwise want.
  - **Observed rate limit:** not measured (we did not exercise the gated WFS,
    by design). The unauthenticated WFS probe returned 401 immediately.
- **Known quirks / gotchas:**
  - **Plaintext credentials are a trap, not an opportunity.** Philadelphia
    ships `username`/`password`/`apiKey` in cleartext in the JS bundle. Their
    being trivially readable does **not** make using them permissible — they are
    *CycloMedia's* B2B credentials, owned by a third-party imagery vendor, and
    replaying them is a ToS violation. Do not extract, store, or use them.
  - **"StreetSmartPHL" name collision.** The OpenDataPhilly dataset
    "StreetSmartPHL" is street-operations data (closures/sweeping/snow/paving),
    **not** the CycloMedia "Street Smart" street imagery. Do not conflate them.
  - **Atlas embeds EagleView too.** `atlas.phila.gov` also embeds EagleView
    oblique/aerial imagery — that is *aerial*, not street-level SVI, and is a
    separate commercial vendor; out of scope here.
  - **Same pattern as `istanbul_ibb`.** This is the second instance of the
    "public city viewer over CycloMedia Street Smart" pattern. Treat any future
    provider matching this shape (city viewer → `StreetSmartApi.js` →
    `*.cyclomedia.com` recordings WFS with embedded credentials) as DEFER/DROP
    by default.

### Coverage extent (administrative, not scraped)

| metric | value |
| --- | --- |
| Region | City of Philadelphia, Pennsylvania, USA (Philadelphia County) |
| Rough bbox (lon min/max) | `-75.29 W`, `-74.95 W` |
| Rough bbox (lat min/max) | `39.86 N`, `40.14 N` |
| Street-miles captured (City/CycloMedia/Esri case study) | ~3,000 mi |
| Coverage SRS in viewer | `EPSG:4326` |

(Extent is the administrative city footprint from public sources, **not** a
scrape of the recordings WFS — that WFS was not driven, by design.)

## 3. Test plan (write these FIRST — red before green)

> **The §4 plan is "defer/drop; do not implement now". There is no permissible
> coverage endpoint to test against. This §3 documents the test plan that a
> would-be implementation would use IF AND ONLY IF a *City-published open
> coverage layer* later appears (see §6 re-probe). Until then, the only test to
> write is the guardrail test, which can and should be added regardless to
> prevent any future code from sliding into the CycloMedia-credential path.**
> Unit tests must not hit the network; decode recorded fixtures under
> `tests/fixtures/cyclomedia_phila/`.

Tests (`tests/test_providers_cyclomedia_phila.py`):

- [ ] `test_cyclomedia_phila_no_credential_replay` — **the hard guardrail.**
      If/when a `cyclomedia_phila` provider module exists, assert it does NOT
      import `requests`/`urllib` directly, does NOT reference the strings
      `APIBasicForPhilly`, `Philly@Basic215`, the embedded `apiKey` value,
      `atlasapi.cyclomedia.com`, `recording/wfs`, `StreetSmartApi`, or
      `getRecordings`, and contains no HTTP Basic auth header construction —
      i.e. the implementation has not slipped into the ToS-hostile
      credential-replay path. **This is non-negotiable.** (This test can be
      added now as a regression guard even though no module exists yet — it
      should assert the module is absent OR clean.)

The following tests apply ONLY if a City-published open coverage layer is later
found (re-probe trigger in §6) and the provider is re-approved as a clean
`json_api` / `vector_geojson` / `coverage_json` source:

- [ ] `test_cyclomedia_phila_registers` — importing
      `coverage_acquisition.providers.cyclomedia_phila` registers
      `"cyclomedia_phila"` in `PROVIDERS`; one source.
- [ ] `test_cyclomedia_phila_source_kind` — the source `kind` matches the
      newly-found open layer's shape (`json_api` for an ArcGIS Feature Service
      query, `vector_geojson` for a GeoJSON download, or `coverage_json` for a
      static committed point list).
- [ ] `test_cyclomedia_phila_coordinate_scheme` —
      `PROVIDER.coordinate_scheme == "web_mercator"` (output grid; points
      supplied in WGS84).
- [ ] `test_cyclomedia_phila_decode_*` — a parser run on a recorded fixture of
      the City open layer's response yields `pano_record`/point rows with
      `provider == "cyclomedia_phila"`, numeric `lat`/`lon` inside the
      Philadelphia bbox, and (if present) an ISO `timestamp`.
- [ ] `test_cyclomedia_phila_bbox_filter` — points outside
      `-75.35 ≤ lon ≤ -74.90, 39.80 ≤ lat ≤ 40.20` are dropped (defensive).
- Fixtures: small recorded samples under `tests/fixtures/cyclomedia_phila/`
  (only from a *City open* endpoint, never from the CycloMedia WFS).

## 4. Implementation subplan (steps for the implementer — TDD)

**The recommended action right now is _no implementation_ (DEFER / DROP).** The
only coverage signal is CycloMedia's gated commercial WFS, and driving it via
the City's embedded B2B credentials is an explicit ToS violation and a hard
project guardrail. There is no City-published open coverage layer to implement
against.

- [ ] **Source kind: N/A today.** No permissible source exists.
- [ ] **Do NOT** add `src/coverage_acquisition/providers/cyclomedia_phila.py`.
- [ ] **Do NOT** extract, store, hardcode, or `.env`-stash the CycloMedia
      credentials (`APIBasicForPhilly` / `Philly@Basic215` / apiKey).
- [ ] **Do NOT** call `https://atlasapi.cyclomedia.com/api/recording/wfs`
      (or any `*.cyclomedia.com` recordings/coverage endpoint) from project
      code, scripts, or tests.
- [ ] **Optional now:** add the `test_cyclomedia_phila_no_credential_replay`
      guardrail test (§3) as a standing regression guard, mirroring
      `test_istanbul_ibb_no_cyclomedia_decryption`.

**If (and only if) a City-published OPEN coverage layer is later found** (§6
re-probe returns positive — e.g. an OpenDataPhilly recording-locations dataset
or a public ArcGIS Feature Service of CycloMedia capture points/extent under an
open license), then a clean implementation would be:

- [ ] Pick the existing source kind matching the open layer (`json_api` for an
      ArcGIS Feature Service `query` endpoint; `vector_geojson` for a GeoJSON
      download; `coverage_json` for a static committed point file — mirror
      `dprk360`). No new source kind expected.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/cyclomedia_phila.py`
      (`ProviderDefinition`, self-registering, `coordinate_scheme="web_mercator"`,
      `default_display_zoom=14`), reading **only** the City open endpoint.
- [ ] Implement until §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `-75.18 39.94 -75.14 39.97` (**Center City
      Philadelphia**, ~39.95 N / -75.16 W) — confirm points land on Center City
      streets, not the Delaware/Schuylkill rivers.
- [ ] Rasterize the pilot subset to a z14 COG (EPSG:3857, `uint8`,
      `1=covered / 255=nodata`); sanity-check.
- [ ] Full extent: Philadelphia County bbox `-75.29 39.86 -74.95 40.14`
      (a feature query / GeoJSON download, not tile discovery, if the open layer
      is a feature service).
- [ ] Create/update the STAC item; update inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> **All §5 criteria are gated on the §4 decision. The current decision is
> DEFER/DROP — there is no provider to verify.** The only thing verifier should
> confirm today is the guardrail:

- `test_cyclomedia_phila_no_credential_replay` passes (or trivially holds
  because no module exists) — the repo contains **no** code that references the
  embedded CycloMedia credentials, the CycloMedia recordings WFS, or
  `StreetSmartApi`/`getRecordings`, and no HTTP Basic auth against
  `*.cyclomedia.com`.

If a City open layer is later found and the provider is re-approved and
implemented:

- All §3 tests pass; `coverage_acquisition.providers.cyclomedia_phila` imports
  and self-registers; CI smoke test passes.
- The source reads **only** the City open endpoint (never the CycloMedia WFS);
  decodes to point/`pano_record` rows with `provider == "cyclomedia_phila"`,
  numeric `lat`/`lon` inside the Philadelphia bbox.
- The Center City pilot subset rasterizes to a valid z14 COG (CRS EPSG:3857,
  `uint8`, covered pixels > 0, covered cells land on Center City streets — not
  the Delaware or Schuylkill rivers).
- Fetches via `polite.polite_fetch` with a descriptive `User-Agent`; no bare
  `urllib`/`requests`.
- Module docstring documents: City-published-open-layer source only; CycloMedia
  imagery is **not** downloaded and CycloMedia's gated WFS is **not** driven;
  ToS caveats recorded.

## 6. Status log

- `2026-05-28` scout: drafted as **DEFER / DROP**. Findings (live probing):
  - **Public viewer:** `https://cyclomedia.phila.gov/` (Vite/React + OpenLayers
    SPA) loads CycloMedia Street Smart SDK from
    `https://streetsmart.cyclomedia.com/api/v24.5/StreetSmartApi.js`. Also
    embedded inside `https://atlas.phila.gov/` (which separately embeds
    EagleView aerial/oblique imagery).
  - **Street Smart init** uses **plaintext** credentials in the JS bundle:
    `username:"APIBasicForPhilly"`, `password:"Philly@Basic215"`,
    `apiKey:"GfElS3oRuroNivgtibsZqDkpCvItyPUNuv0NmXglen8puXoJanEVarsZyns9ynkJ"`,
    `srs:"EPSG:4326"`.
  - **Coverage layer = CycloMedia's gated WFS:** the bundle builds a recordings
    client against `https://atlasapi.cyclomedia.com/api/recording/wfs` with
    HTTP Basic auth (the embedded credentials) and a WFS 1.1.0 `GetFeature`
    bbox query, parsing GML into `{imageId, lng, lat}`. Unauthenticated probe
    of that WFS → **HTTP 401**.
  - **No City open coverage layer.** OpenDataPhilly "StreetSmartPHL" is
    street-operations data (closures/sweeping/snow/paving), NOT CycloMedia
    street imagery. DataBridge GeoServer
    (`citygeo-geoserver.databridge.phila.gov/geoserver/wms`) is used only for
    basemap/zoning tiles. No public ArcGIS Feature Service / open dataset / PASDA
    layer publishes CycloMedia recording points or capture extent under an open
    license. CycloMedia's "Recording Locations Service" / "Coverage Service" are
    CycloMedia's *paid* API products.
  - **robots.txt:** `cyclomedia.phila.gov/robots.txt` → 404;
    `atlas.phila.gov/robots.txt` → SPA HTML (no real robots); 
    `atlasapi.cyclomedia.com/robots.txt` → 404. Dispositive constraint is
    CycloMedia's commercial Street Smart ToS, not robots.
  - **Verdict:** the only coverage signal is CycloMedia's gated commercial WFS,
    reachable only by replaying Philadelphia's licensed B2B credentials — a hard
    ToS guardrail (`CLAUDE.md` "skip paid-B2B-only providers"; `docs/PLAN.md`
    §13 "CycloMedia limited to the public Philadelphia viewer only"). Same
    pattern and same verdict as `istanbul_ibb`. **Defer/drop; do not open an
    implementation issue.**
- `2026-05-28` approval: **pending** (awaiting user review).
- `YYYY-MM-DD` re-probe / re-approval: notes appended here.

### Re-probe checklist (when to revisit)

Run these every 6–12 months until at least one returns a positive answer (a
positive on any of these would flip the verdict toward a clean, in-scope
implementation):

1. **OpenDataPhilly** — search `opendataphilly.org` for "cyclomedia",
   "geocyclorama", "street level imagery", "recording locations", "panorama
   coverage". If the City ever publishes a recording-locations / capture-extent
   point or polygon dataset under the City of Philadelphia open license, that is
   a clean `json_api` / `vector_geojson` / `coverage_json` source.
2. **City ArcGIS Online / DataBridge** — search `phl.maps.arcgis.com` and the
   DataBridge service catalog for a CycloMedia coverage Feature Service / Map
   Service exposed publicly (no token). If found and open-licensed, evaluate it.
3. **PASDA** — search `pasda.psu.edu` for a Philadelphia CycloMedia coverage /
   recording-locations layer published under an open license.
4. **Bundle change** — re-fetch `cyclomedia.phila.gov/assets/index-*.js` and
   grep for any phila.gov-hosted (not `*.cyclomedia.com`) recordings/coverage
   endpoint. If the City ever proxies recordings through its own open,
   unauthenticated host, evaluate it.
5. **Credentials path stays OUT regardless.** Even if probing is easy, the
   `atlasapi.cyclomedia.com/api/recording/wfs` credential-replay path is
   permanently off-limits and is NOT a re-probe trigger.

---

### Open questions for the reviewer

1. **Defer/drop confirmation.** Recommended posture is **defer/drop**: the only
   coverage signal is CycloMedia's gated commercial WFS, and there is no
   City-published open coverage layer. Confirm we leave this deferred (re-probe
   per §6) rather than implementing now.
2. **CycloMedia credential-replay is OUT — hard guardrail.** Philadelphia ships
   its CycloMedia B2B credentials in *plaintext*. Confirm the explicit guardrail:
   even though the credentials are trivially readable, we will NOT extract,
   store, `.env`-stash, or use them, and will NOT drive
   `atlasapi.cyclomedia.com/api/recording/wfs`. This mirrors the
   `istanbul_ibb` ruling and is non-negotiable.
3. **Standing guardrail test.** Recommend adding
   `test_cyclomedia_phila_no_credential_replay` (§3) as a regression guard now,
   even though no provider module exists, to prevent future drift into the
   ToS-hostile path. Confirm.
4. **Re-probe cadence.** Proposed: every 6–12 months, run the §6 checklist
   (especially OpenDataPhilly / PASDA for a City-published recording-locations
   layer). Confirm cadence.

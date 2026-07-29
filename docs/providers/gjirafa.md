# [T3] Provider: Gjirafa Maps / PikBiz "Pamje 360°" (`gjirafa`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER / DROP, on TWO independent grounds:

  (1) NO STREET-LEVEL COVERAGE LAYER EXISTS. Gjirafa's "Pamje 360°" was never
      a continuous street-view coverage product. It is a set of *per-business*
      360° photos attached to POI records in the Gjirafa.biz (formerly
      "GjirafaPikBiz") business directory. There is no coverage tile layer, no
      vector MVT panorama-points layer, and no JSON "is-there-a-panorama-here"
      API. The only proximity-discovery endpoint, `/Biznesi/_explore`, returns
      an HTML fragment of *nearby businesses that have a 360 photo*, keyed by a
      single lat@lng and paginated by a `step` counter — a POI feed, not a
      street network. Coverage = "businesses that opted into a 360 tour", which
      is a paid/listing feature, not a road-network walk-through. There is
      nothing to rasterize into a meaningful street-level presence grid.

  (2) ACCESS IS HARD-BLOCKED AND CRAWLING IS EXPLICITLY PROHIBITED. The host
      `gjirafa.biz` now sits behind Cloudflare and returns a hard
      "Sorry, you have been blocked" page (not a solvable challenge) to
      non-browser traffic; the dedicated map/route subdomains
      (`harta2.gjirafa.biz`, `route.gjirafa.biz`) and the legacy app host
      (`gjirafapikbiz.cloudapp.net`) no longer resolve in DNS at all. The
      archived `gjirafa.biz/robots.txt` opens with
      `# Notice: Crawling Gjirafa.biz is prohibited unless you have express
      written [permission]`. Per `CLAUDE.md` ("respect robots.txt and provider
      ToS … drop any that explicitly forbid automation") this provider is out
      of scope regardless of the data shape.

This subplan documents the investigation and the conditional plan that would
apply ONLY IF Gjirafa ever exposes a first-party, public, scrapable
street-level coverage layer AND relaxes the crawl prohibition. No issue /
branch / code should be created now.
-->

## 1. Summary

Gjirafa (`https://gjirafa.com/`, corporate `https://about.gjirafa.com/`) is a
Kosovo-based search / e-commerce / media technology company ("the Google of the
Balkans") serving Kosovo, Albania, and North Macedonia. Around 2016 it ran
camera cars through Pristina and other towns and launched a street-level "Street
View" effort branded **"Pamje 360°"** ("360° view"), integrated into its
business-directory product **GjirafaPikBiz** (now the **Gjirafa.biz** maps
directory). The viewer ran a Leaflet map over an OpenStreetMap basemap
(`harta2.gjirafa.biz/osm_tiles/{z}/{x}/{y}.png`) with a custom routing engine
(`route.gjirafa.biz`).

**However, scouting concludes Gjirafa should be DEFERRED / DROPPED**, for two
independent reasons, either of which alone is disqualifying:

1. **No street-level coverage layer.** "Pamje 360°" is a **per-business POI
   panorama** feature, not a continuous street-view product. Each business that
   opted in carries a single `pano` id (a capture frame such as
   `camera-20160819-104242-000005041`), loaded on demand from
   `GET /Biznesi/_pamje360?pano=<panoId>` as an HTML fragment. There is no
   coverage tile/MVT/GeoJSON layer enumerating where panoramas exist; the only
   proximity-discovery call, `GET /Biznesi/_explore?location=<lat>@<lng>`,
   returns an HTML list of nearby 360-enabled *businesses*, not a road network.
   The "coverage" this would yield is the set of businesses that bought a 360
   tour — a directory feature, not street-level imagery presence.
2. **Hard-blocked + crawl explicitly prohibited.** `gjirafa.biz` returns a
   Cloudflare hard-block ("Sorry, you have been blocked") to non-browser
   traffic; the map/route subdomains and the legacy `gjirafapikbiz.cloudapp.net`
   app host no longer resolve; and the site's `robots.txt` states crawling is
   **prohibited without express written permission**. Per `CLAUDE.md` this is
   out of scope.

Note on ASIG overlap: Gjirafa's three-country footprint (Kosovo, Albania, North
Macedonia — the viewer literally guards on *"Ju nuk jeni brenda Kosovës,
Shqipërisë, apo Maqedonisë"*, "You are not within Kosovo, Albania, or North
Macedonia") **overlaps geographically with ASIG (Albania)**, but the two are
unrelated systems (ASIG is the Albanian State Authority for Geospatial
Information; Gjirafa is a private directory's POI-360 feature). Treat them as
separate providers; this verdict concerns Gjirafa only and does not affect the
ASIG scout.

See §2 for evidence and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: POI-attached 360 photos (no street-level coverage layer) + hard-blocked & crawl-prohibited — DEFER / DROP

Applying the standard scouting priority (raster overlay → vector MVT → coverage
JSON / point-probe → discoverable panorama viewer):

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.** The
   only raster the viewer loads is the generic **OSM basemap**
   (`harta2.gjirafa.biz/osm_tiles/{z}/{x}/{y}.png`), which is map background,
   not a Gjirafa coverage signal.
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.** The map is plain
   Leaflet with marker clustering; no MVT panorama-points source.
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — NO.** There is no "is-there-a-panorama-at-this-lat/lng" API. The nearest
   thing, `/Biznesi/_explore?location=<lat>@<lng>`, returns an **HTML fragment**
   of nearby *360-enabled businesses* (appended into `#cityImageHolder`,
   paginated by a `step` counter), and `/Biznesi/KrejtLokacionet` is a
   category-filtered **business search** (POST). Both are POI directory feeds,
   not a street-view coverage layer.
4. **A panorama viewer one could discovery-probe? — only per-business.** The
   "Pamje 360°" button (`.streetview .goTo360`, `#panoIDexplorer`) fires
   `GET /Biznesi/_pamje360?pano=<panoId>` where `panoId` comes from the
   business record (`#bizDetailsPano`); businesses without a 360 tour carry an
   empty `data-pano=""`. The panorama is keyed to a POI, not a road location.

- **Homepage / public viewer URL:**
  - Corporate: `https://about.gjirafa.com/` (where `gjirafa.com` /
    `www.gjirafa.com` now 301-redirect).
  - Business directory + maps (successor to "GjirafaPikBiz"):
    `https://gjirafa.biz/` — **Cloudflare hard-blocked** to non-browser traffic.
  - Per-business "Pamje 360°" deep-links (front-end only; backend gated now):
    `https://gjirafa.biz/<business-slug>/?p360=1` and the richer pano-startup
    form
    `https://gjirafa.biz/<slug>/?sv_startup_pano=<panoId>&sv_startup_heading=<h>&sv_startup_tilt=<t>&sv_startup_zoom=<z>`
    — e.g. `…/accounting-house-1/?sv_startup_pano=camera-20160819-104242-000005041&sv_startup_heading=10&sv_startup_tilt=-2.4&sv_startup_zoom=120`.
  - Legacy app host (2016 era, now dead in DNS):
    `http://gjirafapikbiz.cloudapp.net/` (Azure cloud app).
  - Auth/SSO: `https://identity.gjirafa.com/Account/Login` /
    `http://sso.gjirafa.com/Account/Login` (referenced by the detail page;
    some actions route through it).
  - Tier: **T3** ("likely / unverified / gated" in `docs/PLAN.md` §2 and
    `data/external/street_view_providers.xlsx`).

- **How the viewer was investigated.** Live hosts were probed directly with a
  realistic browser User-Agent. Because `gjirafa.biz` is Cloudflare-blocked, the
  viewer JS and business-page HTML were read from Internet Archive (Wayback
  Machine) `id_` raw snapshots, which preserve the exact served bytes
  (note: Wayback `id_` serves gzip-encoded payloads that must be decompressed
  before reading). Inspected artefacts: the Leaflet "map" script bundle
  `/bundles/map?v=…` in both a 2016 build (≈204 KB, served from
  `gjirafapikbiz.cloudapp.net`) and a 2023 build (≈207 KB, from `gjirafa.biz`),
  plus 2017 and 2023 business-detail pages with `?p360=1`. DNS was checked for
  every candidate map subdomain.

- **Live probe results (2026-05-28):**

  | Host / URL | Result | Meaning |
  | --- | --- | --- |
  | `maps.gjirafa.com`, `map.gjirafa.com`, `pikbiz.gjirafa.com`, `harta.gjirafa.com` | **No DNS record** | dedicated map subdomains never existed / removed |
  | `gjirafa.com`, `www.gjirafa.com` | HTTP 200 → 301 to `about.gjirafa.com` | corporate site; no map product here |
  | `gjirafa.biz/` | **HTTP 403 Cloudflare "Sorry, you have been blocked"** (and a 302 to a `bisko` / `une.bisko.io` cookie-gate via browser) | site hard-walls bots |
  | `gjirafa.biz/Biznesi/_pamje360?pano=1` | 302 → Cloudflare/bisko gate | panorama endpoint unreachable to automation |
  | `harta2.gjirafa.biz/osm_tiles/14/x/y.png` | **No DNS record** (HTTP 000) | basemap tile host gone |
  | `route.gjirafa.biz/route/v1` | **No DNS record** (HTTP 000) | routing host gone |
  | `gjirafapikbiz.cloudapp.net` | **No DNS record** (HTTP 000) | legacy app host decommissioned |

  Wayback history shows `gjirafa.biz/<slug>/?p360=1` pages returned HTTP 200 as
  recently as 2023-01-25 but **302** (to the Cloudflare/bisko gate) by
  2024-12-24 — i.e. the directory (and with it the 360 feature) went behind the
  bot wall sometime in 2023–2024.

- **What the viewer fetches** (from the `/bundles/map` Leaflet bundle, 2016 and
  2023 builds — endpoints identical across both):
  - **Per-business panorama (the actual 360 feature):**
    `GET /Biznesi/_pamje360?pano=<panoId>` — returns an **HTML fragment** that
    is injected into `#sw_holder` / prepended to `#map-wrapper`. `panoId` is the
    business's `data-pano` (sourced from `#bizDetailsPano`); empty ⇒ no 360.
  - **Nearby-360 discovery (POI feed, not a coverage layer):**
    `GET /Biznesi/_explore?location=<lat>@<lng>&isDetails=<bool>&step=<n>` —
    returns an **HTML fragment** of nearby businesses that have a 360 view,
    appended into `#cityImageHolder` and paginated via `stepGetNewPikatView360`.
  - **Business search (not panorama-specific):**
    `POST /Biznesi/KrejtLokacionet` ("all locations") with form fields
    `kategoriId, nenkategoriId, nenkategori2Id, query, lokacioni, radius,
    coordinates, url` — the category/area directory search.
  - **Basemap (generic, not a Gjirafa signal):**
    `https://harta2.gjirafa.biz/osm_tiles/{z}/{x}/{y}.png` (web-mercator XYZ
    OSM raster), routing at `https://route.gjirafa.biz/route/v1` (OSRM-style).
  - **Region guard:** the UI shows
    *"Ju nuk jeni brenda Kosovës, Shqipërisë, apo Maqedonisë"* when outside the
    three-country service area, confirming the KS/AL/MK footprint.

- **Coverage endpoint(s):** **None.** No raster overlay, no MVT, no
  coverage/point-probe JSON. The panorama is keyed to a business `panoId`, and
  the only spatial-discovery call (`/Biznesi/_explore`) returns HTML POI cards,
  not a presence grid.

- **Coordinate scheme:** the basemap is **web_mercator** (standard OSM XYZ);
  the panorama/explorer calls take **WGS84 lat/lng** (`<lat>@<lng>`), not tile
  x/y. Irrelevant for harvesting since there is no coverage layer.
- **Zoom range / tile size / response format:** N/A for coverage — there is no
  coverage tile pyramid. (The OSM basemap is the usual 256-px z0–z19, but that
  is third-party background, not Gjirafa imagery presence.) Panorama responses
  are HTML fragments; `pano` ids look like sequential camera frames
  (`camera-YYYYMMDD-HHMMSS-NNNNNNNNN`) with viewer params
  `heading` / `tilt` / `zoom`.
- **Auth:** the public viewer needed **no token** for `_pamje360` historically,
  but the detail page wires an SSO login (`identity.gjirafa.com` /
  `sso.gjirafa.com`) and the whole site is now behind a Cloudflare/`bisko`
  cookie gate. No clean `.env` token mechanism exists; **N/A** (not in scope).
- **Presence rule:** there is no presence API to read. "Has a 360" was a
  per-business boolean (`data-pano` non-empty); deriving street-level coverage
  from a directory of opt-in business panoramas would misrepresent it as a
  street-view product.

- **robots.txt / ToS notes; observed rate limit:**
  - Archived `https://gjirafa.biz/robots.txt` (latest snapshot 2025-04) opens
    with `# Notice: Crawling Gjirafa.biz is prohibited unless you have express
    written [permission]`, then lists named bots with `Crawl-delay: 300` — i.e.
    **automated crawling is explicitly disallowed without written consent.**
  - Live `gjirafa.biz` returns a Cloudflare **hard block**
    ("Sorry, you have been blocked"), and routes browsers through a `bisko` /
    `une.bisko.io` cookie/identity gate — signalling automated access is not
    permitted.
  - Per `CLAUDE.md` ("respect `robots.txt` and provider ToS; drop any that
    explicitly forbid automation") this provider must not be scraped.

- **Known quirks / gotchas (for any future re-scout):**
  - **"Pamje 360°" ≠ street view.** Do not be misled by press coverage calling
    it Kosovo's "Street View" or by the camera-car story (2016): the product as
    shipped is a **business-directory 360 photo** feature, one panorama per
    opted-in POI, surfaced via `/Biznesi/_pamje360?pano=<id>`. There is no
    road-network coverage layer to harvest, even setting the access block aside.
  - The `sv_startup_pano=camera-…` deep-link form *looks* like a navigable
    street-view URL, but it just boots the per-business panorama viewer at a
    given heading/tilt/zoom; it is not evidence of a continuous coverage tileset.
  - All dedicated map infrastructure subdomains (`harta2.gjirafa.biz`,
    `route.gjirafa.biz`) and the legacy `gjirafapikbiz.cloudapp.net` app host
    **no longer resolve** — the maps stack has been substantially retired or
    folded into the gated `gjirafa.biz` directory.
  - Geographic overlap with **ASIG (Albania)** exists (both cover Albania), but
    they are unrelated systems — scout/triage ASIG independently.
  - If ever revisited, the only plausibly-coverage-shaped endpoint is
    `/Biznesi/_explore` (nearby-360 POI feed), which returns **HTML, not JSON**
    and would need a new `discovery_kind` plus HTML parsing — and even then it
    is POI-360, not street-level. Treat that as a fundamentally different
    "POI panorama directory" product, not an SVI street-coverage source.

## 3. Test plan (write these FIRST — red before green)

> **No tests should be written.** There is no in-scope coverage layer, and the
> site explicitly prohibits crawling and hard-blocks bots. The list below is the
> **conditional test plan** that would apply *only if* §7 unblocks — i.e. if
> Gjirafa publishes a genuine first-party street-level coverage layer (tiles /
> MVT / JSON) AND relaxes the crawl prohibition. Until then this section is a
> placeholder, not a work item.

- [ ] `test_gjirafa_url_build` — coverage endpoint URL/template fills correctly
      for a sample input (only meaningful once a real coverage endpoint exists).
- [ ] `test_gjirafa_decode_present` — recorded fixture for a covered location
      decodes to `present`.
- [ ] `test_gjirafa_decode_empty` — recorded fixture for an uncovered location
      decodes to `empty`.
- [ ] `test_gjirafa_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_gjirafa_robots_allowed` — assertion that the chosen prefix is *not*
      disallowed by the live `gjirafa.biz/robots.txt` (currently this test would
      FAIL: crawling is prohibited).
- [ ] `test_gjirafa_user_agent` — fetch helper sends our descriptive
      `User-Agent` and honours the polite-fetch per-host throttle.
- [ ] Fixtures: small recorded response samples under `tests/fixtures/gjirafa/`
      (TBD — to be captured only if/when a public coverage endpoint exists).

## 4. Implementation subplan (steps for the implementer — TDD)

> **Status: blocked at step 0.** Do not start; see §7. The steps below are the
> conditional plan that would apply *only if* §7 unblocks.

- [ ] **Step 0 (precondition):** A fresh scout must confirm ALL of:
      (a) Gjirafa exposes a genuine **first-party street-level coverage layer**
      (a raster/MVT/JSON layer of where panoramas exist along roads — not the
      per-business `_pamje360` POI feature and not the `_explore` POI feed);
      (b) that layer is reachable by automation (no Cloudflare hard block /
      `bisko` gate); and
      (c) `gjirafa.biz/robots.txt` no longer prohibits crawling, OR written
      permission has been obtained.
      If any check fails, keep this subplan deferred. (As of 2026-05-28 all
      three fail.)
- [ ] Source kind: TBD by the restored layer's shape — `raster` if a coverage
      tile overlay appears; `vector_mvt` if a panorama-points MVT appears;
      `coverage_json` / `json_api` if a structured presence API appears.
      The historical `_explore` endpoint returns **HTML**, which no existing
      kind handles — that would be a separate foundation PR for an
      HTML-parsing discovery kind (and is discouraged: it is a POI-360 feed,
      not street-level coverage).
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/gjirafa.py` (`ProviderDefinition`),
      auto-discovered by the registry; reuse `geo.py` web-mercator helpers.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `21.150 42.645 21.185 42.675` (**central Prishtina /
      Pristina, Kosovo** — Sheshi Skënderbeu / Bulevardi Nëna Terezë core);
      expect coverage on the city-centre street grid if a street-level layer
      exists. Secondary pilots: Tirana, Albania (`19.80 41.31 19.84 41.34`) and
      Skopje, North Macedonia (`21.41 41.99 21.45 42.01`).
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on the
      Prishtina road network, not surrounding hills.
- [ ] Two-pass full extent: pass-1 region bbox `19.0 39.6 23.2 43.3`
      (Kosovo + Albania + North Macedonia) at discovery zoom `z=9`; pass-2 at
      the chosen source resolution. Coverage was historically **urban-only**
      (Prishtina and a few towns), so a coarse discovery zoom avoids over-probing
      rural areas — start at 9 and refine.
- [ ] Update the STAC item; update the inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> Only meaningful once §7 unblocks.

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- Pilot tiles/responses fetch & decode; coverage lands on Prishtina urban roads
  (not the surrounding terrain), and within the KS/AL/MK footprint.
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0.
- Fetches via `polite.polite_fetch`; descriptive `User-Agent`;
  `gjirafa.biz/robots.txt` re-checked at implementation time and shown to
  permit the chosen prefix (or written permission on file); ToS caveats
  documented in the module docstring.

## 6. Status log

- `2026-05-28` scout: drafted as **DEFER / DROP**, on two independent grounds.
  (1) No street-level coverage layer: Gjirafa's "Pamje 360°" is a per-business
  POI panorama feature served via `GET /Biznesi/_pamje360?pano=<panoId>` (HTML
  fragment), with the only spatial-discovery call `GET /Biznesi/_explore?
  location=<lat>@<lng>` returning an HTML list of nearby 360-enabled
  *businesses* — no raster/MVT/JSON coverage layer exists. (2) Access blocked &
  crawling prohibited: `gjirafa.biz` returns a Cloudflare hard-block; the
  map/route subdomains (`harta2.gjirafa.biz`, `route.gjirafa.biz`) and the
  legacy `gjirafapikbiz.cloudapp.net` app host no longer resolve in DNS; and
  `gjirafa.biz/robots.txt` states crawling is prohibited without express written
  permission. Wayback shows `?p360=1` pages were HTTP 200 in 2023-01 but 302
  (gated) by 2024-12. Three-country footprint (KS/AL/MK) overlaps ASIG (Albania)
  but is an unrelated system; ASIG triaged separately. Evidence captured via
  Wayback `id_` raw snapshots (Leaflet `/bundles/map` 2016 + 2023 builds, p360
  pages) and direct live/DNS probes.
- `2026-05-28` approval: < pending >

## 7. Recommendation

**Defer indefinitely — treat as effectively dropped for the current project
phase.** Specifically:

1. **Do not create a GitHub issue, branch, or PR for `gjirafa` now.** There is
   nothing in scope to implement: (a) there is no street-level coverage layer —
   only opt-in per-business 360 photos — and (b) the site explicitly prohibits
   crawling and hard-blocks automated access.
2. **Mark `gjirafa` as `skip` / `defunct-for-our-purposes` (or `paused`) in
   `data/external/street_view_providers.xlsx`**, with a note pointing at this
   subplan, the `robots.txt` "crawling prohibited" notice, the Cloudflare hard
   block, and the fact that "Pamje 360°" is a POI-attached photo feature, not a
   street-view coverage product.
3. **Revisit only if a re-scout** (suggested cadence: ~12 months, or triggered
   by an external report) finds ALL of: (a) a genuine first-party **street-level
   coverage layer** (raster/MVT/JSON of road-network panorama locations, not the
   `_pamje360` / `_explore` POI feeds); (b) reachable by automation (no
   Cloudflare hard-block / `bisko` gate); and (c) a `robots.txt` / ToS that
   permits crawling (or written permission obtained). Update §3 / §4 then and
   re-submit for the human-approval gate per `CLAUDE.md`.
4. **Keep separate from ASIG.** Gjirafa's footprint overlaps ASIG in Albania,
   but they are different systems; do not let this verdict influence the ASIG
   scout, and do not merge their coverage.
5. **If a future re-scout finds only the POI-360 directory** (`_explore` /
   `_pamje360`) rather than a street-level layer, it should still be **declined**
   as an SVI street-coverage source: a directory of opt-in business 360 photos
   is a points-of-interest panorama product, not street-level imagery presence,
   and rasterizing it would misrepresent coverage. (It could at most be noted as
   a POI-panorama dataset, out of scope for this project.)

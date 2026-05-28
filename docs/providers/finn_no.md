# [T3] Provider: FINN.no Kart "Gatebilde" (`finn_no`) — RECOMMEND DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DROP — out of scope (Google re-hoster).
FINN.no does NOT operate a first-party Norwegian street-level imagery (SVI)
coverage product. Its map viewer (`kart.finn.no`) has a "Gatebilde"
(street view) button, but that button is a `FINN.Map.Control.GoogleServiceButton`
whose only action is to deep-link / embed **Google Street View**
(`maps.google.no` / `google.no/maps` with a `cbll=` panorama parameter, or a
`/streetview/gsv.jsp` proxy that loads Google's `maps/api/js`). FINN's own tile
layers are a vector basemap (`finnvector`) and Blom aerial/ortho imagery
(`blomurbex.com`) — neither is street-level. The separate property-listing
"360 visning" feature is per-listing interior virtual tours (Matterport /
iGUIDE etc.) uploaded by estate photographers, not a coverage layer. Per
`CLAUDE.md` and `docs/PLAN.md` §2, Google re-hosters are explicitly out of
scope (flag as `google_rehost`). No issue / branch / code should be created.
Additionally, `kart.finn.no/robots.txt` explicitly bans Anthropic crawlers
(`Claude`, `ClaudeBot`, `anthropic-ai`) with `Disallow: /`, and
`www.finn.no/robots.txt` disallows `/map/` and `/map?` for all agents — so
even if a layer existed it would be robots-forbidden to automate.
-->

## 1. Summary

FINN.no (`https://www.finn.no/`) is Norway's dominant online classifieds and
marketplace (real estate, cars, jobs, consumer goods). It runs a long-standing
first-party map service, **FINN kart** (`https://kart.finn.no/`, with a newer
SPA at `https://www.finn.no/map/`), built on OpenLayers and historically
documented in a FOSS4G talk ("Kart på FINN.no — Fra CGI til slippy map"). An
old Wikipedia "List of street view services" entry claims "_Finn.no_ launched
their own Street View service … 12 cities and towns available so far," which is
the reason FINN.no entered our T3 triage as a candidate first-party SVI
provider.

**Scouting concludes FINN.no should be DROPPED as out of scope.** The live FINN
kart viewer does have a "Gatebilde" (street view) control, but reverse-
engineering its JavaScript (`map.min.js` / `mapApp.min.js`) shows the button is
a `GoogleServiceButton` that does nothing but hand off to **Google Street
View** — either a `cbll=` deep-link to `maps.google.no` / `google.no/maps`, or a
`/streetview/gsv.jsp` proxy that embeds Google's Maps JavaScript API (the page
config carries a `googlemaps_api_key`). FINN serves no first-party panorama
imagery and exposes no first-party street-level **coverage** layer (no panorama
tile endpoint, no MVT coverage layer, no point-probe JSON). FINN's own map tile
layers are a vector basemap (`finnvector`) and Blom aerial/ortho photos
(`s02.blomurbex.com`) — aerial, not street-level. The Wikipedia "12 cities"
claim is stale/unverified and is not borne out by the live viewer. The
property-listing "360 visning" is unrelated: per-listing interior virtual tours
(Matterport / iGUIDE / VISCAN etc.) attached to individual ads. There is
nothing first-party and street-level to scrape. See §2 for evidence and §7 for
the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: Google re-hoster + Blom aerial only — DROP (out of scope)

Applying the provider scouting priority in order (cf. kakao/naver/mapy/eniro):

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO**
   (first-party street-level). FINN's raster layers are `finnvector` basemap +
   Blom aerial/ortho, which are not street-level coverage.
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`kind="coverage_json"`/`json_api`)? — NO.**
4. **A first-party panorama viewer one could discovery-probe? — NO.** The
   "Gatebilde" viewer is Google Street View, reached via Google's own
   endpoints. FINN holds no panorama coverage of its own.

- **Homepage / public viewer URL:**
  - Marketplace: `https://www.finn.no/`.
  - Legacy map viewer (OpenLayers, server-rendered shell): `https://kart.finn.no/`.
  - Newer map SPA: `https://www.finn.no/map/` (robots-disallowed; see below).
  - Tier: **T3** (per `data/external/street_view_providers.xlsx` and
    `docs/PLAN.md` §2).

- **How the viewer was investigated (2026-05-28).** The `kart.finn.no/` HTML
  shell was fetched with a descriptive research `User-Agent` (no Cloudflare /
  bot challenge; HTTP 200, `Server: Apache`, ISO-8859-1, CR-delimited long
  lines). The page embeds an inline config object `FINN.mapSettings` and a
  `FINN.loader` script-package manifest. Following the manifest, the OpenLayers
  app bundles were fetched and decoded:
  - `https://kart.finn.no/rel/4248a3/pkg/js/loader.min.js` (bootstrap loader),
  - `https://kart.finn.no/rel/4248a3/pkg/js/finn/map.min.js` (~95 KB; map core),
  - `https://kart.finn.no/rel/4248a3/pkg/js/finn/mapApp.min.js` (~83 KB; app).
  The street-view control implementation was read directly from these bundles.
  WebSearch + the Wikipedia/OSM street-view service lists and the property
  "360 visning" providers were used for corroboration.

- **What the "Gatebilde" (street view) control actually does.** In
  `map.min.js` the control is `FINN.Map.Control.GoogleServiceButton`
  (`title:"Se gatebilde", contentHTML:"Gatebilde"`). Its `trigger()` resolves
  the map centre to WGS84 and then:
  - if `useApi` is set: navigates to `"/streetview/gsv.jsp?lat=…&lng=…"` — a
    server-side JSP proxy page that itself loads Google's Maps JS API
    (`jQuery.getScript("//maps.google.com/maps/api/js?v=3.22"+key…)` using the
    `googlemaps_api_key` from `FINN.mapSettings`); otherwise
  - it builds a Google deep-link: `https://maps.google.no/?ll=…&cbll=…&z=…`
    (the `cbll=` parameter is Google Street View's panorama-location param), or
    for the 3D variant `https://www.google.no/maps/@lat,lon,…`.
  `mapApp.min.js` confirms the analytics labels: the street-view click is logged
  as `{click: t("Going to StreetView","Google")}` and the 3D click as
  `t("Going to 3D","Google")`. **This is unambiguously a Google Street View
  hand-off, not first-party imagery.**

- **FINN's own tile layers (for completeness — none are street-level):**
  - `finnvector` — FINN's vector basemap (`mapType:"finnvector"` in config;
    `tile_server_url:"https://kart.finn.no"`).
  - Blom aerial/ortho — `FINN.Map.Layer.BingStyle` builds tile URLs from
    `//s02.blomurbex.com/v02/GetTile?USERTOKEN=…&SRS=EPSG:3857…` (Blom UrbEx
    aerial/oblique imagery; "flyfoto" in the FINN UI). Aerial, not street-level,
    and itself a third-party (Blom) product.
  - The page meta-description self-describes FINN kart as "en ledende norsk
    karttjeneste med kartsøk, **flyfoto** og annonser" (map search, **aerial
    photos**, listings) — no mention of street-level imagery.

- **The Wikipedia "12 cities own street view" claim is stale/unverified.**
  The English Wikipedia "List of street view services" entry states
  "_Finn.no_ launched their own Street View service. There are 12 cities and
  towns available so far," with past-tense, undated wording. The current
  OpenStreetMap "Street-level imagery services" wiki (which tracks *active*
  scrapable services) does **not** list FINN at all. The live viewer shows no
  first-party panorama layer or endpoint. If FINN ever self-hosted panoramas,
  the feature has since been replaced by the Google Street View hand-off
  observed today.

- **The property-listing "360 visning" is out of scope and unrelated.** FINN
  real-estate ads can carry a "360 visning" / virtual tour. Norwegian
  estate-photography vendors (Matterport, iGUIDE/PANOGRAM, VISCAN, Omvis,
  Scantour360, etc.) advertise that their 360/3D tours "can be shared on
  Finn.no." These are **per-listing interior virtual tours** uploaded per ad —
  not a street-level, location-indexed coverage layer, and explicitly excluded
  by the task scope ("NOT individual listing photos").

- **Coverage endpoint(s):** **None first-party street-level.** No FINN panorama
  tile layer, no MVT coverage layer, no point-probe JSON. Street view is
  Google's; the only first-party rasters are vector basemap + Blom aerial.

- **Coordinate scheme:** N/A for street-level (FINN's basemap/Blom use
  EPSG:3857 web mercator, but there is no street-level layer to fetch).
- **Zoom range / tile size / response format:** N/A (no street-level layer).
- **Auth:** N/A. (`kart.finn.no` sets a `map_jsession` cookie and ships a
  `googlemaps_api_key` for the Google embed, but no first-party SVI endpoint
  exists to authenticate against.)
- **Presence rule:** N/A — there is no first-party street-level response to parse.

- **robots.txt / ToS notes; observed rate limit (checked 2026-05-28):**
  - **`https://kart.finn.no/robots.txt` explicitly bans Anthropic crawlers:**
    it contains `User-agent: AnthropicBot` / `Claude` / `ClaudeBot` /
    `anthropic-ai`, each with `Disallow: /`. It also disallows `/ajax`, `/map/`,
    `/finn/`, `/pal/` for `User-agent: *`. Automating this host with an
    Anthropic-operated agent would violate the site's stated robots policy.
  - **`https://www.finn.no/robots.txt` disallows `/map/` and `/map?`** for
    `User-agent: *` (the new map SPA path), among many other Disallow rules.
  - These directives are decisive on their own: even if a first-party
    coverage layer existed, it would be robots-forbidden to scrape here.
  - No rate limit was probed (no in-scope endpoint to probe). Hosts are behind
    Google Cloud (`via: 1.1 google`, `backend: aurora`).

- **Known quirks / gotchas (for any future re-scout):**
  - The legacy `kart.finn.no` shell is ISO-8859-1 with CR-only line endings;
    naive line-based `grep` collapses it — decode as latin-1 and parse the
    whole blob (the inline `FINN.mapSettings` JSON and the `/rel/<hash>/pkg/js/`
    bundle manifest are where the real logic lives).
  - FINN's street view = Google; FINN's aerial = Blom UrbEx. If a future scout
    is asked to chase the underlying providers: Google Street View is already
    covered by the reference `svmap_google` provider, and Blom is aerial
    (out of street-level scope).
  - The `googlemaps_api_key` in the page is FINN's referrer-restricted browser
    key; it is not a credential we should reuse.

## 3. Test plan (write these FIRST — red before green)

> **No tests should be written.** FINN.no is out of scope (Google re-hoster;
> no first-party street-level coverage layer) and robots-disallowed for
> Anthropic agents. The list below is the **conditional** test plan that would
> apply *only if* §7 is ever unblocked by FINN shipping a genuine first-party
> Norwegian SVI coverage endpoint.

- [ ] `test_finn_no_tile_url_build` — URL template fills correctly for a sample
      `z/x/y` (only meaningful once a real first-party endpoint exists).
- [ ] `test_finn_no_decode_present` — recorded response fixture for a known
      covered tile decodes to `present`.
- [ ] `test_finn_no_decode_empty` — recorded response fixture for a known
      empty (over-fjord/ocean) tile decodes to `empty`.
- [ ] `test_finn_no_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_finn_no_robots_allowed` — assertion that the chosen URL prefix is
      not disallowed by the live robots.txt **and** that the host does not ban
      Anthropic crawlers (currently it does — this test would fail today).
- [ ] `test_finn_no_user_agent` — fetch helper sends our descriptive
      `User-Agent` and honours the polite-fetch throttle.
- [ ] Fixtures: small recorded response samples under `tests/fixtures/finn_no/`
      (TBD — none captured; no in-scope endpoint exists).

## 4. Implementation subplan (steps for the implementer — TDD)

> **Status: blocked at step 0 — do not start.** See §7. The steps below are the
> conditional plan that would apply *only if* §7 unblocks.

- [ ] **Step 0 (precondition):** A fresh scout must confirm BOTH: (a) FINN's
      "Gatebilde" / map viewer serves **first-party** Norwegian panorama
      imagery with a network-visible coverage endpoint (tiles / MVT / JSON),
      not a Google Street View hand-off; AND (b) the relevant URL prefix is
      permitted by robots.txt and the host no longer bans Anthropic crawlers.
      If either check fails, keep this subplan dropped.
- [ ] Source kind: TBD once a genuine first-party endpoint exists; pick the
      smallest existing kind that fits (`raster` / `vector_mvt` /
      `coverage_json` / `json_api`). A new kind would be a separate foundation
      PR per `CLAUDE.md`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/finn_no.py` (`ProviderDefinition`),
      auto-discovered by the registry; reuse `geo.py` web-mercator helpers
      (FINN's basemap/Blom layers are EPSG:3857).
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `10.72 59.90 10.78 59.93` (central Oslo —
      Sentrum / Kvadraturen). Secondary pilots: Bergen
      (`5.30 60.38 5.34 60.40`), Trondheim (`10.38 63.42 10.42 63.44`) —
      consistent with the stale "12 cities" claim.
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on the
      Oslo road network, not the Oslofjord.
- [ ] Two-pass full extent: pass-1 region bbox `4.0 57.9 31.5 71.5`
      (mainland Norway incl. Finnmark; excl. Svalbard) at discovery zoom `z=8`,
      pass-2 at the chosen source zoom (TBD; Norwegian SVI would be urban-only,
      so refine from z8 upward).
- [ ] Update the STAC item; update the inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> Only meaningful once §7 unblocks.

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- Pilot tiles fetch & decode; coverage lands on roads/land (not fjord/ocean).
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0.
- Fetches via `polite.polite_fetch`; descriptive `User-Agent`; robots.txt
  re-checked at implementation time; any third-party attribution disclosed in
  the module docstring.

## 6. Status log

- `2026-05-28` scout: drafted as **DROP — out of scope**. FINN's "Gatebilde"
  control is a `GoogleServiceButton` that deep-links/embeds Google Street View
  (`maps.google.no` `cbll=` / `/streetview/gsv.jsp` → Google Maps JS API);
  FINN's own tile layers are `finnvector` (vector basemap) + Blom aerial
  (`blomurbex.com`); the listing "360 visning" is per-listing Matterport/iGUIDE
  virtual tours. No first-party street-level coverage layer exists.
  `kart.finn.no/robots.txt` bans Anthropic crawlers; `www.finn.no/robots.txt`
  disallows `/map/`.
- `2026-05-28` approval: < pending >

## 7. Recommendation

**DROP — out of scope for the project.** Specifically:

1. **Do not create a GitHub issue, branch, or PR for `finn_no`.** FINN.no does
   not operate a first-party Norwegian street-level imagery coverage product.
   Its "Gatebilde" street view is a Google Street View hand-off, which
   `CLAUDE.md` / `docs/PLAN.md` §2 explicitly exclude (re-hoster — "imagery is
   Google's; flag in inventory as `google_rehost`").
2. **Mark `finn_no` as out-of-scope / `google_rehost` in
   `data/external/street_view_providers.xlsx`**, with a note pointing at this
   subplan: street view = Google embed; aerial = Blom; listing 360 = per-ad
   Matterport/iGUIDE virtual tours; no first-party SVI coverage layer.
3. **Robots/ToS reinforce the drop.** `kart.finn.no/robots.txt` bans
   `Claude` / `ClaudeBot` / `AnthropicBot` / `anthropic-ai` with `Disallow: /`,
   and `www.finn.no/robots.txt` disallows `/map/` and `/map?`. Automating these
   hosts would violate the stated robots policy regardless of scope.
4. **Underlying providers are already / otherwise handled.** Google Street View
   is covered by the reference `svmap_google` provider; Blom is aerial imagery
   (out of street-level scope). No additional FINN-specific work is warranted.
5. **Revisit only if a re-scout** (suggested cadence ~12 months, or triggered by
   an external report) finds that FINN has launched a genuine first-party
   Norwegian panorama product with a network-visible, robots-permitted coverage
   endpoint that is NOT a Google/Blom/third-party re-host. Update §3/§4 then and
   re-submit for the human-approval gate per `CLAUDE.md`.

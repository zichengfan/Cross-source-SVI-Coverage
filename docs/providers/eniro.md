# [T3] Provider: Eniro Gatuvy (`eniro`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-25): DEFER / DROP. Eniro's street-level "gatuvy"
feature has been retired. Eniro's own help page now answers the FAQ
"Hur kan jag se gatubilder på Eniro?" with the explicit notice
"Det är tyvärr inte längre möjligt att se gatufoton på Eniro."
("It is unfortunately no longer possible to view street photos on Eniro.")
Every historical gatuvy deep-link (`https://kartor.eniro.se/gatuvy/...`)
HTTP 301-redirects to the generic `https://www.eniro.se/kartor` page, which
contains no panorama viewer, no street-view layer toggle, no Pegman, and no
panorama / coverage tile or JSON endpoint. There is nothing to scrape. This
subplan documents the full investigation and the conditional plan that would
apply *if* the feature is ever restored. No issue / branch / code should be
created now.
-->

## 1. Summary

Eniro (`https://www.eniro.se/`) is a long-running Swedish online directory and
mapping service, with sister properties Krak (`krak.dk`, Denmark — scouted
separately), Gulesider (`gulesider.no`, Norway), and Degulesider
(`degulesider.dk`). From December 2009 it offered a first-party street-level
panorama product called **"Gatuvy"** (Swedish for "street view"), originally
covering eight Scandinavian cities and three winter resorts; community
references and a 2015 sister-app press release ("Eniros app — se gatuvy") show
the product was promoted into the mobile app as well. The original imagery
appears to have been licensed/sourced via Blom and CycloMedia (the
`eniro.se/help/maps` page historically attributed "Gatuvy och Utsiktsbilder" to
"Blom/CycloMedia").

**However, scouting concludes Eniro should be DEFERRED / DROPPED.** As of the
scout date the feature is officially retired:

- The current Eniro help page (`https://www.eniro.se/hjalp/kartor`) explicitly
  states under "Vanliga frågor": *"Hur kan jag se gatubilder på Eniro? — Det
  är tyvärr inte längre möjligt att se gatufoton på Eniro."*
- The `kartor.eniro.se` subdomain itself is being collapsed into the main
  site: every gatuvy URL on it (e.g. `https://kartor.eniro.se/gatuvy/stockholm`,
  `/gatuvy/G`, `/gatuvy/norrk%C3%B6ping-enebygatan-20`, `/gatuvy/eniro`)
  returns an unconditional `HTTP 301 Moved Permanently` to
  `https://www.eniro.se/kartor`. Even `kartor.eniro.se/robots.txt` 301-redirects.
- The destination page `https://www.eniro.se/kartor` is a generic map app with
  no street-view layer toggle, no Pegman icon, and no panorama-coverage source
  in its MapLibre style. The only layer-control items relate to base map, POIs,
  property lines, aerial, etc.
- A Swedish-language Flashback thread (`/t1256207`, "Eniro kartor, Utsiktfunktion
  borta?") shows users complaining the feature was missing from 2010 through
  2019 with no restoration — consistent with the official retirement notice
  now displayed.
- The third-party tile-rip catalogue `allmapsoft.com/providers/58.htm` lists
  Eniro tile products as **Karta / Flygfoton / Historiska Flygfoton /
  Sjökort** only — *no* panorama / street-view layer is enumerated even by
  scrapers that catalogue every known Eniro endpoint.

With Eniro itself stating the feature is gone and every URL pattern that
served it now redirected away, there is no coverage layer to harvest. See §2
for the evidence and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: feature retired by provider — DEFER / DROP

Applying the kakao/naver/mapy/mappy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.**
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — NO.**
4. **A panorama viewer with an embed/iframe one could discovery-probe? — NO.**

- **Homepage / public viewer URL:**
  - Marketing / directory site: `https://www.eniro.se/`.
  - Current live map viewer (a React SPA): `https://www.eniro.se/kartor`.
  - Historical street-view viewer (now retired): `https://kartor.eniro.se/gatuvy/<slug-or-coords>`.
  - Sister-locale viewers (also no street-view layer at scout time):
    `https://www.krak.dk/kort`, `https://www.gulesider.no/kart`.
  - Tier: **T3** (per `data/external/street_view_providers.xlsx` and `docs/PLAN.md` §2).

- **How the viewer was investigated.** The static HTML for the live SPA was
  fetched via the WebFetch tool with a realistic browser User-Agent. Cloudflare
  bot protection returns HTTP 403 + a JS challenge to bare `curl` requests
  (observed `cf-mitigated: challenge`, `cf-ray`), but WebFetch — which executes
  the challenge — successfully renders the SPA shell. All historical
  `kartor.eniro.se/gatuvy/...` deep-links were probed directly; each returned
  `HTTP 301` with `Location: https://www.eniro.se/kartor`. Eniro's own help
  FAQ was read in Swedish. Independent corroboration came from a Swedish
  community thread (Flashback 1256207), a 2015 press release, and a
  third-party tile-rip catalogue (allmapsoft.com).

- **What the live viewer fetches** (captured 2026-05-25 via WebFetch on
  `https://www.eniro.se/kartor`):
  - The page is a Swedish React/SPA map application served behind Cloudflare
    (Cloudflare Turnstile / managed-challenge; `cf-mitigated: challenge` and
    `cf-ray` headers on every response; CSP nonces on the bot-challenge HTML).
  - Visible UI chrome: header "Eniro.se — Upptäck närheten", navigation
    "Hjälp" / "Feedback", a layer-control section, and a directions
    (`/kartor/vägbeskrivning`) link. **There is no Pegman / street-view button
    and no "gatuvy" / "gatubilder" / "panorama" toggle anywhere in the layer
    panel.**
  - The published MapLibre style index at `https://map-styles.eniro.com/`
    exposes a single link "Go to map" to `/map`; no panorama / street-view
    style is published there.
  - The third-party catalogue `allmapsoft.com/providers/58.htm` (which
    historically enumerated every Eniro raster XYZ endpoint for an offline-tile
    downloader) lists four products only — **Flygfoton (aerial), Historiska
    Flygfoton (historical aerial), Karta (basemap), Sjökort (nautical)** —
    confirming that even external rippers do not see a panorama tile layer.

- **The official "feature is retired" notice.** Eniro's Swedish help page
  `https://www.eniro.se/hjalp/kartor` includes the following FAQ entry under
  "Vanliga frågor om kartor":

  > **Hur kan jag se gatubilder på Eniro?** Det är tyvärr inte längre möjligt
  > att se gatufoton på Eniro.

  ("How can I see street images on Eniro? — It is unfortunately no longer
  possible to view street photos on Eniro.") This is Eniro's first-party
  statement that the product is discontinued.

- **All historical gatuvy URLs now 301-redirect.** Probed 2026-05-25:

  | URL | Status | Location |
  | --- | --- | --- |
  | `https://kartor.eniro.se/` | 301 | `https://www.eniro.se/kartor` |
  | `https://kartor.eniro.se/gatuvy/stockholm` | 301 | `https://www.eniro.se/kartor` |
  | `https://kartor.eniro.se/gatuvy/G` | 301 | `https://www.eniro.se/kartor` |
  | `https://kartor.eniro.se/gatuvy/norrk%C3%B6ping-enebygatan-20` | 301 | `https://www.eniro.se/kartor` |
  | `https://kartor.eniro.se/gatuvy/eniro` | 301 | `https://www.eniro.se/kartor` |
  | `https://kartor.eniro.se/robots.txt` | 301 | `https://www.eniro.se/kartor/` |

  There is no `Cache-Control: no-store` or A/B header on these redirects to
  suggest temporary maintenance; the `kartor.eniro.se` subdomain is being
  permanently collapsed into the main host's `/kartor` route.

- **Coverage endpoint(s):** **None known to exist.** No raster XYZ panorama
  layer, no MVT coverage layer, no JSON point-probe API has been observed
  in the live viewer or published in any third-party catalogue.

- **Coordinate scheme:** N/A (no endpoint).
- **Zoom range / tile size / response format:** N/A.
- **Auth:** N/A. (The live `www.eniro.se` host gates non-browser traffic with a
  Cloudflare managed challenge; this is consistent with general bot protection
  rather than per-feature auth.)
- **Presence rule:** N/A — there is no response to parse.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://www.eniro.se/robots.txt` allows general crawling but disallows
    `/help/`, `/search/`, `/maps`, `/articles`, `/games/`, `/person/`,
    `/company/`, `/customerService/`, `/appPromo`, `/cdn-cgi/`, and several
    `/api/...` endpoints including `/api/person`, `/api/company`,
    `/api/biluppgifter`. **The `Disallow: /maps` directive matters: the
    English-locale map path is explicitly disallowed; the Swedish-locale
    `/kartor` path is currently *not* listed but is the migration target for
    the retired `kartor.eniro.se` subdomain.** Any future scraper here must
    re-check robots.txt at run time.
  - `kartor.eniro.se/robots.txt` is now a redirect (see table above), so the
    historical robots policy for the panorama paths has been deprecated.
  - Cloudflare bot protection + managed-challenge gating implies that
    automated, unattended scraping of any Eniro endpoint is not desired; this
    on its own does not legally forbid it, but it reinforces the recommendation
    that there is nothing to scrape here anyway.

- **Known quirks / gotchas (for any future re-scout):**
  - Imagery, when it existed, was attributed in the help page footer to
    **"Blom / CycloMedia"** — i.e. Eniro was a re-hoster of CycloMedia
    Cycloramas (and historically Blom panoramas). If/when a future Eniro
    product surfaces, it is likely to be a CycloMedia Street Smart
    embed/iframe rather than self-hosted panoramas; coverage signals would
    then live under `*.cyclomedia.com` and the better target is CycloMedia
    directly (and CycloMedia is a paid B2B service, so this would not be
    in-scope for our public-only inventory anyway).
  - The Eniro Group is in publicly-documented financial distress
    (see e.g. press coverage at hernhag.se "Fortsatt mörka signaler från
    Eniro — 2024"), making future restoration of a costly first-party
    street-view product unlikely.
  - The sister-locale viewers (`krak.dk/kort`, `gulesider.no/kart`,
    `degulesider.dk`) are behind the same Cloudflare protection and were
    not directly readable in this scout. **The Krak (Denmark) sibling is
    already being scouted under its own subplan** — the same retirement
    finding may apply there independently and should be verified there
    rather than here.

## 3. Test plan (write these FIRST — red before green)

> No tests should be written until the provider is unblocked by Eniro
> restoring a public coverage endpoint. The plan below is the **conditional
> test list** an implementer would adopt *if* §7 unblocks.

- [ ] `test_eniro_tile_url_build` — URL template fills correctly for a
      sample `z/x/y` (only meaningful once a real endpoint is found).
- [ ] `test_eniro_decode_present` — recorded response fixture for a known
      panorama-bearing tile decodes to `present`.
- [ ] `test_eniro_decode_empty` — recorded response fixture for a known
      empty (over-ocean) tile decodes to `empty`.
- [ ] `test_eniro_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_eniro_robots_allowed` — assertion that the chosen URL prefix is
      not disallowed by the live `www.eniro.se/robots.txt`.
- [ ] `test_eniro_user_agent` — fetch helper sends our descriptive
      `User-Agent` and honours the polite-fetch throttle.
- [ ] Fixtures: small recorded response samples under `tests/fixtures/eniro/`
      (TBD — to be captured once a real endpoint is identified).

## 4. Implementation subplan (steps for the implementer — TDD)

> **Status: blocked at step 0.** Do not start; see §7. The steps below are the
> conditional plan that would apply *if* Eniro ever restores a public coverage
> endpoint and §7 unblocks this subplan.

- [ ] **Step 0 (precondition):** Confirm with a fresh scout that
      `https://www.eniro.se/hjalp/kartor` no longer states the gatuvy feature
      is retired, AND that the live `https://www.eniro.se/kartor` viewer has
      a re-introduced street-view layer toggle with an associated tile / MVT /
      JSON coverage endpoint. If either check fails, keep this subplan
      deferred.
- [ ] Source kind: TBD once an endpoint exists; pick the smallest existing
      kind that fits (`raster` if a coverage overlay returns transparent /
      non-transparent PNGs; `vector_mvt` if it returns MVT; `coverage_json`
      if it returns JSON point lists). If, and only if, no existing kind
      fits, treat that as a separate foundation PR per `CLAUDE.md`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/eniro.py` (`ProviderDefinition`),
      auto-discovered by the registry; reuse `geo.py` web-mercator helpers
      (Eniro's historical scheme was standard EPSG:3857).
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `18.05 59.32 18.10 59.34` (central Stockholm —
      Gamla Stan / Norrmalm); secondary pilots in Göteborg
      (`11.96 57.70 12.00 57.72`) and Norrköping (`16.18 58.58 16.20 58.60`)
      based on the surviving deep-link slugs that existed historically.
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on
      Stockholm road network, not the Baltic.
- [ ] Two-pass full extent: pass-1 region bbox `10.5 55.0 24.5 69.5`
      (Sweden mainland incl. Skåne and Norrland) at discovery zoom `z=8`,
      pass-2 at the chosen source zoom (TBD — historical Blom/CycloMedia
      coverage was urban-only, so a high discovery zoom like 14 would over-
      fetch; start at 8 and refine).
- [ ] Update the STAC item; update the inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> Only meaningful once §7 unblocks.

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- Pilot tiles fetch & decode; coverage lands on roads/land (not ocean / not
  uniformly over uninhabited Norrland).
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0.
- Fetches via `polite.polite_fetch`; descriptive `User-Agent`; ToS caveats
  documented (Eniro robots.txt re-checked at implementation time, CycloMedia
  re-hosting attribution disclosed in module docstring if confirmed).

## 6. Status log

- `2026-05-25` scout: drafted as **DEFER / DROP**. Eniro's own help page
  states the feature is retired; every historical `kartor.eniro.se/gatuvy/...`
  URL HTTP 301-redirects to the generic `/kartor` page; the current map
  viewer has no panorama layer; no third-party catalogue lists an Eniro
  panorama tile endpoint.
- `2026-05-25` approval: < pending >

## 7. Recommendation

**Defer indefinitely — and treat as effectively dropped for the current
project phase.** Specifically:

1. **Do not create a GitHub issue, branch, or PR for `eniro` now.** There is
   nothing in scope to implement: Eniro itself states the gatuvy feature is
   gone, all panorama URLs redirect away, and no coverage endpoint exists.
2. **Mark `eniro` as `defunct` (or `paused`) in
   `data/external/street_view_providers.xlsx`** with a note pointing at this
   subplan and the help-page quote.
3. **Revisit only if a re-scout** (suggested cadence: every ~12 months, or
   triggered by an external report) finds (a) the help-page FAQ no longer
   says the feature is retired and (b) the live `www.eniro.se/kartor`
   viewer reveals a panorama layer toggle with a network-visible coverage
   endpoint. Update §3 / §4 then and re-submit for the human-approval gate
   per `CLAUDE.md`.
4. **Cross-link with the `krak` (Danish sister) subplan.** Krak is being
   scouted independently; the Eniro Group's documented financial pressure
   and the Cloudflare-collapsed `kartor.*` subdomains on the Swedish side
   make a parallel retirement on the Danish side plausible but not assumed.
   Each Nordic locale must be verified on its own evidence rather than
   inferred from this finding.
5. **If a future re-scout finds Eniro embedding CycloMedia Street Smart**
   (the historical attribution suggests this is the likeliest revival path),
   redirect effort to a CycloMedia-direct provider — but note that
   CycloMedia is a paid B2B product without a public anonymous viewer, so
   it is out of scope per `CLAUDE.md` ("Skip … paid-B2B-only providers
   with no public viewer").

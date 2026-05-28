# [T3] Provider: Krak Gadefoto (`krak`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER / DROP. Krak's street-level "gadefoto"
feature has been retired at the backend level, exactly like its Swedish
sibling Eniro. The front-end SPA shell at
`https://map.krak.dk/gadefoto/<slug>` is still served (and Google still
indexes those deep-links), but it boots the shared Eniro map engine against
street-view endpoints that are now dead:

  * the coverage point-probe API `https://streetview.eniro.com/search?east=
    <lon>&north=<lat>` returns a consistent **HTTP 404 with an empty body**
    (3/3 probes);
  * the street-view data origin `https://st.enirocdn.com` returns S3
    **`NoSuchBucket` for bucket `eniro-geo-streetview`** — the entire
    street-view data store has been deleted (2/2 probes);
  * the panorama renderer `https://pano.enirocdn.com/panorender/render?`
    answers only with the bare load-balancer health string
    `Eniro Elastic Load Balancer status: OK` — no panorama backend behind it.

By contrast the *basemap* tile node `https://map01.eniro.com/...` still
returns valid PNG tiles (HTTP 200, `image/png`), proving the Eniro/Krak
platform is alive in general and that it is specifically the street-view
subsystem that has been decommissioned — not a transient outage. There is no
coverage layer to harvest. Additionally, Krak's gadefoto was historically a
**re-host** of third-party panoramas served from the same Eniro street-view
infrastructure that Eniro attributed to Blom / CycloMedia (a paid-B2B
provider) — out of scope per `CLAUDE.md` even if it were restored as such.
This subplan documents the full investigation and the conditional plan that
would apply *if* the feature is ever restored as a first-party, public,
scrapable layer. No issue / branch / code should be created now.
-->

## 1. Summary

Krak (`https://www.krak.dk/`) is Denmark's long-standing online business
directory and mapping service, the Danish sister property of the Eniro Group
(alongside Eniro `eniro.se` / Sweden, Gulesider `gulesider.no` / Norway, and
Degulesider `degulesider.dk`). From ~2009 Krak offered a first-party-branded
street-level panorama product called **"Gadefoto"** ("street photo"), launched
in competition with Google Street View and originally covering the largest
Danish cities (København, Aarhus, Odense and others). The viewer lived at
`https://map.krak.dk/gadefoto/<address-slug>` and ran the **shared Eniro map
engine** (RequireJS app `eniro/main`, profile `config-dk_krak`), the same
codebase that powered Eniro's Swedish "Gatuvy" — including a `js/eniro/...`
asset tree and `static.eniro.com` fonts/logos served under the `dk_krak`
profile.

**However, scouting concludes Krak should be DEFERRED / DROPPED.** As of the
scout date the gadefoto feature is retired at the backend level:

- The coverage point-probe API the viewer calls,
  `https://streetview.eniro.com/search?east=<lon>&north=<lat>`, now returns a
  consistent **HTTP 404, empty body** — there is no longer any
  "is-there-a-panorama-here" service to query.
- The street-view data origin `https://st.enirocdn.com` (config key
  `streetview.url`) returns AWS S3 **`NoSuchBucket`** for bucket
  `eniro-geo-streetview`; the street-view data has been deleted.
- The panorama image renderer `https://pano.enirocdn.com/panorender/render?`
  (config key `pano.url`) responds only with an ELB health-check string, with
  no panorama behind it.
- The Krak help centre no longer carries a gadefoto topic (its help index now
  lists only Generelt, Luftfoto, Matrikler, Ruteplan-og-korttyper, Skæl,
  Søkort); the one residual FAQ question "Hvordan ser jeg gadefoto på Krak?"
  is a lazy-rendered accordion whose answer is no longer in the static
  payload, consistent with the feature being wound down. Web indexers
  summarise Krak's help as stating it is no longer possible to view street
  photos — mirroring Eniro's explicit Swedish retirement notice.
- This independently confirms the parallel-retirement hypothesis flagged in
  the Eniro subplan (`docs/providers/eniro.md` §7.4): both Nordic siblings
  shared the `streetview.eniro.com` / `*.enirocdn.com` street-view backend,
  and that backend has been switched off for both.

With the coverage API 404ing, the panorama data bucket deleted, and the
historical imagery being a Blom/CycloMedia re-host, there is nothing in scope
to harvest. See §2 for the evidence and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: street-view backend decommissioned (and a paid-B2B re-host) — DEFER / DROP

Applying the kakao/naver/mapy/mappy/eniro scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.**
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — EXISTED, NOW DEAD.** The viewer's probe API
   `streetview.eniro.com/search?east=&north=` returns HTTP 404 / empty.
4. **A panorama viewer with an embed/iframe one could discovery-probe? — the
   SPA shell still loads, but its `pano`/`streetview` data endpoints are dead;
   nothing renders.**

- **Homepage / public viewer URL:**
  - Marketing / directory site: `https://www.krak.dk/`.
  - Map app: `https://map.krak.dk/` (also reachable as `https://www.krak.dk/kort`).
  - Historical street-view viewer (shell still served, backend dead):
    `https://map.krak.dk/gadefoto/<address-slug>` — e.g.
    `https://map.krak.dk/gadefoto/k`,
    `https://map.krak.dk/gadefoto/Hellerup-Sigridsvej-25`,
    `https://map.krak.dk/gadefoto/odense-c-risingsvej-60`.
    Canonical link now points at `https://www.krak.dk/kort/gadefoto/<slug>`.
  - Help centre: `https://www.krak.dk/hjaelp/kort/generelt` (topic index has
    no gadefoto entry).
  - Sister-locale viewers (separately scouted / out of scope here):
    `https://www.eniro.se/kartor` (Sweden — retired, see `eniro.md`),
    `https://www.gulesider.no/kart` (Norway).
  - Tier: **T3** ("likely / unverified / gated" in `docs/PLAN.md` §2 and
    `data/external/street_view_providers.xlsx`).

- **How the viewer was investigated.** The live `*.krak.dk` hosts sit behind
  **Cloudflare managed-challenge** bot protection: bare requests (and the
  WebFetch tool) get `HTTP 403 + "Just a moment..."` with
  `cf-mitigated: challenge`, `server: cloudflare`, and a Turnstile
  CSP/`cf-ray`. The SPA shell was therefore read from the Internet Archive
  (Wayback Machine) `id_` raw snapshots, which preserve the exact served HTML
  and JS. The shared Eniro engine's profile config
  (`/v20250618090659/js/eniro/config-dk_krak.js`, build dated 2025-06-18) and
  `eniro/main.js` were pulled the same way and read for endpoints. The
  endpoints themselves (`streetview.eniro.com`, `st.enirocdn.com`,
  `pano.enirocdn.com`, the `map01.eniro.com` basemap node) are *not* behind
  Cloudflare and were probed **live and directly** with a realistic browser
  User-Agent and a `Referer: https://map.krak.dk/` header. Independent
  corroboration: the Eniro sibling scout (`docs/providers/eniro.md`), Wayback
  CDX history of `map.krak.dk/gadefoto/*` (snapshots 2016 → 2025-07), and
  Danish-language press/help references.

- **What the viewer fetches** (from `config-dk_krak.js`, build `20250618090659`):
  - `"streetview.url":"//st.enirocdn.com"` — street-view data origin (tiles /
    panorama metadata).
  - `"pano.url":"//pano.enirocdn.com/panorender/render?"` — panorama image
    renderer.
  - Coverage point-probe (from `main.js`): the viewer issues
    `B.nojsonp("//streetview.eniro.com/search?east="+lon+"&north="+lat)` and,
    in the `.done(function(t){ ... })` callback, treats a **truthy `t[0]`**
    (a non-empty result array) as "a Krak/Eniro panorama exists at this point"
    (then it sets the proposition image from `getStreetviewImg`); if `t[0]` is
    falsy it falls back to drawing a **Mapillary** image instead. This is the
    presence rule that *would* have driven discovery.
  - `"mapillaryCode":"krak.dk"` plus `mapillary.url` /
    `mapillary.signup.*.url` — Mapillary is wired in as the *fallback / overlay*
    imagery source, not the Krak coverage signal.
  - Basemap/other (still live, not street-view): `tile.url "//{s}.eniro.com"`
    with `tile.subdomains "map01..map04"`, `mapsearch.eniro.com`,
    `route.enirocdn.com`, `statmap.eniro.com`, `oblique.enirocdn.com`,
    `layers.enirocdn.com`, `tileversion.eniro.com`.

- **Live probe results (2026-05-28, direct, browser UA + Krak Referer):**

  | Endpoint | Result | Meaning |
  | --- | --- | --- |
  | `https://streetview.eniro.com/search?east=12.5683&north=55.6761` (Copenhagen) | **HTTP 404, 0 bytes** (3/3) | coverage probe API removed |
  | `https://streetview.eniro.com/search?...&radius=100` | HTTP 404, 0 bytes | no surviving variant |
  | `https://st.enirocdn.com/` and `/geo/streetview/...` | **HTTP 404, S3 `NoSuchBucket` `eniro-geo-streetview`** (2/2) | street-view data bucket deleted |
  | `https://pano.enirocdn.com/panorender/render?` | HTTP 200, body `Eniro Elastic Load Balancer status: OK` | bare ELB health page; no panorama backend |
  | `https://tileversion.eniro.com/` | HTTP 404 JSON (`status:404`) | tile-version service present but `/` empty |
  | `https://mapsearch.eniro.com/` | HTTP 404 | (basemap search root; unrelated) |
  | `https://map01.eniro.com/geowebcache/service/tms1.0.0/map/2/2/1.png` | **HTTP 200, `image/png`** | basemap tiles still served — platform alive, only street-view dead |

  The street-view endpoints are consistently dead across repeated probes,
  while the basemap node consistently serves valid tiles — this rules out a
  transient outage and shows a deliberate decommissioning of the street-view
  subsystem.

- **Coverage endpoint(s):** **None live.** The historical coverage probe was
  `GET https://streetview.eniro.com/search?east=<lon>&north=<lat>` returning a
  JSON array (presence = non-empty `t[0]`), but it now 404s with an empty
  body. No raster/MVT street-view coverage layer was ever exposed; coverage was
  point-probe only.

- **Coordinate scheme:** historical probe used **WGS84 lon/lat** directly
  (`east`=longitude, `north`=latitude), not tile x/y. (The basemap engine is
  EPSG:3857 web mercator, but that is irrelevant to the dead street-view API.)
- **Zoom range / tile size / response format:** N/A — point-probe JSON, no
  tile pyramid; nothing live to characterise.
- **Auth:** none was required on the historical probe API (no token/cookie in
  `main.js`); the front-end *site* hosts are Cloudflare-gated, but the
  street-view API hosts are not. N/A now (endpoint gone).
- **Presence rule:** historical — JSON response array, `t[0]` truthy ⇒
  panorama present; falsy ⇒ none (front-end then falls back to Mapillary).
  Not applicable now (404).

- **robots.txt / ToS notes; observed rate limit:**
  - `https://map.krak.dk/robots.txt` historically (Wayback 2023) returned
    `User-agent: * / Allow: /` plus a `Sitemap:` line — i.e. crawling was not
    broadly disallowed — but it is currently served only behind the Cloudflare
    challenge and must be re-fetched at implementation time if ever unblocked.
  - The live front-end hosts (`www.krak.dk`, `map.krak.dk`) enforce a
    **Cloudflare managed challenge** on non-browser traffic, signalling that
    unattended automated access to the site is not desired.
  - The historical gadefoto imagery is a third-party re-host (Blom /
    CycloMedia lineage; CycloMedia is a **paid B2B** product with no public
    anonymous viewer), so it is **out of scope per `CLAUDE.md`** ("Skip …
    re-hosters … paid-B2B-only providers with no public viewer") even if the
    backend were restored in its old form.

- **Known quirks / gotchas (for any future re-scout):**
  - Krak's gadefoto runs the **identical Eniro engine** as Sweden's retired
    "Gatuvy" (`config-dk_krak` is just an Eniro profile; assets live under
    `static.eniro.com` and `*.enirocdn.com`). Coverage state for both locales
    therefore lives on the **same shared `streetview.eniro.com` /
    `eniro-geo-streetview` backend**, which is now off. A future revival on the
    Danish side would almost certainly require that shared backend to come back.
  - The SPA shell at `map.krak.dk/gadefoto/<slug>` and Google's indexed
    deep-links are **misleading**: the HTML still serves, but it boots against
    dead data endpoints. Do not treat the presence of these URLs as evidence
    the feature works — verify the `streetview.eniro.com/search` API directly.
  - The historical imagery provenance is **Blom / CycloMedia** (consistent
    with the Eniro sibling's `Blom/CycloMedia` attribution). If Krak ever
    re-surfaces street imagery it is most likely as a CycloMedia Street Smart
    embed, in which case the in-scope target (if any) is CycloMedia directly —
    and CycloMedia is paid-B2B, out of scope.
  - The Eniro Group is in publicly-documented financial distress, making a
    costly first-party street-view relaunch unlikely.
  - The `pano.enirocdn.com` and `layers.enirocdn.com` hosts return a generic
    "Eniro Elastic Load Balancer status: OK" string at `/`; do not mistake
    this 200 for a working panorama/coverage service.

## 3. Test plan (write these FIRST — red before green)

> No tests should be written until the provider is unblocked by Krak/Eniro
> restoring a public, first-party (non-CycloMedia) coverage endpoint. The plan
> below is the **conditional test list** an implementer would adopt *if* §7
> unblocks. Krak's historical coverage signal was a JSON point-probe, so the
> natural source kind is `coverage_json` / `json_api` rather than `raster`.

- [ ] `test_krak_probe_url_build` — point-probe URL fills correctly for a
      sample `(lon, lat)` into
      `//streetview.eniro.com/search?east=<lon>&north=<lat>` (only meaningful
      once the endpoint is live again).
- [ ] `test_krak_decode_present` — recorded JSON fixture for a known
      panorama-bearing point decodes to `present` (rule: non-empty array /
      truthy `t[0]`).
- [ ] `test_krak_decode_empty` — recorded JSON fixture for a known
      empty point (e.g. over the Øresund / Baltic) decodes to `empty`.
- [ ] `test_krak_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_krak_robots_allowed` — assertion that the chosen URL prefix is not
      disallowed by the live `map.krak.dk/robots.txt` at run time.
- [ ] `test_krak_user_agent` — fetch helper sends our descriptive
      `User-Agent` and honours the polite-fetch per-host throttle.
- [ ] Fixtures: small recorded JSON response samples under
      `tests/fixtures/krak/` (TBD — to be captured once the endpoint is live).

## 4. Implementation subplan (steps for the implementer — TDD)

> **Status: blocked at step 0.** Do not start; see §7. The steps below are the
> conditional plan that would apply *if* Krak restores a public, first-party
> coverage endpoint and §7 unblocks this subplan.

- [ ] **Step 0 (precondition):** Confirm with a fresh scout that
      (a) `https://streetview.eniro.com/search?east=<lon>&north=<lat>` (or its
      successor) returns a real JSON coverage result for Danish points instead
      of HTTP 404, AND that `st.enirocdn.com` serves street-view data instead
      of S3 `NoSuchBucket`, AND (b) the restored imagery is **first-party /
      not a CycloMedia or Blom re-host** (otherwise it is out of scope per
      `CLAUDE.md` regardless of availability). If any check fails, keep this
      subplan deferred.
- [ ] Source kind: most likely `coverage_json` / `json_api` (point-probe JSON
      array, presence = non-empty). Only fall back to `raster` if a restored
      product exposes a rendered coverage tile layer instead. If, and only if,
      no existing kind fits, treat that as a separate foundation PR per
      `CLAUDE.md`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/krak.py` (`ProviderDefinition`),
      auto-discovered by the registry; reuse `geo.py` helpers for the
      web-mercator discovery grid even though the probe takes WGS84 lon/lat.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `12.55 55.67 12.59 55.69` (central Copenhagen —
      Rådhuspladsen / Indre By); secondary pilots in Aarhus
      (`10.19 56.14 10.22 56.16`) and Odense (`10.37 55.39 10.40 55.41`),
      the cities Krak's gadefoto historically covered.
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on
      the Copenhagen road network, not the Øresund.
- [ ] Two-pass full extent: pass-1 region bbox `8.0 54.5 15.2 57.8`
      (Denmark incl. Jylland, Fyn, Sjælland, Bornholm) at discovery zoom
      `z=8`; pass-2 at the chosen source resolution. Historical gadefoto
      coverage was **urban-only** (a handful of cities), so a coarse discovery
      zoom is appropriate to avoid over-probing rural Denmark — start at 8 and
      refine.
- [ ] Update the STAC item; update the inventory status.

## 5. Acceptance criteria (checked by provider-verifier)

> Only meaningful once §7 unblocks.

- All §3 tests pass; module imports & self-registers; CI smoke test passes.
- Pilot probes fetch & decode; coverage lands on Danish urban roads (not the
  sea, not uniformly over rural Jylland).
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0.
- Fetches via `polite.polite_fetch`; descriptive `User-Agent`;
  `map.krak.dk/robots.txt` re-checked at implementation time; provenance
  documented in the module docstring (and the provider dropped if the imagery
  is confirmed to be a CycloMedia/Blom re-host).

## 6. Status log

- `2026-05-28` scout: drafted as **DEFER / DROP**. Krak's gadefoto front-end
  SPA shell still serves (`map.krak.dk/gadefoto/<slug>`, build 2025-06-18) but
  its street-view backend is dead: the coverage probe API
  `streetview.eniro.com/search?east=&north=` returns HTTP 404/empty (3/3); the
  street-view data origin `st.enirocdn.com` returns S3 `NoSuchBucket`
  (`eniro-geo-streetview`, 2/2); `pano.enirocdn.com/panorender/render?` only
  returns an ELB health string; while the basemap node `map01.eniro.com`
  still serves valid PNG tiles (200) — confirming a deliberate street-view
  decommissioning, not an outage. Same shared Eniro backend as the
  retired Swedish "Gatuvy"; historical imagery is a Blom/CycloMedia re-host
  (paid-B2B, out of scope). Front-end hosts are Cloudflare-gated.
- `2026-05-28` approval: < pending >

## 7. Recommendation

**Defer indefinitely — and treat as effectively dropped for the current
project phase.** Specifically:

1. **Do not create a GitHub issue, branch, or PR for `krak` now.** There is
   nothing in scope to implement: the coverage probe API 404s, the street-view
   data bucket is deleted, and the historical imagery is a Blom/CycloMedia
   re-host (out of scope per `CLAUDE.md`).
2. **Mark `krak` as `defunct` (or `paused`) in
   `data/external/street_view_providers.xlsx`** with a note pointing at this
   subplan, the `streetview.eniro.com/search` 404, and the
   `eniro-geo-streetview` `NoSuchBucket` evidence.
3. **Revisit only if a re-scout** (suggested cadence: every ~12 months, or
   triggered by an external report) finds (a) the
   `streetview.eniro.com/search` API (or a successor) returning real JSON
   coverage for Danish points, (b) `st.enirocdn.com` serving street-view data
   again, and (c) the restored imagery being **first-party rather than a
   CycloMedia/Blom re-host**. Update §3 / §4 then and re-submit for the
   human-approval gate per `CLAUDE.md`.
4. **Cross-link with the Eniro (`eniro`) and other Eniro-Group locale
   subplans.** Krak and Eniro share the `streetview.eniro.com` /
   `*.enirocdn.com` street-view backend; this scout independently confirms the
   parallel-retirement hypothesis raised in `docs/providers/eniro.md` §7.4.
   The Norwegian (`gulesider.no`) and Danish-directory (`degulesider.dk`)
   siblings, if ever inventoried, almost certainly share the same now-dead
   backend and can be triaged by the same single probe
   (`streetview.eniro.com/search`).
5. **If a future re-scout finds Krak embedding CycloMedia Street Smart**
   (the likeliest revival path given the historical provenance), redirect
   effort to a CycloMedia-direct provider — but note CycloMedia is a paid B2B
   product without a public anonymous viewer, so it is out of scope per
   `CLAUDE.md`.

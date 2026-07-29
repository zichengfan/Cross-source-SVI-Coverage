# [T3] Provider: İstanbul Şehir Haritası — Panorama (`istanbul_ibb`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

`istanbul_ibb` is the panoramic street-view product of the **İstanbul Büyükşehir
Belediyesi** ("Istanbul Metropolitan Municipality", IBB) — the Turkish
municipal government of Istanbul Province. It is exposed inside the IBB
public-facing city-map web app **Harita İstanbul** (`https://harita.istanbul/`,
the successor to the legacy `sehirharitasi.ibb.gov.tr`, which 302-redirects to
the new host) under the "Panorama / Sokak Görüntüleri" sidebar tool. The
panorama coverage is municipal — confined to the 39 districts of Istanbul
Province (a bbox of roughly **28.06 E – 29.74 E, 40.90 N – 41.25 N**, both the
European and Anatolian sides, both Bosphorus shores). It is a first-party
SVI surface from a public authority, which is why it sits in `docs/PLAN.md` §2
as a **T3 candidate**.

**Scouting verdict: RECOMMEND DEFER (not skip permanently, do not implement
now).** Live probing on 2026-05-25 establishes three facts that together rule
out a *clean* coverage scrape today:

1. **The panoramas are actually Cyclomedia.** The IBB panorama viewer
   (`https://cbspanorama.ibb.gov.tr/panorama/panorama2018/`) is a thin wrapper
   around the commercial **Cyclomedia Street Smart** SDK
   (`/street-smart/lib/streetsmart/StreetSmartApi.js`), initialized with
   IBB's licensed Cyclomedia credentials (`username` / `password` /
   `ApiKey` / `ConfigurationUrl`) that are AES-encrypted in three hidden
   `<label>`s (`gak` / `gal` / `gam`) and decrypted client-side by
   `cbspanorama.ibb.gov.tr/js/cr.js` before being handed to
   `StreetSmartApi.init(...)`. Once initialized, the panorama imagery, the
   pano cube faces, and *the Cyclomedia coverage WFS* are all fetched directly
   from Cyclomedia's `*.cyclomedia.com` infrastructure — not from IBB.
   Scraping the coverage *map* (the WFS recordings layer) therefore means
   replaying IBB's licensed B2B Cyclomedia credentials against Cyclomedia's
   commercial servers — a non-public, ToS-hostile path that this project will
   not take.
2. **IBB's only public, unauth coverage endpoint is a single-point random
   sampler.** The IBB-side panorama API exposes exactly one coverage-like
   route: `GET https://cbspanorama.ibb.gov.tr/api/streetsmart/GetRandomWithCoordinates`,
   which returns **one** random panorama:
   `{"id":"WE8UXF62","coordinates":[28.418766848079844,41.04734936541154],"date":"2023-12-28T06:36:55.69+00:00"}`.
   There is **no `?bbox=`, no `?z/x/y` tile, no list endpoint, no extent
   query**. Brute-checked variants (`GetPanoramas`, `GetByExtent`, `GetAll`,
   `List`, `Coverage`, `GetCoordinates`, `Search`, `/api/Panorama/List`, …)
   all return `404`. The only structurally legitimate way to *enumerate*
   IBB's panorama set without using Cyclomedia credentials is to sample
   `GetRandomWithCoordinates` until saturation — i.e. ~3N requests for
   ~95 % coverage of N panoramas. With Cyclomedia spacing ~5 m and ~10 000 km
   of road in Istanbul Province this is plausibly N ≈ 100 k – 500 k panoramas
   → ~300 k – 1.5 M requests just to enumerate, against an endpoint never
   intended as a bulk extent feed.
3. **The dataset is a single ~6-month campaign (2023-07 → 2024-01).** Every
   `date` field observed in 48 random samples falls in `2023-07` through
   `2024-01` — a single Cyclomedia capture wave for Istanbul. The coverage
   surface is therefore static for this scrape cadence; this is not lost work
   if implementation is deferred.

The provider is **not defunct, not retired, not login-gated** for the viewer —
the public viewer works fine in a normal browser and the random-coordinate API
is unauthenticated. It is **legally and architecturally awkward** for a global
coverage scrape: the underlying coverage *belongs to Cyclomedia*, the
`GetRandomWithCoordinates` sampler is an unintended-bulk-channel, and IBB's
own published REST API (`sehirharitasiapi.ibb.gov.tr/developer/`) documents
only viewer-embedding helpers, not a coverage-list endpoint. **Defer; do not
open an implementation issue. Re-probe at the next provider sweep** to check
whether (a) IBB ever publishes a `GetByExtent` endpoint or releases the
panorama coverage layer on the IBB Open Data Portal, or (b) the Cyclomedia
backing is replaced with an in-house IBB capture with a public WFS. See §6 for
the re-probe checklist.

## 2. Research findings (filled by provider-scout)

### Verdict detail — why defer

- **Front host (the city-map web app):** `https://harita.istanbul/` (the
  successor to `https://sehirharitasi.ibb.gov.tr/`, which `302`-redirects to
  `https://harita.istanbul/` on every path — verified live `2026-05-25`,
  including `/`, `/panorama/`, `/panorama/developer/`). The legacy
  developer-API pages quoted in older write-ups
  (`sehirharitasi.ibb.gov.tr/developer/`,
  `sehirharitasi.ibb.gov.tr/panorama/developer/`) **no longer exist** — every
  one of them 302s to the SPA root.
- **The SPA app bundle.** `harita.istanbul/` is a React/maplibre SPA whose two
  bundles are `static/js/main.<hash>.js` (≈ 3.2 MB) and
  `static/js/31257.<hash>.js` (≈ 4.4 MB). The panorama feature is wired in
  `main.js` and the actual panorama viewer is loaded into an `<iframe
  id="panorama-iframe">` whose `src` is built dynamically (see below).
- **Panorama-related endpoints visible in the bundles:**
  - `https://cbspanorama.ibb.gov.tr/panorama/panorama` — the iframe-viewer
    base path; a full URL is built as
    `https://cbspanorama.ibb.gov.tr/panorama/panorama{panoramaType}/?token={token}`
    with optional `&coordinates={lon},{lat}&imageId={id}&yaw={deg}&pitch={deg}`.
    The SPA calls `ConfigurePanorama({panoramaType:"2018", token:"fc470f86-…"
    | "9dd8b8ac-…"})`, resolving to e.g.
    `…/panorama/panorama2018/?token=fc470f86-16b6-44c2-81ec-0fe145d34b7b`.
    These two viewer tokens are **embed allow-list keys**, not coverage-API
    keys — they unlock the viewer iframe when the request carries
    `Referer: https://harita.istanbul/`; without that referer the viewer
    302s to `/Panorama/Error`.
  - `https://cbspanorama.ibb.gov.tr/api/streetsmart/GetRandomWithCoordinates`
    — the only coverage-shaped data endpoint. Unauth, CORS-enabled (the host
    sends `Access-Control-Allow-Origin: *`), returns one random pano (see
    Coverage endpoint below).
  - `https://cbspanoramapreview.ibb.gov.tr/?coordinates=<lon>,<lat>` — used
    by the SPA's "find a panorama near here" UX; the host **does not resolve
    in DNS** (`NXDOMAIN`) for an unauthenticated external client and is
    presumably reachable only from inside IBB's network. Cannot be used.
  - `https://sehirharitasigateway.ibb.gov.tr/api` — the SPA's general API
    gateway (catalogues, base-maps, search, layers). No panorama-coverage
    route surfaced here.
  - `https://basemap.ibb.gov.tr/static/rehber_altlik.json` — basemap style
    descriptor; not panorama.
- **The viewer's iframe HTML (live fetch 2026-05-25, with
  `Referer: https://harita.istanbul/`):**

  ```html
  <!DOCTYPE html><html lang="en"><head>
    <title>IBB CBS Panorama 2018</title>
    <script src="/js/PanoramaModule.js"></script>
    <script src="/js/cr.js"></script>
    <script src="/street-smart/lib/react/react.production.min.js"></script>
    <script src="/street-smart/lib/react/react-dom.production.min.js"></script>
    <script src="/street-smart/lib/lodash/lodash.min.js"></script>
    <script src="/street-smart/lib/openlayers/ol.js"></script>
    <script src="/street-smart/lib/proj4/proj4.js"></script>
    <script src="/street-smart/lib/streetsmart/StreetSmartApi.js"></script>
    <link rel="stylesheet" href="/css/panorama-2018.css"/>
  </head><body>
    <label id="gak" hidden>pZfq5Gk6QrUO1IjfLLhFkZzGvmJ3FHVI…(AES ciphertext)…CCoE=</label>
    <label id="gal" hidden>G/hvv2635xcB4jtt8EKgUWSnwYWGJaV4BeXO/xLxoLQ=</label>
    <label id="gam" hidden>01adwGQdzLjjO7VR98Ki2A==</label>
    <div id="no-recording"><label>Seçtiğiniz noktaya ait çekim bulunmamaktadır.</label></div>
    <div id="no-auth"><label>Seçtiğiniz noktayı görüntüleme izniniz bulunmamaktadır.</label></div>
    <div id="panorama-2018"></div>
  </body></html>
  <script>PanoramaModule.Panorama2018.initializePanorama();</script>
  ```

  `PanoramaModule.js` (verified live, 23 KB, obfuscated with hex-named locals)
  decrypts the three `gak`/`gal`/`gam` labels via `cr.js` (a CryptoJS bundle
  shipping PBKDF2-+-AES-CBC) into a JSON `{UserName, Password,
  ConfigurationUrl, ApiKey, RenderDistance, BoundaryBox}` and passes the
  result straight into `StreetSmartApi.init(initialParameters)` with
  `srs: "EPSG:5269"` (Turkish national LCC TM30, `+proj=tmerc +lat_0=0
  +lon_0=27 +k=1 +x_0=9500000 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0
  +units=m +no_defs`, registered into OpenLayers via `proj4` inside
  `initializePanorama`). After that, **Cyclomedia's Street Smart SDK fetches
  the recordings layer and the panorama imagery directly from Cyclomedia's
  servers**, not from `cbspanorama.ibb.gov.tr` — confirmed by the SDK
  identity (`StreetSmartApi`) and by the absence of any other host in the
  iframe's network surface besides Cyclomedia and the IBB iframe host.
- **Why the "encrypted credentials" path is off-limits.** The three labels are
  decryptable client-side (any browser does it on page load); a scraper could
  reproduce the decryption and obtain IBB's Cyclomedia
  `username/password/ApiKey/ConfigurationUrl`. **Doing so to drive Cyclomedia's
  Atlas Recordings WFS from outside the IBB viewer would be (a) using IBB's
  licensed commercial credentials against the third-party owner of the
  imagery (Cyclomedia), and (b) violating Cyclomedia's commercial Street
  Smart API ToS, which restricts use to the licensed customer's
  embed/viewer context.** This project is a polite, public-coverage scraper —
  it does not impersonate a B2B client of a third-party imagery vendor. This
  is the single hardest blocker.
- **Two-pass enumeration via the random-coordinate sampler.** The one path
  that *is* legitimately public — sampling `GetRandomWithCoordinates`
  unauthenticated until the seen-id set saturates — is technically feasible
  but is (a) clearly an unintended use of an endpoint designed to seed the
  viewer with a "pretty" starting pano, (b) heavy: at expected N ≈ 100 k –
  500 k panoramas, ≈ 3N requests for ~95 % saturation (Coupon Collector) =
  300 k – 1.5 M requests, and (c) brittle: there is no documented guarantee
  the sampler distribution is uniform over panoramas (it could be weighted
  toward "interesting" sites, biasing coverage). **Recommended only as a
  fallback if the user explicitly wants Istanbul coverage despite the
  caveats**, and even then as a *separate, opt-in* implementation behind
  a new source kind (see §4 — out-of-scope of a normal provider PR).

### Provider properties (the slots the template expects)

- **Homepage / public viewer URL:**
  - SPA: `https://harita.istanbul/` (open the **Panorama / Sokak
    Görüntüleri** tool in the left toolbar to drop a pin and open a pano).
  - Legacy redirect host: `https://sehirharitasi.ibb.gov.tr/` (302 → SPA).
  - Direct viewer iframe (requires `Referer: https://harita.istanbul/`):
    `https://cbspanorama.ibb.gov.tr/panorama/panorama2018/?token=fc470f86-16b6-44c2-81ec-0fe145d34b7b`
    optionally `&coordinates=<lon>,<lat>` and/or `&imageId=<id>` (e.g.
    `WE8UXF62`).
- **Tier:** **T3** (matches `docs/PLAN.md` §2).
- **Coverage endpoint(s):**
  - The single public, unauthenticated, coverage-shaped endpoint is
    ```
    GET https://cbspanorama.ibb.gov.tr/api/streetsmart/GetRandomWithCoordinates
    ```
    - **HTTP method:** `GET`. No query parameters; no body.
    - **Headers required for a 200:** none strictly; a polite descriptive
      `User-Agent` is enough. CORS is open (`Access-Control-Allow-Origin: *`).
    - **Response:** `application/json`, a single object —
      `{"id": "<panoid>", "coordinates": [<lon>, <lat>], "date": "<ISO-8601>"}`.
      `coordinates` is `[lon, lat]` in **WGS84 EPSG:4326** (confirmed: all
      observed pairs sit on Istanbul streets at expected lat/lon).
    - **Behaviour:** each call returns a *different* random panorama with
      replacement. In a 48-request burst, 46 distinct IDs were observed
      (~96 % unique → near-uniform sampling with replacement; ID space ≫ 48).
  - There is **no `?bbox=`**, **no `?z/x/y`**, **no list**, **no extent
    query**. Brute-probed sibling endpoints all 404 (verified
    `2026-05-25`):
    ```
    /api/streetsmart/GetPanoramas        404
    /api/streetsmart/GetByExtent         404
    /api/streetsmart/GetAll              404
    /api/streetsmart/List                404
    /api/streetsmart/Coverage            404
    /api/streetsmart/GetCoordinates      404
    /api/streetsmart/Search              404
    /api/streetsmart                     400 (validation error: `url` required — proxy stub, not a coverage list)
    /api/Panorama                        404
    /api/Panorama/List                   404
    /api/Panorama/GetAll                 404
    /swagger, /swagger/index.html        404
    ```
  - `GET /api/streetsmart?url=<https-url>` returns a `400 "url field is
    required"` validation error when called without `?url=` and an
    `Object reference not set to an instance of an object.` when called with
    a foreign URL — it is plainly an internal HTTP proxy stub for the
    Cyclomedia config / Street Smart calls IBB's own JS makes, not a generic
    coverage feed.
- **Coordinate scheme:**
  - The `GetRandomWithCoordinates` payload uses **WGS84 (`EPSG:4326`,
    `[lon, lat]`)**.
  - The IBB viewer / OpenLayers / Cyclomedia stack internally projects to
    **`EPSG:5269`** (Turkish TM30: `+proj=tmerc +lat_0=0 +lon_0=27 +k=1
    +x_0=9500000 +y_0=0 +ellps=GRS80 +units=m +no_defs`); not relevant for
    coverage, but record it for any future imagery-side work.
  - This project's coverage grid is **`web_mercator` (EPSG:3857)** as usual;
    points are supplied in WGS84 and rasterized like the existing point-list
    providers.
- **Zoom range / tile size / response format:** **not applicable.** The
  endpoint is not tile-based. There is no `{z}/{x}/{y}`, no
  vector-tile / raster-tile layer. Response is JSON, single object,
  ~110 bytes.
- **Auth:** **none** for `GetRandomWithCoordinates`. The viewer iframe
  requires a *referer-check* token (`?token=fc470f86-…`) and `Referer:
  https://harita.istanbul/`, but these gate viewer embedding, not data. **No
  `.env` key would be needed** for the legitimate (sampler) coverage path.
  The Cyclomedia path *is* gated by AES-encrypted credentials that would
  require client-side decryption and impersonation — explicitly **out of
  scope** of this provider; no `.env` key for that either.
- **Presence rule:** "IBB has a panorama here" ⇔ a panorama record (id,
  lat, lon, date) is present in the enumerated-or-sampled set. Each record
  becomes one `pano_record` (`provider="istanbul_ibb"`,
  `panoid=<id>`, `lat`, `lon`, `timestamp=<date>`), is rasterized onto the
  z14 grid with `point_buffer_cells≈1.0` (mirror `dprk360` / point-list
  providers), and `coverage_pixel_count` is counted from the rasterized
  cells. Because there is no bbox query and no "checked-empty" signal, the
  cells outside the seen-point footprint are `nodata (255)`, not
  `checked-empty (0)` — the same convention `dprk360` uses.
- **robots.txt / ToS notes; observed rate limit:**
  - `https://harita.istanbul/robots.txt` (verbatim, 2026-05-25):

    ```
    # https://www.robotstxt.org/robotstxt.html
    User-agent: *
    Disallow:
    ```

    All paths allowed. `robots_allows()` returns `True` for everything.
  - `https://cbspanorama.ibb.gov.tr/robots.txt` returns **empty body**
    (`Content-Length: 0`, no `Disallow`) → also allowed.
  - **IBB Open Data Portal license** (`https://data.ibb.gov.tr/en/license`) is
    `CC BY 4.0` with mandatory attribution and excludes personal data /
    military insignia / third-party rights IBB cannot license. The panorama
    coverage layer **is not in the Open Data Portal catalog** (verified via
    portal search); IBB's CC BY 4.0 therefore does *not* automatically cover
    the panorama data. The publication path is the city-map app, which
    carries no explicit API ToS.
  - **Cyclomedia's commercial Street Smart license** *does* apply to the
    panorama imagery and the recordings WFS, and forbids non-customer
    automated bulk access. This is the dispositive ToS for any path beyond
    the random sampler.
  - **Observed rate limit:** none enforced in a 48-request burst at
    ~3 req/s with a polite UA. The endpoint sits behind a stateless `nginx`
    edge and `Cache-Control: no-cache`; expect that high volumes would
    eventually be rate-limited or blocked. There is no published quota.
  - **Recommended throttle if and when the sampler path is implemented:**
    `polite.polite_fetch` with `min_interval_seconds ≥ 0.2` (≤ 5 req/s) and
    the project's standard retry/backoff.
- **Known quirks / gotchas:**
  - **Turkish-language API surfaces.** The host names (`sehirharitasi` =
    "city map", `cbspanorama` = "GIS panorama"), UI strings ("Sokak
    Görüntüleri" = "Street Views", `Seçtiğiniz noktaya ait çekim
    bulunmamaktadır` = "No recording at the selected point",
    `Seçtiğiniz noktayı görüntüleme izniniz bulunmamaktadır` = "You don't
    have permission to view the selected point"), and the developer docs are
    all Turkish. The JSON API itself is English-keyed (`id`, `coordinates`,
    `date`).
  - **Legacy host 302 trap.** Every path on the old
    `sehirharitasi.ibb.gov.tr` redirects to the SPA root
    (`/`, `/panorama/`, `/panorama/developer/` all 302 → `https://harita.istanbul/`).
    Cached scout notes referring to `sehirharitasi.ibb.gov.tr/panorama/developer/`
    are stale and yield no useful content.
  - **Viewer iframe needs the right `Referer`.** Without
    `Referer: https://harita.istanbul/`, `/panorama/panorama2018/?token=...`
    302s to `/Panorama/Error` (which itself 404s). Only matters if a future
    implementer wants to scrape the viewer HTML for any reason; the random
    sampler ignores referer.
  - **EPSG:5269 internal CRS.** The Cyclomedia/OpenLayers stack reprojects
    on the fly to Turkish TM30. Not used by our coverage extraction (we get
    WGS84 from `GetRandomWithCoordinates`), but flagged for the imagery side.
  - **Single capture wave, narrow date window.** All 48 sampled dates fall
    in 2023-07 → 2024-01. The dataset is effectively a one-shot Cyclomedia
    Istanbul campaign; no per-pano date layer beyond that range will appear.
  - **"Random sampler" may be non-uniform.** The endpoint name suggests a
    "give me a pretty pano to start on" UX. There is no guarantee
    `GetRandomWithCoordinates` returns each panorama with equal probability
    — it could be weighted toward landmarks (Sultanahmet, Bosphorus
    waterfront, Taksim) and under-sample suburbs. Coupon-collector estimates
    of N assume uniform sampling and may badly under-/over-estimate true
    coverage size. Implementer must measure the saturation curve early if
    this path is ever pursued.
  - **The "encrypted credentials" path is a trap.** `gak/gal/gam` plus
    `cr.js` decrypt to real Cyclomedia `username`/`password`/`ApiKey` /
    `ConfigurationUrl`. **Do not extract them; do not call Cyclomedia
    Atlas/StreetSmart from outside the viewer.** That is a Cyclomedia
    ToS violation regardless of how technically easy it is.

### Coverage extent (rough, from 48 random samples)

| metric | value |
| --- | --- |
| Lon (min, max) | `28.0620 E`, `29.7375 E` |
| Lat (min, max) | `40.8974 N`, `41.2495 N` |
| Date range | `2023-07-31` through `2024-01-23` |
| Distinct IDs / sample size | `46 / 48` (≈ 96 % unique) |
| Modal capture months | `2023-08`, `2023-09`, `2023-10`, `2023-11` |

The bbox tightly matches Istanbul Province's administrative outline (`28.0 E
– 29.8 E, 40.8 N – 41.3 N`). The 48-sample uniqueness suggests the population
is at least in the low thousands and very likely six figures — consistent
with Cyclomedia's published ~5 m spacing over the ~10 000 km of Istanbul road.

## 3. Test plan (write these FIRST — red before green)

> **The plan in §4 is "defer; do not implement now". This §3 is the test
> plan that the *would-be* implementation would use IF the user overrides
> the defer recommendation, and is the test plan to use when the eventual
> sampler-based implementation is approved. Unit tests must not hit the
> network; decode recorded fixtures under `tests/fixtures/istanbul_ibb/`.**

Fixtures (commit small):
- `tests/fixtures/istanbul_ibb/random_sample.json` — a single recorded
  response from `GET …/api/streetsmart/GetRandomWithCoordinates`, e.g.
  `{"id":"WE8UXF62","coordinates":[28.418766848079844,41.04734936541154],"date":"2023-12-28T06:36:55.69+00:00"}`.
- `tests/fixtures/istanbul_ibb/random_sample_batch.jsonl` — 5–10 recorded
  responses, one per line, for the dedup/aggregator tests (use only the
  five already captured in scout 2026-05-25, *not* a fresh live burst).
- `tests/fixtures/istanbul_ibb/coverage_extent.json` — a tiny static
  point-list file in `{"lastModified":..., "panos":[{...},{...}, …]}` shape
  produced by the aggregator from the batch fixture, used by the
  `coverage_json` decode test.

Tests (`tests/test_providers_istanbul_ibb.py`):

- [ ] `test_istanbul_ibb_registers` — importing
      `coverage_acquisition.providers.istanbul_ibb` registers
      `"istanbul_ibb"` in `PROVIDERS`; `get_provider("istanbul_ibb").key
      == "istanbul_ibb"`; the provider has exactly one source.
- [ ] `test_istanbul_ibb_source_kind` — the single
      `SourceDefinition.kind == "coverage_json"` (the existing point-list
      kind, fed by an aggregated-samples file — see §4 Approach A); the
      `template` is a `file://` (or runner-resolved local) URL pointing at
      the aggregated samples file under `data/external/istanbul_ibb/`.
- [ ] `test_istanbul_ibb_coordinate_scheme` —
      `PROVIDER.coordinate_scheme == "web_mercator"` (output grid; points
      supplied in WGS84, mirroring `dprk360`).
- [ ] `test_istanbul_ibb_sampler_parse` — a parser run on
      `random_sample.json` returns `{"panoid":"WE8UXF62",
      "lat":41.0473…, "lon":28.4188…, "timestamp":"2023-12-28T06:36:55.69+00:00"}`.
      Specifically: the `coordinates` array is `[lon, lat]`, not `[lat,
      lon]` — guard against an accidental swap.
- [ ] `test_istanbul_ibb_aggregator_dedupes` — feeding the aggregator the
      `random_sample_batch.jsonl` fixture (with at least one duplicate
      `id`) produces a deduplicated `{"panos":[...]}` JSON whose pano
      count == number of distinct ids.
- [ ] `test_istanbul_ibb_decode_pano_records` — feeding the
      `coverage_json` decoder the aggregated `coverage_extent.json` yields
      one `pano_record` per distinct id with `provider == "istanbul_ibb"`,
      numeric `lat`/`lon`, ISO timestamp, and the records are shaped so
      `runners.py` / `rasterize.py` consume them unchanged.
- [ ] `test_istanbul_ibb_bbox_filter` — the aggregator drops any sampled
      point that falls outside `28.0 ≤ lon ≤ 29.9, 40.8 ≤ lat ≤ 41.4`
      (the Istanbul Province envelope), with a unit test feeding it a
      synthetic out-of-bbox record (defensive; in practice the API only
      returns Istanbul points, but the filter is cheap insurance against a
      future scope change).
- [ ] `test_istanbul_ibb_no_auth_required` — the `SourceDefinition` sets
      no `token_query_param`; the module references no `.env` key; the
      sampler URL has no token.
- [ ] `test_istanbul_ibb_no_cyclomedia_decryption` — a guard test that
      asserts the provider module does *not* import any of
      `Crypto`, `cryptography`, or reference the strings `gak`, `gal`,
      `gam`, `StreetSmartApi`, `ConfigurationUrl`, `cyclomedia` —
      i.e. the implementation has not silently slipped into the
      ToS-hostile credential-decryption path. This is a hard guardrail.
- [ ] `test_istanbul_ibb_sampler_saturation_meta` — the aggregator emits a
      `meta` block with `sample_count`, `distinct_id_count`,
      `last_new_id_at_sample`, `lon_min/lon_max/lat_min/lat_max`, and a
      crude saturation estimate; basic schema check only.

## 4. Implementation subplan (steps for the implementer — TDD)

**The recommended action right now is _no implementation_.** This section
documents the implementation path **only so it can be approved later if
defer is reversed**. The implementer must not start work without explicit
re-approval after a re-probe (see §6).

If/when re-approved, the implementation is shaped like `dprk360` (a
**point-list provider**, not a tile provider):

### Source kind decision

- [ ] **Source kind: existing `coverage_json`** (Approach A — same shape as
  `dprk360`). The provider's data lives in a single committed file
  `data/external/istanbul_ibb/coverage_extent.json` in the
  `{"lastModified":"<scrape-date>", "panos":[{"panoid":..,
  "lat":.., "lon":.., "timestamp":..}, ...]}` schema that
  `source_kinds/coverage_json.py::decode_coverage_json` already parses.
  The source `template` is a `file://` URL (or the equivalent
  runner-resolved local path) pointing at that file. **No new source kind
  is needed; no shared-file edit is needed.** Mirror `dprk360` exactly.
- [ ] Alternative — Approach B (only if the user prefers): a new
  `random_sampler` source kind in a *separate* foundation PR (per
  `CLAUDE.md`), with its own runner integration that knows how to call a
  non-tile, non-bbox single-record endpoint repeatedly until a saturation
  criterion is met. Cleaner conceptually, but it edits shared code
  (`source_kinds/`, `runners.py`) and is large. Recommended **only** if
  multiple future providers turn out to need the same "saturate by random
  sampling" shape; for `istanbul_ibb` alone, Approach A is cheaper.

### Steps (Approach A)

- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Build the *one-shot* enumerator script (not part of the runner,
  not part of the provider PR's shared code) at
  `scripts/scrape_istanbul_ibb_sampler.py`:
  - Loops `GET …/api/streetsmart/GetRandomWithCoordinates` through
    `polite.polite_fetch` (descriptive `User-Agent`, ≤ 5 req/s,
    standard retry/backoff).
  - Maintains a `dict[id, {lat,lon,timestamp,first_seen_sample}]`,
    appending each new id and skipping duplicates.
  - Filters to `28.0 ≤ lon ≤ 29.9, 40.8 ≤ lat ≤ 41.4` defensively.
  - **Saturation stop criterion** (two-of-three, whichever fires first):
    (a) ≥ 50 000 distinct ids; (b) ≥ 200 000 total samples; (c) the rate
    of new ids per 1 000 samples falls below 1 (~99.9 % saturation
    estimate). Configurable. Logs progress every 1 000 samples.
  - Writes the aggregated `coverage_extent.json` to
    `data/external/istanbul_ibb/coverage_extent.json` and a sibling
    `meta.json` with sample stats. The aggregated JSON is the *committed
    data file* the provider source reads.
  - **Run in `tmux`** (per `CLAUDE.md` long-running scrape rule); this
    is a multi-hour job at minimum. The script is *not* the runner —
    it's a one-shot data-collection helper.
- [ ] Add `src/coverage_acquisition/providers/istanbul_ibb.py`
  (`ProviderDefinition`), self-registering:
  - `key="istanbul_ibb"`,
    `output_namespace="istanbul_ibb_panorama_points"`,
    `run_label_prefix="istanbul_ibb_panorama"`,
    `coordinate_scheme="web_mercator"`,
    `default_display_zoom=14`.
  - One `SourceDefinition`:
    - `id="istanbul_ibb_panorama_sites"`, `kind="coverage_json"`,
    - `template` = a `file://` URL (or local-path convention runner
      accepts) resolving to
      `data/external/istanbul_ibb/coverage_extent.json`,
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3"}`,
    - `storage_subdir="coverage_json"`,
    - `expect_content_type_prefix="application/json"`,
    - `notes` describing that this is a point list aggregated from the
      IBB random-coordinate sampler, single capture wave 2023–2024,
      Cyclomedia-sourced.
  - `area_presets`: declare the pilot + full-extent bboxes inline; do
    **not** edit `_presets.py`.
  - Module docstring records: (a) this is a **point-list provider**, not
    tile-based; (b) the data was aggregated via the random-coordinate
    sampler (no bbox endpoint exists) and is committed to the repo as a
    static file; (c) the imagery is **Cyclomedia-sourced** and is *not*
    downloaded — only the (`id`, lat, lon, date) tuples are stored; (d)
    the Cyclomedia-credential decryption path is intentionally NOT used
    (it would violate Cyclomedia ToS); (e) `harita.istanbul/robots.txt`
    allows everything; (f) coverage is Istanbul Province only.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot:** bbox `28.96 41.00 29.00 41.03` (**Sultanahmet / Eminönü
  — Istanbul historic peninsula**, ~3 km × 3 km). Filter the committed
  `coverage_extent.json` to the pilot bbox; confirm 100s–1000s of
  panorama points land on streets (Sultanahmet Square, Sirkeci,
  Eminönü waterfront, Galata Bridge approach). Same shape as the
  Mapilio pilot bbox (`28.96 41.00 29.00 41.03`) so existing analysis
  tooling can compare them directly.
- [ ] Rasterize the pilot subset to a z14 COG (`rasterize.py`,
  `point_buffer_cells≈1.0`, EPSG:3857, `uint8`,
  `1=covered / 255=nodata`).
- [ ] **Full extent:** there is **no two-pass tile discovery** — the
  coverage set is the committed point file. Rasterize all distinct
  points over the Istanbul Province envelope
  bbox `28.0 40.8 29.9 41.4` to the z14 COG. Document that "discovery"
  for this provider = re-running the sampler script.
- [ ] Update / create the STAC item for `istanbul_ibb` (extent =
  Istanbul Province bbox, scrape date, tier T3, "source" =
  `cbspanorama.ibb.gov.tr/api/streetsmart/GetRandomWithCoordinates`
  via sampler, ToS notes: Cyclomedia imagery not downloaded). Update
  the inventory status for `istanbul_ibb`.

### Why a normal "scrape on every coverage run" doesn't fit

`runners.py` enumerates `{z}/{x}/{y}` tiles over a bbox; this provider has
no tiles and no bbox endpoint. The aggregated point file is built **once,
out of band**, and committed; the provider source then behaves like
`dprk360` — a static, hand-built (here: sampler-built) point list. Future
re-scrapes are explicit re-runs of the sampler script, not part of the
nightly/weekly runner.

## 5. Acceptance criteria (checked by provider-verifier)

> **All §5 criteria are gated on the decision in §4 — until defer is
> reversed by the user, the provider is not implemented and there is
> nothing for verifier to check.** Once approved and implemented:

- All §3 tests pass; `coverage_acquisition.providers.istanbul_ibb` imports
  and self-registers (`"istanbul_ibb"` in `PROVIDERS`); CI smoke test
  passes.
- The provider's single source is `kind="coverage_json"`,
  `coordinate_scheme="web_mercator"`; the source resolves the committed
  `data/external/istanbul_ibb/coverage_extent.json` and decodes to one
  `pano_record` per distinct id; every record has numeric `lat`/`lon`,
  ISO `timestamp` in `2022-01-01..today`, and a non-empty `panoid`.
- The committed point table has no duplicate ids, has ≥ 25 000 records
  (a sanity floor consistent with Istanbul-scale Cyclomedia density),
  and every point lies inside `28.0 ≤ lon ≤ 29.9, 40.8 ≤ lat ≤ 41.4`.
- The Sultanahmet/Eminönü pilot subset rasterizes to a valid z14 COG
  (CRS EPSG:3857, `uint8`, covered pixels > 0, covered cells land on
  Sultanahmet/Eminönü streets — not the Marmara Sea, not the Golden Horn,
  not the Bosphorus water).
- Sampler script runs through `polite.polite_fetch` with a descriptive
  `User-Agent` and ≤ 5 req/s; no bare `urllib` / `requests`.
- Module docstring documents: point-list provider; data aggregated from
  the IBB random-coordinate sampler (no bbox endpoint exists);
  Cyclomedia-credential decryption path intentionally NOT used (ToS);
  only `(id, lat, lon, date)` tuples are stored, no imagery; single
  capture wave 2023–2024.
- `test_istanbul_ibb_no_cyclomedia_decryption` (§3) passes — i.e. the
  module is *clean* of any Cyclomedia-impersonation code.

## 6. Status log

- `2026-05-25` scout: drafted as **DEFER**. Findings (live probing):
  - **Front host:** `harita.istanbul/` (React/maplibre SPA). The legacy
    `sehirharitasi.ibb.gov.tr/` 302s to it on every probed path
    (`/`, `/panorama/`, `/panorama/developer/`); the
    `sehirharitasi.ibb.gov.tr/panorama/developer/` page cited by older
    write-ups no longer exists.
  - **Panorama viewer:** an `<iframe>` to
    `https://cbspanorama.ibb.gov.tr/panorama/panorama2018/?token=...`
    requiring `Referer: https://harita.istanbul/`. The iframe HTML loads
    `StreetSmartApi.js` and `PanoramaModule.js`, decrypts three
    AES-encrypted labels (`gak`/`gal`/`gam`) via `cr.js`, and hands
    `{UserName, Password, ConfigurationUrl, ApiKey, BoundaryBox}` to
    `StreetSmartApi.init(...)` — i.e. **IBB's panoramas are
    Cyclomedia Street Smart** under licensed B2B credentials. The
    panorama tiles, imagery, and recordings WFS are then fetched
    directly from Cyclomedia, not IBB.
  - **Only public coverage endpoint:** `GET
    https://cbspanorama.ibb.gov.tr/api/streetsmart/GetRandomWithCoordinates`
    — returns *one* random panorama as `{id, coordinates:[lon,lat],
    date}` (e.g. `WE8UXF62 / [28.418766848, 41.047349365] /
    2023-12-28T06:36:55Z`). Unauth, CORS-open, no `?bbox=`, no
    `?z/x/y`. Brute-checked `GetPanoramas` /
    `GetByExtent` / `GetAll` / `List` / `Coverage` / `GetCoordinates`
    / `Search` / `/api/Panorama/{List,GetAll}` / `/swagger` → all
    `404`. `/api/streetsmart` is a generic
    `?url=`-required HTTP proxy stub used by IBB's own JS, not a
    coverage feed.
  - **48-sample burst** at ~3 req/s with descriptive UA:
    - 46 / 48 distinct ids (≈ 96 % unique);
    - bbox `28.062–29.738 E, 40.897–41.250 N` (matches Istanbul
      Province exactly);
    - dates all in `2023-07-31 .. 2024-01-23` (single capture wave;
      modal months 2023-08..2023-11).
    - No rate limiting observed in this small burst.
  - **robots.txt:** `harita.istanbul` = `User-agent: * / Disallow:`;
    `cbspanorama.ibb.gov.tr` returns an empty robots.txt. Both allow all.
  - **IBB Open Data Portal CC BY 4.0 license does NOT cover the
    panorama layer** (layer is not in the open-data catalog). Cyclomedia
    commercial ToS *does* govern the imagery and the recordings WFS.
  - **Verdict:** *legitimate* coverage scrape would require sampling
    `GetRandomWithCoordinates` ~3 × N times to enumerate ~95 % of an
    expected N ≈ 100k–500k panoramas (300k–1.5M requests) against an
    endpoint not intended as a bulk feed. The cleaner-looking
    "decrypt the labels and call Cyclomedia directly" path is a
    Cyclomedia ToS violation and is explicitly ruled out. **Defer; do
    not open an implementation issue today.**
- `2026-05-25` approval: **pending** (awaiting user review).
- `YYYY-MM-DD` re-probe / re-approval: notes appended here.

### Re-probe checklist (when to revisit)

Run these every 3–6 months until at least one returns a positive answer:

1. **IBB Open Data Portal** — search `data.ibb.gov.tr` for
   "panorama" / "sokak görüntüsü" / "sokak görüntüleri" / "cyclomedia". If
   the panorama layer (or even just a point dataset of pano coordinates)
   is ever published there under CC BY 4.0, the provider becomes a clean
   `coverage_json` implementation overnight.
2. **`cbspanorama.ibb.gov.tr` endpoint surface** — re-brute-check
   `GetByExtent`, `GetPanoramas`, `GetAll`, `List`,
   `/api/Panorama/GetAll`, `/swagger`. If any becomes 200, that's the
   coverage feed.
3. **Bundle change** — re-fetch `harita.istanbul/static/js/main.<hash>.js`
   and grep for `streetsmart` / `panorama`. If new endpoints appear in
   the SPA's fetch surface, evaluate them.
4. **In-house re-capture** — watch IBB CBS announcements
   (`cbsakademi.ibb.istanbul`) for a switch from Cyclomedia to an
   in-house IBB capture system; that would remove the Cyclomedia ToS
   blocker.
5. **Updated capture date** — sample
   `GetRandomWithCoordinates` ~50 times. If observed `date` values
   include anything significantly after `2024-01`, a new Cyclomedia
   campaign has been added and (if Approach A is approved) the static
   point file would need re-scraping.

---

### Open questions for the reviewer

1. **Defer vs override.** Recommended posture is **defer**. The user
   may override and authorize the sampler-based Approach A
   implementation. Confirm whether to (a) leave deferred until a
   re-probe trigger fires, or (b) green-light Approach A now despite
   the ~300k–1.5M-request enumeration cost and the open question of
   sampler uniformity.
2. **Cyclomedia path is OUT.** Confirming the explicit guardrail —
   even if the user wants Istanbul coverage badly, the
   credential-decryption / Cyclomedia-WFS path is **off-limits**. The
   `test_istanbul_ibb_no_cyclomedia_decryption` guard test in §3
   enforces this in code if implementation ever happens. Confirm this
   guard is non-negotiable.
3. **Source-kind reuse.** Approach A reuses the existing
   `coverage_json` kind via a `file://` template (mirroring the
   `dprk360` precedent). This depends on the runner being able to
   resolve a `file://` / local-path template, which `dprk360` already
   exercises. If the runner cannot, a tiny runner tweak — or
   Approach B's `random_sampler` foundation kind — becomes necessary.
   Flag for the runner owner during approval.
4. **Sampler saturation criterion.** Proposed: stop at the first of
   ≥ 50 000 distinct ids OR ≥ 200 000 total samples OR < 1 new id per
   1 000 samples. Confirm these thresholds, especially the 50k floor
   (it presumes Istanbul Cyclomedia has at least ~50k panos; if true N
   is lower the script can stop earlier on the saturation criterion;
   if N is much higher (~500k) the 200k cap may need to lift to 1M+).
5. **Pilot bbox parity with Mapilio.** Proposed pilot bbox
   `28.96 41.00 29.00 41.03` is identical to the Mapilio Istanbul
   pilot bbox so the two providers can be visually compared on the
   exact same area. Confirm or substitute a different Istanbul
   sub-area.
6. **Re-probe cadence.** Proposed: every 3–6 months, run the §6
   checklist. Confirm cadence.

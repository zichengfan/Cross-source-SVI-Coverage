# [T2] Provider: DPRK 360 (`dprk360`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

DPRK 360 (`http://www.dprk360.com/`) is an independent 360° panorama project by
Singaporean photographer Aram Pan documenting sites inside North Korea (DPRK)
and a few China–DPRK border towns. It is **not** a continuous, pannable
street-level service: it is a **fixed, finite set of ~37 immersive 360° virtual
tours**, each covering one named site (a monument, a hotel, a museum, a farm, a
plane interior, etc.). Each tour is a self-contained 3DVista virtual-tour bundle
served from `https://dprk360.com/360/<slug>/`. The project is in scope as an
active, scrapable, non-defunct, non-re-hoster, non-paid-B2B provider: even a few
dozen panorama sites is genuine coverage in a country where almost no other SVI
provider has any. For this database we need only **coverage availability** —
"DPRK 360 has a 360° panorama at/near this location" — so the deliverable is a
small **point list** of the tour sites, rasterized onto the shared z14 grid by
buffering each point ~1 cell.

This is a **point-list provider**, not a tile-based one. It is closest in spirit
to the `coverage_json` source kind, but with one important difference documented
in §2 and §4: **the coordinates do not exist anywhere on the DPRK 360 server**
and must be supplied by a small, hand-geocoded table committed to the repo.

## 2. Research findings (filled by provider-scout)

### Verdict: a FIXED LIST OF ~37 panorama sites — no tile layer, no coverage API

There is **no** raster `{z}/{x}/{y}` tile layer, **no** vector MVT layer, and
**no** JSON coverage endpoint. DPRK 360 is a WordPress content site whose
panorama content is a finite set of static 3DVista tours. The "coverage" is the
**set of tour sites**, enumerable from the site itself; the **coordinates of
those sites are not published in any machine-readable form** and must be
hand-geocoded from the (well-known, named) places.

- **Homepage / public viewer URL:**
  - Homepage / blog: `http://www.dprk360.com/` (HTTPS works:
    `https://dprk360.com/`; `www.` and apex both resolve). This is a standard
    WordPress site.
  - Panorama viewer URL pattern: `https://dprk360.com/360/<slug>/` — e.g.
    `https://dprk360.com/360/juche_tower/`. Each is a 3DVista
    (`TDV.Tour` / `lib/tdvplayer.js`) virtual-tour bundle.
  - **Tier:** T2.

- **How the panorama list was identified (the coverage source):**
  - `https://dprk360.com/robots.txt` advertises a sitemap
    `https://dprk360.com/wp-sitemap.xml`. The `/360/<slug>/` viewer URLs are
    **not** in the sitemap (they are static directories outside WordPress).
  - The WordPress REST API **is** open and is the clean way to enumerate posts:
    `https://dprk360.com/wp-json/wp/v2/posts?per_page=100&_fields=id,slug,link,title`
    returns all **62 posts** (`X-WP-Total: 62`). Categories
    (`/wp-json/wp/v2/categories`): `inside-north-korea` (44 posts) is the
    panorama category; `highres` (5), `blog` (13) are non-panorama.
  - Each panorama **post** under `/inside-north-korea/...` embeds **one or more**
    `https://dprk360.com/360/<slug>/` viewer links in its HTML body. Scraping
    the `<body>` of all 62 posts for `dprk360.com/360/<slug>` and de-duplicating
    yields **37 distinct tour slugs** (the coverage set). Verified live
    2026-05-22 — all 37 `/360/<slug>/` URLs return **HTTP 200**.
  - **The 37 distinct tour slugs (the full coverage list as of 2026-05-22):**
    `12th_pyongyang_fashion_exhibition`, `air_koryo_Il-18`, `air_koryo_Il-76`,
    `arirang2013`, `bongsu_church`, `changchung_cathedral`,
    `changjon_street_night`, `chongsanri_cooperative_farm`, `chongsu`,
    `chongun_rock`, `chonsam_cooperative_farm`, `farmer_house`,
    `golden_triangle_bank_rason`, `hungnam_fertilizer_complex`, `hyangsan_dam`,
    `hyangsan_hotel`, `juche_tower`, `juche_tower_floating_view`,
    `kaesong_old_town`, `kalma_beach`, `koryo_hotel`, `kpaaf_mi-17`,
    `kumsusan_palace_of_the_sun`, `mangyongdae_native_home`,
    `mangyongdae_prize_international_marathon`,
    `mansudae_grand_monument_floating_view`, `mansudae_grand_monument_night`,
    `monument_to_party_founding`, `pohyon_buddhist_temple`,
    `rungrado_may_day_stadium`, `samjiyon_grand_monument`, `sariwon_migok`,
    `sci_tech_complex`, `victorious_fatherland_liberation_war_museum`,
    `virtual_gallery_anti_us_war_posters`, `yanggakdo_hotel`, `yeonmijeong`.
  - A handful of slugs are not geographic *sites* (e.g.
    `virtual_gallery_anti_us_war_posters` is an indoor exhibit;
    `*_floating_view` / `*_night` are alternate renders of a site already in
    the list). De-duplicate by **physical site** when building the point table
    (see §4) — the expected distinct *site* count after collapsing alternate
    renders is roughly **30–34 points**, all worth keeping.

- **"Coverage endpoint(s)":** there is no coverage tile/JSON endpoint. The two
  fetchable, machine-readable inputs are:
  1. **`https://dprk360.com/wp-json/wp/v2/posts?per_page=100&_fields=id,slug,link,title`**
     — `GET`, JSON, no auth. The post inventory; pagination via `?page=N` if a
     future re-scrape exceeds 100 posts (62 today, one page).
  2. The HTML body of each `/inside-north-korea/<post-slug>/<id>/` post — `GET`,
     `text/html`, no auth — scraped for `dprk360.com/360/<slug>` substrings to
     get the tour list.
  Optionally, each `https://dprk360.com/360/<slug>/` tour can be probed with a
  `HEAD`/`GET` purely to confirm it is live (HTTP 200) — useful as a freshness
  check, not for coordinates.

- **Coordinate scheme:** **WGS84 lat/lon** in the final point table. **There are
  NO coordinates on the server** — this is the key finding. The 3DVista tour
  bundles (`/360/<slug>/script_general.js`) were inspected and contain **no**
  `latitude`/`longitude`/`gps`/`googleMaps`/`panoramaMapLocation` data; the
  WordPress posts carry **no** geo plugin meta (`/wp-json/.../posts/<id>` `meta`
  is empty). Therefore the lat/lon for each site must be **hand-geocoded** from
  the place name (all are named, well-known landmarks — Juche Tower, Kumsusan
  Palace, Yanggakdo Hotel, Rungrado May Day Stadium, etc.) and **committed to
  the repo as a static table** (see §4). This is a one-time human/lookup step;
  ~30 well-known landmarks geocode unambiguously.

- **Zoom range / tile size / response format:** not applicable — no tiles. The
  panorama viewer media are cube-face JPEGs
  (`media/panorama_<id>_<n>/<face>/<level>/<x>_<y>.jpg`) and are **not**
  downloaded — this project stores coverage presence only, never imagery.

- **Auth:** **none.** The WordPress REST API, the post HTML, and the `/360/`
  tours are all public and unauthenticated. **No `.env` key is needed.**

- **Presence rule:** "DPRK 360 has imagery here" ⇔ the location is one of the
  ~30–34 panorama sites in the committed point table. After rasterization, each
  site point is buffered by ~1 z14 cell (`rasterize.py`,
  `point_buffer_cells=1.0`) → that cell (and immediate neighbours) = covered
  (1); everywhere else = nodata (255). There is no "checked-empty" concept for a
  finite point list — cells are either a known site or nodata.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://dprk360.com/robots.txt` (verbatim, fetched 2026-05-22):

    ```
    User-agent: *
    Disallow: /wp-admin/
    Allow: /wp-admin/admin-ajax.php

    Sitemap: https://dprk360.com/wp-sitemap.xml
    ```

    Only `/wp-admin/` is disallowed. The `/wp-json/`, `/inside-north-korea/`,
    and `/360/` paths this provider reads are **all allowed** —
    `robots_allows()` returns `True` for every URL fetched.
  - **ToS:** DPRK 360 is a personal project (Aram Pan). The site has a
    privacy-policy page but no machine-readable API ToS. This provider stores
    only a **derived binary coverage raster** (presence of a panorama at a
    place) plus a small point list of public landmark names/coords — **no
    imagery, no panorama media, no copyrighted tour content** is downloaded or
    redistributed. Record this caveat in the module docstring. This is a tiny,
    polite scrape (≈ 1 API call + 62 post pages once; ~30 optional HEAD probes).
  - **Rate limit:** none observed; the site is small. Use the project polite
    default (`polite.polite_fetch`, descriptive User-Agent, per-host throttle).
    The whole scrape is < 100 requests total and is run once per re-scrape.

- **Known quirks / gotchas:**
  - **Not a tile provider.** No `{z}/{x}/{y}`. The runner's tile-enumeration
    machinery does not apply — see §4 for how this provider is shaped instead.
  - **Coordinates are NOT on the server.** Unlike the `coverage_json` kind
    (where each pano JSON carries `lat`/`lon`), DPRK 360 publishes no
    coordinates anywhere. The point table is **hand-geocoded and committed to
    the repo**. This is the single most important implementation fact.
  - **Coverage is place-level, not pano-level.** Each `/360/<slug>/` tour is a
    *multi-scene* tour of one site (e.g. the war museum tour has ~9 scenes:
    "Entrance", "USS Pueblo - Bridge", "Battle Of Taejon", ...). For a global
    z14 coverage grid the whole site collapses to **one point** — do not try to
    place each interior scene separately (they have no coordinates anyway).
  - **Alternate-render slugs.** Some sites appear under multiple slugs
    (`juche_tower` + `juche_tower_floating_view`; `mansudae_grand_monument_*`).
    Collapse these to one point per physical site in the table.
  - **Non-site tours.** `virtual_gallery_anti_us_war_posters` and similar are
    indoor/abstract exhibits inside a site already on the list (or with no
    distinct geography) — map them to the parent site or drop them; note the
    decision in the table.
  - **A few sites are on the China side of the border** (e.g. Dandong-area
    border content referenced in posts; `golden_triangle_bank_rason` is in
    Rason, DPRK). Geocode each to its real country — most are DPRK, a few are
    Chinese border towns. The discovery bbox in §4 covers both.
  - **3DVista bundles are static.** The tour list changes only when Aram Pan
    adds a new tour (rare — last new content ~2023). A re-scrape is a manual
    re-run, not a scheduled crawl. Pin the slug list in the committed table and
    re-verify on re-scrape.
  - **HTTP vs HTTPS / `www`.** The inventory lists `http://www.dprk360.com/`.
    Use `https://dprk360.com/` (HTTPS upgrade works; some embedded links use
    `www.`, which 301-redirects to the apex). Normalise to `https://dprk360.com`.

## 3. Test plan (write these FIRST — red before green)

Unit tests must not hit the network. Commit small recorded fixtures under
`tests/fixtures/dprk360/`:
- `wp_posts.json` — a trimmed recorded
  `wp-json/wp/v2/posts?per_page=100&_fields=id,slug,link,title` response
  (a handful of posts is enough for the parser test).
- `post_with_tours.html` — one recorded `/inside-north-korea/.../` post HTML
  body that embeds ≥ 2 `dprk360.com/360/<slug>` links (e.g. the Air Koryo post,
  which embeds three tours).
- `points.json` (or `points.csv`) — the committed hand-geocoded point table
  itself (see §4); it is both the data file and a test fixture.

Tests (`tests/test_providers_dprk360.py`):

- [ ] `test_dprk360_registers` — importing
  `coverage_acquisition.providers.dprk360` registers `"dprk360"` in `PROVIDERS`;
  `get_provider("dprk360").key == "dprk360"`; the provider has exactly one
  source.
- [ ] `test_dprk360_source_kind` — the single `SourceDefinition.kind` is
  `"coverage_json"` (see §4 — the existing point-list kind) **or** the agreed
  static-point-list kind; assert whichever §4 settles on.
- [ ] `test_dprk360_coordinate_scheme` — `PROVIDER.coordinate_scheme` is the
  WGS84 lat/lon scheme used for point rasterization (`web_mercator` grid is the
  output; points are supplied in WGS84 — match how `apple_lookaround` /
  `rasterize.py` consume `pano_records`).
- [ ] `test_dprk360_point_table_loads` — the committed `points.json` parses to a
  list of records, each with non-empty `slug`, `site_name`, numeric `lat` in
  `[37.0, 43.5]` and `lon` in `[124.0, 131.5]` (the DPRK + China-border
  envelope), and a `country` of `KP` or `CN`. Assert the table has **≥ 25**
  points (sanity floor; expected ~30–34).
- [ ] `test_dprk360_point_table_no_dupes` — no two rows share the same
  `(round(lat,4), round(lon,4))`; alternate-render slugs are collapsed so each
  physical site appears once.
- [ ] `test_dprk360_decode_pano_records` — feeding the source decoder the
  committed point table yields one `pano_record` per site with `provider ==
  "dprk360"`, a `panoid` (use the slug), and numeric `lat`/`lon` — i.e. the
  records are shaped exactly like the `coverage_json` kind's `pano_records` so
  `runners.py` / `rasterize.py` can consume them unchanged.
- [ ] `test_dprk360_post_tour_extraction` — a parser run over
  `post_with_tours.html` extracts the expected set of `/360/<slug>` slugs
  (≥ 2, de-duplicated, lower-cased, `www.`-normalised). (This test guards the
  *re-scrape* helper that regenerates the slug list; it does not run at
  coverage-build time.)
- [ ] `test_dprk360_wp_posts_parse` — the WP-API parser over `wp_posts.json`
  returns the post `link`s for category `inside-north-korea` and ignores
  `blog`/`highres` posts.
- [ ] `test_dprk360_no_auth_required` — the `SourceDefinition` sets no
  `token_query_param`; the module references no `.env` key.

## 4. Implementation subplan (steps for the implementer — TDD)

### Source kind decision — read this first

DPRK 360 is a **fixed point list whose coordinates are not on the server**. The
existing `coverage_json` kind (`src/coverage_acquisition/source_kinds/coverage_json.py`)
is the *closest* model — it already emits `pano_records` with `lat`/`lon` that
`runners.py` writes to `pano_records.csv` and `rasterize.py` buffers by ~1 cell.
**But** `coverage_json` currently expects to *fetch one JSON file per `{x}/{y}`
tile* with a `{"panos": [...]}` schema, and the runner enumerates tiles over a
bbox. DPRK 360 has no tile endpoint and no per-tile JSON.

Two viable approaches — **the reviewer must pick one** (see Open Questions):

- **Approach A (recommended) — reuse `coverage_json` with a single committed
  data file.** Treat the hand-geocoded point table as the one and only
  "coverage JSON". Commit `data/external/dprk360/points.json` in the exact
  `{"panos": [{"panoid": <slug>, "lat": .., "lon": .., "site_name": ..,
  "country": ..}, ...], "lastModified": "<scrape-date>"}` schema the existing
  `decode_coverage_json` already parses. The provider's source `template` is a
  `file://` URL (or the provider is fetched via a one-tile job at a fixed
  `x=0,y=0`) pointing at that committed file, so **no new source kind is
  needed** and `decode_coverage_json` works unchanged. This keeps the provider
  PR free of shared-file edits.
- **Approach B — a small new `static_points` source kind** (a separate
  `foundation`-labelled PR *before* the provider PR, per `CLAUDE.md`): a kind
  that reads a committed local point file and emits `pano_records` directly,
  with no tile enumeration. Cleaner conceptually, but it edits shared code
  (`source_kinds/`, possibly `runners.py`'s job builder). Only do this if the
  reviewer judges the `file://`-single-tile hack in Approach A too ugly.

The steps below assume **Approach A**; if Approach B is chosen, the foundation
PR lands first and the provider PR then just declares `kind="static_points"`.

### Steps

- [ ] **Source kind: existing `coverage_json`** (Approach A) — no new kind. If
  the reviewer picks Approach B, add `static_points` as a separate foundation PR
  first.
- [ ] **Build the committed point table.** Create
  `data/external/dprk360/points.json`. For each of the 37 tour slugs in §2:
  1. Identify the physical site from the slug + the parent
     `/inside-north-korea/` post title/text.
  2. Collapse alternate-render slugs (`*_floating_view`, `*_night`, the two
     `air_koryo_*` plane interiors → keep as distinct *or* merge to one
     "Pyongyang airport / Air Koryo" point — document the choice) and
     non-geographic exhibits to one point per physical site.
  3. Hand-geocode each site to WGS84 lat/lon (all are named landmarks —
     Juche Tower 39.0356 N 125.7656 E, Kumsusan Palace, Rungrado May Day
     Stadium on Rungra Island, Yanggakdo Hotel on Yanggak Island, Pohyon
     Temple at Mt. Myohyang, Samjiyon Grand Monument near Mt. Paektu, etc.).
     Use OpenStreetMap / Wikipedia coordinates; record the source per row.
  4. Write each row as `{"panoid": <primary slug>, "lat": .., "lon": ..,
     "site_name": <human name>, "country": "KP"|"CN", "tour_url":
     "https://dprk360.com/360/<slug>/", "coord_source": <where geocoded>}`.
  5. Wrap as `{"lastModified": "2026-05-22", "panos": [ ... ]}`.
  Expected ~30–34 rows. This file is the provider's coverage data and a test
  fixture; commit it (it is small, public landmark coordinates only).
- [ ] **Re-scrape helper (optional but recommended).** Add a small script /
  module function that regenerates the *slug list* (not the coordinates) from
  the live site: GET the WP API, GET each `inside-north-korea` post, extract
  `/360/<slug>` links, diff against `points.json`, and report any new or
  removed tours so a human can geocode additions on the next re-scrape. This is
  the parser exercised by `test_dprk360_post_tour_extraction` /
  `test_dprk360_wp_posts_parse`. It uses `polite.polite_fetch`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/dprk360.py` defining `PROVIDER`
  (`ProviderDefinition`) and calling `register_provider(PROVIDER)`:
  - `key="dprk360"`, `output_namespace="dprk360_panorama_points"`,
    `run_label_prefix="dprk360_panorama"`,
    `coordinate_scheme="web_mercator"` (output grid; points supplied in WGS84),
    `default_display_zoom=14`.
  - One `SourceDefinition`:
    - `id="dprk360_panorama_sites"`, `kind="coverage_json"` (Approach A),
    - `template` = a `file://` URL (or relative-path convention the runner
      accepts) resolving to `data/external/dprk360/points.json`,
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3"}`,
    - `storage_subdir="coverage_json"`,
    - `expect_content_type_prefix="application/json"`,
    - `notes` describing that this is a fixed, hand-geocoded point list of ~30
      DPRK 360 panorama sites (coordinates not published by the provider).
  - `area_presets`: declare the pilot + full-extent bboxes inline in this module
    (do **not** edit `_presets.py`).
  - Module docstring: record (a) this is a **fixed point-list** provider, not a
    tile provider; (b) **coordinates are hand-geocoded and committed** because
    DPRK 360 publishes none; (c) the ToS posture — only a derived coverage
    raster + public landmark coordinates are stored, never panorama imagery;
    (d) coverage = ~30 named sites in the DPRK + a few China border towns.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot:** there is no live tile fetch. The "pilot" is rasterizing the
  **Pyongyang subset** of the point table — bbox `125.68 38.98 125.83 39.08`
  (central Pyongyang: Juche Tower, Kim Il Sung Square, Mansudae, the war
  museum, sci-tech complex are all inside). Confirm those points decode to
  `pano_records` and land in central Pyongyang (on land, not the Taedong River).
- [ ] Rasterize the pilot subset to a z14 COG (`rasterize.py`,
  `point_buffer_cells≈1.0`, EPSG:3857, `uint8`, 1=covered / 255=nodata).
  Sanity-check covered cells fall on Pyongyang landmarks.
- [ ] **Full extent:** there is **no two-pass tile discovery** — the coverage
  set is the committed point table. Rasterize all ~30 points over the full
  envelope bbox `124.0 37.0 131.5 43.5` (DPRK + China-border towns) to the
  z14 COG. Document that "discovery" for this provider = the slug-list
  re-scrape helper, not a tile sweep.
- [ ] Update / create the STAC item for `dprk360` (extent = the point envelope,
  scrape date, tier T2, "source" = `dprk360.com` WP API + `/360/` tours, ToS
  notes). Update the inventory status for `dprk360`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.dprk360` imports and
  self-registers (`"dprk360"` in `PROVIDERS`); CI smoke test (import + register
  + dry-run) passes.
- The provider's single source decodes the committed `points.json` to one
  `pano_record` per site (`provider == "dprk360"`, numeric `lat`/`lon`,
  `panoid` = slug); ≥ 25 sites present.
- The committed point table has no duplicate sites; every point falls inside the
  DPRK + China-border envelope (`124–131.5 E`, `37–43.5 N`) and on land.
- The z14 COG is valid: CRS EPSG:3857, `uint8`, covered pixels > 0, isolated
  points buffered ~1 cell; covered cells land on real DPRK / border landmarks
  (Pyongyang cluster visibly correct).
- Any live fetches (the re-scrape helper) go through `polite.polite_fetch` with
  a descriptive User-Agent; no bare `urllib`/`requests`.
- Module docstring documents: fixed point-list provider; coordinates
  hand-geocoded (provider publishes none); only a coverage raster + public
  landmark coordinates stored, never imagery; robots.txt allows all fetched
  paths.

## 6. Status log

- `2026-05-22` scout: drafted. Investigated `dprk360.com` live. Findings:
  - DPRK 360 is a WordPress site; panorama content is **~37 static 3DVista
    virtual tours** at `https://dprk360.com/360/<slug>/`, **not** a tile-based
    or API-based coverage service. No raster `{z}/{x}/{y}` layer, no vector
    MVT, no JSON coverage endpoint.
  - The tour list is enumerable: WP REST API
    `wp-json/wp/v2/posts?per_page=100&_fields=...` (62 posts, `X-WP-Total: 62`,
    open, no auth) → scrape each `inside-north-korea` post body for
    `dprk360.com/360/<slug>` links → **37 distinct tour slugs** (all return
    HTTP 200, verified 2026-05-22). After collapsing alternate renders /
    non-site exhibits, ~30–34 distinct physical sites.
  - **No coordinates anywhere on the server.** The 3DVista bundles
    (`/360/<slug>/script_general.js`) contain no `latitude`/`longitude`/`gps`/
    `panoramaMapLocation` data; WordPress post `meta` is empty. Coordinates
    must be **hand-geocoded from the named landmarks and committed to the
    repo** as `data/external/dprk360/points.json`.
  - `robots.txt`: only `/wp-admin/` disallowed — `/wp-json/`,
    `/inside-north-korea/`, `/360/` all allowed. Auth: none, no `.env` key.
  - Recommended source kind: existing **`coverage_json`** fed by a single
    committed point file (Approach A) — no new source kind, no shared-file
    edit. Approach B (a `static_points` foundation kind) noted as an
    alternative if the reviewer dislikes the `file://`-single-fetch shape.
  - Verdict: DPRK 360 is **cleanly scrapable** as a small fixed point-list
    provider. Worth keeping — ~30 panorama sites in a country with almost no
    other SVI coverage.
- `2026-05-22` approval: **pending** (awaiting user review).
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **Source-kind approach (A vs B).** Approach A reuses the existing
   `coverage_json` kind by pointing the source `template` at a committed local
   `points.json` (via a `file://` URL or a one-tile job). It needs **no
   shared-file change** and keeps the provider PR self-contained — recommended.
   Approach B adds a clean new `static_points` source kind in a separate
   foundation PR. Confirm A, or request B. (If the runner cannot resolve a
   `file://`/local-path `template` at all, a *tiny* runner tweak — or Approach
   B — becomes necessary; flag for the runner owner.)
2. **Hand-geocoding is unavoidable.** DPRK 360 publishes zero coordinates, so
   the ~30-point table must be hand-geocoded from named landmarks and committed.
   Confirm this is acceptable (it is a one-time ~30-row lookup of well-known
   places; OSM/Wikipedia coordinates, one `coord_source` per row for
   traceability).
3. **Alternate-render and non-site slugs.** Confirm the rule: collapse
   `*_floating_view` / `*_night` and the two `air_koryo_*` plane interiors to
   one point per physical site, and map non-geographic exhibits
   (`virtual_gallery_anti_us_war_posters`) to their parent site or drop them —
   the table records the decision per row.
4. **Re-scrape cadence.** DPRK 360 adds tours rarely (last new content ~2023).
   Confirm that re-discovery is a **manual** run of the slug-list helper (diff
   live `/360/` slugs against `points.json`), not a scheduled crawl.
5. **No date layer.** The tours carry no capture dates in machine-readable form
   (some post bodies mention years in prose). Confirm `dprk360` ships with no
   `*_year.tif` date layer.
</content>
</invoke>

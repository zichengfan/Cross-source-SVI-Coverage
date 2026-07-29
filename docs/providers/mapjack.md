# [T3] Provider: MapJack Street View (`mapjack`) — RECOMMEND IMPLEMENT

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): IMPLEMENT. Despite the inventory flagging MapJack as
"old / unverified", the service is ALIVE and was REBUILT in 2025. `mapjack.com`
serves a modern viewer (openresty, `Last-Modified: 2025-04-10`, footer "© 2025
MapJack", Google Maps JS API base map + a custom WebGL panorama viewer). Most
importantly, the coverage layer is a plain, unauthenticated, standard
web-mercator XYZ raster tile pyramid: `dots_r5/{z}/{x}/{z}_{x}_{y}.gif`
(256x256 GIF, semi-transparent blue dots = panorama positions). Probed live
2026-05-28: present tiles return HTTP 200 + GIF with non-transparent dot
pixels; absent tiles return HTTP 404. This maps cleanly onto the existing
`raster` source kind with a 404-as-absent presence rule. Coverage is seven Thai
cities (Chiang Mai, Phuket, Krabi, Hua Hin, Ayutthaya, Mae Hong Son, Pai) plus a
set of US Bay-Area / Tahoe / Yosemite cities whose tiles are STILL served by the
server even though the viewer's city list comments them out. There is one
material ToS caveat (the Terms of Use forbid "mass downloads / bulk feeds of
imagery or any numerical data") — see §2; the project stores only a derived
binary-presence raster, no imagery and no MapJack numerical data, but the
implementer MUST scrape politely (low concurrency, throttle, descriptive UA) and
document the caveat in the module docstring. This is the opposite of the `xygo`
case: the backend is live and the coverage signal is trivially scrapable today.
-->

## 1. Summary

MapJack (mapjack.com; author/operator credited in page source as "Björn Morén",
historically HQ'd in Hong Kong) is one of the earliest street-level imagery
pioneers, launched ~2007 (initial release May 2007) — predating widespread
Google Street View. It captured ground-level 360° panoramas at car/ground level
across **Thailand** (Chiang Mai, Phuket, Krabi, Hua Hin, Ayutthaya, Mae Hong
Son, Pai) and several **US** locations (San Francisco Bay Area, Oakland, Palo
Alto, San Jose, Sausalito, Lake Tahoe, Yosemite). The imagery is old (mostly
2007–2009 vintage), but the **website itself is live and was rebuilt in 2025**
(modern openresty host, Google Maps JS API base map, WebGL panorama viewer,
"© 2025 MapJack" footer). It is in scope as a T3 first-party SVI provider
(not a re-hoster, not paid-B2B): Thailand street-view providers are rare in the
inventory, and MapJack is the only one with a public viewer. Scouting confirms a
**live, publicly scrapable coverage layer** — a standard XYZ raster tile
overlay (`dots_r5`) — so the recommendation is **IMPLEMENT** as a `raster`
provider, not defer. The one caveat is a restrictive Terms-of-Use clause
(§2) that requires polite, low-volume scraping of the derived coverage signal.

## 2. Research findings (filled by provider-scout)

### Verdict: live, scrapable raster coverage layer — IMPLEMENT

Applying the kakao/naver/mapy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — YES.**
   The viewer renders panorama-position "blue dots" as a Google Maps
   `ImageMapType` overlay backed by GIF tiles at
   `dots_r5/{z}/{x}/{z}_{x}_{y}.gif`. This IS the coverage layer and is the
   recommended source. (No further fallback needed.)
2. Vector tile layer? — n/a (not used).
3. Coverage JSON API? — n/a (not used for the map overlay). The per-city site
   data lives under `data_r5/` and is only consulted on click to load
   individual panoramas; coverage discovery does not need it.

### Live infrastructure probe (2026-05-28)

| Host / path | Status | Notes |
|---|---|---|
| `www.mapjack.com` / `mapjack.com` | `209.17.116.160` | HTTP 200, `Server: openresty/1.27.1.2`, `Last-Modified: 2025-04-10`. The rebuilt viewer. |
| `https://www.mapjack.com/` | HTTP 200 | HTTPS is served (use it). |
| `explore.mapjack.com` | `205.178.146.236` | HTTP 404 — stale subdomain, ignore. |
| `dots_r5/{z}/{x}/{z}_{x}_{y}.gif` | **200 (present) / 404 (absent)** | The coverage tile pyramid. Verified across z8–z18 over Thai cities. |
| `config.js` | 200 | Drives the viewer; contains the tile-URL template, city list + bboxes (see below). |
| `index_min.js` | 200 | Minified viewer; contains the `getTileUrl` builder (verbatim below). |

The homepage `<head>` loads `config.js`, `index_min.js`, and the Google Maps
JS API (`maps.googleapis.com/maps/api/js?key=...&libraries=maps,marker,places`).
The Google base map is **not** the coverage signal — only the `dots_r5` overlay
is. We never touch Google's tiles.

### The coverage tile layer — verbatim from `index_min.js`

The dot overlay is registered as a Google Maps `ImageMapType`:

```js
new google.maps.ImageMapType({
  getTileUrl:(t,e)=>this.serverAddress+DOT_OVERLAY_FOLDER+"/"+e+"/"+t.x+"/"+e+"_"+t.x+"_"+t.y+".gif",
  tileSize:new google.maps.Size(256,256),
  opacity:t, minZoom:0, maxZoom:17
})
```

with, from `config.js`:

```js
const SERVER_ADDRESS = "";              // => tiles are relative to mapjack.com
const DOT_OVERLAY_FOLDER = "dots_r5";
```

Here `t` is the Google Maps tile coord `{x, y}` and `e` is the **zoom**, so the
resolved template (standard XYZ web-mercator, z/x/y) is:

```
https://www.mapjack.com/dots_r5/{z}/{x}/{z}_{x}_{y}.gif
```

- **Coverage endpoint:** `GET https://www.mapjack.com/dots_r5/{z}/{x}/{z}_{x}_{y}.gif`
- **HTTP method:** GET (HEAD also works — useful for cheap discovery).
- **Headers:** none required. A descriptive `User-Agent` and
  `Referer: https://www.mapjack.com/` are polite and were used in probing.
  No cookie, no token.
- **Query params:** none (path-only).
- **Coordinate scheme:** **`web_mercator`** (standard Google/OSM XYZ; verified
  by computing z/x/y for Chiang Mai/Ayutthaya centres and getting 200s, and 404s
  for ocean/Bangkok-centre). The `{z}` value is repeated inside the filename.
- **Zoom range / tile size / response format:** tile size **256x256**. Viewer
  display caps at maxZoom 17, but the server also serves **z18** tiles (probed
  200). Low zooms down to **z8** (and lower) return real dot tiles, so the
  pyramid is dense across the whole range — ideal for two-pass discovery.
  Response format: **GIF** (palette mode `P` with a transparent index;
  PIL `Image.open(...).convert("RGBA")` yields correct alpha).

### Presence rule (how a response decides "imagery exists here")

- **HTTP 200 + GIF body with `alpha>0` pixels ⇒ COVERED (1).** Every present
  tile probed contained hundreds–thousands of non-transparent blue-dot pixels;
  there is no "blank 200" tile.
- **HTTP 404 (HTML error body, ~355 bytes) ⇒ CHECKED-EMPTY / no coverage (0).**
  Absent tiles 404 cleanly. Verified: central Bangkok (13.756N, 100.502E),
  Andaman ocean, and the Sahara all 404 at z14/z16.

So the rule is: **`coverage_from=alpha`** with covered = `coverage_pixel_count>0`,
and **404 ⇒ checked-empty (not nodata)**. See the §2 "Decoder gap" note: the
existing `raster` source kind treats `transparent_png`/`http_204` empties via
empty-body/204, not 404, and the runner's `skip_404` records a 404 as *skipped*
rather than as *checked-empty(0)*. For MapJack the 404 IS a definitive
"no-coverage-here" signal at that tile, so the implementer should ensure 404
tiles are counted as `is_empty` (0) — see §4 for the two clean ways to do this
without inventing a new source kind.

### Coverage extent — cities + bboxes (from `config.js` `CITIES`)

**Active in the live viewer (Thailand):** (bbox = `lon1 lat1 lon2 lat2`)

| City | min_lon | min_lat | max_lon | max_lat |
|---|---|---|---|---|
| Chiang Mai | 98.899549 | 18.697236 | 99.073957 | 18.864633 |
| Phuket | 98.109975 | 7.689332 | 98.535695 | 8.164030 |
| Krabi | 98.708579 | 7.998986 | 98.932426 | 8.212439 |
| Hua Hin | 99.952519 | 12.564533 | 99.961703 | 12.576638 |
| Ayutthaya | 100.532096 | 14.328220 | 100.596812 | 14.372458 |
| Mae Hong Son | 97.776283 | 19.261233 | 98.310493 | 19.583723 |
| Pai | 98.418760 | 19.304568 | 98.474035 | 19.417288 |

(The `Pattaya` city block is commented out in `config.js`; tiles may or may not
still exist — discovery will tell.)

**Commented-out in the viewer but tiles STILL served by the server (USA):**
Lake Tahoe, Oakland, Palo Alto, **San Francisco**, San Jose, Sausalito,
Yosemite. Confirmed live: the SF z8 tile (`dots_r5/8/40/8_40_98.gif`) returns 200
with 626 non-transparent pixels. The full-extent two-pass discovery (§4) will
pick these up automatically since it sweeps a global low-zoom grid and follows
404 vs 200; do not hardcode the US bboxes off the (commented) config — let
discovery find them. US city bboxes from the commented config, for reference:
SF `-122.617716 37.629874 -122.343058 37.843281`, Oakland
`-122.342665 37.732446 -122.186797 37.890847`, Palo Alto
`-122.281259 37.335640 -122.034754 37.504694`, San Jose
`-121.990668 37.257780 -121.629504 37.368282`, Sausalito
`-122.547747 37.828707 -122.444407 37.885089`, Lake Tahoe
`-120.316223 38.799400 -119.755921 39.389858`, Yosemite
`-119.959717 37.50101 -119.130249 38.164795`.

### Auth, robots, ToS

- **Auth.** **None.** The `dots_r5` tiles are unauthenticated path-only GETs.
  No cookie, no token, **no `.env` key needed.** (The Google Maps API key in the
  page is for Google's base map / Places search, which we do not scrape.)
- **robots.txt.** `https://www.mapjack.com/robots.txt` → **HTTP 404** (no robots
  file). Under the project's posture (`polite.robots_allows` treats a missing /
  non-200 robots.txt as **allowed**), there is no `Disallow` rule blocking the
  `dots_r5` path.
- **ToS — IMPORTANT CAVEAT.** `terms_of_use.html` states: *"You may not use
  MapJack in a manner which gives you or any other person access to mass
  downloads, bulk feeds of imagery or any numerical data,"* plus
  personal-non-commercial-use and no-derivative-works clauses on the **imagery**.
  Interpretation for this project: we do **not** download or redistribute any
  MapJack imagery, and we do **not** redistribute MapJack numerical data (e.g.
  the `data_r5` site files or dot coordinates). We only fetch the public
  rendered `dots_r5` *overlay GIF tiles* (the same bytes a browser fetches) and
  derive a binary presence raster from pixel alpha — analogous to how `kakao`
  derives presence from the rendered `map_roadviewline` overlay. To stay on the
  polite side of the "mass downloads / bulk feeds" clause: keep concurrency low
  (1–2), throttle per host, prefer HEAD for discovery, fetch only the small
  covered-city extents (not a global sweep of full-res tiles), and stop on
  sustained 429/5xx. **Document this caveat verbatim in the module docstring.**
  If the user is uncomfortable with the bulk-download clause, that is a
  project-level call — flag it at the approval gate (open question §7-equivalent
  in the status log).
- **Observed rate limit.** None hit during probing (~20 tile fetches, no 429).
  openresty front-end; behave politely and expect no documented quota.

### Known quirks / gotchas

- **GIF, not PNG.** Tiles are palette-mode GIFs with a transparent index. The
  existing `raster` `summarize_png` opens via PIL `Image.open` and
  `convert("RGBA")`, which handles GIF transparently — verified locally
  (alpha>0 counts: Chiang Mai z14 = 4187 px; z16 = 1880 px). Set
  `expect_content_type_prefix="image/"` (server returns `image/gif`), not
  `image/png`.
- **404 = absent, not error.** The defining presence quirk. Must be modeled as
  checked-empty(0), and the scrape must run with `skip_404` so a 404 doesn't
  abort the run. See §4 decoder note.
- **Server serves more than the viewer shows.** maxZoom in JS is 17 but z18
  tiles exist; the US cities are commented out of `CITIES` but their tiles are
  still served. Trust the *tiles* (200/404), not the viewer's city list, for
  the true extent.
- **`{z}` repeated in filename.** The URL template embeds zoom twice:
  `dots_r5/{z}/{x}/{z}_{x}_{y}.gif` (folder is `{z}/{x}`, filename is
  `{z}_{x}_{y}.gif`). Easy to get wrong — pin it in a test (§3).
- **Tiny per-city extents.** Hua Hin / Pai / Ayutthaya bboxes are very small
  (single-village). The Thai extent total is modest; the US extent adds a few
  Bay-Area cities. This is a small, fast provider.
- **No capture-date layer.** The overlay encodes only positions, not dates.
  A `mapjack_year.tif` date layer is **out of scope** (imagery is broadly
  2007–2009 but not exposed per-tile in the coverage layer).
- **HTTPS works** — use `https://www.mapjack.com/...` (unlike the dead `xygo`).

## 3. Test plan (write these FIRST — red before green)

Offline, fixtures only (unit tests must not hit the network — record the GIFs
below once, by hand, then commit them):

- [ ] `test_mapjack_tile_url_build` — the `raster` template resolves to
  `https://www.mapjack.com/dots_r5/14/12696/14_12696_7321.gif` for
  `z=14, x=12696, y=7321` (Chiang Mai centre). Asserts the doubled-`{z}`
  filename pattern `{z}_{x}_{y}.gif` and the `{z}/{x}/` folder path.
- [ ] `test_mapjack_decode_present` — the recorded Chiang Mai GIF fixture
  decodes (via the `raster` kind / `summarize_png`) to
  `coverage_pixel_count > 0` and `is_empty=False` (covered = 1).
- [ ] `test_mapjack_decode_absent_404` — a 404 response (HTML error body, the
  recorded ~355-byte body, `http_status=404`) is classified as **checked-empty
  (is_empty=True, 0)**, NOT as a hard error and NOT as nodata. (This is the
  decoder-gap test; see §4 — it may require the small `http_404` empty rule.)
- [ ] `test_mapjack_decode_gif_content_type` — a `Content-Type: image/gif`
  payload passes the `expect_content_type_prefix="image/"` guard (does not get
  `skipped` as a content-type mismatch).
- [ ] `test_mapjack_web_mercator_scheme` — coordinate scheme is `web_mercator`;
  z14 (lat=18.7885, lon=98.9826) maps to tile (x=12696, y=7321) via the shared
  `geo.py` web-mercator helper.
- [ ] `test_mapjack_registers` — importing the module self-registers `"mapjack"`
  in `PROVIDERS` with one `raster` source.
- Fixtures under `tests/fixtures/mapjack/`:
  - `dots_r5_14_12696_7321.gif` — a real present tile (Chiang Mai, ~2.7 KB).
  - `dots_r5_16_50787_29284.gif` — a smaller present tile (Chiang Mai z16).
  - `absent_404.html` — the recorded 404 error body (~355 bytes) + a note that
    it arrives with `http_status=404`, `content_type=text/html`.
  - (Optional) `dots_r5_8_40_98.gif` — an SF z8 present tile, to assert US
    coverage is still served.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: `raster` (existing).** No new source kind is needed. **One
  small decoder consideration:** MapJack's empty signal is **HTTP 404**, whereas
  the current `raster` kind only treats empty-body / HTTP 204 as
  `transparent_png`/`http_204` empties, and the runner's `skip_404` currently
  records 404s as *skipped* (not counted as checked-empty 0). Pick ONE:
  - **(a, preferred) Add an `empty_tile_rule="http_404"`** branch to
    `source_kinds/raster.py` so a 404 (`ctx.http_status == 404`) sets
    `is_empty=True`. This is a tiny, provider-agnostic addition to a shared
    file → it must land in its **own small foundation PR first** (it edits a
    shared module, which a provider PR may not). Then `mapjack.py` sets
    `options={"empty_tile_rule": "http_404", "coverage_from": "alpha"}` and the
    scrape runs with `skip_404=True` so the 404 short-circuits before decode —
    OR the runner is taught to route 404s through the decoder for kinds that
    declare an `http_404` rule. Confirm the runner path with the maintainer; the
    cleanest is: runner still `skip_404`s, but counts skipped-404 as
    checked-empty(0) in the summary for this rule.
  - **(b, no shared edit)** Treat 404 purely as `skip_404` (existing behavior):
    covered tiles (200) are burned as 1, everything not-200 is simply absent.
    The published binary raster is then "1 where covered, nodata elsewhere"
    rather than "1 / 0 / nodata". This needs zero foundation work and ships
    entirely inside `mapjack.py`, at the cost of not distinguishing
    checked-empty(0) from never-checked(nodata). Given the project's binary-
    presence model (1 = imagery exists, nodata = none), **(b) is acceptable**
    and is the lighter path; choose (a) only if the 0/255 distinction is wanted.
  Decide with the maintainer at the approval gate; default to (b).
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/mapjack.py` (`ProviderDefinition`),
  modeled on `kakao.py` / `kartaview.py`:
  - `key="mapjack"`, `coordinate_scheme="web_mercator"`.
  - one `SourceDefinition(id="mapjack_dots_r5", kind="raster",
    template="https://www.mapjack.com/dots_r5/{z}/{x}/{z}_{x}_{y}.gif",
    headers={"User-Agent": "<project UA>", "Accept": "image/gif,image/*;q=0.9",
    "Referer": "https://www.mapjack.com/"},
    expect_content_type_prefix="image/", storage_subdir="tiles",
    options={"coverage_from": "alpha", "empty_tile_rule": "http_404"|<see above>,
    "overlay_folder": "dots_r5"})`.
  - `area_presets` with the Chiang Mai pilot bbox (below).
  - Module docstring: record the ToS "mass downloads / bulk feeds" caveat
    verbatim, the 404-as-absent rule, the GIF format, and that US tiles are
    still served though hidden from the viewer.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Pilot fetch: bbox `98.899549 18.697236 99.073957 18.864633`
  (**Chiang Mai** — the densest, default-start city; NOTE: the task's suggested
  central-Bangkok bbox is NOT covered by MapJack — Bangkok-centre tiles 404).
  Fetch at source zoom ~z16; expect hundreds of covered tiles on the old-town
  street grid.
- [ ] Rasterize the pilot area to a z14 binary-presence COG; sanity-check that
  coverage lands on Chiang Mai's streets/old-town moat, not the surrounding
  mountains or the Ping river only.
- [ ] Two-pass full extent:
  - **Pass-1 (discovery)** at zoom **z8** over a region that bounds all known
    MapJack coverage. Two discovery regions:
    1. Thailand `97.5 6.5 101.0 20.0` (covers all 7 Thai cities).
    2. US Bay-Area + Sierra `-122.7 37.0 -119.0 39.5` (covers SF/Oakland/Palo
       Alto/San Jose/Sausalito/Tahoe/Yosemite, which are still served).
    Use HEAD or GET; a 200 marks a candidate cell, a 404 prunes it. This is a
    handful of z8 tiles per region — very cheap.
  - **Pass-2 (fill)** at source z16 only inside cells flagged covered by pass-1.
- [ ] Update the STAC item (extent = union of Thai + US covered tiles, tier T3,
  source endpoint, scrape date, ToS caveat). Update the inventory status from
  "Unverified (old reference)" to "live_raster".

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; module imports & self-registers `"mapjack"` in `PROVIDERS`;
  CI smoke test (import/register/dry-run) passes.
- Pilot tiles fetch & decode: Chiang Mai z16 tiles return 200 GIFs that decode
  to `coverage_pixel_count>0`; coverage lands on Chiang Mai roads/old town (land,
  not ocean); a probed ocean/Bangkok-centre tile is correctly treated as absent
  (404).
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0, internal
  overviews present.
- Fetches go through `polite.polite_fetch` with a descriptive User-Agent and
  per-host throttle; concurrency low (1–2); `skip_404` enabled; the ToS
  "mass downloads / bulk feeds" caveat is documented in the module docstring.

## 6. Status log

- `2026-05-28` scout (provider-scout): **drafted — recommend IMPLEMENT.**
  Evidence summary:
  - `mapjack.com` is LIVE and REBUILT in 2025: HTTP 200, `Server:
    openresty/1.27.1.2`, `Last-Modified: 2025-04-10`, footer "© 2025 MapJack",
    Google Maps JS API base map + custom WebGL panorama viewer.
  - Coverage layer found in `index_min.js` as a Google Maps `ImageMapType`:
    `getTileUrl = SERVER_ADDRESS + "dots_r5/" + z + "/" + x + "/" + z + "_" + x
    + "_" + y + ".gif"`, 256x256, web-mercator XYZ.
  - Live tile probes 2026-05-28: Chiang Mai z12–z18 and Ayutthaya z12–z16 →
    HTTP 200 image/gif with non-transparent dot pixels (e.g. z14 = 4187 px);
    central Bangkok / Andaman ocean / Sahara → HTTP 404 (HTML, ~355 B).
    So **200+alpha = covered, 404 = absent**. HEAD requests work (cheap
    discovery). z8 tiles exist (good for pass-1).
  - US coverage tiles (e.g. SF z8 `dots_r5/8/40/8_40_98.gif`, 626 px) are STILL
    served although the US cities are commented out of `config.js` `CITIES`.
  - No auth, no token, no cookie. `robots.txt` is 404 (⇒ allowed). HTTPS works.
  - ToS caveat: Terms of Use forbid "mass downloads, bulk feeds of imagery or
    any numerical data" and restrict imagery reuse — the project stores only a
    derived binary-presence raster (no imagery, no numerical data), but the
    scrape must be polite/low-volume and the caveat documented. **Flag at the
    approval gate.**
  - Maps onto the existing `raster` source kind. The only nuance is the
    404-as-absent presence rule (see §4): default to the no-shared-edit path
    (b) unless the user wants checked-empty(0) vs nodata(255), which needs a
    small `http_404` empty-rule foundation PR (a).
- `2026-05-28` approval: < pending — human approval gate >
- **Open questions for the user:**
  1. Are we comfortable scraping MapJack's rendered `dots_r5` overlay tiles
     given the ToS "no mass downloads / bulk feeds" clause? (Derived
     binary-presence only; no imagery; polite low-volume fetch — but the user
     should make the call.)
  2. Presence encoding: ship binary "1/nodata" (path b, no foundation work) or
     "1/0/nodata" via a tiny `http_404` empty-rule foundation PR (path a)?
  3. US extent: include the still-served US cities (SF Bay Area, Tahoe,
     Yosemite) in scope, or scope MapJack to Thailand only? (Discovery finds
     them either way; this is a scoping choice.)

## 7. Recommendation

**Implement** as a small T3 `raster` provider. MapJack is live, recently
rebuilt, requires no auth, and serves a clean standard web-mercator XYZ
coverage tile pyramid (`dots_r5/{z}/{x}/{z}_{x}_{y}.gif`) with a trivial
presence rule (200+alpha = covered, 404 = absent). It reuses the existing
`raster` source kind with at most a one-line `http_404` empty-rule addition
(optional). The extent is small (7 Thai cities + a handful of still-served US
cities), making it a fast, low-risk provider. The only gating item is the ToS
"no mass downloads / bulk feeds" clause (§2, open question 1) — resolve that at
the approval gate, document the caveat in the module docstring, and scrape
politely (low concurrency, throttle, HEAD-based discovery, stop on sustained
errors).

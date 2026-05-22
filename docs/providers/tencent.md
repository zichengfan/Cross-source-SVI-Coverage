# [T2] Provider: Tencent Maps Street View (`tencent`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Tencent Maps (腾讯地图, formerly SoSo Maps / QQ Maps), operated by Tencent, is
one of China's three major consumer mapping platforms. It ships a first-party
street-level panorama product (街景, "Street View") with imagery captured mostly
**2013–2016** and concentrated in **Chinese cities** (281 covered regions in the
provider's own config; the community has mapped 299). Street View is exposed in
the **mobile app**, not the `map.qq.com` web viewer, but the underlying coverage
and panorama HTTP endpoints (`sv.map.qq.com`, `mapvectors.map.qq.com`) are
public, unauthenticated, and have been reverse-engineered. It is in scope as an
active, first-party, non-rehosting SVI provider (Tier 2 — coverage is dated and
the discovery path is more involved than a plain web-mercator tile sweep).

**This is the awkward case among the China providers.** Tencent does **not**
serve a rendered `{z}/{x}/{y}` PNG coverage-overlay raster the way Kakao/Naver/
Mapy do, and it does **not** serve standard Mapbox Vector Tiles. Its coverage
layer is a **proprietary binary vector tile format** (`TXVN` signature, raw
DEFLATE body) on a **custom Tencent pixel-coordinate grid**, addressed by a
per-city tile index rather than by `(z, x, y)`. Scouting it thoroughly so the
implementer can build it from this file alone is the point of this subplan.

## 2. Research findings (filled by provider-scout)

### Verdict: NO raster overlay, NO standard MVT — a proprietary binary vector layer

Per the scouting priority order:

1. **Rendered raster overlay tile layer — NOT FOUND.** Unlike Kakao
   (`map_roadviewline`), Naver (`nrb/styles ... mt=ps`), and Mapy
   (`panorama_ln_hybrid-m`), Tencent serves no `{z}/{x}/{y}` PNG layer that
   draws "street view exists here". The Tencent **web** viewer
   (`https://map.qq.com/`) does not expose Street View at all (it is a
   mobile-app feature), so there is no web overlay layer to scrape. The blue
   "street view available" lines users see exist only inside the **mobile app**,
   which draws them client-side from the binary vector layer below.
2. **Vector tile layer — FOUND, but it is NOT standard MVT.** The coverage layer
   is `https://mapvectors.map.qq.com/mobile_street` — a custom binary format
   (`TXVN` magic, raw-DEFLATE body, delta-encoded LineStrings) on Tencent's own
   pixel grid. `ogr2ogr` / the project's `mvt_decoder.py` cannot read it. It
   therefore needs a **new source kind** with a bespoke decoder (see §4).
3. **`sv.map.qq.com` point endpoints — FOUND, usable as a cross-check / fallback
   discovery path** (`sv.map.qq.com/xf` nearest-panorama search).

The recommended primary path is the **`mobile_street` binary vector layer**
because it enumerates whole-city coverage in a bounded number of tiles; the
`xf` point endpoint is a fallback only (a point-probe grid, like `ja360`).

- **Homepage / public viewer URL:**
  - Tencent Maps web: `https://map.qq.com/` — has Layers but **no Street View**
    in the browser; Street View is a mobile-app feature.
  - Third-party reverse-engineered viewer: `https://qq-map.netlify.app/` (by
    "ReAnna"; renders Tencent panoramas and, in the linked research, the
    coverage lines).
  - Definitive reverse-engineering write-ups (the basis of this subplan):
    `https://reanna.neocities.org/blog/qq-maps-street-view/` and
    `https://reanna.neocities.org/blog/qq-maps-lines/`.

- **Tier:** T2 — first-party national SVI provider, but coverage is dated
  (2013–2016), the discovery path needs a per-city config (`streetcfg.dat`), and
  the layer format is bespoke; not a clean web-mercator tile sweep.

- **Source kind:** **NEW kind `tencent_mobile_street`** (proprietary binary
  vector → presence). This is a genuine new source kind and must land as a
  **separate Phase-0 foundation PR before the `tencent` provider PR** (see §4).
  The existing kinds do not fit: `raster` expects a PNG; `vector_mvt` expects
  Mapbox MVT decodable by `ogr2ogr`; `coverage_json` expects JSON. The
  `mobile_street` body is a Tencent-specific `TXVN` binary.

- **Coverage endpoint(s):**

  - **Primary — the coverage vector layer (`mobile_street`):**
    ```
    GET https://mapvectors.map.qq.com/mobile_street?df=1&idx={idx}&lv={lv}&dth=20&bn=1&bl={bl}
    ```
    - `idx` — Tencent city/region identifier (4-digit, e.g. Beijing `1001`).
      The full list of `idx` values **and each region's bounding box** comes
      from `streetcfg.dat` (see "Known quirks").
    - `lv` — data level. **Only `11, 12, 13, 14, 18` are valid.** (Display
      zooms 10–18 map to data levels via `DATA_LEVELS =
      [11,11,12,13,14,18,18,18,18,18]`.)
    - `bl` — per-city tile index, `0 .. (tilesX*tilesY - 1)`, filled
      **column-major: north→south within a column, then west→east**. The tile
      count for a city is derived from its `streetcfg` bounding box at the
      chosen `lv` (see "Coordinate scheme").
    - `df=1`, `dth=20`, `bn=1` — fixed constants (purpose unclear; send as-is).
    - **HTTP method:** `GET`. **Verified live 2026-05-22**: Beijing `idx=1001,
      lv=13` returns HTTP 200 `text/plain` binary; `bl=10` → 37-byte empty
      tile, `bl=200` → 852-byte tile with line features. An unknown `idx`
      (`9999`) returns **HTTP 404 `not found`** (9-byte body).

  - **Fallback / cross-check — the nearest-panorama point endpoint (`xf`):**
    ```
    GET https://sv.map.qq.com/xf?lat={lat}&lng={lng}&r={radius}&output=json
    ```
    `lat`/`lng` are **GCJ-02** degrees; `r` is a search radius in metres.
    **Verified live 2026-05-22**: Shenzhen `(22.5431, 114.0579) r=500` returns
    `detail.svid` = a non-empty 23-char panorama id (coverage present);
    Tiananmen Beijing and an open-ocean point return `detail.svid == ""`
    (no coverage). Response `Content-Type: application/javascript;charset=GBK`
    — **GBK-encoded**, decode accordingly (road names are GBK Chinese).
    This is a point-probe path (like `ja360`) — use only as a fallback.

  - **Panorama metadata (reference only, not used for coverage):**
    `GET https://sv.map.qq.com/sv?output=json&svid={svid}` and the panorama
    image tiles `https://sv{1}.map.qq.com/tile?from=web&svid={svid}&level={z}&x={x}&y={y}`
    — imagery, not coverage; out of scope (we map presence, not pixels).

  - **Headers:** **none required.** `mobile_street` returns HTTP 200 **with no
    Referer and no special headers** (verified — a bare request with only a
    `User-Agent` succeeds, and the same request without a `Referer` also
    succeeds). For polite scraping the `SourceDefinition.headers` should still
    set a descriptive `User-Agent` and a `Referer: https://map.qq.com/` for
    consistency with the other providers. No cookie, no API key.

- **Coordinate scheme:** **NOT web mercator, and NOT any scheme `geo.py`
  currently supports** (`web_mercator` / `yandex_wgs84_mercator` / `baidu` /
  `kakao_epsg5181`). Two distinct coordinate concerns:
  1. **Datum:** all Tencent inputs/outputs are **GCJ-02** (the Chinese
     encrypted datum). WGS84 must be converted to GCJ-02 before use. `geo.py`
     **already has `wgs84_to_gcj02(lon, lat)`** (used by the `baidu` scheme) —
     reuse it; no new datum code is needed.
  2. **Tile grid:** the `mobile_street` layer uses a **Tencent pixel-coordinate
     grid**, not a `(z, x, y)` slippy grid. Constants (from the
     `qq-maps-lines` write-up):
     - `PX_SCALE = 268435456` (= 2^28).
     - `A = 114.59155902616465`.
     - pixel → GCJ-02:
       `lng = 360 * px_x / PX_SCALE - 180`;
       `lat = atan(exp(deg2rad(180 - 360 * px_y / PX_SCALE))) * A - 90`.
     - GCJ-02 → pixel:
       `px_x = (lng + 180) * PX_SCALE / 360`;
       `px_y = (PX_SCALE / 360) * (180 - rad2deg(log(tan((lat + 90) / A))))`.
     - A `mobile_street` "tile" at data level `lv` spans a fixed pixel size;
       per-city tiles are addressed by the single integer `bl`, **not** `(x,y)`
       — `bl` increments column-major (N→S, then W→E) inside the city's
       `streetcfg` bounding box.
  - **Implication for the project:** because the coverage layer is enumerated
    **per city by `bl` index over a `streetcfg` bbox**, the standard two-pass
    `(z, x, y)` tile runner does **not** apply directly. The `tencent` source
    kind drives a *city/bl enumeration*, decodes each `TXVN` tile to WGS84
    LineStrings (pixel→GCJ-02→WGS84), and the rasterizer burns those lines onto
    the shared z14 EPSG:3857 grid. The provider's `coordinate_scheme` field
    should be set to a descriptive new value (e.g. `tencent_px`) but its real
    job is documentation — the new source kind owns the geometry, the generic
    `tile_range_for_bbox` dispatcher is **not** used for this provider. See §4
    open question 1.

- **Zoom range / tile size / response format:**
  - Valid data levels: **`lv ∈ {11, 12, 13, 14, 18}`** only. For coverage
    rasterized at the project's z14 grid, **`lv=14`** is the natural fetch level
    (the community dataset used `lv=18`, the finest, which yields many more
    small tiles per city; `lv=14` is a good cost/detail balance — confirm with
    a pilot, see §4 open question 2).
  - Response is **not** an image and **not** JSON. It is a binary blob:
    - **30-byte header**, little-endian:
      `int idx; uint8 level; int tile_index; char signature[4] ("TXVN");
       int date; int file_offset; uint8 unknown; int body_size;`
    - The body starts at **byte 32**, compressed with **raw DEFLATE**
      (`zlib.decompress(body, -15)` / Node `inflateRawSync`).
    - The inflated body is a layer/feature structure: layers, each with
      features that are **LineStrings**, points delta-encoded relative to the
      tile origin (first point per layer absolute; subsequent absolute points
      flagged by a `127` byte). Point multiplier:
      `COMPRESS_LEVEL = [7,11,11,11,11,11,11,11,11]`,
      `multiplier = floor(tileSize / (1 << compressLevel))`.
  - **Verified live decode 2026-05-22** (Beijing `idx=1001, lv=13`):
    - `bl=10`: total 37 bytes, header `body_size = 7`, `unknown = 0`,
      `signature = TXVN`, `date = 20150227` → an **empty (no-coverage) tile**.
    - `bl=100`: total 128 bytes, `body_size = 98`, `unknown = 1`; body at
      offset 32 inflates to 101 bytes of layer/feature data.
    - `bl=200`: total 852 bytes, `body_size = 822`, `unknown = 1`; body
      inflates to 1067 bytes containing LineString features.
  - Tile size of the proprietary tile: per the SDK math
    (`tileSize / (1 << compressLevel)`); the implementer derives it from the
    decoded header `level` — record the exact value once measured in the pilot.

- **Auth:** **none.** No token, no cookie, no API key, no signed URL —
  confirmed live for both `mobile_street` and `xf`. **No `.env` key is needed
  or added for `tencent`.** Do not add a `TENCENT_*` slot to `.env.example`.

- **Presence rule:** "Street view imagery exists in this tile" ⇔ the decoded
  `TXVN` tile contains **≥ 1 LineString feature**. Operationally the
  cheapest, most robust signal is the **header `body_size`**:
  - `body_size <= 7` (the empty-tile body — verified 7 bytes, `unknown == 0`,
    total response 37 bytes) ⇒ **checked-empty** (no coverage in that tile).
  - `body_size > 7` ⇒ inflate the body and parse features; tiles with ≥ 1
    LineString ⇒ **covered**. (Decoding and counting features is the
    authoritative check; `body_size` is the fast pre-filter.)
  - An unknown `idx` ⇒ HTTP 404 `not found` — a configuration error, not a
    coverage signal; the city `idx` list must come from `streetcfg.dat`.
  - For the `xf` fallback: `detail.svid != ""` ⇒ coverage present at that point
    (and `detail.x/y` give the panorama location); `detail.svid == ""` ⇒ none.
  - z14 raster mapping: tiles/lines that decode to coverage → contributing z14
    cells **covered (1)**; decoded-but-empty tiles → **checked-empty (0)**;
    never-fetched cells → **nodata (255)** — the standard rasterize flow, but
    fed from decoded LineStrings rather than from PNG alpha.

- **Capture date:** the `TXVN` header carries a **`date` field**
  (verified `20150227` = 2015-02-27 for the Beijing tiles). This makes an
  optional `tencent_year.tif` date layer *feasible* directly from the coverage
  tiles (unlike Kakao/Naver/Mapy, whose rendered overlays carry no date). The
  date layer is **out of scope for the initial provider PR** but should be
  noted as a strong follow-up candidate (see §6).

- **robots.txt / ToS notes; observed rate limit:**
  - **`https://sv.map.qq.com/robots.txt` → HTTP 200, `User-agent: *` /
    `Disallow: /`.** The `sv.map.qq.com` host (the `xf` fallback endpoint and
    the panorama endpoints) **disallows all crawling.** Therefore the `xf`
    fallback path is **robots-disallowed** — it must be treated as a
    last-resort, human-decision-only option, **not** the default scrape path.
  - **`https://map.qq.com/robots.txt` → HTTP 200, `Disallow: /`** — the web
    viewer host is also disallowed; this provider does not crawl it (used only
    as a `Referer` string, like the Kakao/Naver pattern).
  - **`https://mapvectors.map.qq.com/robots.txt` → HTTP 503** (no robots.txt
    served; `stgw` gateway returned "Service Temporarily Unavailable"). The
    project's `polite.robots_allows` treats a non-200 / unreachable robots.txt
    as **allowed**, so the **primary `mobile_street` endpoint on
    `mapvectors.map.qq.com` is permitted under the project's robots posture.**
    **Re-fetch `mapvectors.map.qq.com/robots.txt` at implementation time and
    record the result in the status log** — if it later returns a real
    `Disallow: /`, escalate to the user before scraping.
  - **This is the central ToS finding:** the *only* host this provider should
    crawl is **`mapvectors.map.qq.com`** (no robots.txt → allowed). The
    `sv.map.qq.com` `xf` fallback is robots-disallowed and must not be used as
    the routine discovery path — see §4 open question 3.
  - Tencent's general Terms of Service restrict bulk reuse of map data; this
    project stores only a **derived binary coverage raster** (presence/absence),
    never Tencent imagery or the rendered tiles long-term. Record this caveat in
    the module docstring.
  - **Observed rate limit:** none hit in light manual probing of `mobile_street`
    (a handful of `bl` values fetched cleanly). No documented limit. Use the
    project polite default via `polite.polite_fetch` with a **conservative
    per-host throttle** (e.g. `PolitePolicy(min_interval_seconds ≈ 0.3)`), and
    exponential backoff on 429/5xx — `mapvectors.map.qq.com` already showed a
    transient 503 on `robots.txt`, so the host can throttle. Keep concurrency
    low.

- **Known quirks / gotchas:**
  - **Needs `streetcfg.dat` — the central dependency.** Coverage discovery is
    **per city**: you must know the list of region `idx` values *and each
    region's bounding box* to enumerate `bl` tiles. That list lives in
    `streetcfg.dat`, a binary config file **shipped inside the Tencent Maps
    Android APK** (the `qq-maps-lines` write-up reverse-engineered its binary
    structure: region IDs, names, bounding boxes; ~281 regions). There is **no
    documented way to enumerate coverage without it** — an unknown `idx` simply
    404s. The implementer must obtain `streetcfg.dat` (extract from the current
    APK, or reuse the community-derived list). The community repo
    `chaofunchengfeng/TencentMapPanoramaCoverageAreaData` publishes 299
    per-city GeoJSON coverage files keyed by 4-digit `idxId` and a
    `database/mobile_street.sqlite3.db` — a usable cross-check and a possible
    source of the `idx` list, though it does not itself commit `streetcfg.dat`.
    **This is the single biggest implementation risk — see §4 open question 4.**
  - **Proprietary binary format — needs a bespoke decoder.** `TXVN` + raw
    DEFLATE + delta-encoded LineStrings is not MVT; `ogr2ogr` and the project's
    `mvt_decoder.py` cannot read it. The new `tencent_mobile_street` source
    kind must implement the header parse + `inflateRaw` + feature decode (the
    `qq-maps-lines` write-up gives the full byte layout; the §3 fixtures pin
    it).
  - **Per-city `bl` enumeration, not `(z, x, y)`.** The standard web-mercator
    two-pass tile runner does not apply. Discovery is: for each region `idx`,
    compute the tile grid from its `streetcfg` bbox at the chosen `lv`, iterate
    `bl = 0 .. count-1`. The new source kind owns this enumeration.
  - **GCJ-02 datum.** All coordinates are GCJ-02. Decoded tile geometry is in
    GCJ-02 and must be converted toward WGS84 before rasterizing onto the
    EPSG:3857 grid. `geo.py` has `wgs84_to_gcj02` (forward only); a GCJ-02→WGS84
    inverse is needed — the standard approach is iterative inversion of
    `wgs84_to_gcj02` (a few Newton iterations; ~1 m accuracy), which the
    foundation PR for the new source kind should add to `geo.py` next to the
    existing Baidu/GCJ helpers. Flag this small `geo.py` addition.
  - **Dated coverage.** Tencent SV imagery is largely 2013–2016; the `TXVN`
    `date` field confirms this (Beijing tiles dated 2015). Coverage is
    **city-centric** (little rural coverage). Bound discovery to the
    `streetcfg` regions; do not sweep all of China blindly.
  - **GBK encoding on `xf`.** The `xf` JSON is `charset=GBK`, not UTF-8 —
    decode as GBK if the fallback path is ever used (road names are Chinese).
  - **`sv.map.qq.com` is robots-disallowed.** Do not route the routine scrape
    through the `xf` point endpoint. `mapvectors.map.qq.com` (no robots) is the
    permitted host.
  - **Empty tile is HTTP 200, not 404.** A no-coverage `bl` tile returns
    HTTP 200 with the 37-byte `body_size==7` blob. The 404 is reserved for an
    *unknown idx*. Emptiness is decided from `body_size` / decoded features,
    never from status code.

## 3. Test plan (write these FIRST — red before green)

All tests are **offline** — they decode recorded fixtures and never hit the
network (`docs/PLAN.md` §12). Mirror the decode-fixture style of the existing
source-kind tests.

Fixtures to record live under `tests/fixtures/tencent/` (captured 2026-05-22
during scouting; small real responses):
- `mobile_street_beijing_lv13_bl200.bin` — a real `mobile_street` tile **with
  coverage** (`GET .../mobile_street?df=1&idx=1001&lv=13&dth=20&bn=1&bl=200`);
  852 bytes, `TXVN`, `body_size=822`, body inflates to LineString features.
- `mobile_street_beijing_lv13_bl100.bin` — a second smaller covered tile
  (`bl=100`, 128 bytes, `body_size=98`) for a second decode case.
- `mobile_street_beijing_lv13_bl10_empty.bin` — a real **empty** tile
  (`bl=10`, 37 bytes, `body_size=7`, `unknown=0`) — the no-coverage signature.
- `xf_shenzhen_present.json` — a real `xf` response with `detail.svid != ""`
  (Shenzhen) — for the fallback-path tests.
- `xf_empty.json` — a real `xf` response with `detail.svid == ""` (ocean) —
  the fallback no-coverage signature.

Tests (`tests/test_providers_tencent.py` + the new source-kind tests):

- [ ] `test_tencent_registers` — importing
  `coverage_acquisition.providers.tencent` registers `"tencent"` in
  `PROVIDERS`; `get_provider("tencent").key == "tencent"` with exactly one
  source whose `kind == "tencent_mobile_street"`.
- [ ] `test_tencent_provider_shape` — `coordinate_scheme == "tencent_px"`
  (the descriptive new value); the source carries no `token_query_param` and
  no auth; the module references no `.env` key.
- [ ] `test_tencent_mobile_street_url_build` — the source `template` fills
  correctly for sample `idx/lv/bl`: with `idx=1001, lv=13, bl=200` it produces
  `https://mapvectors.map.qq.com/mobile_street?df=1&idx=1001&lv=13&dth=20&bn=1&bl=200`
  (assert host `mapvectors.map.qq.com`, the fixed `df=1&dth=20&bn=1`, and the
  `idx`/`lv`/`bl` substitution).
- [ ] `test_tencent_txvn_header_parse` — feeding
  `mobile_street_beijing_lv13_bl200.bin` to the `TXVN` header parser yields
  `idx == 1001`, `level == 13`, `signature == b"TXVN"`, `date == 20150227`,
  `body_size == 822`; the parser raises/flags on a wrong magic.
- [ ] `test_tencent_decode_present` — decoding
  `mobile_street_beijing_lv13_bl200.bin` via the `tencent_mobile_street` source
  kind yields ≥ 1 LineString feature and `is_empty is False`; decoding
  `..._bl100.bin` likewise yields ≥ 1 feature.
- [ ] `test_tencent_decode_empty` — decoding
  `mobile_street_beijing_lv13_bl10_empty.bin` (`body_size == 7`) yields
  **zero** features and `is_empty is True` — classified checked-empty, not an
  error, no stored payload.
- [ ] `test_tencent_inflate_raw` — the decoder uses **raw DEFLATE** on the body
  from byte 32 (`zlib.decompress(body, -15)`); a regression guard that a
  zlib-wrapped `decompress` would fail (the body has no zlib header).
- [ ] `test_tencent_pixel_to_wgs84` — the Tencent pixel→GCJ-02→WGS84 conversion
  round-trips: a known GCJ-02 point → pixel → back to GCJ-02 within tolerance,
  using `PX_SCALE = 268435456` and `A = 114.59155902616465`; and a decoded
  Beijing line lands inside Beijing's bbox (sanity: not in the ocean).
- [ ] `test_tencent_gcj02_to_wgs84_inverse` — the new GCJ-02→WGS84 inverse in
  `geo.py` inverts `wgs84_to_gcj02` to ≤ ~1 m for a Beijing point.
- [ ] `test_tencent_lv_values` — the source/options restrict `lv` to
  `{11,12,13,14,18}`; an invalid `lv` is rejected before any fetch.
- [ ] `test_tencent_bl_enumeration` — given a small synthetic city bbox and a
  `lv`, the per-city `bl` tile enumerator produces the expected
  `tilesX*tilesY` count with column-major (N→S, then W→E) ordering.
- [ ] (fallback path, only if §4 open question 3 approves it)
  `test_tencent_xf_decode` — `xf_shenzhen_present.json` decodes to a presence
  point at `detail.x/y`; `xf_empty.json` (`svid == ""`) decodes to
  checked-empty. The JSON is GBK-decoded without error.
- Fixtures: the five recorded samples under `tests/fixtures/tencent/` above.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: NEW `tencent_mobile_street`** — a genuine new source kind,
  **a separate `foundation`-labelled PR that must merge to `dev` before the
  `tencent` provider PR** (per `CLAUDE.md`: provider PRs touch no shared file).
  Scope of that foundation PR (summarised so this subplan is self-contained):
  - Add `src/coverage_acquisition/source_kinds/tencent_mobile_street.py`
    registering the kind via `register_source_kind("tencent_mobile_street", ...)`.
    The handler must:
    1. Parse the 30-byte `TXVN` header (LE: `int idx; uint8 level;
       int tile_index; char[4] sig; int date; int file_offset; uint8 unknown;
       int body_size`); verify `sig == b"TXVN"`.
    2. `body_size <= 7` ⇒ `is_empty=True`, no features (checked-empty).
    3. Else `zlib.decompress(body[32:], -15)` (raw DEFLATE) and decode the
       layer/feature structure into LineStrings (delta-encoded points; first
       point per layer absolute, subsequent absolute points flagged by `127`;
       `COMPRESS_LEVEL=[7,11,...]`, `multiplier = floor(tileSize/(1<<lvl))`).
    4. Convert each point Tencent-pixel → GCJ-02 → WGS84 and emit WGS84
       LineString geometry + the header `date` for downstream rasterizing.
    5. Drive the **per-city `bl` enumeration**: given a region `idx` + its
       `streetcfg` bbox + `lv`, compute the tile grid (column-major N→S, W→E)
       and iterate `bl`.
  - Add to `geo.py` a small `tencent` helper block (next to the Baidu/GCJ
    helpers): the `PX_SCALE`/`A` pixel↔GCJ-02 functions and a **GCJ-02→WGS84
    inverse** (iterative inversion of the existing `wgs84_to_gcj02`).
  - Decide how the runner enumerates this provider: it is **not** a
    `(z,x,y)` tile sweep. Either (a) extend the runner with a
    `discovery_mode == "tencent_city_bl"` branch (like `ja360`'s
    `point_probe`), or (b) have the source kind own the full enumeration. Pick
    one in the foundation PR and document it. See open question 1.
  - Unit-test the new kind against the §3 fixtures.
- [ ] **Obtain the `streetcfg` region list.** Before the provider can run, the
  implementer needs the list of Tencent SV region `idx` values and each
  region's bounding box (and a human-readable name). Options, in order of
  preference: (a) extract `streetcfg.dat` from the current Tencent Maps Android
  APK and parse it per the `qq-maps-lines` byte layout; (b) reuse the
  community-derived 4-digit `idxId` list from
  `chaofunchengfeng/TencentMapPanoramaCoverageAreaData` and reconstruct
  bounding boxes from its per-city GeoJSON. Commit the resulting region table
  as a small data file under the provider (e.g.
  `src/coverage_acquisition/providers/_data/tencent_streetcfg.json`) so the
  scrape is reproducible. See open question 4.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/tencent.py` defining `PROVIDER`
  (`ProviderDefinition`) and calling `register_provider(PROVIDER)`:
  - `key="tencent"`, `output_namespace="tencent_streetview_coverage"`,
    `run_label_prefix="tencent_streetview"`, `default_display_zoom=14`,
    `coordinate_scheme="tencent_px"`.
  - `area_presets`: declare the pilot bbox **inline in this module** (do not
    edit `_presets.py`) — `shenzhen_futian_pilot_bbox` (see pilot below).
  - One `SourceDefinition`:
    - `id="tencent_mobile_street"`, `kind="tencent_mobile_street"`.
    - `template="https://mapvectors.map.qq.com/mobile_street?df=1&idx={idx}&lv={lv}&dth=20&bn=1&bl={bl}"`.
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Referer": "https://map.qq.com/"}`.
    - `expect_content_type_prefix=None` (response is `text/plain` binary, not an
      image — do not assert an `image/` prefix).
    - `storage_subdir="tiles"`.
    - `options={"data_level": "14", "px_scale": "268435456",
      "lat_const_a": "114.59155902616465",
      "streetcfg_path": "_data/tencent_streetcfg.json",
      "valid_levels": "11,12,13,14,18"}`.
    - `notes`: "Tencent Street View coverage — proprietary `TXVN` binary
      vector layer (`mobile_street`), per-city `bl` enumeration over
      `streetcfg` regions, GCJ-02 datum. Presence = ≥1 decoded LineString
      (`body_size>7`)."
  - Module docstring: record (a) this is the proprietary `mobile_street` binary
    vector layer, **not** a raster overlay and **not** standard MVT;
    (b) the `streetcfg.dat` dependency; (c) the GCJ-02 datum; (d) the ToS /
    robots posture — crawl **only `mapvectors.map.qq.com`** (no robots.txt →
    allowed); never crawl `sv.map.qq.com` or `map.qq.com` (both `Disallow: /`);
    (e) coverage is Chinese cities, imagery 2013–2016; no auth.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `114.04 22.52 114.08 22.56` (**Shenzhen — Futian
  district**, a dense, confirmed-covered area; the `xf` probe at
  `(22.5431, 114.0579)` returned a real `svid`). Identify the Shenzhen region
  `idx` from the `streetcfg` table, compute its `bl` tile grid at `lv=14`,
  fetch the `mobile_street` tiles intersecting the pilot bbox, decode the
  `TXVN` binary, and confirm ≥ 1 LineString of coverage on Futian's street
  network.
- [ ] Rasterize the pilot area to a z14 COG (`rasterize.py`): convert decoded
  GCJ-02 LineStrings to WGS84, reproject to EPSG:3857, burn line coverage onto
  the shared z14 grid (`uint8`, 1=covered / 0=checked-empty / 255=nodata).
  Sanity-check: covered pixels land on Shenzhen streets/land, not the bay or
  Hong Kong.
- [ ] **Full extent:** iterate every region `idx` in the `streetcfg` table; for
  each, enumerate `bl = 0 .. count-1` at `lv=14`, decode, keep tiles with
  coverage, drop `body_size==7` empties. This is a bounded sweep (~281 regions ×
  their per-city tile counts) — run detached in `tmux` (`run-scraper`). There
  is no `(z,x,y)` two-pass discovery here; the `streetcfg` region list **is**
  the discovery pass. (If a coarse pre-pass is wanted, run `lv=11` first to
  find which regions have any coverage, then `lv=14` for the rest.)
- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T2"`,
  `source_endpoint="https://mapvectors.map.qq.com/mobile_street?...idx={idx}&lv={lv}&bl={bl}"`,
  `tos_notes` per §2). Update the inventory status for `tencent`.
- [ ] (Future, out of scope here) optional `tencent_year.tif` date layer from
  the `TXVN` header `date` field.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.tencent` imports and
  self-registers in `PROVIDERS`; CI smoke test (import/register/dry-run) passes.
- The provider's single source is `kind="tencent_mobile_street"` (the new
  foundation source kind) with no auth fields and no `.env` key.
- The `mobile_street` URL `template` builds
  `.../mobile_street?df=1&idx={idx}&lv={lv}&dth=20&bn=1&bl={bl}` correctly.
- The `TXVN` decoder parses the header, distinguishes `body_size<=7` empty
  tiles (checked-empty) from covered tiles, raw-inflates and decodes
  LineStrings, and converts Tencent-pixel → GCJ-02 → WGS84.
- Pilot fetch over Shenzhen Futian returns decodable `TXVN` tiles with ≥ 1
  LineString; coverage burns onto Shenzhen streets/land, not water.
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0, extent within
  the discovered Chinese-city envelope.
- Fetches via `polite.polite_fetch` with a descriptive User-Agent and a
  conservative throttle; **only `mapvectors.map.qq.com` is crawled**;
  `sv.map.qq.com` / `map.qq.com` (both robots `Disallow: /`) are never crawled.
- ToS / robots caveats and the `streetcfg.dat` dependency are documented in the
  `providers/tencent.py` module docstring and the STAC `tos_notes`.

## 6. Status log

- `2026-05-22` scout: drafted. Findings, verified live this session:
  - **No rendered raster coverage overlay** and **no standard MVT** —
    Tencent's web viewer (`map.qq.com`) has no Street View; the coverage layer
    is the proprietary binary `mobile_street` vector format.
  - Primary endpoint:
    `https://mapvectors.map.qq.com/mobile_street?df=1&idx={idx}&lv={lv}&dth=20&bn=1&bl={bl}`.
    Verified live: Beijing `idx=1001,lv=13` → HTTP 200 `text/plain` binary
    (`bl=10` 37-byte empty `body_size=7`; `bl=100` 128-byte covered; `bl=200`
    852-byte covered). Body at byte 32 is raw DEFLATE; inflated bodies decode
    to LineString features. Header carries a capture `date` (`20150227`).
    Unknown `idx` → HTTP 404 `not found`. Works **without** Referer/auth.
  - Format: `TXVN` 30-byte header + raw-DEFLATE body; data levels limited to
    `lv ∈ {11,12,13,14,18}`; per-city `bl` tile index (column-major N→S, W→E).
  - Coordinate scheme: **GCJ-02 datum** + a **Tencent pixel grid**
    (`PX_SCALE=2^28`, `A=114.59155902616465`) — not web mercator, not any
    `geo.py` scheme today. `geo.py` has `wgs84_to_gcj02`; a GCJ-02→WGS84
    inverse is needed.
  - Fallback: `sv.map.qq.com/xf?lat&lng&r&output=json` — GCJ-02 point search,
    `detail.svid != ""` ⇒ coverage. Verified Shenzhen present, ocean/Tiananmen
    empty. Response is **GBK**-encoded. **`sv.map.qq.com/robots.txt` is
    `Disallow: /`** — the `xf` path is robots-disallowed; do not use it as the
    routine scrape.
  - robots: `mapvectors.map.qq.com/robots.txt` → HTTP 503 (no file → allowed —
    the only host this provider crawls). `sv.map.qq.com` and `map.qq.com` →
    `Disallow: /` (not crawled).
  - **Central dependency:** the region `idx` list + per-region bounding boxes
    come from `streetcfg.dat`, shipped inside the Tencent Maps Android APK
    (~281 regions). No documented enumeration without it. The community repo
    `chaofunchengfeng/TencentMapPanoramaCoverageAreaData` (299 per-city GeoJSON
    + a sqlite DB, keyed by 4-digit `idxId`) is a usable cross-check / `idx`
    source.
  - Two foundation prerequisites: a **new `tencent_mobile_street` source kind**
    (TXVN decoder + per-city `bl` enumeration) and a small `geo.py` addition
    (Tencent pixel math + GCJ-02→WGS84 inverse) — both must land before the
    provider PR.
- `2026-05-22` approval: **pending** — awaiting user review.
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **New source kind + non-`(z,x,y)` enumeration.** `tencent` cannot reuse
   `raster` / `vector_mvt` / `coverage_json`; it needs a new
   `tencent_mobile_street` source kind that (a) decodes the `TXVN` binary and
   (b) drives a **per-city `bl` enumeration** instead of a web-mercator
   `(z,x,y)` sweep. Confirm this lands as a Phase-0 foundation PR before the
   provider PR, and decide whether the per-city enumeration lives in the runner
   (a new `discovery_mode`, like `ja360`'s `point_probe`) or inside the source
   kind.
2. **Data level `lv`.** Valid levels are `{11,12,13,14,18}`. This subplan
   proposes `lv=14` for the z14-grid scrape (the community dataset used the
   finest `lv=18`). Confirm `lv=14`, or prefer `lv=18` for finer line geometry
   at the cost of many more tiles per city.
3. **`xf` fallback is robots-disallowed.** `sv.map.qq.com/robots.txt` is
   `Disallow: /`, so the `xf` point-probe fallback must **not** be the routine
   scrape path. The primary `mobile_street` path on `mapvectors.map.qq.com`
   (no robots.txt → allowed) is unaffected. Confirm the provider ships
   `mobile_street`-only and the `xf` path is documented as
   reference/cross-check only (and its §3 test is optional).
4. **`streetcfg.dat` acquisition.** Coverage discovery needs the region `idx`
   list + bounding boxes from `streetcfg.dat` inside the Tencent Maps Android
   APK. The implementer must either extract+parse the APK config or reuse the
   community `idxId` list. Confirm which path is acceptable, and that a small
   committed region table (`_data/tencent_streetcfg.json`) under the provider
   is the right home for it (it is provider-specific data, not a shared-file
   edit).
5. **Dated coverage / new source kind cost vs. T2 value.** Tencent SV imagery
   is 2013–2016 and city-centric; the provider also costs a new source kind, a
   `geo.py` addition, and an APK-derived config. Confirm Tencent is worth the
   foundation investment as a T2 provider, or whether it should be deferred
   behind the cleaner raster providers. (Recommendation: keep it — it is a
   major national provider and the `mobile_street` path is clean once the
   foundation lands; the `TXVN` `date` field even enables a future date layer.)
6. **`coordinate_scheme` value.** The provider needs a `coordinate_scheme`
   string but does **not** use the generic `tile_range_for_bbox` dispatcher
   (the new source kind owns the geometry). This subplan uses `tencent_px` as a
   documentation-only value. Confirm that is acceptable, or whether the
   dispatcher should gain a no-op `tencent_px` branch for consistency.

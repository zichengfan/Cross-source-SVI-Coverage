# [T1] Provider: Kakao Maps Road View (`kakao`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Kakao Maps Road View (카카오맵 로드뷰) is the street-level imagery service of
KakaoMap, the dominant consumer mapping platform in South Korea. Coverage is
South Korea only (Seoul, Busan, Jeju, etc.; nothing outside Korea) and is dense,
with imagery dating back to ~2008. It is in scope because it is active and
programmatically reachable, is not defunct, is not a re-hoster, and is not
paid-B2B.

**This subplan REDESIGNS `kakao` from a point-probe provider into a
`kind="raster"` tile provider.** Kakao Maps renders a dedicated
**Road View coverage-overlay tile layer** — the semi-transparent blue lines that
draw "Road View exists on this road" over the basemap when Road View mode is
on. Those overlay tiles are public `{L}/{y}/{x}.png` images on Kakao's tile CDN
(`*.daumcdn.net`). We fetch and rasterize that rendered overlay exactly like
`svmap_google` rasterizes Google's `sv-map` overlay — no panorama point API, no
`streetlevel` library, no per-point JSON probing. The previous revision of this
file incorrectly concluded "no coverage tile layer exists" — that conclusion was
about the panorama-*point* API (`rv.map.kakao.com/roadview-search`), not the
rendered overlay raster layer, which does exist and is the subject of this
redesign.

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:** `https://map.kakao.com/` — toggle the Road
  View ("로드뷰") button to draw the blue coverage overlay. The viewer host is
  `map.kakao.com`; the **tile CDN** is `map{0..3}.daumcdn.net` (the bare
  `map.daumcdn.net` alias also works).
- **Tier:** T1.

- **Coverage endpoint — the Road View overlay raster tile layer:**
  - **URL template:**
    `https://map{s}.daumcdn.net/map_roadviewline/{version}/L{z}/{y}/{x}.png`
  - Recommended concrete template (single CDN host, no `{s}` rotation needed):
    `https://map0.daumcdn.net/map_roadviewline/3.00/L{z}/{y}/{x}.png`
  - **Layer code:** `map_roadviewline` — Kakao's Road View coverage-line
    overlay. (`map_skyview` = satellite, `map_2d` = basemap, etc.; the SDK's
    `ROADVIEW` tileset, copyright "KnWorks", is built from this layer.)
  - **Version segment:** `3.00`. The Kakao Maps JS SDK
    (`https://t1.daumcdn.net/mapjsapi/js/main/4.4.19/kakao.js`) defines
    `aa.Cf = aa.ROADVIEW || "3.00"` — `3.00` is the default Road View overlay
    version. (An old blog used `7.00`; both `3.00` and `7.00` return identical
    tiles today — the segment is effectively a cache buster. Pin `3.00`.)
  - **Path order is `L{z}/{y}/{x}`** — the L-level prefix, then **y, then x**
    (confirmed from the SDK's skyview builder
    `"map"+(a&3)+".daumcdn.net/map_skyview/L"+d+"/"+b+"/"+a+".jpg"`, where
    `a`=x, `b`=y, `d`=L-level — i.e. `.../L{d}/{b=y}/{a=x}`). Do **not** swap
    x/y.
  - **Method:** `GET`. No query string required.

- **Coordinate scheme:** **NOT web mercator.** Kakao map tiles use a
  **Korea-specific Transverse Mercator grid (EPSG:5181)** — a custom grid
  `geo.py` does not currently support. This is the one structural complication
  of the redesign and requires a small foundation change (see §4, item 1).
  Grid parameters (from the Gaia3D `OL3_KoreanTmsLayer` reference, the de-facto
  public spec, and confirmed live against Seoul/Busan/Jeju):
  - **CRS:** EPSG:5181 — `+proj=tmerc +lat_0=38 +lon_0=127 +k=1 +x_0=200000
    +y_0=500000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs`.
  - **Tile origin (bottom-left, EPSG:5181 metres):** `(-30000, -60000)`.
  - **Y axis points UP** (origin at bottom-left; tile `y` increases northward —
    this is TMS-style, **not** the XYZ top-left scheme).
  - **Resolutions array (metres/pixel), index = L-level:**
    `[2048, 1024, 512, 256, 128, 64, 32, 16, 8, 4, 2, 1, 0.5, 0.25]`
    (14 levels, `L0`..`L13`).
  - **Tile size:** 256×256 px.
  - **Tile math:** project (lon,lat) WGS84 → (X,Y) EPSG:5181, then
    `tx = floor((X - (-30000)) / (resolution[L] * 256))`,
    `ty = floor((Y - (-60000)) / (resolution[L] * 256))`.
    Verified: Seoul City Hall (126.9779, 37.5663) → EPSG:5181
    `(198047.5, 451862.8)` → **L7 tile `(tx=55, ty=124)`**, which fetches a
    real overlay tile.

- **Zoom range / native overlay zoom / tile size / response format:**
  - **The `map_roadviewline` overlay is served at `L7` ONLY.** A full L0–L13
    scan over Seoul (3×3 tile grid per level) returned content **only at L7**;
    every other level returns the empty placeholder. Kakao draws the coverage
    overlay into a single resolution level and the viewer scales it
    client-side. **`L7` is the only level to fetch.**
  - L7 resolution = **16 m/pixel** (256 px tile = 4096 m on the ground).
  - Response format: **PNG, 256×256, RGBA** (transparent background + blue
    strokes). `Content-Type: image/png`.
  - **`display_zoom_min = display_zoom_max = 7`** (the provider has exactly one
    valid source zoom: L7). `default_display_zoom = 7`.
  - **Note on grid mismatch:** L7 (16 m/px) is coarser than the project's
    analysis grid z14 (~9.5 m/px). This is acceptable — the overlay strokes are
    thick (≈8–12 px wide) so they over-represent each covered road; rasterizing
    L7 tiles onto the z14 grid (`raster` kind → `rasterize.py`) yields a sound
    binary-presence layer, the same coarse-overlay tradeoff `svmap_google`
    accepts. Document the 16 m/px native resolution in the module docstring.

- **Auth:** **none.** No token, no cookie, no API key, no signed URL. A plain
  `GET` with a descriptive `User-Agent` returns the tile. A `Referer` of
  `https://map.kakao.com/` is sent for politeness/consistency with the viewer
  but is **not** enforced (tiles return 200 without it). **No `.env` key
  needed.**

- **Presence rule:** **alpha-based** (`coverage_from="alpha"`). The overlay is
  drawn as semi-transparent blue strokes on a **fully transparent background**
  (`alpha == 0`). Each road stroke is rendered at `alpha == 117`
  (`RGB ≈ (157, 194, 246)`); where strokes overlap (intersections, parallel
  roads within the ~10 px stroke width) the alpha composites up to ~254 and the
  colour darkens (`RGB ≈ (25, 91, 181)`). **Re-verified live 2026-05-21** on the
  L7 Seoul City Hall tile (`L7/124/55`): `alpha == 0` for only 6.0% of pixels,
  `alpha > 0` for 94.0% — dense central Seoul has Road View on essentially every
  street, so at 16 m/px the fat strokes merge into a near-solid fill. (The
  earlier "33% / 67%" figure in this subplan was a scout mismeasurement;
  the **rule** — `alpha > 0` ⇔ coverage — is correct, confirmed by the empty
  tiles below.) Therefore:
  - "Road View imagery exists at a pixel" ⇔ `alpha > 0` at that pixel.
  - The existing `raster` source kind's `summarize_png()` already computes
    exactly this (`coverage_pixel_count = np.count_nonzero(alpha)`); no new
    decode logic is needed — `decode_raster` works as-is.
  - **Empty / no-coverage tile signature — two forms, both HTTP 200, both
    `coverage_pixel_count == 0`:**
    1. **256×256 fully-transparent PNG** (~1.2 KB) — returned for in-Korea land
       tiles with no Road View (mountains: verified Seoraksan and Jirisan peaks
       → 100% `alpha == 0`).
    2. **68-byte 1×1-pixel fully-transparent PNG** — returned offshore / outside
       the grid extent (verified Pacific Ocean, East Sea).
    There is **no 404 and no 204**. `summarize_png` handles both (it reads any
    dimensions) → `coverage_pixel_count == 0` ⇒ checked-empty. Because the
    no-coverage tile is always a transparent PNG, set the source option
    **`empty_tile_rule="transparent_png"`** (the B0 foundation rule, as used by
    `yandex`) so zero-coverage tiles are flagged `is_empty` and not stored —
    Korea is ~70% mountainous, so most L7 tiles are empty.

- **robots.txt / ToS notes; observed rate limit:**
  - **`https://map0.daumcdn.net/robots.txt` → HTTP 200, `User-agent: *` /
    `Disallow:` (empty disallow ⇒ everything allowed).** Same for
    `map.daumcdn.net` and `map1.daumcdn.net`. **The tile CDN explicitly permits
    crawling.** This redesign fetches **only** from `*.daumcdn.net`.
  - `https://map.kakao.com/robots.txt` is `Disallow: /` — but this provider
    does **not** crawl the viewer host at all (it is used only as a `Referer`
    string). Record this caveat in the module docstring, as the previous
    revision did.
  - No documented or observed rate limit; a 7×6 L7 tile sweep over Seoul ran
    with no throttling or errors. Use the project polite default
    (`polite.polite_fetch`, per-host throttle). All tiles come from one host
    family (`map{s}.daumcdn.net`); a single fixed host (`map0`) keeps the
    per-host throttle honest. This is a polite scrape of public, unauthenticated
    coverage-overlay tiles for availability research — not the imagery itself.

- **Known quirks / gotchas:**
  - **Custom EPSG:5181 grid, not web mercator.** The single biggest difference
    from `svmap_google` (which is plain `web_mercator`). The fetch loop's tile
    selection and the rasterizer's tile→bounds reprojection both need the
    EPSG:5181 grid. This needs a new `coordinate_scheme` (see §4 item 1).
  - **Overlay exists at L7 only.** Do not attempt L8+ (always empty) or
    sub-L7 (always empty). The provider's source zoom is fixed at 7.
  - **TMS-style y-axis (origin bottom-left, y increases north).** Opposite of
    the standard XYZ top-left convention. The tile-math helper must not flip y
    to top-left.
  - **Empty tiles are HTTP 200, not 404/204.** Empty-tile detection is purely
    `alpha == 0` after decode — never rely on status code. `skip_404` logic is
    irrelevant here. The 1×1 PNG (rather than a full 256×256 transparent PNG)
    is normal; `summarize_png` handles any dimensions.
  - **Coverage is South Korea only.** Discovery must be bounded to the Korean
    peninsula bbox; do not sweep globally.
  - **Version segment is cosmetic.** `3.00` and `7.00` return identical bytes;
    pin `3.00` (the current SDK default) and treat a future content change as a
    re-scrape trigger, not a per-request lookup.
  - **No date layer.** The rendered overlay carries no capture-date
    information (it is a single flat presence layer). A `*_year.tif` date layer
    is **not** possible from this source and is out of scope for `kakao`.
  - **Single CDN host vs. `{s}` rotation.** Kakao's viewer load-balances across
    `map0..map3.daumcdn.net` via `x & 3`. For a polite scraper a single fixed
    host (`map0`) is simpler and keeps `polite`'s per-host throttle meaningful;
    use `map0` in the template. (If throughput ever matters, host rotation is a
    later optimization, not part of this PR.)

## 3. Test plan (write these FIRST — red before green)

All tests are offline and decode recorded PNG fixtures; no live tile fetches in
unit tests (`docs/PLAN.md` §12). Mirror the raster-decode tests used for
`svmap_google` / the `raster` source kind.

Fixtures recorded live under `tests/fixtures/kakao/` (captured 2026-05-21):
- `roadviewline_L7_seoul.png` — the L7 Seoul City Hall overlay tile
  (`https://map0.daumcdn.net/map_roadviewline/3.00/L7/124/55.png`); a 256×256
  RGBA PNG, ~52 KB, 94% of pixels with `alpha > 0` (dense Road View coverage).
- `roadviewline_L7_empty.png` — the offshore empty signature
  (`.../L7/-63/363.png`, Pacific Ocean); the 68-byte 1×1 fully transparent PNG.
- `roadviewline_L7_empty_land.png` — the in-Korea no-coverage signature
  (`.../L7/64/72.png`, Jirisan peak); a 256×256 fully-transparent PNG (~1.2 KB).

Tests (`tests/test_providers_kakao.py`):

- [ ] `test_kakao_registers` — importing `coverage_acquisition.providers.kakao`
  registers `"kakao"` in `PROVIDERS`; `PROVIDERS["kakao"].key == "kakao"`.
- [ ] `test_kakao_provider_shape` — provider has exactly one source; its
  `kind == "raster"`; `coordinate_scheme == "kakao_epsg5181"`;
  `default_display_zoom == 7`; the source's `display_zoom_min == 7` and
  `display_zoom_max == 7`; no token/cookie/auth fields are set.
- [ ] `test_kakao_tile_url_build` — the source `template` fills correctly for a
  sample `(z, x, y)`: with `z=7, x=55, y=124` it produces
  `https://map0.daumcdn.net/map_roadviewline/3.00/L7/124/55.png` (assert host,
  the `map_roadviewline` layer, the `3.00` version, the `L{z}` prefix, and that
  the path order is `L{z}/{y}/{x}` — y before x).
- [ ] `test_kakao_tilecoord_seoul` — the EPSG:5181 tile-math helper maps Seoul
  City Hall `(lon=126.9779, lat=37.5663)` at `L7` to tile `(x=55, y=124)`
  (guards the EPSG:5181 projection + origin `(-30000,-60000)` + L7 resolution
  `16` m/px + 256-px tile, and the bottom-left/y-up axis).
- [ ] `test_kakao_decode_coverage` — decoding `roadviewline_L7_seoul.png` via
  the `raster` kind's `summarize_png` yields `width == 256`, `height == 256`,
  `coverage_pixel_count > 40000`, `coverage_ratio > 0.5` — presence detected.
- [ ] `test_kakao_decode_empty` — decoding `roadviewline_L7_empty.png` (1×1) and
  `roadviewline_L7_empty_land.png` (256×256 transparent) both yield
  `coverage_pixel_count == 0` ⇒ checked-empty, raster value `0`. Assert
  `summarize_png` does not raise on a 1×1 image.
- [ ] `test_kakao_presence_alpha_not_color` — presence is decided by **alpha**,
  not by RGB: a synthetic 4×4 PNG that is fully transparent except one pixel
  with `alpha > 0` decodes to `coverage_pixel_count == 1`; a fully transparent
  4×4 PNG decodes to `0`. (Pins `coverage_from="alpha"`.)
- [ ] `test_kakao_tile_range_korea` — `tile_range_for_bbox` for the South Korea
  bbox `(124.5, 33.0, 131.9, 38.7)` at `L7` with the `kakao_epsg5181` scheme
  returns the deterministic `TileRange(x_min=-1, x_max=168, y_min=1,
  y_max=158)`, `count == 26860`. Note `x_min == -1` is correct — the bbox's
  far-SW corner (124.5°E, 33.0°N) projects one tile west of the EPSG:5181 grid
  origin; off-grid tiles simply return the empty placeholder, so the sweep is
  still well-formed. (The scout's earlier "non-negative, low thousands" estimate
  was wrong; ~27k 4096 m tiles is the real, still-cheap sweep size.)

- Fixtures: `tests/fixtures/kakao/roadviewline_L7_seoul.png`,
  `tests/fixtures/kakao/roadviewline_L7_empty.png`,
  `tests/fixtures/kakao/roadviewline_L7_empty_land.png` (small recorded PNGs).

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind:** `raster` — **existing**, no new source kind needed. The
  `raster` kind (`src/coverage_acquisition/source_kinds/raster.py`) already
  decodes PNG tiles by alpha (`summarize_png` → `coverage_pixel_count`). `kakao`
  is a straight `kind="raster"` provider mirroring
  `src/coverage_acquisition/providers/svmap_google.py`.

- [ ] **Foundation prerequisite — new `kakao_epsg5181` coordinate scheme.**
  Kakao's tiles are on the EPSG:5181 Korea TM grid, which `geo.py` does not yet
  support (`web_mercator` / `yandex_wgs84_mercator` / `baidu` only). Adding the
  scheme is a **separate `foundation`-labelled PR that must merge before the
  `kakao` provider PR** — it edits the shared `geo.py` and must not be bundled
  with the provider module (per `CLAUDE.md`: provider PRs touch no shared file).
  Scope of that foundation PR (summarised here so this subplan is
  self-contained):
  - Add to `geo.py` a `kakao_epsg5181` branch with:
    - constants: origin `(-30000.0, -60000.0)`, tile size `256`, resolutions
      `[2048,1024,512,256,128,64,32,16,8,4,2,1,0.5,0.25]`.
    - `kakao_lonlat_to_tile(lon, lat, zoom)` — project WGS84→EPSG:5181 (via
      `pyproj`, already a transitive dep; otherwise add it), then
      `tx=floor((X+30000)/(res*256))`, `ty=floor((Y+60000)/(res*256))`.
    - `kakao_bbox_to_tile_range(bbox, zoom)` — corner transform → `TileRange`.
    - `kakao_tile_to_lonlat_bounds(x, y, zoom)` — inverse, for the rasterizer
      (EPSG:5181 tile extent → WGS84 bounds; y-up).
    - wire all three into the dispatchers `tile_range_for_bbox` and
      `tile_to_lonlat_bounds_for_scheme`.
  - Unit-test the foundation scheme against the scout's verified anchor: Seoul
    City Hall `(126.9779, 37.5663)` @ L7 → `(55, 124)`.
  - Flag to the foundation owner that the rasterizer must reproject EPSG:5181
    tile bounds to EPSG:3857 for the z14 COG (the COG CRS stays EPSG:3857).

- [ ] Write the §3 tests first; confirm they fail (red).

- [ ] Add `src/coverage_acquisition/providers/kakao.py` defining `PROVIDER`
  (`ProviderDefinition`) and calling `register_provider(PROVIDER)` — mirror
  `svmap_google.py` exactly in shape:
  - `key="kakao"`, `output_namespace="kakao_roadview_overlay_raster"`,
    `run_label_prefix="kakao_roadview_overlay"`.
  - `default_display_zoom=7`.
  - `coordinate_scheme="kakao_epsg5181"`.
  - `area_presets={"seoul_city_hall_bbox": BoundingBox(...)}` — see pilot bbox
    below; declare the `BoundingBox` inline in the module (do **not** add it to
    `providers/_presets.py`, per that file's conflict-free docstring).
  - One `SourceDefinition`:
    - `id="kakao_roadviewline"`, `kind="raster"`.
    - `template="https://map0.daumcdn.net/map_roadviewline/3.00/L{z}/{y}/{x}.png"`.
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "image/png,image/*;q=0.9,*/*;q=0.1",
      "Referer": "https://map.kakao.com/"}`.
    - `display_zoom_min=7`, `display_zoom_max=7` (overlay exists at L7 only).
    - `expect_content_type_prefix="image/"`.
    - `storage_subdir="tiles"`.
    - `options={"coverage_from": "alpha", "empty_tile_rule": "transparent_png",
      "layer": "map_roadviewline", "version": "3.00",
      "native_resolution_m_per_px": "16"}` — `coverage_from` kept explicit even
      though `alpha` is the `raster` kind default; `empty_tile_rule` flags the
      transparent no-coverage tiles (both the 1×1 and the 256×256 forms) as
      `is_empty` so they are not stored (most of mountainous Korea is empty).
    - `notes`: "Kakao Road View coverage-overlay raster tiles
      (`map_roadviewline`, EPSG:5181 grid, served at L7 only). Presence =
      alpha>0 (transparent bg, semi-transparent blue strokes)."

- [ ] Implement until the §3 tests pass (green); refactor.

- [ ] Module docstring: record (a) this is the **rendered overlay raster** layer
  (`map_roadviewline`), not a panorama API; (b) the **EPSG:5181** custom grid
  and that the overlay is **L7-only** at 16 m/px; (c) the ToS caveat — fetch
  **only** from `*.daumcdn.net` (robots `Disallow:` empty = allowed); never
  crawl `map.kakao.com` (which has `Disallow: /`; it is only a `Referer`);
  (d) coverage is South Korea only; no auth.

- [ ] Pilot fetch: bbox `126.960 37.560 126.990 37.580`
  (`Seoul — City Hall / Jung-gu`, ~2.7 km × 2.2 km). At L7 this is a small
  handful of tiles around `(tx≈55, ty≈124)`; expect every tile to be a
  ~50–60 KB RGBA PNG with dense blue coverage strokes along the Seoul street
  network (City Hall, Sejong-daero, Cheonggyecheon).

- [ ] Rasterize the pilot area to a z14 COG (`rasterize.py`): decode each L7
  tile, treat `alpha > 0` pixels as covered, reproject the EPSG:5181 tile
  footprint to EPSG:3857, burn onto the shared z14 grid. Sanity-check: covered
  pixels land on Seoul streets/land (not the Han River or sea); CRS EPSG:3857;
  `uint8`; covered pixels > 0.

- [ ] Two-pass full extent: pass-1 discovery region = South Korea bbox
  `124.5 33.0 131.9 38.7`. Because the overlay is **L7-only**, there is no
  separate coarse discovery zoom — pass-1 and pass-2 are both at L7. Sweep the
  Korea bbox at L7 (≈ a few thousand 4096 m tiles; cheap), keep tiles whose
  decoded `coverage_pixel_count > 0`, drop the rest as checked-empty. (If the
  two-pass runner insists on a coarser pass-1 zoom, run a single-pass L7 sweep
  over the Korea bbox instead — the tile count is small enough that two passes
  add no benefit. Flag this to the runner owner.)

- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T1"`,
  `source_endpoint="https://map0.daumcdn.net/map_roadviewline/3.00/L{z}/{y}/{x}.png"`,
  `tos_notes` per §2). Update the inventory status for `kakao`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.kakao` imports and
  self-registers in `PROVIDERS`; CI smoke test (import/register/dry-run) passes.
- The provider's single source is `kind="raster"`,
  `coordinate_scheme="kakao_epsg5181"`, source zoom fixed at L7.
- Pilot L7 tiles fetch over Seoul, return `image/png`, and decode to
  `coverage_pixel_count > 0`; an out-of-Korea tile decodes to
  `coverage_pixel_count == 0` (checked-empty, raster value `0`) without error.
- Coverage burns onto Seoul streets/land, not water.
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0, extent within
  the South Korea bbox.
- Empty tiles (HTTP 200 + 1×1 transparent PNG) are handled as checked-empty,
  not as errors or 404s.
- Fetches via `polite.polite_fetch` with a descriptive User-Agent; ToS caveats
  (`*.daumcdn.net` only — robots-allowed; never `map.kakao.com`) documented in
  the module docstring.

## 6. Status log

- `2026-05-20` scout: drafted (original) — concluded point-query JSON API,
  `kind="streetlevel"`.
- `2026-05-20` approval: pending.
- `2026-05-21` scout: **REDESIGNED to `kind="raster"`.** Re-scouted the Kakao
  Maps Road View rendered coverage-overlay tile layer. Confirmed live:
  - Endpoint
    `https://map{s}.daumcdn.net/map_roadviewline/{version}/L{z}/{y}/{x}.png`
    (`s∈0..3`, `version=3.00` per the Kakao JS SDK
    `aa.Cf=aa.ROADVIEW||"3.00"`). Fetchable with HTTP 200, `image/png`.
  - Grid is **EPSG:5181** (Korea TM): origin `(-30000,-60000)`, tile size 256,
    resolutions `[2048..0.25]`, y-axis up. Verified Seoul City Hall
    `(126.9779,37.5663)` → L7 tile `(55,124)`.
  - The `map_roadviewline` overlay is served at **L7 only** (16 m/px); all
    other L-levels return empty placeholders.
  - The L7 Seoul tile renders the Road View coverage overlay — semi-transparent
    blue strokes (`RGB≈(75,194,255)`, `alpha≈130`) on a transparent background;
    presence rule is `alpha > 0` (`coverage_from="alpha"`). Verified visually.
  - Empty/no-coverage tiles = HTTP 200 + a 68-byte 1×1 transparent PNG (no 404,
    no 204). Verified for Pacific Ocean and out-of-range coordinates.
  - **robots.txt:** the tile CDN `*.daumcdn.net` returns `User-agent: *` /
    `Disallow:` (empty ⇒ allowed). The viewer host `map.kakao.com` is
    `Disallow: /` but is not crawled by this provider.
  - Auth: none. No `.env` key. Coverage: South Korea only.
  - One open foundation dependency: a new `kakao_epsg5181` coordinate scheme in
    `geo.py` (separate foundation PR before the provider PR).
- `2026-05-21` approval: approved by the user (raster redesign).
- `2026-05-21` foundation: the `kakao_epsg5181` coordinate scheme landed on
  `dev` via the B0 foundation PRs (#22, #23). The provider PR can proceed.
- `2026-05-21` implement: rebuilt `providers/kakao.py` as a `kind="raster"`
  provider on branch `provider/kakao`. While recording fixtures, two scout
  findings were corrected (see §2/§3): (a) the covered L7 Seoul tile is 94%
  `alpha>0`, not 67% — the rule `alpha>0 ⇔ coverage` still holds, confirmed by
  mountain tiles decoding to 100% transparent; (b) the no-coverage signature
  has **two** forms — a 1×1 transparent PNG (offshore) and a 256×256 fully
  transparent PNG (in-Korea mountains) — so the source sets
  `empty_tile_rule="transparent_png"`. Fixtures recorded:
  `roadviewline_L7_{seoul,empty,empty_land}.png`.
- `YYYY-MM-DD` verify: notes appended here.

---

### Open questions for the reviewer

1. **`kakao_epsg5181` coordinate scheme is a foundation dependency.** This
   provider needs a new `coordinate_scheme` in the shared `geo.py` (EPSG:5181
   Korea TM grid: project, tile-range, tile-bounds, dispatcher wiring) plus a
   `pyproj` dependency for the WGS84↔EPSG:5181 transform. Confirm this lands as
   a `foundation` PR before the `kakao` provider PR. No other in-scope provider
   needs EPSG:5181 today, so the scheme can be `kakao`-specific.
2. **L7-only overlay vs. the two-pass runner.** The overlay exists at exactly
   one zoom (L7). The two-pass discovery machinery assumes a coarse discovery
   zoom distinct from the z14 fetch zoom. For `kakao`, pass-1 and pass-2 are
   both L7 — effectively a single-pass L7 sweep of the Korea bbox (a few
   thousand 4096 m tiles, cheap). Confirm the runner can run a single-zoom
   sweep for this provider, or that running L7 as both passes is acceptable.
3. **16 m/px native vs. z14 (~9.5 m/px) analysis grid.** L7 is ~1.7× coarser
   than z14. The blue strokes are thick (8–12 px) and over-represent each
   covered road, so binary presence on z14 is sound, but covered roads will be
   slightly fattened. Confirm this coarse-overlay tradeoff is acceptable (it is
   the same one `svmap_google` accepts) or whether a thinning/centerline step
   is wanted in `rasterize.py` (out of scope for this provider PR if so).
4. **Old `streetlevel`-based `kakao` artifacts.** The current
   `providers/kakao.py` is the point-probe implementation and registers a
   `streetlevel` probe (`register_streetlevel_probe`). The redesign PR replaces
   that module wholesale with the `kind="raster"` version; confirm the
   `streetlevel`-probe registration for `kakao` (and any `data/raw/kakao` /
   `data/intermediate/kakao` point outputs) should be removed as part of this
   PR.
5. **No date layer.** The rendered overlay carries no capture date — `kakao`
   will have no `*_year.tif`. Confirm that is accepted (it is inherent to a
   rendered-overlay raster source).

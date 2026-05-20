# [T1] Provider: Kakao Maps Road View (`kakao`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Kakao Maps Road View (카카오맵 로드뷰) is the street-level imagery service of
KakaoMap, the dominant consumer mapping platform in South Korea. Coverage is
South Korea only (Seoul, Busan, Jeju, etc.; nothing outside Korea). It is an
active, high-density SVI dataset with imagery dating back to ~2008 and is
**natively supported by the `streetlevel` Python library** (a Tier-1 provider in
the project triage, `docs/PLAN.md` §2). It is in scope because it is active and
programmatically reachable, is not defunct, is not a re-hoster, and exposes its
coverage through a public JSON API rather than being paid-B2B-only.

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:** `https://map.kakao.com/` (Road View mode:
  `map_type=TYPE_MAP&map_attribute=ROADVIEW`). Public viewer host is
  `map.kakao.com`.
- **Tier:** T1 (streetlevel-native).

- **Coverage endpoint(s):** Kakao does **not** serve a coverage tile layer
  (no raster blue-lines, no MVT). Coverage is discovered through a **point-query
  JSON API**: a radius search around a lat/lon. This is what `streetlevel.kakao`
  wraps, and is the endpoint this provider uses.

  - **Primary (radius search):**
    `GET https://rv.map.kakao.com/roadview-search/v2/nodes?PX={lon}&PY={lat}&RAD={radius}&PAGE_SIZE={limit}&INPUT=wgs&TYPE=w&SERVICE=glpano`
    - `PX` = longitude (WGS84), `PY` = latitude (WGS84), `INPUT=wgs` selects
      WGS84 input.
    - `RAD` = search radius in metres (max **100**; streetlevel default 35).
    - `PAGE_SIZE` = max results (max **100**; streetlevel default 50).
    - Wrapped by `streetlevel.kakao.find_panoramas(lat, lon, radius, limit, session)`
      and `find_panoramas_async(...)`.
  - **By-id (not used for coverage):**
    `GET https://rv.map.kakao.com/roadview-search/v2/node/{panoid}?SERVICE=glpano`
    — wrapped by `streetlevel.kakao.find_panorama_by_id`. Used only for
    single-pano metadata / historical panos; **not** needed for coverage
    enumeration.
  - **Method:** `GET`. **Headers:** none required (the bare request returns
    JSON; tested with a custom descriptive User-Agent and it works fine).

- **Coordinate scheme:** input/output is **WGS84 lon/lat** (`wgsx`/`wgsy` in
  the response). The project's z14 raster grid is standard `web_mercator`, so
  `coordinate_scheme="web_mercator"` is correct for this provider. Kakao also
  returns `wcongx`/`wcongy` (WCongnamul, Kakao's own projection) and
  `wtmx`/`wtmy` (Korea TM) — **ignore both**; always use `wgsx`/`wgsy`.

- **Zoom range / tile size / response format:** Not a tile API — there is no
  zoom or tile size. Response is **JSON**. Shape (confirmed live, Seoul):
  ```json
  {"street_view": {
     "cnt": 3,
     "street": null,
     "streetList": [
       {"id": 1050215196, "angle": "270.2",
        "img_path": "/2015/09/1013588/2_100271_1013588_20150930032301",
        "wgsx": 126.9777695, "wgsy": 37.5661338,
        "wcongx": 495090.0, "wcongy": 1129611.0,
        "wtmx": 198036.0, "wtmy": 451844.4,
        "addr": "서울 중구 태평로1가",
        "st_name": null, "st_type": null, "area_type": null,
        "shot_date": "2015-09-30 00:00:00", "shot_tool": "101",
        "spot": null, "past": null}
     ]}}
  ```
  Empty response (ocean / outside Korea):
  ```json
  {"street_view": {"cnt": 0, "street": null, "streetList": null}}
  ```
  `streetlevel.kakao.parse_panoramas(response)` turns `streetList` into
  `KakaoPanorama` objects; each has `.id`, `.lat`, `.lon`, `.date`,
  `.heading`, `.image_path`, `.panorama_type` (a `PanoramaType` IntEnum from
  `shot_tool`). `.date` is parsed from the timestamp suffix of `img_path`.

- **Auth:** **none.** No token, no cookie, no API key. No `.env` key needed.

- **Presence rule:** "imagery exists" at a query point ⇔
  `response["street_view"]["cnt"] > 0` (equivalently, `find_panoramas(...)`
  returns a non-empty list). Each returned `KakaoPanorama` is one coverage
  point at `(.lon, .lat)`. The set of all returned panorama coordinates across
  all discovery queries is the coverage point cloud that gets rasterized to the
  z14 binary-presence grid (PLAN §1: "burn geometry; buffer isolated points").

- **robots.txt / ToS notes; observed rate limit:**
  - `https://rv.map.kakao.com/robots.txt` → **404 Not Found** (no robots.txt on
    the API host ⇒ `polite.robots_allows` treats it as allowed).
  - `https://map.kakao.com/robots.txt` → `User-agent: * Disallow: /` (and
    explicit `Disallow` for AI bots incl. `ClaudeBot`). **This restriction is on
    the viewer host `map.kakao.com`, not on the API host `rv.map.kakao.com`.**
    The provider must fetch coverage **only** from `rv.map.kakao.com` and must
    **not** crawl `map.kakao.com`. Record this caveat in the module docstring.
  - No documented rate limit observed; a radius-100 query in dense Seoul
    returned 96 panoramas in one call with no throttling. Use the project's
    polite default (`PolitePolicy`, `min_interval_seconds=0.25`); consider a
    slightly higher interval (e.g. 0.5 s) given the dense point-grid sweep.
  - This is a polite scrape of a public, unauthenticated JSON endpoint for
    coverage-availability research (not the imagery itself, not AI training).

- **Known quirks / gotchas:**
  - **Point-query, not tile-query.** There is no coverage tile layer. Coverage
    discovery must sweep a **grid of query points** over Korea and union the
    returned panorama coordinates. This is fundamentally different from the
    raster/MVT providers and is the main reason a dedicated `streetlevel`
    source kind is needed.
  - **Radius cap 100 m, limit cap 100.** Adjacent query points must be spaced
    so their search disks tile the area. With `RAD=100`, a point grid spaced
    ~140 m (≈ `100 * sqrt(2)`) gives full coverage with slight overlap. In very
    dense urban cores a single `RAD=100` query can hit the 100-result cap and
    silently miss panoramas; for the **coverage** use case (binary presence)
    this is acceptable — we only need ≥1 hit per z14 cell — but the discovery
    grid spacing should be ≤ the z14 cell size (~1.9 km) anyway, so density is
    fine. Document the cap.
  - **Coverage is South Korea only.** Queries outside Korea (Tokyo, Pacific)
    return `cnt: 0`. The pass-1 discovery region must be the Korean peninsula
    bbox; do not sweep globally.
  - `find_panorama_by_id` "only appears to work for the most recent coverage at
    a location" (per streetlevel docstring) — irrelevant here since we use
    `find_panoramas`, but note it if historical dates are pursued later.
  - `shot_date` in the raw JSON is often `YYYY-MM-DD 00:00:00` (date only);
    `streetlevel` instead parses the precise timestamp from the `img_path`
    suffix into `KakaoPanorama.date`. Use `.date` for the optional date layer.
  - Historical panoramas at a location are in the `past` field of a street
    entry (null in all sampled responses). Not needed for binary presence;
    ignore for now.
  - `streetlevel.kakao` itself sends **no custom headers** and uses `requests`
    directly. The project requires fetching via `polite.polite_fetch`. Do **not**
    call `streetlevel`'s networking functions in the fetch loop — use
    `streetlevel.kakao.api.build_find_panoramas_request_url(...)` to build the
    URL, fetch via `polite_fetch`, then decode with
    `streetlevel.kakao.parse.parse_panoramas(...)` (or the equivalent JSON
    walk). This keeps throttle/retry/robots centralised. See §4.

## 3. Test plan (write these FIRST — red before green)

All tests are offline: record JSON fixtures and decode them. Live API calls are
forbidden in unit tests (`docs/PLAN.md` §12).

Fixtures to record under `tests/fixtures/kakao/`:
- `nodes_seoul.json` — a real `find_panoramas` response for Seoul City Hall
  (`PY=37.5663, PX=126.9779, RAD=50, PAGE_SIZE=3`), `cnt > 0`, 3 `streetList`
  entries (sample already captured by scout — see §2).
- `nodes_empty.json` — a `cnt: 0` response (`{"street_view": {"cnt": 0,
  "street": null, "streetList": null}}`), from an ocean query.

Tests (`tests/test_providers_kakao.py`, plus a case in the source-kind test
file if the `streetlevel` kind is exercised generically):

- [ ] `test_kakao_registers` — importing `coverage_acquisition.providers.kakao`
  registers `"kakao"` in `PROVIDERS`; `PROVIDERS["kakao"].key == "kakao"`.
- [ ] `test_kakao_provider_shape` — provider has exactly one source, its `kind`
  is the streetlevel kind (`"streetlevel"`), `coordinate_scheme ==
  "web_mercator"`, and no auth/token fields are set.
- [ ] `test_kakao_query_url_build` — the source's URL template / builder fills
  correctly for a sample `(lat, lon, radius, limit)`: produces
  `https://rv.map.kakao.com/roadview-search/v2/nodes?PX=126.9779&PY=37.5663&RAD=100&PAGE_SIZE=100&INPUT=wgs&TYPE=w&SERVICE=glpano`
  (assert host, path, and each query param). Reuse / mirror
  `streetlevel.kakao.api.build_find_panoramas_request_url`.
- [ ] `test_kakao_decode_coverage` — decoding `nodes_seoul.json` yields 3
  coverage points; each has a numeric `panoid`, and `lat`/`lon` within the
  Seoul bbox (`126.5 < lon < 127.5`, `37.4 < lat < 37.7`); presence is True.
- [ ] `test_kakao_decode_empty` — decoding `nodes_empty.json` (`cnt: 0`) yields
  zero coverage points and presence is False (this is the "checked-empty"
  case → raster value `0`).
- [ ] `test_kakao_decode_uses_wgs_not_wcong` — the decoded point coordinates
  equal the `wgsx`/`wgsy` values from the fixture, **not** `wcongx`/`wcongy`
  or `wtmx`/`wtmy` (guards against picking the wrong coordinate field).
- [ ] `test_kakao_decode_date` — a decoded record carries a capture date
  derived from the panorama (`img_path` timestamp suffix → e.g.
  `2015-09-30`), for the optional date layer.
- [ ] `test_kakao_presence_rule` — a `has_coverage`-style predicate returns
  `True` for `nodes_seoul.json` and `False` for `nodes_empty.json` (this is
  what the two-pass `extent.discover_coverage_tiles` will call).

- Fixtures: `tests/fixtures/kakao/nodes_seoul.json`,
  `tests/fixtures/kakao/nodes_empty.json` (small recorded samples; trim
  `streetList` to ≤3 entries).

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind:** NEW kind `streetlevel` — `src/coverage_acquisition/source_kinds/streetlevel.py`.
  This is a **separate foundation PR that must merge first** (`docs/PLAN.md` §4
  item 3 already names `streetlevel` as a seed kind). The kakao provider PR
  depends on it and must not itself add the source kind. Design of the
  `streetlevel` kind (foundation work, summarised here so this subplan is
  self-contained):
  - It is a **point-query / JSON** kind, not a `{z}/{x}/{y}` tile kind. The
    fetch loop calls a per-source URL builder with a query point (and radius),
    fetches via `polite.polite_fetch`, and the kind's `decode_*` handler walks
    the JSON into `pano_records` (the same `DecodeResult.pano_records` channel
    `coverage_json` already uses — see `source_kinds/coverage_json.py`).
  - For kakao the decode handler: `json.loads` the payload, read
    `street_view.cnt`; if `0` → `is_empty=True`, `pano_count=0`; else map each
    `streetList` entry to a pano record with `provider="kakao"`,
    `panoid=id`, `lat=wgsy`, `lon=wgsx`, `timestamp` from the panorama date,
    plus `fetched_at`. The kind should be generic enough that `naver` (also
    `rv.map` / streetlevel-native) can reuse it later — keep the kakao-specific
    JSON walk behind a small per-source option (e.g.
    `options={"streetlevel_module": "kakao"}`) or a thin decoder dispatch.
  - Keep `streetlevel`'s own `requests`-based networking **out** of the hot
    loop; only use `streetlevel.kakao.api.build_find_panoramas_request_url` and
    `streetlevel.kakao.parse.parse_panoramas` (pure functions). Fetching is the
    project's job via `polite_fetch`.
  - The two-pass discovery for a point-query provider sweeps a **grid of query
    points** (not tiles): generate WGS84 points over the region spaced
    `~140 m` (`RAD=100` disks tiling with overlap), query each, union the
    returned panorama coordinates. The `extent` module / runner will need a
    point-grid mode for `streetlevel` sources; flag this to the foundation
    owner if `extent.discover_coverage_tiles` is tile-only today.

- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/kakao.py` defining `PROVIDER`
  (`ProviderDefinition`) and calling `register_provider(PROVIDER)`:
  - `key="kakao"`, `output_namespace="kakao_roadview_coverage"`,
    `run_label_prefix="kakao_roadview_coverage"`,
    `coordinate_scheme="web_mercator"`.
  - `default_display_zoom=14` (z14 analysis grid; point-query provider has no
    real "display zoom", this is just the nominal value).
  - One `SourceDefinition`:
    - `id="kakao_roadview_nodes"`, `kind="streetlevel"`.
    - `template="https://rv.map.kakao.com/roadview-search/v2/nodes?PX={lon}&PY={lat}&RAD={radius}&PAGE_SIZE={limit}&INPUT=wgs&TYPE=w&SERVICE=glpano"`
      (the streetlevel kind fills `{lon}/{lat}/{radius}/{limit}` per query
      point; if the foundation kind prefers building the URL via
      `streetlevel.kakao.api`, keep `template` as documentation and select the
      builder via `options`).
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "application/json", "Referer": "https://map.kakao.com/"}`.
    - `expect_content_type_prefix="application/json"`.
    - `storage_subdir="nodes"`.
    - `options={"streetlevel_module": "kakao", "search_radius_m": "100",
      "page_size": "100", "grid_spacing_m": "140"}`.
    - `notes`: "Kakao Road View coverage via the rv.map.kakao.com radius-search
      JSON API. Point-query, not tiles; presence = street_view.cnt > 0."
  - `area_presets={"seoul_city_hall_bbox": BoundingBox(...)}` — see pilot bbox
    below. Declare the `BoundingBox` inline in the module (do **not** add to
    `providers/_presets.py` — keep that file conflict-free, per its docstring).
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] Module docstring: record the ToS caveat — fetch only from
  `rv.map.kakao.com` (no robots.txt, allowed); never crawl `map.kakao.com`
  (which has `Disallow: /`). Coverage is South Korea only. No auth.
- [ ] Pilot fetch: bbox `126.960 37.560 126.990 37.580`
  (`Seoul — City Hall / Jung-gu`, ~3.0 km × 2.2 km). Sweep a ~140 m point grid
  over this bbox, expect coverage points densely along the street network
  (City Hall, Sejong-daero, Cheonggyecheon area).
- [ ] Rasterize the pilot area to a z14 COG (`rasterize.rasterize_geometries_to_cog`,
  points buffered by ~1 cell); sanity-check: covered pixels land on Seoul
  streets/land, not in water, CRS EPSG:3857, `uint8`.
- [ ] Two-pass full extent: pass-1 discovery region = South Korea bbox
  `124.5 33.0 131.9 38.7` swept as a **point grid** (no Korean coverage exists
  outside this). Recommended discovery grid spacing for pass-1: coarse
  (e.g. one query point per z11 tile, ~15 km) with `RAD=100` is **not**
  sufficient to detect all coverage — instead use a moderate grid (~1–2 km
  spacing, i.e. roughly the z14 cell size) so any covered z14 cell is sampled.
  Discovery zoom equivalent: **z14-aligned point grid** (one query point per
  z14 cell centroid over the Korea bbox); cells with `cnt > 0` proceed to a
  dense `RAD=100` / `~140 m` sweep for the final point cloud. (If a true
  two-zoom scheme is wanted, pass-1 = z11 point grid as a fast land/region
  filter, pass-2 = z14 dense sweep within hit regions; the implementer/foundation
  owner picks based on the `extent` module's point-grid support.)
- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T1"`,
  `source_endpoint="https://rv.map.kakao.com/roadview-search/v2/nodes"`,
  `tos_notes` per §2). Update the inventory status for `kakao`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.kakao` imports and
  self-registers in `PROVIDERS`; CI smoke test (import/register/dry-run) passes.
- Pilot fetch returns non-empty JSON for Seoul; decoding yields coverage points
  on known Seoul streets (lands on roads/land, not in the Han River / sea).
- The decoded point cloud uses WGS84 (`wgsx`/`wgsy`), not WCongnamul.
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0, extent within
  the South Korea bbox.
- Empty (`cnt: 0`) queries are handled as checked-empty (raster value `0`),
  not errors.
- Fetches via `polite.polite_fetch` with a descriptive User-Agent; no calls to
  `streetlevel`'s own networking in the fetch loop; ToS caveats
  (`rv.map.kakao.com` only, never `map.kakao.com`) documented in the module
  docstring.

## 6. Status log

- `2026-05-20` scout: drafted. Confirmed live against `streetlevel` 0.12.7 and
  the `rv.map.kakao.com` API — coverage is a point-query JSON API (radius
  search), South Korea only, no auth, custom User-Agent accepted. Key open
  items below.
- `2026-05-20` approval: pending — awaiting user review.
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **`streetlevel` source kind is a hard dependency.** This provider needs the
   new `streetlevel` source kind (point-query / JSON, not tile-based) to land
   first as a foundation PR. Confirm that foundation PR is scheduled before the
   T1 batch, and that the `extent`/runner two-pass machinery will support a
   **point-grid sweep** (current `extent.discover_coverage_tiles` and the
   `runners` job builder are tile-`{z}/{x}/{y}` oriented). This affects `naver`,
   `mapy`, `ja360` too — all four T1 streetlevel providers are point-query.
2. **Discovery grid spacing.** Korea bbox swept at ~140 m spacing is ~hundreds
   of thousands of query points (heavy). Recommended approach: coarse z11-ish
   point-grid pass-1 to localise covered regions, then dense `RAD=100` sweep
   only there. Confirm the extent module should implement this two-tier
   point-grid, or whether a coarser binary-presence accuracy is acceptable.
3. **Date layer.** `KakaoPanorama.date` (precise, from `img_path`) is available
   per pano — should the optional `*_year.tif` date layer be produced for
   `kakao` now, or deferred? The data is essentially free to collect alongside
   coverage.
4. **Historical panoramas (`past` field).** Null in all sampled responses;
   ignored for binary presence. Confirm that is acceptable (it is, for a
   presence raster).

# [T1] Provider: Mapy.com / Mapy.cz (`mapy`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Mapy.com (formerly Mapy.cz) is the dominant Czech web-mapping service, operated
by Seznam.cz. It offers a "Panorama" street-level imagery layer with extensive
coverage of the Czech Republic (and effectively only the Czech Republic — see
§2). Imagery is a mix of Seznam's own car-captured panoramas and, for 2020+
coverage, Cyclomedia panoramas. It is in scope as an active provider that is
natively supported by the `streetlevel` Python library (already an installed
dependency), making it a Tier-1 "streetlevel-native" provider. There is no tile
or vector coverage layer to scrape; coverage is discovered by point queries
against Mapy's FRPC panorama API through `streetlevel.mapy`.

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:**
  - Homepage: `https://mapy.com/` (also `https://en.mapy.cz/`).
  - Panorama viewer: open a pano permalink, e.g.
    `https://en.mapy.cz/zakladni?pano=1&pid=<panoid>&...` (see
    `streetlevel.mapy.util.build_permalink`).
  - Tier: **T1** (streetlevel-native).

- **Coverage endpoint(s):** Mapy exposes **no tile-based coverage layer** (no
  raster tiles, no MVT, no per-tile coverage JSON). Coverage is queried point by
  point through Seznam's FRPC (Fast Remote Procedure Call, a binary RPC) API.
  All access is wrapped by `streetlevel.mapy`; do **not** call the endpoint
  directly.
  - Endpoint: `https://pro.mapy.cz/panorpc` (FRPC; `pyfrpc.FrpcClient`).
  - Method used for discovery: FRPC procedure **`getbest`**, args
    `(lon, lat, radius, options)` — finds the best panorama within `radius`
    metres of a point. Returns `status == 200` with a `panInfo` dict when
    imagery exists, or `status != 200` when none exists nearby.
  - Other procedures (`detail`, `getneighbours`) exist for metadata/links but
    are **not needed** for coverage presence; `getneighbours` may optionally be
    used later to densify discovered coverage (see Known quirks).
  - Required header (set automatically by `streetlevel`):
    `Referer: https://en.mapy.cz/` — without it, Cyclomedia (2020+) panoramas
    are not returned.
  - The library entry point is `streetlevel.mapy.find_panorama(lat, lon,
    radius=100.0, year=None, links=True, historical=True)`:
    - `links` / `historical` each trigger **extra** network requests. For
      coverage discovery they MUST be set to `links=False, historical=False` to
      keep one request per probe point.

- **Coordinate scheme:** `web_mercator` for the project's z14 grid. The
  provider API itself takes/returns plain **WGS84 lat/lon** (EPSG:4326). No
  custom datum shift (unlike Baidu/Yandex). Probe points are generated as
  WGS84 lat/lon; presence results are WGS84 lat/lon points that get burned onto
  the standard web-mercator z14 raster.

- **Zoom range / tile size / response format:** Not tile-based. There is no
  "zoom" for coverage. The "zoom" levels in `streetlevel` (`max_zoom` 0/1/2)
  refer to *panorama image* resolution, which this project does NOT download.
  - Response format: a Python dict decoded from FRPC by `pyfrpc`. A successful
    `getbest` returns `{"status": 200, "result": {"panInfo": {...}}}`.
    `streetlevel.mapy.parse_getbest_response` turns `panInfo` into a
    `MapyPanorama` dataclass.
  - `MapyPanorama` fields used by this project:
    `id` (int pano ID), `lat`, `lon` (WGS84, the *actual* pano location, which
    may differ slightly from the probe point), `date` (`datetime`, tz-aware,
    UTC), `provider` (str, e.g. `"cyclomedia"` or a Seznam label), `elevation`.

- **Auth:** **none.** No API key, token, or cookie. The only required header is
  `Referer: https://en.mapy.cz/`, which `streetlevel` sets internally. **No
  `.env` key is needed** for `mapy`.

- **Presence rule:** For each probe point `(lat, lon)`, call
  `find_panorama(lat, lon, radius=R, links=False, historical=False)`:
  - returns a `MapyPanorama` → imagery is present at that point; record the
    returned pano (`id`, `lat`, `lon`, `date`, `provider`) as a coverage point.
  - returns `None` → no imagery within `radius` metres of that point.
  The z14 raster cell is marked **covered (1)** if any discovered pano falls in
  it, **checked-empty (0)** for probed cells with no pano, **nodata (255)**
  for cells never probed. Discovered panos are deduplicated by pano `id`.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://en.mapy.cz/robots.txt` responded `200` with an **empty body** (no
    `Disallow` rules served). `https://pro.mapy.cz/robots.txt` returns
    `405 Not Allowed` (the FRPC host is not a normal web host).
  - The FRPC panorama API is undocumented/unofficial; `streetlevel` is the
    de-facto community client. Mapy's general Terms of Use restrict bulk reuse
    of content; this project stores only **coverage presence** (point
    locations + dates), not panorama imagery, which is the lighter-touch use.
    **Record this caveat in the provider module docstring** and keep probing
    polite.
  - No published rate limit. Observed latency in scouting: a cold `getbest`
    call ~0.6–2.6 s; treat the API as slow and rate-limited in practice. Use a
    conservative throttle (target ≈ **1 request/second**, with retry/backoff).
  - **Polite-scraper caveat:** `streetlevel.mapy` uses its own `pyfrpc` client
    and does NOT route through this project's `polite.polite_fetch`. The
    `streetlevel` source kind (foundation) must therefore implement throttle +
    retry/backoff itself around each `find_panorama` call (see §4).

- **Known quirks / gotchas:**
  - **No tile endpoint** — this is the defining quirk. The provider cannot use
    `raster` / `vector_mvt` / `coverage_json` kinds. It needs the new
    `streetlevel` source kind, which discovers coverage by **probing a grid of
    points** instead of fetching tiles.
  - **Probe grid spacing.** z14 cells are ~9.5 m at the equator and ~6.1 m at
    Czech latitude (~49.8° N: cos49.8°≈0.646 → ~9.5×0.646 ≈ 6.1 m). A single
    z14 cell is far smaller than a sensible probe radius. Probe on a **coarser
    grid** (e.g. one probe every ~150–250 m) with `radius` ≈ half the grid
    spacing so probes tile the area without large gaps; each returned pano is
    then burned into whatever z14 cell its true `lat/lon` lands in. Discovery
    is two-pass (§4): a coarse pass finds populated regions, a finer pass
    densifies them. Document the chosen spacing/radius in the module.
  - **Pano location ≠ probe location.** `getbest` returns the nearest pano,
    whose `lat/lon` can be up to `radius` metres from the probe point. Always
    rasterize the **returned** `lat/lon`, never the probe point.
  - **Coverage is Czech-only in practice.** Scouting confirmed panos in Prague,
    Brno, Ostrava; **no** panos in Bratislava (SK), Vienna (AT), or the High
    Tatras (SK). Treat the discovery region as the Czech Republic bbox; do not
    waste probes outside it.
  - **`provider` field varies.** 2020+ panos report `provider == "cyclomedia"`;
    older ones report a Seznam label. Both count as Mapy coverage; keep the
    `provider` string in the intermediate data for provenance only.
  - **Dates are exposed** (`MapyPanorama.date`, tz-aware UTC `datetime`), and
    `historical=True` returns prior-year panos at the same spot via the
    `panInfo["timeline"]` years. The optional `*_year.tif` date layer can use
    `date.year` of the most-recent pano per cell. The base coverage scrape uses
    `historical=False` (one request/probe); a date layer, if built, is a
    follow-up that may re-probe with `historical=True`.
  - **FRPC dependency.** `streetlevel.mapy` pulls in `pyfrpc`; it is already
    installed transitively via `streetlevel`. No extra dependency to add.
  - **`getbest` arg order.** `streetlevel`'s `find_panorama` takes `(lat, lon)`
    but the underlying FRPC call passes `(lon, lat, radius, options)` — always
    go through `streetlevel`, never hand-build the FRPC args.
  - `find_panorama` raises on network/transport errors (it does not return
    `None` for those); the source kind must catch transport exceptions and
    retry, distinct from a legitimate `None` (no coverage).

## 3. Test plan (write these FIRST — red before green)

Unit tests must not hit the network. `streetlevel.mapy.find_panorama` is
**monkeypatched/mocked** to return canned `MapyPanorama` objects or `None`, and
canned FRPC dicts are stored as fixtures.

- [ ] `test_mapy_registers` — importing `coverage_acquisition.providers.mapy`
      registers `"mapy"` in `PROVIDERS`; `get_provider("mapy")` returns a
      `ProviderDefinition` whose `key == "mapy"` and that has ≥1 source.
- [ ] `test_mapy_source_kind_is_streetlevel` — the provider's single
      `SourceDefinition.kind == "streetlevel"` and its `options` name the
      streetlevel client (`options["streetlevel_module"] == "mapy"`).
- [ ] `test_mapy_coordinate_scheme` — `PROVIDER.coordinate_scheme ==
      "web_mercator"` (probe grid + raster are standard web mercator).
- [ ] `test_mapy_probe_grid_build` — given the pilot bbox and the configured
      probe spacing, the grid generator yields the expected count and the
      expected first/last `(lat, lon)` probe points (deterministic, no network).
- [ ] `test_mapy_decode_present` — feeding the `streetlevel` source-kind
      decoder a mocked `find_panorama` that returns a `MapyPanorama`
      (`id=104046742`, `lat=50.08756`, `lon=14.42158`, `date` 2023-08-11,
      `provider="cyclomedia"`) yields a `DecodeResult` with `pano_count == 1`
      and one `pano_records` entry carrying `panoid`, `lat`, `lon`,
      `timestamp` (the ISO date), and `provider`.
- [ ] `test_mapy_decode_absent` — a mocked `find_panorama` returning `None`
      yields `DecodeResult` with `pano_count == 0`, `is_empty == True`, and no
      `pano_records`.
- [ ] `test_mapy_decode_uses_returned_location` — when the mocked pano's
      `lat/lon` differs from the probe point, the recorded coverage point uses
      the **pano's** `lat/lon`, not the probe point's.
- [ ] `test_mapy_dedup_by_panoid` — two probes that resolve to the same pano
      `id` collapse to a single coverage record.
- [ ] `test_mapy_no_auth_required` — the provider needs no token: the
      `SourceDefinition` has no `token_query_param` and no `.env` key is
      referenced.
- [ ] `test_mapy_transport_error_retries` — when the mocked `find_panorama`
      raises a transport error then succeeds, the source kind retries and does
      not mark the cell empty (retry/backoff path, distinct from `None`).
- Fixtures under `tests/fixtures/mapy/`:
  - `getbest_present.json` — a recorded `getbest` response dict (status 200,
    `result.panInfo`) for the Prague pilot point, used to build a real
    `MapyPanorama` via `parse_getbest_response` without the network.
  - `getbest_absent.json` — a recorded `getbest` response with `status != 200`
    (ocean point), decoding to `None`.
  - Record these once with a tiny throwaway script during implementation
    (`streetlevel.mapy.api.MapyApi().getbest(...)`), then commit them small.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: NEW kind `streetlevel`** — `src/coverage_acquisition/
      source_kinds/streetlevel.py`. This is a **separate foundation PR that
      must merge first** (PLAN §4 item 3 already lists `streetlevel` as a
      seeded kind). The `mapy` provider PR depends on it and must not create or
      edit it. The `streetlevel` kind differs from the tile-based kinds:
  - It does **not** fetch HTTP tiles. Instead it consumes a **probe grid** of
    `(lat, lon)` points (generated from the requested bbox + a probe-spacing
    option) and, for each point, calls the configured `streetlevel`
    sub-module's `find_panorama(lat, lon, radius, links=False,
    historical=False)`.
  - It implements its **own throttle + retry/backoff** around each call
    (because `streetlevel` bypasses `polite.polite_fetch`): conservative
    ≈1 req/s default, exponential backoff on transport errors, a descriptive
    process identity. Per-provider rate is configurable via `SourceDefinition.
    options`.
  - It writes discovered panoramas to `data/intermediate/<key>/` as the
    re-rasterizable point source of truth (GeoParquet), mirroring how the
    `coverage_json` kind emits `pano_records`. `DecodeResult` fields reused:
    `pano_count`, `pano_records`, `is_empty`.
  - It is driven by the existing two-pass extent runner: pass-1 = coarse probe
    grid over the discovery region; pass-2 = fine probe grid only over cells
    where pass-1 found panos.
  - The kind is selected by `SourceDefinition.kind == "streetlevel"` and the
    `streetlevel` sub-module name comes from `options["streetlevel_module"]`
    (here `"mapy"`), so the same kind serves `kakao`, `naver`, `ja360`.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/mapy.py` defining `PROVIDER` as a
      `ProviderDefinition` and calling `register_provider(PROVIDER)`. Shape:
  - `key="mapy"`, `output_namespace="mapy_panorama_points"`,
    `run_label_prefix="mapy_panorama"`, `coordinate_scheme="web_mercator"`,
    `default_display_zoom=14`.
  - One `SourceDefinition`:
    - `id="mapy_panorama_streetlevel"`, `kind="streetlevel"`,
    - `template=""` (no URL template — the streetlevel kind ignores it; if the
      `SourceDefinition` requires a non-empty template, set a documentary
      placeholder such as `"streetlevel://mapy/find_panorama"`),
    - `options={"streetlevel_module": "mapy", "probe_radius_m": "125",
      "probe_spacing_m": "200", "requests_per_second": "1",
      "links": "false", "historical": "false"}`,
    - `storage_subdir="panorama_points"`,
    - `notes` describing the FRPC `getbest` discovery mechanism and the
      Czech-only extent.
  - `area_presets`: declare the pilot bbox inline in this module (do **not**
    add to `_presets.py`).
  - Module docstring: record the ToS caveat (undocumented FRPC API; only
    coverage presence + dates are stored, never imagery) and the
    `Referer: https://en.mapy.cz/` requirement.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `14.40 50.075 14.44 50.095` (**Prague — Old Town
      / city centre**, ~2.8 km × 2.2 km). Expect dense coverage on the central
      street network. Scouting confirmed a pano at `(50.08756, 14.42158)`,
      pano id `104046742`. Use `probe_spacing_m≈200`, `probe_radius_m≈125`.
- [ ] Rasterize the pilot area to a z14 COG (EPSG:3857, `uint8`,
      1=covered / 0=checked-empty / 255=nodata); buffer isolated points by
      ~1 cell; sanity-check that covered pixels land on Prague streets.
- [ ] **Two-pass full extent:** pass-1 discovery region = **Czech Republic
      bbox** `12.09 48.55 18.86 51.06`, coarse probe grid at spacing
      ≈ 1000–2000 m (the "discovery zoom" equivalent — there is no tile zoom,
      so express discovery as a coarse probe spacing, not a `z`). Pass-2:
      re-probe at spacing ≈ 150–250 m only in the cells where pass-1 found
      panos. Do **not** probe outside the Czech bbox (no coverage there).
- [ ] Update the STAC item for `mapy` (extent = discovered coverage envelope,
      scrape date, tier T1, source endpoint `pro.mapy.cz/panorpc`, ToS notes).
      Update the inventory status for `mapy`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.mapy` imports and
  self-registers (`"mapy"` in `PROVIDERS`); CI smoke test (import + register +
  dry-run) passes.
- Pilot probe run resolves panoramas in central Prague; decoded coverage
  points land on roads/land in the Czech Republic (not ocean, not outside CZ).
- z14 COG is valid: CRS EPSG:3857, `uint8`, covered pixels > 0, internal
  overviews present.
- The `streetlevel` source kind throttles probe calls (≈1 req/s) with
  retry/backoff and a descriptive process identity; no use of bare
  `urllib`/`requests` for the FRPC calls (all via `streetlevel.mapy`).
- ToS caveats documented in the `mapy.py` module docstring (undocumented FRPC
  API; only coverage presence/dates stored, not imagery; `Referer` header
  requirement).

## 6. Status log

- `2026-05-20` scout: drafted. Confirmed against installed `streetlevel`
  `0.12.7`. `streetlevel.mapy.find_panorama` works live (Prague pano
  `104046742`, provider `cyclomedia`, date 2023-08-11); `None` returned for an
  ocean point; `historical=True` returned 4 prior-year panos at the Prague
  spot; coverage confirmed Czech-only (Prague/Brno/Ostrava yes; Bratislava/
  Vienna/High Tatras no). No tile/MVT/JSON coverage layer exists — provider
  requires the new `streetlevel` source kind, which discovers coverage by
  probing a grid of points rather than fetching tiles. No auth/`.env` key
  needed. `en.mapy.cz/robots.txt` served an empty body (no Disallow rules).
- `2026-05-20` approval: pending — awaiting user review.
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **Probe-grid spacing/radius.** Proposed defaults: full-extent pass-1 spacing
   ≈ 1–2 km, pass-2 spacing ≈ 150–250 m, `radius` ≈ half the spacing. Finer =
   more complete but slower at ≈1 req/s (a 200 m grid over all of Czechia is on
   the order of ~2M probes ≈ many hours). The reviewer should confirm the
   accuracy/runtime trade-off, or approve a coarser final grid (e.g. 300–400 m)
   if a slightly thinner z14 raster is acceptable.
2. **`streetlevel` source kind is a hard prerequisite.** This provider cannot
   ship until the foundation `streetlevel` kind (probe-grid driver +
   self-throttling, since `streetlevel` bypasses `polite_fetch`) is merged.
   Confirm that foundation PR is scheduled before the `mapy` provider PR.
3. **Date layer.** Mapy exposes per-pano capture dates and a historical
   timeline. Recommend deferring the optional `mapy_year.tif` date layer to a
   follow-up (it needs `historical=True`, doubling+ the request count).
   Confirm the base coverage scrape ships first with `historical=False`.
4. **Densification via `getneighbours`.** As an alternative/supplement to a
   fine probe grid, discovered panos could be walked via `get_links` /
   `getneighbours` to follow the capture path. This is more efficient but more
   complex; flagged as a possible optimisation, not part of this subplan.

# [T2] Provider: Mapilio (`mapilio`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Mapilio is a global crowdsourced street-level imagery platform, operated from
the United Kingdom (with an engineering presence in Turkey). Contributors upload
imagery captured from smartphones, action cameras, and 360° rigs; Mapilio runs
ML feature extraction over it and the platform claims data in 83+ countries. It
is a Mapillary-style open platform: a public web map viewer at
`https://mapilio.com/app`, an open SDK (`mapilio-kit`) and documentation on
GitHub (`https://github.com/mapilio`), and — most importantly for this project —
a public **Mapbox Vector Tile (MVT)** coverage layer served from a GeoServer
host with **no authentication**. It is in scope as an active, scrapable T2
provider: not defunct, not a re-hoster, not paid-B2B. This project fetches the
MVT coverage layer and rasterizes the sequence lines onto the shared z14 grid —
the same `kind="vector_mvt"` pattern already used by `mapillary` and the
geometry-MVT path used by `kartaview`. Only coverage presence is stored; no
street-level imagery is downloaded.

## 2. Research findings (filled by provider-scout)

### Verdict: Mapilio serves a `vector_mvt` coverage layer (use existing kind)

The Mapilio web viewer (`https://mapilio.com/app`, a Next.js SPA using
MapLibre/Mapbox GL) draws its coverage from an **MVT vector-tile source**, not a
rendered raster overlay and not a custom grid. Evidence gathered from the live
viewer JS bundle and by probing the tile host directly.

- **Homepage / public viewer URL:**
  - Homepage: `https://mapilio.com/`
  - Public web map viewer: `https://mapilio.com/app`
  - Developer docs org / open SDK: `https://github.com/mapilio` (notably
    `mapilio-kit`, `MapSyncer`, `iD` fork). A docs site is advertised at
    `https://docs.mapilio.com/` but at scout time that host returns
    `{"detail":"Not Found"}` (it is an API host, not a rendered docs site) and
    the `mapilio/docs` GitHub repo is empty — **the tile endpoint is therefore
    undocumented**; it was reverse-engineered from the viewer bundle.
  - Tier: **T2**.

- **How the coverage layer was identified.** The viewer is a Next.js SPA. The
  map code lives in the chunk bundle
  `https://mapilio.com/_next/static/chunks/6225-<hash>.js`
  (`6225-4bbde418ef19af98.js` at scout time). It registers a MapboxGL **vector**
  source and three coverage sub-layers:

  ```js
  map.addSource("mapilio-tiles", {
    type: "vector",
    tiles: ["https://geo.mapilio.com/map/{x}/{y}/{z}"],
  });
  map.addLayer({ id:"map-road-layer",    type:"line",   source:"mapilio-tiles",
                 "source-layer":"map_roads_line",  minzoom:6,  maxzoom:23 });
  map.addLayer({ id:"map-point-wrapper", type:"circle", source:"mapilio-tiles",
                 "source-layer":"world_img_cache", minzoom:0,  maxzoom:6  });
  map.addLayer({ id:"map-point-layer",   type:"circle", source:"mapilio-tiles",
                 "source-layer":"map_points",      minzoom:15, maxzoom:23 });
  ```

  A second, separate source `mapilio-object-tiles`
  (`https://geo.mapilio.com/features/{x}/{y}/{z}`, `source-layer`
  `map_features`) carries ML-detected map objects (traffic signs, etc.) — **not
  imagery coverage; ignore it.** The coverage footprint is the
  `mapilio-tiles` source.

- **Coverage endpoint(s):**
  - **Coverage MVT (use this):**
    `https://geo.mapilio.com/map/{x}/{y}/{z}`
  - Object-detection MVT (reference only, not coverage):
    `https://geo.mapilio.com/features/{x}/{y}/{z}`
  - **HTTP method:** `GET`.
  - **URL path order is `{x}/{y}/{z}`** — x first, then y, then z. This is
    **not** the usual `{z}/{x}/{y}` token order. Verified live: the Berlin z14
    tile is `https://geo.mapilio.com/map/8802/5373/14` (returns a 436 KB MVT),
    whereas `https://geo.mapilio.com/map/14/8802/5373` (z/x/y order) returns
    **HTTP 400**. The `SourceDefinition.template` must therefore be
    `https://geo.mapilio.com/map/{x}/{y}/{z}`.
  - **Query params:** none. No `?access_token`, no `?apikey`. A bare `GET`
    returns the tile.
  - **Required headers:** none are enforced. The tile returns `200` with and
    without a `Referer`/`User-Agent`. Still send a descriptive `User-Agent`,
    `Referer: https://mapilio.com/`, and
    `Accept: application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1`
    for politeness and viewer-consistency (mirroring `mapillary.py`).
  - **Host:** single host `geo.mapilio.com` (a GeoServer / Jetty instance —
    `SERVLET: dispatcher`, GeoServer error pages). No host sharding.

- **Coordinate scheme:** **`web_mercator`** — standard EPSG:3857 / WGS84
  spherical Mercator XYZ, 4096-unit MVT extent, the same scheme as `mapillary`
  and `kartaview`. Verified by computing standard web-mercator tile indices for
  Istanbul / Berlin and getting non-empty MVT tiles, and for the Atlantic Ocean
  / open-water indices getting empty tiles. No custom datum.
  - Note the **path order quirk** above: web-mercator tile *enumeration* still
    produces ordinary integer `z/x/y`; only the URL string places them as
    `{x}/{y}/{z}`.

- **Zoom range / tile size / response format:**
  - **MVT extent:** 4096 (standard). Tiles are Mapbox Vector Tiles.
  - **Response Content-Type:** `application/vnd.mapbox-vector-tile`.
  - **Native zoom range:** the `map_roads_line` coverage layer renders from
    **z6 to z23** (`minzoom:6, maxzoom:23` in the viewer). Probed live: Berlin
    returns non-empty `map_roads_line` tiles at z6, z8, z10, z12, and z14.
    z14 — the project's analysis zoom — works everywhere coverage exists.
  - **Important volume note:** `map_roads_line` carries **full-resolution
    sequence geometry at every zoom** (it is not generalized for low zooms). A
    single Berlin tile is ~436 KB at z14, ~1 MB at z12, ~2 MB at z10, ~14 MB at
    z8, ~16 MB at z6. Coarse-zoom tiles are large; pick the discovery zoom
    accordingly (see §4 — z10 recommended, not z6/z8).
  - **`world_img_cache`** (z0–6) is an overview-cluster sub-layer; `map_points`
    (z15–23) is individual image points. Neither is needed — `map_roads_line`
    is the contiguous coverage footprint and the only layer this project
    decodes.

- **Auth:** **none.** No API key, token, cookie, or signed URL. Confirmed by
  direct probing (`200` with no query string and no headers). **No `.env` key
  is needed** for `mapilio`. (`mapilio-kit`'s upload SDK uses an OAuth login,
  but that is for *uploading*; the read-only coverage MVT tiles are public.)

- **Presence rule:** decode each MVT tile and read its `map_roads_line` layer.
  - **Coverage present** ⇔ the tile decodes to **≥ 1 feature** in the
    `map_roads_line` layer (LineString sequence geometries). The existing
    `vector_mvt` decoder already yields `feature_count` / `record_count` and
    `layer_counts_json`; presence is `feature_count > 0`.
  - **No coverage** ⇔ the tile is a **zero-byte body** (`HTTP 200`,
    `content-length: 0`, content-type still
    `application/vnd.mapbox-vector-tile`). Verified live for the Atlantic Ocean,
    New York City (Mapilio has no coverage there at scout time), and Izmir.
    There is **no 404 and no 204** for in-grid empties; an *out-of-grid* index
    (e.g. `map/99999/99999/14`) returns **HTTP 400**.
  - z14 raster cell mapping (standard `vector_mvt` → `rasterize.py` flow): a
    tile with `map_roads_line` features → the cells the lines pass through are
    **covered (1)**; a probed tile with zero features → **checked-empty (0)**;
    never-probed cells → **nodata (255)**. Isolated/short line geometries are
    buffered by ~1 cell per the project's vector→raster rule.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://geo.mapilio.com/robots.txt` → **HTTP 404** (GeoServer serves no
    robots.txt). `https://mapilio.com/robots.txt` → the Next.js SPA returns its
    app shell, not a real robots file (no `Disallow` rules served). With no
    robots.txt present, `robots_allows()` returns `True` — fetching is not
    disallowed. Re-confirm both during implementation and record in the status
    log.
  - The `geo.mapilio.com/map` tile endpoint is **undocumented** (the
    advertised `docs.mapilio.com` is down / the `mapilio/docs` repo is empty).
    Mapilio is, however, an explicitly *open* crowdsourced platform with a
    public viewer and open SDK; the data model is contributor-sourced imagery
    meant to be shared. This project stores only a **binary coverage raster**
    (presence, not imagery, not the rendered tiles). **Record this caveat in
    the provider module docstring** (undocumented endpoint; only a coverage
    raster is published) and keep the scrape polite and small. If Mapilio
    publishes formal API terms later, revisit.
  - No published rate limit. GeoServer/Jetty host; tiles are not obviously
    CDN-cached. Use a conservative per-host throttle (≈ 3–4 req/s;
    `PolitePolicy(min_interval_seconds ≈ 0.25–0.3)`) with the shared
    retry/backoff. Because coarse tiles are large (multi-MB), keep concurrency
    at 1 and prefer the recommended discovery zoom.

- **Known quirks / gotchas:**
  - **Non-standard URL path order `{x}/{y}/{z}`** (x first, then y, then z).
    The `template` must be `https://geo.mapilio.com/map/{x}/{y}/{z}`. The
    `{z}/{x}/{y}` order returns HTTP 400. This is the single biggest gotcha and
    is pinned by a dedicated URL-build test (§3).
  - **Empty tile = zero-byte HTTP 200**, not a 404/204. The `vector_mvt`
    decoder must treat a zero-byte payload as `feature_count == 0` /
    `is_empty == True` and not raise. See §4 for the small decoder
    robustness check this requires.
  - **Out-of-grid index = HTTP 400.** A web-mercator bbox sweep stays within
    `0 ≤ x,y < 2^z`, so this should not occur in normal operation; the runner's
    `skip_404` does not cover 400 — the fetch loop should treat a 400 on a
    valid-range tile as a skip-with-warning, not a hard stop. (In-range tiles
    never 400 in scout probing.)
  - **`map_roads_line` is full-resolution at all zooms** — coarse-zoom tiles
    are multi-MB (z6 ≈ 16 MB, z8 ≈ 14 MB, z10 ≈ 2 MB). Do **not** run
    discovery at z6/z8; use z10 (≈ 2 MB/tile, manageable). The MVT decoder
    handles large tiles fine; the cost is bandwidth/time.
  - **Two MVT sources — use `mapilio-tiles` (`/map/`), not
    `mapilio-object-tiles` (`/features/`).** The `/features/` source is
    ML-detected map objects, not imagery coverage.
  - **Coverage is global but sparse/uneven.** Mapilio claims 83+ countries but
    actual coverage is contributor-driven and patchy. Scout probing found dense
    coverage in **Istanbul** and **Berlin**, none in New York or Izmir at scout
    time. The two-pass discovery sweep is essential — do not assume any city
    has coverage without a discovery pass. The pilot city below (Istanbul) was
    confirmed live.
  - **No capture dates in the coverage layer.** `map_roads_line` features carry
    a `fov` property (`360` vs other = panoramic vs flat) and sequence IDs, but
    the coverage MVT is a presence layer — a `mapilio_year.tif` date layer is
    **out of scope** for this provider (per-image dates would require the
    separate image-metadata API; defer as a possible follow-up).
  - **GeoServer host.** `geo.mapilio.com` is a GeoServer instance; it also
    exposes a WFS endpoint (`/mapilio/ows?service=WFS...`) used by the viewer
    for click-to-query. The WFS path is **not** needed — the `/map/` MVT tiles
    are the coverage source. (WFS is noted only as a fallback if the MVT
    endpoint ever changes.)

## 3. Test plan (write these FIRST — red before green)

Unit tests must not hit the network (`docs/PLAN.md` §12). Decode small recorded
MVT fixtures under `tests/fixtures/mapilio/`. Mirror the `mapillary` /
`vector_mvt` decode tests.

- [ ] `test_mapilio_registers` — importing
      `coverage_acquisition.providers.mapilio` registers `"mapilio"` in
      `PROVIDERS`; `get_provider("mapilio")` returns a `ProviderDefinition`
      whose `key == "mapilio"` with exactly one source.
- [ ] `test_mapilio_source_kind_is_vector_mvt` — the provider's single
      `SourceDefinition.kind == "vector_mvt"`.
- [ ] `test_mapilio_coordinate_scheme` — `PROVIDER.coordinate_scheme ==
      "web_mercator"`.
- [ ] `test_mapilio_tile_url_build` — formatting the source `template` with
      `z=14, x=8802, y=5373` yields **exactly**
      `https://geo.mapilio.com/map/8802/5373/14` — asserting the `{x}/{y}/{z}`
      path order (x first, z last), the `geo.mapilio.com/map/` host+path, and
      that there is no `?access_token` / query string. This test is the guard
      for the path-order quirk.
- [ ] `test_mapilio_decode_present` — feeding the `vector_mvt` decoder the
      `tile_istanbul_z14.mvt` fixture yields a `DecodeResult` with
      `feature_count > 0`, the `layer_counts_json` reporting a non-zero
      `map_roads_line` count, and `is_empty` falsy; the stored payload is
      written.
- [ ] `test_mapilio_decode_empty` — feeding the `vector_mvt` decoder the
      `tile_empty.mvt` fixture (the zero-byte body) yields a `DecodeResult` with
      `feature_count == 0` and `is_empty` truthy; the decoder does **not**
      raise on an empty payload.
- [ ] `test_mapilio_layer_names` — the `SourceDefinition.layer_names` contains
      `"map_roads_line"` (so the decoder targets the coverage layer, not the
      object/point layers).
- [ ] `test_mapilio_no_auth_required` — the `SourceDefinition` has no
      `token_query_param`; the module references no `.env` key.
- [ ] `test_mapilio_decode_present_geometry_is_lines` — (defensive) the decoded
      `map_roads_line` features are `LineString` / `MultiLineString` geometries
      (`geometry_type` from the feature rows), guarding against a future
      endpoint change that swaps the layer's geometry type.
- Fixtures under `tests/fixtures/mapilio/` (record once with a tiny throwaway
  script, then commit small — trim to a handful of features if the live tile is
  large):
  - `tile_istanbul_z14.mvt` — `GET https://geo.mapilio.com/map/9510/6142/14`
    (a dense, covered Istanbul tile; the live tile is ~290 KB — if too large to
    commit, re-record a sparser covered z14 tile or truncate to a small subset
    of `map_roads_line` features).
  - `tile_empty.mvt` — the zero-byte empty body (e.g. `GET
    https://geo.mapilio.com/map/4823/6160/14`, New York, no coverage). A
    0-byte file is fine to commit.
  - `tile_berlin_z14.mvt` — optional second covered tile
    (`GET https://geo.mapilio.com/map/8802/5373/14`) for a rasterization
    sanity check; truncate if large.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: existing `vector_mvt`.** No new kind. The provider mirrors
      `src/coverage_acquisition/providers/mapillary.py` (closest analog — same
      kind, same MVT/MapboxGL viewer pattern) and the geometry-MVT handling in
      `kartaview.py`. Use `vector_decoder="custom_mvt"` (the pure-Python
      `mvt_decoder` path, like `mapillary`) so no `ogr2ogr` runtime dependency
      is needed.
- [ ] **Verify the `vector_mvt` decoder tolerates a zero-byte payload.** The
      empty-tile signature is a zero-byte body. Confirm
      `source_kinds/vector_mvt.py` → `mvt_decoder.decode_tile(b"")` returns an
      empty decoded tile (`feature_count == 0`) and does not raise, and that the
      runner records it as `is_empty` / checked-empty. If `decode_tile` raises
      on empty input, that is a **one-line robustness fix to a shared file
      (`mvt_decoder.py` or `vector_mvt.py`)** — if so, land it as its own small
      `foundation` PR **before** the `mapilio` provider PR (per `CLAUDE.md`,
      provider PRs touch no shared file). If `decode_tile(b"")` already returns
      cleanly (likely), no foundation PR is needed and `mapilio` is a pure
      provider-only PR. The implementer must check this first and record the
      outcome in the status log.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/mapilio.py` defining `PROVIDER`
      as a `ProviderDefinition` and calling `register_provider(PROVIDER)`.
      Shape (mirror `mapillary.py`):
  - `key="mapilio"`, `output_namespace="mapilio_mvt_coverage"`,
    `run_label_prefix="mapilio_coverage"`, `coordinate_scheme="web_mercator"`,
    `default_display_zoom=14`.
  - One `SourceDefinition`:
    - `id="mapilio_map_roads_line_vtp"`, `kind="vector_mvt"`,
    - `template="https://geo.mapilio.com/map/{x}/{y}/{z}"` (note `{x}/{y}/{z}`
      order — x first),
    - `headers={"User-Agent": "global-svi-coverage-observatory/0.3",
      "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
      "Referer": "https://mapilio.com/"}`,
    - `layer_names=("map_roads_line",)`,
    - `storage_subdir="vector_mvt"`,
    - `vector_decoder="custom_mvt"`,
    - `expect_content_type_prefix="application/"` (or leave unset — the body,
      not the content-type, decides presence),
    - **no** `token_query_param` (public, no auth),
    - `notes` describing the coverage layer, the `{x}/{y}/{z}` path order, and
      the zero-byte empty-tile signal.
  - `area_presets`: declare the pilot bbox inline in this module (do **not**
    add to `_presets.py`).
  - Module docstring: record that this is the MVT coverage layer
    (`map_roads_line` from the `mapilio-tiles` source), the `{x}/{y}/{z}` path
    quirk, the zero-byte empty-tile signal, the ToS caveat (undocumented
    `geo.mapilio.com/map` endpoint; only a binary coverage raster is published,
    no imagery), no auth, and that coverage is global but sparse/contributor-
    driven.
- [ ] Implement until the §3 tests pass (green); refactor.
- [ ] **Pilot fetch:** bbox `28.96 41.00 29.00 41.03` (**Istanbul — Beyoğlu /
      city centre**, ~3.4 km × 3.3 km) at display zoom **z14**. Expect dense
      `map_roads_line` coverage on the central street network. Scouting
      confirmed the filled z14 tile `map/9510/6142/14` (~290 KB MVT, dense
      `map_roads_line`).
- [ ] Rasterize the pilot area to a z14 COG (EPSG:3857, `uint8`,
      1=covered / 0=checked-empty / 255=nodata) via `rasterize.py`: burn the
      `map_roads_line` LineString geometries onto the shared z14 grid, buffering
      isolated short segments by ~1 cell. Sanity-check that covered pixels land
      on Istanbul streets, not the Bosphorus or sea.
- [ ] **Two-pass full extent:** Mapilio coverage is global but sparse. Pass-1
      discovery: sweep the populated landmasses at discovery zoom **z10** (NOT
      z6/z8 — those tiles are 14–16 MB each; z10 tiles are ≈ 2 MB and
      manageable), recording which z10 cells return non-empty
      `map_roads_line`. Pass-2: fetch z14 tiles only inside the discovered z10
      cells. A global z10 sweep is ~1M tiles worst-case but the vast majority
      return a zero-byte empty body quickly; if a global sweep is too costly
      for the first run, scope pass-1 to a coarse global grid or to the
      countries Mapilio advertises and expand later. Restrict pass-2 strictly
      to discovered cells.
- [ ] Update / create the STAC item for `mapilio` (extent = discovered coverage
      envelope, scrape date, tier T2, source endpoint
      `geo.mapilio.com/map/{x}/{y}/{z}`, ToS notes). Update the inventory
      status for `mapilio`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.mapilio` imports and
  self-registers (`"mapilio"` in `PROVIDERS`); CI smoke test (import + register
  + dry-run) passes.
- The provider's single source is `kind="vector_mvt"`,
  `coordinate_scheme="web_mercator"`, `layer_names` includes `map_roads_line`;
  the tile `template` builds the `{x}/{y}/{z}` URL
  `https://geo.mapilio.com/map/{x}/{y}/{z}` with no auth params.
- Pilot z14 fetch over central Istanbul returns non-empty MVT tiles that decode
  to `feature_count > 0` with `map_roads_line` features; a no-coverage tile
  (zero-byte body) decodes to `is_empty` / `feature_count == 0` without raising.
  Decoded coverage lands on roads/land (not water).
- z14 COG is valid: CRS EPSG:3857, `uint8`, covered pixels > 0, internal
  overviews present.
- Fetches go through `polite.polite_fetch` with a descriptive User-Agent and a
  conservative throttle; no bare `urllib`/`requests` in the provider path.
- ToS caveats documented in the `mapilio.py` module docstring (undocumented
  `geo.mapilio.com/map` MVT endpoint; only a binary coverage raster is
  published, never imagery; coverage is global but contributor-driven/sparse).

## 6. Status log

- `2026-05-22` scout: drafted. Confirmed live that Mapilio's web viewer
  (`mapilio.com/app`, Next.js + MapboxGL/MapLibre) draws coverage from an **MVT
  vector-tile source**:
  - Endpoint reverse-engineered from the viewer chunk bundle
    `mapilio.com/_next/static/chunks/6225-4bbde418ef19af98.js`:
    `map.addSource("mapilio-tiles",{type:"vector",
    tiles:["https://geo.mapilio.com/map/{x}/{y}/{z}"]})` with `source-layer`
    `map_roads_line` (the coverage footprint, `minzoom:6 maxzoom:23`),
    `world_img_cache` (z0–6 overview), and `map_points` (z15–23 image points).
    A separate `mapilio-object-tiles` source (`/features/{x}/{y}/{z}`,
    `map_features`) is ML-detected objects — not coverage.
  - **URL path order is `{x}/{y}/{z}`** (x first, z last). Verified: Berlin z14
    `map/8802/5373/14` → 436 KB MVT; the `{z}/{x}/{y}` order
    `map/14/8802/5373` → HTTP 400.
  - Probed live: Istanbul z14 `map/9510/6142/14` → 290 KB MVT, single layer
    `map_roads_line` with 2301+ LineString features (ogrinfo + a Python MVT
    parser agree); Berlin z14 → 436 KB / 2301 features; Atlantic Ocean, New
    York, Izmir z14 → zero-byte HTTP 200 (`content-length: 0`, content-type
    still `application/vnd.mapbox-vector-tile`) = no coverage. Out-of-grid
    index `map/99999/99999/14` → HTTP 400.
  - `map_roads_line` carries full-resolution geometry at all zooms: z14 ≈
    436 KB, z12 ≈ 1 MB, z10 ≈ 2 MB, z8 ≈ 14 MB (211k features), z6 ≈ 16 MB.
    Discovery should run at z10, not z6/z8.
  - Auth: none — `200` with no query string and no headers. No `.env` key.
  - `geo.mapilio.com/robots.txt` → HTTP 404 (GeoServer serves none);
    `mapilio.com/robots.txt` returns the SPA shell (no Disallow). Fetching is
    not disallowed. The `/map/` endpoint is undocumented (`docs.mapilio.com` is
    down, `mapilio/docs` repo empty).
  - Coverage is global but sparse/contributor-driven; pilot city = Istanbul
    (confirmed dense).
- `2026-05-22` approval: pending.
- `YYYY-MM-DD` implement / verify: notes appended here.

---

### Open questions for the reviewer

1. **`vector_mvt` decoder on a zero-byte payload.** Mapilio's empty-tile signal
   is a zero-byte HTTP 200 body. The implementer must verify
   `mvt_decoder.decode_tile(b"")` / `source_kinds/vector_mvt.py` handle this as
   `feature_count == 0` / `is_empty` without raising. If it already does
   (likely — `mapillary`/`kartaview` MVT tiles can also be empty), `mapilio` is
   a pure provider-only PR with no shared-file edits. If `decode_tile` raises on
   empty input, a one-line robustness fix lands as a small `foundation` PR
   first. Confirm this approach.
2. **Discovery zoom & global sweep cost.** `map_roads_line` is full-resolution
   at every zoom, so coarse tiles are multi-MB (z8 ≈ 14 MB). Proposed discovery
   zoom is **z10** (≈ 2 MB/tile). A truly global z10 pass-1 is ~1M tiles
   (mostly fast zero-byte empties). Confirm z10, and whether pass-1 should be a
   full global sweep or scoped to Mapilio's advertised countries / a coarse
   global pre-filter first.
3. **Date layer out of scope.** The coverage MVT encodes presence only (plus a
   `fov` flag for 360° vs flat); per-image capture dates would require the
   separate image-metadata API. Confirm `mapilio` ships without a
   `mapilio_year.tif` date layer.
4. **Undocumented endpoint / ToS posture.** `geo.mapilio.com/map` is an
   undocumented GeoServer MVT endpoint (the advertised `docs.mapilio.com` is
   down). Mapilio is an explicitly open crowdsourced platform, and this project
   publishes only a derived binary coverage COG (raw tiles kept only in
   gitignored `data/raw/`). Confirm this satisfies the ToS posture, or require
   deleting `data/raw/mapilio/` after rasterization.

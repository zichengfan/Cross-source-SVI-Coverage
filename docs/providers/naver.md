# [T1] Provider: Naver Maps Street View (`naver`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

Naver Maps ("Naver Geo / 거리뷰") is South Korea's dominant domestic web-map
provider and ships a first-party street-level panorama product ("거리뷰",
Street View) covering virtually all of South Korea — Seoul, the six metro
cities, secondary towns, rural roads, and offshore islands such as Jeju. It is
**active** (latest panoramas observed dated 2026-01-29), produces its own
imagery (car / bicycle / trekker capture; not a re-hoster), and is **natively
supported by the installed `streetlevel` library** (`streetlevel.naver`). It is
a Tier-1 streetlevel-native provider per PLAN §2 and is in scope for the global
SVI coverage database. Coverage is acquired by probing Naver's panorama
endpoints through `streetlevel.naver` and rasterizing the discovered panorama
points onto the shared z14 grid.

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:** `https://map.naver.com` — Street View is the
  "거리뷰" layer; a panorama permalink looks like
  `https://map.naver.com/p?c=17,0,0,0,adh&p=<panoid>,0,10,80,Float`.
- **Tier:** T1 (streetlevel-native). `streetlevel` 0.12.7 is installed and
  exposes `streetlevel.naver`.

- **Coverage endpoint(s):** Naver has **no public coverage tile layer** (no
  raster/MVT/JSON tile endpoint for "where imagery exists"). Coverage is
  discovered by *probing* Naver's panorama metadata API, which the
  `streetlevel.naver` module wraps. The relevant calls and the HTTP endpoints
  they hit:

  | streetlevel call | HTTP endpoint (GET) | Purpose |
  |---|---|---|
  | `naver.find_panorama(lat, lon, ...)` | `https://map.naver.com/p/api/panorama/nearby/{lon}/{lat}` | Nearest-pano-to-a-point lookup. Returns a GeoJSON `FeatureCollection`. |
  | `naver.get_neighbors(panoid)` | `https://panorama.map.naver.com/metadataV3/around/{panoid}?lang=ko` | All panoramas near a given pano (street + air sections). |
  | `naver.find_panorama_by_id(panoid, lang)` | `https://panorama.map.naver.com/metadataV3/basic/{panoid}?lang={lang}` | Full metadata for one pano (date, type, `timeline_id`). |
  | `naver.get_historical(timeline_id)` | `https://panorama.map.naver.com/metadata/timeline/{timeline_id}` | Older panoramas at the same spot (date layer). |

  All requests are plain `GET`, no query params beyond those shown, and
  `streetlevel.naver.api` sends a single header `Referer: https://map.naver.com`.
  The provider module must additionally set the project's descriptive
  `User-Agent` (see §2 Auth / robots).

- **Coordinate scheme:** `web_mercator` for the z14 output grid. **The provider
  itself is not tile-based** — there is no `{z}/{x}/{y}` template. Discovery is
  point/flood-fill driven in WGS84 lon/lat; results are panorama *points*
  (`lat`, `lon` in EPSG:4326) which `rasterize.py` reprojects to z14. Note the
  `nearby` URL path order is `{lon}/{lat}` (longitude first), and the GeoJSON
  `geometry.coordinates` array is `[lon, lat]` — easy to swap, watch carefully.

- **Zoom range / tile size / response format:** Not applicable as tiles. The
  provider yields **vector point records** (panorama points). For the two-pass
  extent runner, "pass 1" is a coarse lon/lat sampling grid (see §2 Discovery
  strategy), not a tile zoom; for the z14 burn the analysis zoom is fixed at 14
  per PLAN §3. Responses are JSON / GeoJSON.

- **Auth:** **none.** No token, no cookie, no login. The endpoints are public
  and unauthenticated; `streetlevel.naver` makes no auth calls. **No `.env` key
  is required for this provider.** (Do not add a `NAVER_*` slot to
  `.env.example`.)

- **Presence rule:** "Imagery exists here" =
  - `find_panorama(lat, lon)` returns a non-`None` `NaverPanorama` — i.e. the
    `nearby` response has `len(features) > 0`. An empty response is
    `{"type": "FeatureCollection", "features": []}`; `find_panorama` returns
    `None`. Ocean / out-of-country points (tested: open sea, Tokyo) return
    `None`; in-coverage points (tested: Gangnam Seoul, Jeju) return a pano.
  - Each discovered/neighbor pano contributes one **covered point** at its
    (`lat`, `lon`). The set of all collected points is the coverage geometry;
    `rasterize.rasterize_geometries_to_cog` burns them (buffering isolated
    points by ~1 z14 cell, PLAN §1).
  - Filter to street-level types only — keep `PanoramaType` values
    `CAR (3)`, `BICYCLE (4)`, `TREKKER (13)` and treat `MESH_EQUIRECT (15)` as
    street-level too (Naver's newer 3D car footage). **Drop** `AIR (1)`,
    `DRONE (2)`, `INDOOR* (10/11/100)`, `UNDERWATER (12)`, `MUSEUM (5)`,
    `PENSION (7/8)`. The `get_neighbors` response already splits `street` vs
    `air`; prefer its `street` section.

- **robots.txt / ToS notes; observed rate limit:**
  - **`https://map.naver.com/robots.txt` disallows almost everything**:
    `User-agent: *` → `Disallow: /` with only `Allow: /$` and `Allow: /p/$`.
    The discovery endpoint `https://map.naver.com/p/api/panorama/nearby/...` is
    under `/p/` but is **not** the literal `/p/$` path, so a strict robots
    reading does **not** allow it. `ClaudeBot` and AI-training agents are
    explicitly `Disallow: /`.
  - `https://panorama.map.naver.com/robots.txt` returns **404** (no robots
    file) → `polite.robots_allows` treats an unreachable robots.txt as allowed.
    Three of the four endpoints (`get_neighbors`, `find_panorama_by_id`,
    `get_historical`) live on `panorama.map.naver.com`.
  - **Action required / open question (see §6):** `map.naver.com/robots.txt`
    technically disallows the `nearby` discovery endpoint under the project's
    "respect robots.txt" posture (PLAN §1, CLAUDE.md). Options for the human
    reviewer: (a) accept a documented, narrowly-scoped exception for this
    low-volume metadata probe with a strict throttle, (b) restrict discovery to
    seed points only and rely on `get_neighbors` (on `panorama.map.naver.com`,
    which has no robots restriction) for the flood-fill, minimizing
    `map.naver.com` calls, or (c) drop the provider. **This subplan assumes
    option (b)** — seed with a *small, fixed* set of `find_panorama` calls and
    do the bulk of discovery via `get_neighbors`. The provider module docstring
    must record this ToS caveat verbatim.
  - Observed behavior: no rate-limit error seen in light manual testing, but no
    documented limit. Use a **conservative throttle**: `min_interval_seconds`
    >= 1.0 (stricter than the 0.25 default), `max_retries=3` with backoff.
    Korea-only provider, so total request volume is bounded.

- **Known quirks / gotchas:**
  - `find_panorama` snaps to the **nearest** pano — a query point ~50 m off a
    road still returns the road's pano. So a coarse discovery grid will "pull
    in" nearby coverage; do not treat the returned `lat/lon` as the query point.
    De-duplicate panos by `id`.
  - `find_panorama` ignores aerial/underwater panoramas (per its docstring) —
    convenient, but still type-filter neighbor results.
  - `get_neighbors` can return **hundreds** of street panos for one pano
    (244 observed at Gangnam). This is the engine of the flood fill but also a
    request amplifier — cap the flood-fill frontier and de-dup aggressively.
  - URL/coordinate order: `nearby` path is `{lon}/{lat}`; GeoJSON coords are
    `[lon, lat]`; `find_panorama(lat, lon)` takes lat first. Three different
    orders in one provider — a prime source of bugs; pin with a unit test.
  - `streetlevel.naver` returns `None` (not an exception) for empty/ocean
    points and `[]`/empty `Neighbors` for missing neighbors — code must handle
    `None` everywhere.
  - Capture dates are exposed (`NaverPanorama.date`, and `get_historical` for a
    full timeline) — this provider **can** populate the optional `*_year.tif`
    date layer (PLAN §3). Out of scope for the first pilot PR; note it.
  - The provider does **not** fit the URL-template `SourceDefinition.template`
    model. The new `streetlevel` source kind must accept a non-templated
    source whose "fetch" is a `streetlevel` library call, not a `{z}/{x}/{y}`
    GET. See §4.

## 3. Test plan (write these FIRST — red before green)

All tests are offline. `streetlevel.naver` network calls are **monkeypatched**;
decode logic runs against **recorded JSON fixtures** captured from the live
endpoints. Fixtures live under `tests/fixtures/naver/`.

Fixtures to record (small, hand-trimmed real responses):
- `tests/fixtures/naver/nearby_gangnam.json` — a real `nearby` FeatureCollection
  with >=1 feature (capture from
  `https://map.naver.com/p/api/panorama/nearby/127.0276/37.4979`).
- `tests/fixtures/naver/nearby_empty.json` — `{"type":"FeatureCollection","features":[]}`.
- `tests/fixtures/naver/around_gangnam.json` — a real `metadataV3/around/<panoid>`
  response, trimmed to ~5 street panos + (optionally) 1 air pano, so type
  filtering can be exercised.

Tests (`tests/test_providers_naver.py` unless noted):

- [ ] `test_naver_registers` — importing `coverage_acquisition.providers`
  registers `"naver"` in `PROVIDERS`; `get_provider("naver")` returns a
  `ProviderDefinition` with `key == "naver"` and exactly one `SourceDefinition`
  whose `kind == "streetlevel"`.
- [ ] `test_naver_source_definition` — the source's `options` (or equivalent)
  declares the streetlevel backend (`"streetlevel_module": "naver"`), the
  street-level type allow-list, and carries a descriptive `User-Agent` +
  `Referer: https://map.naver.com` header. `template` is empty/sentinel (the
  streetlevel kind is not URL-templated).
- [ ] `test_naver_decode_nearby_present` — feeding `nearby_gangnam.json` to the
  naver decode helper yields >=1 pano point record with numeric `lat`/`lon` in
  Korea's range (`33 <= lat <= 39`, `124 <= lon <= 132`), the correct `panoid`,
  and `is_empty` falsey.
- [ ] `test_naver_decode_nearby_empty` — `nearby_empty.json` decodes to zero
  point records and `is_empty` truthy (a checked-but-empty probe).
- [ ] `test_naver_decode_around_type_filter` — `around_gangnam.json` decodes so
  that only street-level types (`CAR/BICYCLE/TREKKER/MESH_EQUIRECT`) survive;
  any `AIR`/`DRONE`/`INDOOR`/`UNDERWATER` pano is dropped. Assert the dropped
  count and surviving count.
- [ ] `test_naver_coordinate_order` — a regression test pinning that a GeoJSON
  feature with `geometry.coordinates == [lon, lat]` decodes to a record with
  `lat`/`lon` *not* swapped (use distinct, unambiguous values, e.g.
  lon=127.5, lat=37.5, and assert `record["lat"] == 37.5`).
- [ ] `test_naver_dedup_by_id` — decoding a payload containing the same `panoid`
  twice yields a single point record.
- [ ] `test_naver_discovery_offline` (in `tests/test_extent.py` or the provider
  test file) — with `streetlevel.naver.find_panorama` /
  `get_neighbors` monkeypatched to return canned `NaverPanorama` objects from
  the fixtures, the discovery routine returns exactly the de-duplicated set of
  in-coverage points the stub exposes, makes **no real network call**, and
  respects the configured frontier cap.
- Fixtures: small recorded response samples under `tests/fixtures/naver/`.

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] **Source kind: NEW kind `streetlevel`** — this is a separate **foundation
  PR that must merge first** (PLAN §4 item 3 names `streetlevel` as a seed
  kind; `source_kinds/streetlevel.py` does not yet exist). The `naver` provider
  PR depends on it and must not create it. The `streetlevel` kind must:
  - Accept a `SourceDefinition` whose `options` name a streetlevel submodule
    (`"streetlevel_module": "naver"`) and a discovery config, instead of a
    `{z}/{x}/{y}` URL template.
  - Expose a decode/collect path that, given fetched panorama JSON (or
    `streetlevel` objects), returns `DecodeResult.pano_records` (lat/lon/panoid/
    date/type) — mirroring `coverage_json`'s `pano_records` shape so
    `rasterize.py` can consume it unchanged.
  - Route discovery + fetch through `polite.polite_fetch` *or*, if calling the
    `streetlevel` library directly, pass a `requests.Session` whose adapter
    enforces the project throttle/UA; either way no raw `urllib`/`requests` in
    the hot loop (CLAUDE.md). Document whichever approach the foundation PR
    picks; this provider just declares the source.
  - If the streetlevel kind cannot be made to honor `polite` in time, the
    fallback is to call `naver.api.build_*_request_url(...)` to get the plain
    URLs and fetch them with `polite_fetch`, then parse with `naver.parse.*`.
    Either is acceptable; the provider module is identical.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/naver.py` defining `PROVIDER` as a
  `ProviderDefinition` and calling `register_provider(PROVIDER)`:
  - `key="naver"`, `output_namespace="naver_streetview_points"`,
    `run_label_prefix="naver_streetview"`, `default_display_zoom=14`,
    `coordinate_scheme="web_mercator"`.
  - One `SourceDefinition(id="naver_streetlevel_panos", kind="streetlevel", ...)`
    with `template=""` (sentinel), `headers={"User-Agent":
    "global-svi-coverage-observatory/0.3 (+https://github.com/zichengfan/Cross-source-SVI-Coverage)",
    "Referer": "https://map.naver.com"}`, `storage_subdir="streetlevel"`, and
    `options` carrying: `streetlevel_module="naver"`, the street-level
    `PanoramaType` allow-list `(3, 4, 13, 15)`, and the discovery config
    (seed-grid spacing, flood-fill frontier cap, throttle hint).
  - `area_presets`: declare the pilot bbox **inside the provider module** (do
    not edit `_presets.py`) — `seoul_gangnam_pilot_bbox` (see below).
  - Module docstring records the **robots.txt / ToS caveat** from §2 verbatim
    and the chosen discovery posture (option (b)).
- [ ] Implement the naver decode helper (parse `nearby` + `around` JSON →
  type-filtered, de-duplicated pano point records) until the §3 tests pass
  (green); refactor.
- [ ] **Pilot fetch:** bbox `127.020 37.490 127.060 37.520`
  (Seoul — Gangnam / Yeoksam, dense guaranteed coverage; ~3.6 x 3.3 km). Seed a
  small lon/lat grid inside this bbox (e.g. ~300 m spacing → ~140 seed points),
  call `find_panorama` per seed, then flood-fill via `get_neighbors` with a
  frontier cap, de-dup by `id`, clip points to the bbox. Expect hundreds of
  street panos on known roads (Teheran-ro, Gangnam-daero).
- [ ] Rasterize the pilot area to a z14 COG with
  `rasterize.rasterize_geometries_to_cog` (points → shapely `Point`s in
  EPSG:4326, `point_buffer_cells=1.0`); sanity-check: covered pixels land on
  Gangnam's street grid, not on the Han River or rooftops; CRS EPSG:3857,
  `uint8`.
- [ ] **Two-pass full extent:** pass-1 discovery region bbox
  `124.5 33.0 131.9 38.7` (mainland South Korea + Jeju + offshore islands).
  Pass 1 = a coarse seed grid over the region at **~2–3 km spacing** (the
  "discovery zoom" analogue ≈ z11–z12 sampling); panos found seed the
  `get_neighbors` flood-fill; pass 2 burns the collected points at z14. Cap the
  flood-fill and persist the panorama point set to
  `data/intermediate/naver/` as GeoParquet (the re-rasterizable source of
  truth, PLAN §3) before rasterizing.
- [ ] Update the STAC item (`catalog.upsert_provider_item`, `tier="T1"`,
  `source_endpoint="https://map.naver.com/p/api/panorama/nearby + panorama.map.naver.com/metadataV3"`,
  `tos_notes=<robots caveat>`); update the inventory status for `naver`.
- [ ] (Future, out of scope here) optional date layer: `NaverPanorama.date` /
  `get_historical` → `naver_streetview_points_year.tif`.

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; `coverage_acquisition.providers.naver` imports and
  self-registers in `PROVIDERS`; CI import/register/dry-run smoke test passes.
- Pilot discovery returns >0 street-level panoramas inside the Gangnam bbox;
  decoded points have valid `lat`/`lon` within South Korea and correct
  (non-swapped) coordinate order.
- z14 COG is valid (`rio_cogeo.cog_validate`), CRS EPSG:3857, `uint8`, covered
  pixels > 0, and coverage lands on roads/land (not ocean) — Gangnam street grid.
- All fetching goes through `polite.polite_fetch` (or a `polite`-backed
  session); descriptive `User-Agent` set; throttle >= 1.0 s/host.
- The robots.txt / ToS caveat is documented in the `providers/naver.py`
  docstring and in the STAC item `tos_notes`; the chosen discovery posture
  (option (b), minimize `map.naver.com` calls) is recorded.
- No `NAVER_*` secret is required or added (provider is unauthenticated).

## 6. Status log

- `2026-05-20` scout: drafted. Confirmed `streetlevel` 0.12.7 installed and
  `streetlevel.naver` functional against live endpoints (Gangnam, Jeju return
  panos; ocean/Tokyo/mountains return `None`). Confirmed Naver has **no public
  coverage tile layer** — coverage must be discovered by probing the
  `nearby` + `metadataV3/around` panorama-metadata endpoints and rasterizing
  panorama points. No auth required.
- `2026-05-20` open questions for the human reviewer:
  1. **robots.txt** — `map.naver.com/robots.txt` (`Disallow: /`, only `/$` and
     `/p/$` allowed, `ClaudeBot` explicitly blocked) does not permit the
     `/p/api/panorama/nearby/...` discovery endpoint under a strict reading.
     `panorama.map.naver.com` has no robots.txt (404 → allowed). This subplan
     assumes **option (b)**: minimize `map.naver.com` use (small fixed seed
     grid only) and do the bulk discovery via `get_neighbors` on
     `panorama.map.naver.com`. Reviewer must confirm option (b), pick (a)
     documented exception, or (c) drop the provider.
  2. **Foundation dependency** — `naver` requires the new `streetlevel` source
     kind (`source_kinds/streetlevel.py`), which must be built and merged as a
     separate foundation PR before the `naver` provider PR. Confirm sequencing.
  3. **Flood-fill bounds** — `get_neighbors` can return 200+ panos per call;
     the full-extent crawl over all of South Korea could be large. The seed-grid
     spacing and frontier cap in §4 are starting estimates; reviewer may want a
     tighter request budget or a per-region batching plan.
- `2026-05-20` approval: < pending >

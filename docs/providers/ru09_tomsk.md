# [T3] Provider: ru09.ru Tomsk street panoramas (`ru09_tomsk`) — RECOMMEND DEFER / SKIP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER / SKIP. The service is LIVE and reachable
(`https://www.tomsk.ru09.ru/`, HTTP 200, nginx, RU host 176.120.26.62), unlike
its already-skipped siblings ru09.ru Novosibirsk / ru09.ru Sochi (PLAN.md §2
"Skip — defunct"). But it is NOT a street-view coverage source worth scraping:

  1. The panorama product is a tiny, frozen set of ~50-per-page x ~9 pages of
     *individual spot panoramas* ("Панорамные фото") on roughly ten central
     Tomsk streets, first published 2009-12-29 and last updated 2010-11-11 —
     15+ years stale, not continuous drive coverage.
  2. The only machine-readable coverage signal (panorama point locations) lives
     in the map's `/ajax2/` XML response under a `panopts` node, but the request
     requires a runtime-computed `do=<token>` action that could not be recovered
     from the Dean-Edwards-packed map JS (`/script.php?...&package=4`). Every
     bbox/scale parameter combination probed returned an empty `text/xml`
     (HTTP 200, 0 bytes), so no fixture could be recorded and no presence rule
     verified.
  3. `robots.txt` explicitly bans `ClaudeBot` from the whole site
     (`User-agent: ClaudeBot` / `Disallow: /`), and the panorama pages are
     marked `<meta name="robots" content="noindex,nofollow">`.
  4. Coordinates are a custom local map grid (MAP_CONFIG units, scalelist
     [1,2,4,8,16,32]), not web-mercator/WGS84, with no recoverable transform.

The coverage footprint (~10 central streets, ~6 km^2) is also negligible at the
project's z14 global grid, and Yandex — already a first-class provider — has
far denser Tomsk panorama coverage (`yandex.ru/maps/67/tomsk/panorama/`). This
subplan documents the full investigation so the provider can be revived *iff*
ru09.ru ever exposes a usable coverage layer; no issue/branch/code now.
-->

## 1. Summary

ru09.ru is a family of Russian regional city-portal / online-map sites
(`<city>.ru09.ru`), of which `tomsk.ru09.ru` is the Tomsk instance. Among many
business-directory and realty features, the Tomsk map offers a "Панорамы улиц"
(street panoramas) feature: KRPANO-based 360° spot panoramas placed on the
city map, browsable both on the interactive map (`/map`, panorama mode button
"Панорамы города") and via a dedicated gallery (`/panorams`). It was catalogued
as a T3 candidate because it is a first-party (non-re-hosted) Russian SVI
service, distinct from the already-skipped, fully-defunct sibling instances
ru09.ru **Novosibirsk** and ru09.ru **Sochi** (PLAN.md §2). Unlike those, the
Tomsk site is still online — but scouting concludes the panorama product is a
small, frozen, 2009–2010 spot-panorama set with no reliably scrapable coverage
endpoint, behind a `ClaudeBot`-banning `robots.txt`. **Recommendation:
DEFER / SKIP** — see §2 for evidence, §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: live site, but no usable scrapable coverage layer — DEFER / SKIP

Applying the kakao/naver/mapy scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.** The
   base map is custom raster tiles (`pics1..4.tomsk.ru09.ru`, 256×256, custom
   grid), but there is **no separate "where panoramas exist" overlay tile
   layer**. Panorama points are vector markers drawn from an XML response, not a
   tile layer.
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.** The viewer is a
   bespoke ~2010-era JS map engine (Dean-Edwards-packed `/script.php` bundles,
   `excanvas.js` shim for IE), not MVT.
3. **Coverage JSON / XML API (`kind="coverage_json"` / `json_api`)? — EXISTS BUT
   UNREACHABLE IN PRACTICE.** The map driver issues requests to `/ajax2/`
   (declared in `MAP_CONFIG.ajax`) that return `text/xml`; the response is
   parsed by `ProcessXML` → `ProcessPanopts`, which reads a `panopts` node and
   calls `ShowPanoPoint(...)` for each panorama marker (`PANO_POINT_SIZE`,
   `PANO_POINT_RADIUS`, `pano_point_id` constants confirm per-point markers).
   This is the coverage signal. **But the request's `do=<action>` value is a
   runtime-computed minified variable, not a literal**, so it could not be
   recovered from the static packed JS; every guessed parameter set (`do=map`,
   `x1/y1/x2/y2&scale`, `currentscalenum`, `panopts=1`, etc.) returned
   **HTTP 200 with an empty (0-byte) `text/xml` body**. With no live non-empty
   response, no presence rule can be confirmed and no fixture recorded.

- **Homepage / public viewer URL.**
  - Map viewer: `https://www.tomsk.ru09.ru/map` (panorama mode via the
    "Панорамы города" button `#panomode`).
  - Panorama gallery: `https://www.tomsk.ru09.ru/panorams` (individual
    panoramas addressed as `#panophoto=<id>`, e.g. 836–956; ~9 pages
    `?page=2..9`).
  - Mobile: `https://m.tomsk.ru09.ru/map?m=1`.
- **Tier:** T3 (likely / unverified / gated — confirmed *live but not usefully
  scrapable*).
- **Coverage endpoint(s).** `https://www.tomsk.ru09.ru/ajax2/` — HTTP GET,
  `Content-Type: text/xml`. Returns the visible map objects (labels + panorama
  points) for the current viewport. **Query params unknown**: the driver builds
  `?do=<runtime-token>&...x1=&y1=&x2=&y2=...` (bbox in *custom grid units*) plus
  scale/state flags; the dictionary words `x1,x2,y1,y2,scale,labels,
  showlabelsinfo,currentscalenum` appear in the packer dictionary but the
  literal `do=` action is computed at runtime and was not recoverable
  statically. A secondary endpoint `/ajax.php` (HTML) serves UI fragments.
- **Coordinate scheme:** **other / custom local grid** — NOT web-mercator and
  NOT WGS84. From `MAP_CONFIG`:
  `extent={x1:-2164.84375,y1:-2240.34375,x2:5304.125,y2:2817.21875}`,
  `defaultcenter={x:972,y:797}`, `tile_size 256×256`,
  `scalelist=[1,2,4,8,16,32]`, `streetview_scalelist=[16,32]`. No
  grid→WGS84 transform is exposed; deriving one would require georeferencing
  the custom grid against known landmarks (out of scope here).
- **Zoom range / tile size / response format:** panoramas are only shown at the
  two finest scales (`streetview_scalelist=[16,32]`, i.e. scale indices 4–5 of
  6). Tiles are 256×256 raster from `pics1..4.tomsk.ru09.ru`. Coverage objects
  arrive as XML from `/ajax2/`.
- **Auth:** none observed (no token/cookie needed for `/ajax2/` or the panorama
  pages). No `.env` key would be required.
- **Presence rule (intended, UNVERIFIED):** "≥1 `panopts`/panorama-point node in
  the `/ajax2/` XML for a viewport ⇒ a panorama exists there; burn each point
  (after grid→WGS84 transform, buffered ~1 cell) into the raster." Cannot be
  confirmed without a non-empty live response.
- **robots.txt / ToS notes; observed rate limit.**
  `https://www.tomsk.ru09.ru/robots.txt` contains an **explicit, project-
  relevant ban**:
  ```
  User-agent: ClaudeBot
  Disallow: /
  ```
  plus blanket disallows for `/feedback`, `/captcha.php`, `/addcompany` under
  `User-agent: *` (the `/map`, `/panorams`, `/ajax2/` paths are *not* in the `*`
  disallow list, but the ClaudeBot block is total). Panorama pages carry
  `<meta name="robots" content="noindex,nofollow">`. No rate-limit headers were
  observed; site is small and would warrant a slow, polite cadence if ever
  revisited.
- **Known quirks / gotchas.**
  - `windows-1251` (Cyrillic) encoding throughout — must decode as cp1251.
  - Map JS is Dean-Edwards `p,a,c,k,e,d`-packed across
    `/script.php?ver=5.294&package={3,4,5,6}`; package 4 holds the panorama
    marker logic (`ProcessPanopts`, `ShowPanoPoint`, `PANO_POINT_*`).
  - Content frozen: panorama articles dated **2009-12-29** (id=25, initial
    launch, ~10 streets), **2010-11-11** (id=77, last "Обновление панорам
    улиц"). No evidence of any panorama refresh since 2010.
  - This is **not** a Yandex/Google re-host (it is first-party KRPANO content),
    but Yandex already covers Tomsk panoramas far more densely and is an
    existing project provider — so this adds little.

### Live infrastructure probe (2026-05-28)

| Host / URL | Status | Notes |
|---|---|---|
| `https://www.tomsk.ru09.ru/` | HTTP 200, 44.6 KB | nginx; cp1251; **LIVE** |
| `https://www.tomsk.ru09.ru/map` | HTTP 200, 37.7 KB | viewer HTML; carries `MAP_CONFIG`, KRPANO refs |
| `https://m.tomsk.ru09.ru/map?m=1` | HTTP 200, 36.3 KB | mobile viewer; same `/ajax2/`+`/ajax.php` backend |
| `https://www.tomsk.ru09.ru/panorams` | HTTP 200, 50 KB | gallery; `#panophoto=836..956`; pages `?page=2..9` |
| `https://www.tomsk.ru09.ru/panorams/836` | HTTP 200, 17 KB | single-panorama page; `noindex,nofollow`; **no lat/lon embedded** |
| `https://www.tomsk.ru09.ru/ajax2/` (no/guessed params) | HTTP 200, `text/xml`, **0 bytes** | coverage endpoint; empty for all probed param sets |
| `https://www.tomsk.ru09.ru/ajax.php` | HTTP 200, `text/html`, 0 bytes | UI-fragment endpoint |
| `https://www.tomsk.ru09.ru/robots.txt` | HTTP 200 | **`ClaudeBot: Disallow: /`** |
| Resolved IP | `176.120.26.62` | Russian host; reachable from this network |

### Why this is DEFER, not a normal build

- **No recoverable coverage request.** The single source of panorama locations
  (`/ajax2/` `panopts` XML) needs a runtime-computed `do=` action; static
  reverse-engineering of the packed JS did not yield it, and blind probing
  returned only empty XML. An implementer would have to capture live browser
  traffic against a `ClaudeBot`-banned site to proceed — outside polite posture
  and not justified by the payoff.
- **Negligible, frozen footprint.** ~10 central Tomsk streets of 2009–2010 spot
  panoramas. At z14 (~9.5 m/px) the whole footprint is a handful of pixels and
  is already covered (densely) by Yandex.
- **Custom non-georeferenced grid.** Even with the XML, points are in a bespoke
  pixel grid with no published WGS84 transform.

## 3. Test plan (write these FIRST — red before green)

> Not applicable while the verdict is DEFER/SKIP — no provider module is built,
> so there is nothing to test. The tests below are the target *iff* ru09.ru
> later exposes a usable, documented coverage response and the verdict is
> revisited. They cannot be written today because **no non-empty `/ajax2/`
> fixture could be recorded** (every probe returned 0-byte XML).

- [ ] `test_ru09_tomsk_request_build` — URL/params for `/ajax2/` fill correctly
      for a sample viewport (REQUIRES the real `do=` action — currently unknown).
- [ ] `test_ru09_tomsk_decode_panopts` — a recorded `/ajax2/` XML fixture with a
      `panopts` node decodes to ≥1 panorama point (REQUIRES a non-empty fixture —
      not obtainable today).
- [ ] `test_ru09_tomsk_decode_empty` — an empty/no-`panopts` response decodes to
      "no coverage".
- [ ] `test_ru09_tomsk_grid_to_wgs84` — custom-grid (x,y) → WGS84 transform maps
      a known landmark to its true Tomsk lat/lon (REQUIRES a derived transform —
      not available today).
- [ ] `test_ru09_tomsk_registers` — module self-registers in `PROVIDERS`.
- Fixtures: `tests/fixtures/ru09_tomsk/` — **cannot be populated** until a
  non-empty `/ajax2/` response is captured.

## 4. Implementation subplan (steps for the implementer — TDD)

> Blocked behind the DEFER verdict. The remaining unknowns below are exactly
> what must be resolved before this provider is buildable.

- [ ] Source kind: would be `coverage_json`-style (XML variant; the existing
      `coverage_json` kind would need an XML decode path, or a small new
      `coverage_xml` kind — that is a separate foundation PR, not part of this
      provider). **Do not build yet.**
- [ ] **PREREQUISITE 1** — recover the exact `/ajax2/` request: capture live
      network traffic from `https://www.tomsk.ru09.ru/map` in panorama mode at
      scale 16/32 over a central-Tomsk viewport; record the `do=` action and the
      full param set, and a sample non-empty XML body.
- [ ] **PREREQUISITE 2** — derive the custom-grid → WGS84 transform by
      georeferencing the `MAP_CONFIG.extent` grid against ≥3 known Tomsk
      landmarks; verify it lands central Tomsk at ~56.48 N, 84.95 E.
- [ ] **PREREQUISITE 3** — resolve ToS posture: the `ClaudeBot` `Disallow: /`
      ban means any automated fetch must be explicitly justified/authorized; the
      user must decide whether to proceed at all.
- [ ] Only if all three resolve: write §3 tests (red) → add
      `src/coverage_acquisition/providers/ru09_tomsk.py` → green → refactor.
- [ ] Pilot bbox (central Tomsk, were it buildable):
      `84.93 56.46 84.99 56.51` (Lenin Prospekt / Площадь Ленина core — the
      2009–2010 panorama streets). Discovery zoom: the two streetview scales
      (indices 4–5, i.e. scale 16 and 32).

## 5. Acceptance criteria (checked by provider-verifier)

> N/A under the DEFER verdict. If revived, standard criteria apply: §3 tests
> pass; module imports & self-registers; pilot `/ajax2/` requests fetch & decode
> to panorama points; points transform to plausible central-Tomsk lat/lon (on
> land/roads); z14 COG valid (EPSG:3857, `uint8`, covered pixels > 0); fetches
> via `polite.polite_fetch` with descriptive UA; the `ClaudeBot` robots ban and
> 2009–2010-frozen-content caveats documented in the module docstring.

## 6. Status log

- `2026-05-28` scout: drafted. **Verdict: DEFER / SKIP.** Service is LIVE
  (`tomsk.ru09.ru`, nginx, RU IP 176.120.26.62) but (a) panorama product is a
  frozen 2009–2010 spot-panorama set on ~10 central streets; (b) the only
  coverage signal (`/ajax2/` `panopts` XML) needs a runtime-computed `do=`
  action not recoverable from the packed JS, and all probes returned 0-byte XML;
  (c) `robots.txt` bans `ClaudeBot` site-wide and panorama pages are
  `noindex,nofollow`; (d) coordinates are a custom non-georeferenced grid; (e)
  footprint is negligible at z14 and already covered by Yandex. Distinct from
  (and not as dead as) the already-skipped ru09.ru Novosibirsk / Sochi
  instances. Recommend recording in the inventory as
  `skip — live but no scrapable coverage layer (robots ClaudeBot ban; frozen
  2010 spot panoramas)`. Revive only if ru09.ru publishes a usable coverage API.
- `YYYY-MM-DD` approval: < pending — awaiting user decision >
- `YYYY-MM-DD` implement / verify: —

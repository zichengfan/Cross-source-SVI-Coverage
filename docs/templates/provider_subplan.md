# [T<tier>] Provider: <Provider name> (`<key>`)

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.
-->

## 1. Summary

One paragraph: what the provider is, its country/region, and why it is in scope
(active + scrapable; not defunct, not a re-hoster, not paid-B2B-without-viewer).

## 2. Research findings (filled by provider-scout)

- **Homepage / public viewer URL:**
- **Tier:** T1 / T2 / T3
- **Coverage endpoint(s):** URL template, HTTP method, headers, query params
- **Coordinate scheme:** web_mercator | yandex_wgs84_mercator | baidu | other
- **Zoom range / tile size / response format:**
- **Auth:** none | token | cookie — how obtained, `.env` key name
- **Presence rule:** how a response is read to decide "imagery exists here"
- **robots.txt / ToS notes; observed rate limit:**
- **Known quirks / gotchas:**

## 3. Test plan (write these FIRST — red before green)

- [ ] `test_<key>_tile_url_build` — URL template fills correctly for sample z/x/y
- [ ] `test_<key>_decode_*` — response fixture decodes to expected presence
- [ ] `test_<key>_registers` — module self-registers in `PROVIDERS`
- [ ] <provider-specific: coordinate scheme, empty-tile, auth header, ...>
- Fixtures: small recorded response samples under `tests/fixtures/<key>/`

## 4. Implementation subplan (steps for the implementer — TDD)

- [ ] Source kind: `<existing kind>` | NEW kind `<name>` (separate foundation PR first)
- [ ] Write the §3 tests first; confirm they fail (red)
- [ ] Add `src/coverage_acquisition/providers/<key>.py` (`ProviderDefinition`)
- [ ] Implement until the §3 tests pass (green); refactor
- [ ] Pilot fetch: bbox `<min_lon> <min_lat> <max_lon> <max_lat>` (`<pilot city>`)
- [ ] Rasterize the pilot area to a z14 COG; sanity-check
- [ ] Two-pass full extent: pass-1 region bbox `<...>` at discovery zoom `<z>`
- [ ] Update the STAC item; update the inventory status

## 5. Acceptance criteria (checked by provider-verifier)

- All §3 tests pass; module imports & self-registers; CI smoke test passes
- Pilot tiles fetch & decode; coverage lands on roads/land (not ocean)
- z14 COG is valid, CRS EPSG:3857, `uint8`, covered pixels > 0
- Fetches via `polite.polite_fetch`; descriptive User-Agent; ToS caveats documented

## 6. Status log

- `YYYY-MM-DD` scout: drafted.
- `YYYY-MM-DD` approval: < pending | approved by user | revisions requested >
- `YYYY-MM-DD` implement / verify: notes appended here.

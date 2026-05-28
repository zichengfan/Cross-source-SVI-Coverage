# [T3] Provider: Mappls RealView (`mappls`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER / DROP. Mappls RealView is India's
first-party 360° street imagery service (MapmyIndia / CE Info Systems), and
the imagery itself is real and pan-India. BUT the coverage layer is **not
publicly scrapable**: there is no anonymous coverage tile/JSON endpoint. The
consumer viewer at `https://www.mappls.com/realview` renders RealView only
through the Mappls Web Maps SDK (`sdk.mappls.com`), which is OAuth2-token
gated (returns HTTP 401 without a token), AND the consumer site additionally
gates RealView behind a **server-side login + per-account approval +
3-minute/day usage cap** (`userAuth?CallRealView` → `message:"approved"` only
for logged-in/approved accounts). The developer RealView API requires a
registered Mappls Console API key (OAuth2, 24h access tokens) and is a
licensed/metered product. The Mappls Terms & Conditions explicitly forbid
reverse engineering, caching "to avoid paying fees", and building products on
MMI data without paying. Harvesting the coverage layer would therefore
require credentials and would violate ToS. No issue / branch / code should be
created now. See §2 for the evidence and §7 for the conditional restart plan.
-->

## 1. Summary

Mappls RealView (`https://about.mappls.com/realview/`) is the 360° street-level
imagery service of **Mappls**, the consumer brand of **MapmyIndia / CE Info
Systems Ltd.**, India's home-grown mapping company. Launched July 2022 and
positioned as India's "first and only" indigenous street imagery service (an
Indian alternative to Google Street View), RealView is a genuine first-party
panorama dataset: MapmyIndia advertises a repository of 400 million+ geo-tagged
360° panoramas, of which a subset (~100,000 km across hundreds of cities and
highways — Greater Mumbai, Bengaluru, Delhi NCR, Pune, Hyderabad, Chennai,
Jaipur, Ahmedabad, Goa, etc.) is exposed in the free consumer viewer. As
first-party, active, India-wide imagery it is squarely *in topical scope* for
the database (`docs/PLAN.md` §2 lists `mappls` as a T3 candidate, and §13 flags
it as a likely gated provider).

**However, scouting concludes Mappls RealView should be DEFERRED / DROPPED.**
The *coverage layer* (where panoramas exist) is not served through any
anonymous, public endpoint. It is rendered inside a token-gated SDK, the
consumer viewer adds a login + approval + daily-time-cap gate on top, the
developer API is a licensed OAuth2 product, and the ToS forbid automated
extraction and cache-to-avoid-fees. There is no scrapable coverage surface
that does not require credentials or breach ToS. See §2 for evidence.

## 2. Research findings (filled by provider-scout)

### Verdict: coverage layer is SDK-token-gated + login/approval-gated + ToS-prohibited — DEFER / DROP

Applying the standard scouting priority (rendered raster overlay → vector
tile layer → coverage JSON / point-probe API → discovery-probable embed):

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NONE
   reachable anonymously.** The basemap and all overlays (including the
   RealView coverage highlight) are served by the Mappls Web Maps SDK style
   endpoint `https://sdk.mappls.com/map/vapi/getStyles/`, which returns
   **HTTP 401** for any request without a valid OAuth2 token (verified:
   `HTTP/2 401`, `r: rq`, nginx). No anonymous tile URL was found.
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NONE found.** The
   coverage geometry ("highlighted coverage" the user clicks) is drawn by the
   SDK's `map.realview(true)` call; no `.pbf`/MVT or vector source URL is
   present in the consumer bundle — it lives behind the gated SDK.
3. **Coverage JSON / point-probe API (`kind="coverage_json"` / `json_api`)?
   — GATED.** The only coverage-related request the consumer page issues is
   the **authorization** call, not a coverage query:
   `POST https://www.mappls.com/userAuth?CallRealView` with an obfuscated
   body `en.code({'mamth':'CallRealView','attmpt':attempt})`. Anonymously this
   returns the **login-shell HTML** (HTTP 200 but the marketing/login page),
   never a `message:"approved"` JSON. The panorama/coverage data endpoints are
   internal to the gated SDK and were never exposed.
4. **A discovery-probeable embed/iframe? — NO.** RealView is only reachable
   through the gated SDK widget; there is no public per-tile or per-bbox
   coverage embed.

- **Homepage / public viewer URL:**
  - Product / marketing: `https://about.mappls.com/realview/`,
    `https://about.mappls.com/api/realview-api/`.
  - Consumer viewer / "live demo": `https://www.mappls.com/realview`
    (the toggle lives in the main map app `https://www.mappls.com/`).
  - Developer docs: `https://github.com/mappls-api/mappls-web-maps-js`
    (`docs/V3.0/RealView.md` — docs only, no SDK source committed).
  - Console / token issuance: `https://auth.mappls.com/console`,
    `https://apis.mappls.com/`, OAuth2 token-generation API.
  - Tier: **T3** ("likely / unverified / gated" in `docs/PLAN.md` §2;
    inventory flags it "likely login-gated API").

- **How the viewer was investigated.** `https://www.mappls.com/realview` is
  served behind AWS CloudFront and sets a `PHPSESSID` cookie; an
  unauthenticated GET returns a **login/marketing shell** (~89 KB HTML), not
  the live map. The map application logic is the bundle
  `https://www.mappls.com/js/?386.js` (~899 KB), which *was* fetchable and
  read directly. It contains the RealView toggle wiring; the actual rendering
  is delegated to the Mappls Web Maps SDK on `sdk.mappls.com`.

- **Coverage endpoint(s):** None public. Load-bearing findings from the
  consumer bundle `https://www.mappls.com/js/?386.js`:
  - The RealView toggle calls into the SDK:
    `map.realview(true,function(d){ ... if(d=='wrong map') {...} })`. The
    notify text confirms a *visual* coverage layer exists in the viewer —
    *"RealView lets you see 360 degree panoramas of places & roads. Zoom,
    pan, look for and then click on the highlighted coverage."* — but that
    highlight is drawn by the gated SDK, not from an anonymous endpoint.
  - **Access gate** (`call_feedbackfrm`): the viewer POSTs to
    `userAuth?CallRealView` and only enables RealView when the JSON response
    has `message == "approved"` AND `decode.module` contains `"Realview"`:
    ```js
    xhr=$.post('userAuth?CallRealView', en.code({'mamth':'CallRealView','attmpt':attempt}), function (data){
      var decode = JSON.parse(data);
      ...
      if(attempt && decode.message=="approved" && decode.module.indexOf("Realview")!=-1){ $('#realv_trig').show(); }
      else { map.realview=function(){} }                       // ← RealView disabled outright if not approved
      if(!attempt && access_module && access_module.indexOf("Unlimited_Time")==-1){
        show_error("You've reached the daily usage limit of 3 minute. Your request for the extension is still pending for approval.", ...);
      }
    });
    ```
    i.e. RealView in the consumer viewer requires (a) login, (b) server-side
    approval of the `Realview` module for that account, and (c) is capped at
    **3 minutes per day** unless the account is granted `Unlimited_Time`. A
    scraper cannot satisfy this without registered credentials.
  - SDK style/tile origin `https://sdk.mappls.com/map/vapi/getStyles/` →
    **HTTP 401** without a token (verified). The basemap is added via
    `map.addTile({tiles: dy_urls})` where `dy_urls` is delivered only after
    SDK auth.
  - Developer RealView API: enabled per-key in the Mappls API Console;
    OAuth2 access tokens (valid 24h) via the Token Generation API; usage is
    licensed/metered (freemium with paid tiers).

- **Coordinate scheme:** N/A for harvesting. The SDK is a MapLibre-GL-based
  web-mercator viewer (`maplibregl-*` classes present), so the underlying
  grid is standard web mercator — but no anonymous tiles are reachable to
  fetch on that grid.

- **Zoom range / tile size / response format:** Unknown / inaccessible. The
  coverage highlight and panorama metadata are produced by the gated SDK;
  format never observed. (If ever opened, MapLibre web-mercator z0–~z22 with
  256/512 px tiles would be expected.)

- **Auth:** **REQUIRED, two layers.**
  1. SDK layer — OAuth2 bearer token from `auth.mappls.com` / `apis.mappls.com`
     (`sdk.mappls.com` 401s without it). On the consumer site this token is
     minted server-side for a logged-in session (the page reads it via
     `getToken()` → `window.Native.getAccessToken()` in-app, or a
     session-bound web token); it is **not** an anonymous bootstrap token a
     scraper can mint.
  2. Consumer RealView layer — additionally requires login + the `Realview`
     module being `approved` for the account, with a 3-min/day cap.
  No `.env` key is proposed because there is no credential-free path; a
  developer key (`MAPPLS_CLIENT_ID` / `MAPPLS_CLIENT_SECRET` / `MAPPLS_API_KEY`)
  would be the only legal route and is out of scope (licensed/paid, ToS-bound).

- **Presence rule:** Not determinable from any public response — there is no
  anonymous coverage response to read.

- **robots.txt / ToS notes; observed rate limit:**
  - `https://www.mappls.com/robots.txt` returns the **login-shell HTML**, not
    a real robots policy (soft-200, `content-type: text/html`) — i.e. there is
    no machine-readable allow rule, and the absence of a robots allowlist does
    not grant permission given the explicit ToS prohibitions below.
  - **Terms & Conditions** (`https://about.mappls.com/api/terms-&-conditions`)
    explicitly prohibit, among others: *"decipher, decompile, disassemble,
    reverse engineer, create derivative product or otherwise attempt to derive
    any source code or content from the MMI Products"*; *"create copies of MMI
    Products in the form of Cache to avoid paying 'fees' to Mappls"*; and
    *"use MMI Products to build commercial applications and products without
    paying a fee"*. The grant is a *"non-exclusive, non-assignable,
    revocable limited license"* contingent on proper authentication.
  - Observed rate limit: N/A (no anonymous endpoint to measure). The consumer
    app self-imposes the 3-minute/day RealView cap noted above.

- **Known quirks / gotchas:**
  - RealView imagery is genuinely first-party (not a Google re-host), so it is
    *worth* capturing if access is ever granted — the blocker is access, not
    scope.
  - The consumer bundle obfuscates request bodies (`en.code(...)`, `atob(...)`
    handlers), and key map-style/data URLs are delivered post-auth, so even a
    logged-in HAR capture would need careful token handling.
  - Two independent gates (SDK OAuth2 + consumer login/approval/quota) means
    even a registered consumer login is insufficient for bulk coverage harvest.

## 3. Test plan (write these FIRST — red before green)

**Not applicable while the verdict is DEFER / DROP.** No provider module is to
be written, so there are no tests to author now. The conditional test plan
below applies *only if* §7's restart conditions are ever met (a public,
credential-free, ToS-permitted RealView coverage layer is confirmed):

- [ ] `test_mappls_tile_url_build` — coverage tile/JSON URL template fills for
      a sample z/x/y (or bbox) once a real anonymous endpoint exists.
- [ ] `test_mappls_decode_present` / `_empty` — recorded coverage-response
      fixtures decode to presence / absence.
- [ ] `test_mappls_registers` — module self-registers in `PROVIDERS`.
- [ ] `test_mappls_auth_header` — if a documented, license-permitted token is
      used, the fetch attaches it correctly (and the key is read from `.env`).
- Fixtures: small recorded coverage samples under `tests/fixtures/mappls/`
  (only collectable once a permitted endpoint exists).

## 4. Implementation subplan (steps for the implementer — TDD)

**Do not implement.** Verdict is DEFER / DROP. The steps below are the
conditional plan that would apply only after §7's restart conditions are met
and a fresh human approval is obtained:

- [ ] Re-scout to confirm a public, credential-free, ToS-permitted RealView
      coverage endpoint (raster tiles, MVT, or coverage JSON) actually exists.
- [ ] Source kind: most likely `vector_mvt` or `coverage_json` (web-mercator
      MapLibre viewer) — confirm against the real response; no NEW kind expected.
- [ ] Write the §3 tests first; confirm they fail (red).
- [ ] Add `src/coverage_acquisition/providers/mappls.py` (`ProviderDefinition`),
      fetching via `polite.polite_fetch` with a descriptive UA, documenting the
      ToS caveat in the module docstring.
- [ ] Pilot fetch: **central Delhi** bbox `77.20 28.58 77.25 28.63`
      (Connaught Place / India Gate corridor — dense RealView coverage). Backup
      pilot: **Bengaluru** bbox `77.58 12.96 77.62 13.00` (MG Road / Cubbon Park).
- [ ] Rasterize the pilot area to a z14 COG; sanity-check coverage lands on
      Delhi/Bengaluru roads, not ocean.
- [ ] Two-pass full extent: pass-1 region bbox `68.0 6.0 98.0 37.5`
      (India mainland incl. NE) at discovery zoom `z9`–`z10`, then z14 fetch
      only where coverage was seen.
- [ ] Update the STAC item; update the inventory status.
- [ ] Candidate source-zoom range (if ever opened): **z9 (discovery) → z14
      (analysis)**, web mercator.

## 5. Acceptance criteria (checked by provider-verifier)

**Deferred — not gating any merge now.** If restarted: all §3 tests pass;
module imports & self-registers; CI smoke test passes; pilot tiles fetch &
decode; coverage lands on Indian roads/land (not ocean); z14 COG is valid,
CRS EPSG:3857, `uint8`, covered pixels > 0; fetches via `polite.polite_fetch`
with descriptive UA; **ToS caveat and any license/key requirement documented
in the module docstring**, and access shown to be permitted before any
full-extent scrape.

## 6. Status log

- `2026-05-28` scout: drafted. **Verdict DEFER / DROP.** Evidence: consumer
  bundle `www.mappls.com/js/?386.js` gates RealView behind
  `userAuth?CallRealView` (login + `Realview` module approval + 3-min/day cap);
  SDK style endpoint `sdk.mappls.com/map/vapi/getStyles/` returns HTTP 401
  without an OAuth2 token; developer RealView API is a licensed OAuth2 product
  (key from `auth.mappls.com/console`); `mappls.com/robots.txt` is a soft-200
  login shell (no allowlist); ToS forbid reverse engineering, cache-to-avoid-
  fees, and unlicensed product building. No anonymous coverage tile/JSON
  endpoint exists. Imagery is genuine first-party (in topical scope) — the
  blocker is access + ToS, not provider quality.
- `YYYY-MM-DD` approval: < pending — awaiting user decision: DEFER/DROP vs.
  pursue a licensed Mappls Console key (out of current scope) >
- `YYYY-MM-DD` implement / verify: n/a (deferred).

## 7. Conditional restart conditions

Reconsider `mappls` only if one of these becomes true (each needs fresh human
approval before any code):

1. Mappls publishes (or is observed to serve) a **public, credential-free**
   RealView coverage layer — e.g. an anonymous vector-tile or coverage-JSON
   endpoint exposing where panoramas exist — that does not require login and is
   not disabled by the `userAuth?CallRealView` gate.
2. The project decides to acquire and budget a **licensed Mappls Console API
   key** and confirms the license terms permit deriving and publishing a
   binary coverage raster (this is a paid/ToS-bound path, currently out of
   scope per `CLAUDE.md`'s "skip paid-B2B" posture for the coverage-harvest
   use case; would need explicit sign-off).
3. Mappls' Terms & Conditions are revised to permit automated coverage
   extraction / caching for non-commercial research.

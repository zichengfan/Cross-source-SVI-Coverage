# [T3] Provider: EGmedia (`egmedia`) — RECOMMEND DEFER / DROP

<!--
This file is the provider's implementation subplan AND its GitHub issue body.
provider-scout fills it. It must be complete enough to implement the provider
from this file alone. It requires USER APPROVAL before any issue/branch/code.

SCOUT VERDICT (2026-05-28): DEFER / DROP. `egmedia` is not a first-party
street-level imagery coverage provider, and in any case no longer exists as a
live service. Two distinct things hide behind the inventory's thin
"egmedia / Sweden / unverified" entry, and neither is in scope:

  1. The literal domain `egmedia.se`, which the inventory copied (verbatim,
     down to the "10 cm accuracy" phrasing) from one uncritical sentence in
     Wikipedia's "List of street view services". That domain was a small
     GÄVLE-BASED PHOTOGRAPHY / MEDIA STUDIO ("EGmedia", Andreas Jonsson,
     Södra Kungsgatan 40b, 802 50 Gävle), whose street-level work was as a
     "Google Street View | Trusted" photographer — i.e. they shot 360 business
     tours that are PUBLISHED INTO GOOGLE'S Street View, not an independent
     coverage layer. The domain is now DEAD: it resolves NXDOMAIN today, was a
     Loopia "parked" page by 2018, and a "domain for sale" page by 2020.

  2. The actual large-area Swedish street-level imagery the Wikipedia sentence
     refers to (Gothenburg/Stockholm/Gävle/Malmö, "10 cm accuracy") is
     CYCLOMEDIA imagery, historically distributed in the Nordics by BLOM —
     a PAID-B2B product with no public anonymous viewer. Out of scope per
     CLAUDE.md ("Skip … re-hosters … paid-B2B-only providers with no public
     viewer"), and already represented in the project's narrow CycloMedia
     exception only via `cyclomedia_phila` (the free Philadelphia viewer).

There is no public, first-party, scrapable COVERAGE layer to harvest for
`egmedia` under either interpretation. This subplan documents the full
investigation, what could and could not be confirmed, and the conditions
under which a re-scout would ever be warranted. No issue / branch / code
should be created now.
-->

## 1. Summary

The inventory entry `egmedia` ("Sweden", "unverified") is thin and, on
investigation, conflates two unrelated things — neither of which is an
in-scope street-level imagery (SVI) coverage provider:

- **`egmedia.se` itself** was a small **photography / media studio in Gävle,
  Sweden** ("EGmedia", contact Andreas Jonsson, Södra Kungsgatan 40b, 802 50
  Gävle; `info@egmedia.se`). Its self-described business areas (from its own
  archived Joomla site) were *"virtuella turer (panorama), flygfoto/film,
  fotografering och webbdesign"* and prominently **"Google Street View |
  Trusted"** — meaning it was a Google-certified photographer that produced
  360° business-interior tours **published into Google's** Street View
  (its portfolio reads "GSV - Baravara - Gävle", "GSV - Bilhörnan i
  Sandviken", "Exempel Google maps", "Exempel Google sök"). It never operated
  an independent first-party SVI coverage map. The domain is now defunct —
  NXDOMAIN as of the scout date, a Loopia *parked* page in 2018, and a
  *"domain for sale"* page in 2020.

- **The large-area Swedish street imagery** that Wikipedia's "List of street
  view services" attaches to the name (Gothenburg, Stockholm, Gävle, Malmö,
  "10 cm accuracy") is **CycloMedia** imagery, historically distributed in the
  Nordic countries by **Blom** under a reseller agreement. CycloMedia is a
  **paid-B2B** product with no public anonymous viewer (the project's only
  sanctioned CycloMedia slice is the narrow free Philadelphia viewer,
  `cyclomedia_phila`). Out of scope per `CLAUDE.md`.

Recommendation: **DEFER / DROP** and mark the inventory row accordingly. See
§2 for evidence and §7 for the recommendation.

## 2. Research findings (filled by provider-scout)

### Verdict: not a first-party SVI coverage provider, and defunct — DEFER / DROP

Applying the standard scouting priority in order:

1. **Rendered coverage-overlay raster tile layer (`kind="raster"`)? — NO.**
2. **Vector tile coverage layer (`kind="vector_mvt"`)? — NO.**
3. **Coverage JSON / point-probe API (`coverage_json` / `json_api`)? — NO.**
4. **A panorama viewer with an embed/iframe to discovery-probe? — NO** live
   viewer of any kind exists; the domain does not resolve.

- **Identity disambiguation (the FIRST task):** The candidate interpretations
  posed in the brief were (a) "EG Media" Scandinavian media/mapping company;
  (b) a Sweden/Denmark aerial/street imagery provider; (c) the EG A/S software
  group. Evidence below shows the inventory's `egmedia` is **(a-adjacent but
  much smaller): a single-studio Swedish photography agency, `egmedia.se`**, and
  is unrelated to the EG A/S group (interpretation c). Distinct unrelated
  same-name entities were also found and ruled out: `egmedia.net` (a German
  *werbeagentur*), `egmedia.com` (a strategy/"sustainable growth" consultancy,
  live on Cloudflare), and an `egmedia.myspreadshop.de` merch shop — none are
  SVI providers.

- **Homepage / public viewer URL:** `http://www.egmedia.se/` (and
  `egmedia.se`). **Dead.** No street-view viewer URL ever existed; the site was
  a Joomla brochure site, later a parking page.

- **Tier:** **T3** ("likely / unverified / gated" per `docs/PLAN.md` §2 and
  `data/external/street_view_providers.xlsx`).

- **How the provider was investigated.** Live DNS + the Internet Archive
  Wayback CDX/`id_` raw snapshots were used (the live domain no longer exists,
  so the archive is the only source of its historical content). WebSearch was
  used to disambiguate the name and to source the CycloMedia/Blom lineage.

- **Live + archival probe results (2026-05-28):**

  | Probe | Result | Meaning |
  | --- | --- | --- |
  | `nslookup egmedia.se` / `www.egmedia.se` | **NXDOMAIN** (control domains resolve fine) | domain is gone; no live service |
  | Wayback CDX `egmedia.se` | snapshots **2016 → 2020-08-30 only**, then none | service was wound down years ago |
  | Wayback `2018-07-26` homepage | `<title>Parked at Loopia</title>` | parked, no content, by 2018 |
  | Wayback `2020-08-30` homepage | `<title>egmedia.se \| domain for sale</title>` ("Domain Brokers Sweden … this domain is AVAILABLE for purchase") | domain abandoned, listed for sale |
  | Wayback `2016-10-22` `index.php/sv` | Joomla "derfotograf" template; title *"EGmedia.se - Moderna medier, Google Business View … Google Street View Trusted"*; team page (Andreas / Jimmy / Thomas), Gävle address, portfolio "GSV - … - Gävle / Sandviken", "Google POI", "Exempel Google maps / Google sök" | a photography studio doing **Google** GSV-Trusted / Business-View work — imagery lives on Google, not a first-party coverage layer |

- **Wikipedia / inventory provenance.** Wikipedia's "List of street view
  services" (Sweden section) states verbatim: *"EGmedia.se and CycloMedia
  Technology BV offers actual street views of the largest cities in Sweden e.g.
  Gothenburg, Stockholm, Gävle and Malmö on pixel level with 10 cm accuracy."*
  The inventory's `egmedia` row is a direct copy of this single sentence. The
  sentence conflates the small Gävle studio's name with CycloMedia's product;
  the "10 cm accuracy / largest cities" claim describes **CycloMedia**, not the
  studio.

- **CycloMedia / Blom lineage (the in-the-cities imagery).** Blom ASA and
  CycloMedia signed a reseller agreement (after a Nordic pilot) under which
  Blom was the exclusive Nordic provider of CycloMedia's street-level imagery.
  CycloMedia is **paid-B2B** with no public anonymous viewer — out of scope per
  `CLAUDE.md`. This is the same Blom/CycloMedia lineage flagged by the sibling
  Eniro/Krak scouts for retired Nordic street view.

- **Coverage endpoint(s):** **None.** No raster, MVT, coverage-JSON, or
  point-probe endpoint exists or ever existed for a first-party `egmedia`
  coverage layer. (Its GSV-Trusted tours are inside Google Street View, covered
  by the existing `svmap_google` provider, not by a separate `egmedia` source.)
- **Coordinate scheme:** N/A — no coverage service.
- **Zoom range / tile size / response format:** N/A.
- **Auth:** N/A (no service to authenticate against).
- **Presence rule:** N/A.

- **robots.txt / ToS notes; observed rate limit:** `egmedia.se` does not
  resolve, so there is no live `robots.txt` or ToS to read. The historical
  imagery routes either to **Google** (GSV-Trusted business tours — governed by
  Google's terms, already handled via `svmap_google`) or to **CycloMedia**
  (paid-B2B, no public viewer). No polite-scraping posture is applicable
  because there is nothing to scrape.

- **Known quirks / gotchas (for any future re-scout):**
  - Do not confuse `egmedia.se` (dead Swedish photo studio) with the unrelated
    live `egmedia.com` (strategy consultancy) or `egmedia.net` (German ad
    agency) — none are SVI providers.
  - The "10 cm / largest Swedish cities" claim is **CycloMedia's**, not the
    studio's; treat any inventory text mentioning CycloMedia as an out-of-scope
    paid-B2B signal.
  - The studio's "street view" was **Google Street View | Trusted** (interior
    business 360 tours pushed into Google) — already inside the `svmap_google`
    coverage, not a separate source.

## 3. Test plan (write these FIRST — red before green)

**Not applicable — no provider module will be created.** There is no live,
first-party, scrapable coverage endpoint to characterise, decode, or test. If
a re-scout ever overturns this verdict (see §7), the standard test plan
(URL-build, fixture decode, self-registration, coordinate-scheme,
empty-response, auth-header) would be authored at that time against the newly
discovered endpoint.

## 4. Implementation subplan (steps for the implementer — TDD)

**Not applicable — DEFER / DROP.** No source kind is selected, no
`providers/egmedia.py` is to be written, no pilot/discovery bbox is proposed
(there is no coverage to pilot). Instead:

- [ ] Mark the `egmedia` row in `data/external/street_view_providers.xlsx`
      as **DROP** with reason: *"not a first-party SVI provider; defunct Gävle
      photo studio (Google GSV-Trusted) + Wikipedia conflation with CycloMedia
      (paid-B2B, Blom-distributed). Domain NXDOMAIN."*
- [ ] No issue, no branch, no code.

## 5. Acceptance criteria (checked by provider-verifier)

**Not applicable** — no module ships. The "acceptance" of this scout is that
the DEFER/DROP recommendation and its evidence (§2) are accepted at the human
approval gate and the inventory row is annotated.

## 6. Status log

- `2026-05-28` scout: drafted. **Verdict: DEFER / DROP.** Confirmed `egmedia.se`
  was a small Gävle photography studio (Google GSV-Trusted / Business-View),
  now defunct (NXDOMAIN; parked 2018; for-sale 2020). Confirmed the inventory
  text is a verbatim copy of one Wikipedia sentence that conflates the studio
  with CycloMedia (paid-B2B, Blom-distributed in the Nordics) — out of scope.
  No first-party scrapable coverage layer exists under any interpretation.
- `2026-05-28` approval: **pending user review.**

## 7. Recommendation & conditions for re-scout

**Recommendation: DEFER / DROP `egmedia`.** Reasons, in order of decisiveness:

1. **Defunct.** `egmedia.se` does not resolve (NXDOMAIN); it was already a
   parked/for-sale domain by 2018–2020. There is no live service of any kind.
2. **Not a first-party SVI coverage provider.** When live, `egmedia.se` was a
   small Gävle photography studio whose "street view" output was **Google
   Street View | Trusted** business tours — imagery hosted by Google and
   already within `svmap_google`'s coverage, not an independent layer.
3. **The cities-scale imagery is paid-B2B.** The "Gothenburg/Stockholm/Gävle/
   Malmö, 10 cm" claim describes **CycloMedia** (Blom-distributed in the
   Nordics), explicitly out of scope per `CLAUDE.md` except for the narrow free
   `cyclomedia_phila` viewer.

A re-scout would only be warranted if **all** of the following became true:
the `egmedia.se` name were revived as a **live, first-party** SVI service with
its **own public, anonymous coverage viewer** (tile/MVT/JSON endpoint), serving
imagery it owns (not Google re-host, not CycloMedia paid-B2B). None of these
hold today, and there is no indication they will.

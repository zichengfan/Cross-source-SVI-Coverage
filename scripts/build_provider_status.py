"""Build the consolidated provider-status inventory.

Reads the source inventory `data/external/street_view_providers.xlsx` (the
untouched input that drives the tier list) and emits a derived report
`data/processed/provider_status.xlsx` that records, for every provider, whether
it was implemented and *why* / why not.

Scope: every row of the source inventory PLUS the pre-existing global reference
providers that are registered in the codebase but not listed in the inventory
(Apple Look Around, Baidu, Google/svmap, KartaView, Mapillary, Panoramax,
Yandex).

Status taxonomy:
- implemented  : a registered provider module with a working coverage scraper.
- reference    : pre-existing global provider already in the codebase.
- paused       : implemented but full-extent scrape held pending a decision.
- deferred     : scouted, conditionally implementable later (blocker is external
                 / time-bound: outage, IP-block, token/egress, ToS gate).
- dropped      : scouted and ruled out (defunct, re-host, no coverage layer).
- skipped      : not actively scouted; ruled out from the inventory + project
                 rules (defunct / paid-B2B-only / Google-rehost).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "data" / "external" / "street_view_providers.xlsx"
OUT = REPO / "data" / "processed" / "provider_status.xlsx"

# Keyed by the source inventory's Provider string. Each entry:
# (key, status, tier, source_kind, reference, reason)
# key/source_kind/reference are "" when not applicable.
INVENTORY_STATUS: dict[str, tuple[str, str, str, str, str, str]] = {
    "Carte.ma": ("carte_ma", "deferred", "T2", "", "subplan docs/providers/carte_ma.md (PR #2)",
                 "Real first-party Moroccan SVI with a scrapable tiled coverage layer, but the whole "
                 "service has returned HTTP 500 on every path since ~April 2025. Endpoints verified from "
                 "Wayback; implementable if/when it returns online."),
    "Moriwo": ("", "skipped", "", "", "",
               "Dead link per Wikipedia; defunct. Not scouted."),
    "Barikoi": ("barikoi", "implemented", "T2", "vector_mvt", "PR #35",
                "ThirdEye360 MVT coverage layer; implemented and merged."),
    "Tencent Maps": ("tencent", "implemented", "T2", "tencent_mobile_street", "PRs #41/#43",
                     "Documented TXVN street-view tile scheme; implemented and merged."),
    "MapmyIndia / Mappls": ("mappls", "deferred", "T3", "", "subplan docs/providers/mappls.md (PR #7)",
                            "Genuine first-party RealView 360, but the coverage layer is entirely "
                            "token/login/OAuth-gated (SDK 401 anonymously) and ToS forbid scraping/caching. "
                            "Would need a paid Console key."),
    "Tehran municipality": ("", "skipped", "", "", "",
                            "Dead link per Wikipedia; likely defunct. Not scouted."),
    "myIsfahan": ("myisfahan", "deferred", "T3", "", "subplan docs/providers/myisfahan.md (PR #7)",
                  "Real first-party municipal Shahrnama viewer + coverage probe reverse-engineered from "
                  "archives, but every *.isfahan.ir host TCP-times-out from our network (IP block) and the "
                  "wire format was never archived. Needs an Iran-accepting egress."),
    "Kuwait Finder": ("kuwait_finder", "deferred", "T3", "", "subplan docs/providers/kuwait_finder.md (PR #7)",
                      "Not app-only as the inventory implied: a real PACI web endpoint (self-hosted "
                      "Mapillary-v3 GeoJSON probe) exists and was reverse-engineered, first-party LiDAR gov "
                      "data. But *.paci.gov.kw is geo-fenced/WAF-blocked from our network and the probe is "
                      "token-gated. Needs Kuwait egress + a config.json capture."),
    "Urban Explorer": ("", "skipped", "", "", "",
                       "Paid B2B, unlikely freely scrapeable; unverified. Not scouted."),
    "Kakao Maps": ("kakao", "paused", "T1", "raster", "PRs #6/#24 (fork)",
                   "Implemented as a raster coverage-overlay provider (EPSG:5181). Full-extent scrape "
                   "PAUSED pending a collaborator decision on source zoom + the Kakao L7 question."),
    "Naver Maps": ("naver", "paused", "T1", "raster", "PRs #9/#26 (fork)",
                   "Implemented as a raster coverage-overlay provider. Full-extent scrape PAUSED pending "
                   "the same source-zoom decision as kakao/mapy."),
    "DPRK 360": ("dprk360", "implemented", "T2", "coverage_json", "PR #40",
                 "Fixed-point static panoramas; implemented and merged."),
    "MapJack": ("mapjack", "implemented", "T3", "raster", "PR #10",
                "Rebuilt 2025; web-mercator XYZ raster GIF coverage overlay, no auth. Implemented + "
                "verified (Chiang Mai pilot). Stores only a derived binary-presence raster (ToS forbids "
                "bulk imagery/data feeds). Note: the inventory lists MapJack twice (Thailand + USA); same "
                "service, both covered."),
    "MappointAsia": ("", "skipped", "", "", "",
                     "Custom/commercial B2B; not a public first-party coverage source. Not scouted."),
    "Streetview.vn": ("streetview_vn", "implemented", "T2", "vector_mvt", "PR #36",
                      "NDAVIEW MVT coverage layer; implemented and merged."),
    "ASIG": ("asig", "implemented", "T3", "vector_geojson", "PR #11 (needs foundation #6)",
             "National first-party StreetView 360; unauthenticated per-tile GeoJSON coverage. Implemented "
             "+ verified (Tirana pilot, 11,464 points). Needed the new vector_geojson source kind (#6)."),
    "CycloMedia": ("", "skipped", "", "", "",
                   "Paid-B2B vendor with no public first-party coverage feed; out of scope. The only "
                   "sanctioned slice was the free Philadelphia viewer (see cyclomedia_phila), which was "
                   "itself dropped. Appears 6x in the inventory (BE/DK/DE/NL/NO/SE) — all skipped."),
    "Geckomatics": ("", "skipped", "", "", "",
                    "B2B / paid mapping-data vendor; no public coverage layer. Not scouted."),
    "Rutmap": ("", "skipped", "", "", "",
               "Unknown/unverified, no URL in source; insufficient signal. Not scouted."),
    "BusinessView": ("", "skipped", "", "", "",
                     "Imagery hosted on Google Maps (re-hoster), not a first-party coverage layer. Out of scope."),
    "VisionTech": ("", "skipped", "", "", "",
                   "Imagery hosted on Google Maps (re-hoster), not first-party. Out of scope."),
    "Mapy.cz / Mapy.com": ("mapy", "paused", "T1", "raster", "PR #27 (fork)",
                           "Implemented as a raster coverage-overlay provider. Full-extent scrape PAUSED "
                           "pending the same source-zoom decision as kakao/naver."),
    "Krak": ("krak", "dropped", "T3", "", "subplan docs/providers/krak.md (PR #5)",
             "Shares Eniro's streetview.eniro.com backend, now decommissioned (probe API 404s, S3 bucket "
             "deleted); was a CycloMedia re-host anyway. Out of scope."),
    "COWI DDG": ("", "skipped", "", "", "",
                 "Paid B2B; no public first-party coverage. Not scouted."),
    "Mappy": ("mappy", "deferred", "T2", "", "subplan docs/providers/mappy.md (PR #2)",
              "Vendor-flagged 'obsolete'; the only coverage signal is a point-probe API returning 404 "
              "across central Paris. No coverage layer to scrape."),
    "ja.is (Já 360)": ("ja360", "deferred", "T1", "vector_mvt", "subplan docs/providers/ja360.md (PR #2)",
                       "Coverage is a clean Mapbox vector tile layer (ja360 source) — fully specced and "
                       "implementable — but the endpoint is Iceland-IP-only and blocked from our network. "
                       "Needs an Iceland egress."),
    "Position Images": ("", "skipped", "", "", "",
                        "Archive-only / defunct. Not scouted."),
    "Tuttocittà": ("tuttocitta", "dropped", "T3", "", "subplan docs/providers/tuttocitta.md (PR #4)",
                   "Relaunched April 2025 as an OSM/TomTom SPA with no panorama layer; the 2006 'Visual' "
                   "product is dead. robots.txt disallows AI crawlers; CloudFront geo-blocks to IT/EU."),
    "GjirafaPikBiz": ("gjirafa", "dropped", "T3", "", "subplan docs/providers/gjirafa.md (PR #7)",
                      "'Pamje 360' is per-business POI panoramas, not a street-level coverage layer. Site "
                      "is Cloudflare hard-blocked and robots.txt prohibits crawling."),
    "Finn.no": ("finn_no", "dropped", "T3", "", "subplan docs/providers/finn_no.md (PR #7)",
                "'Street view' is a Google Street View hand-off (re-hoster), not first-party. robots.txt "
                "explicitly bans Anthropic crawlers."),
    "ru09.ru (Tomsk)": ("ru09_tomsk", "deferred", "T3", "", "subplan docs/providers/ru09_tomsk.md (PR #7)",
                        "Live first-party KRPANO, but a frozen ~2010 set of ~10 streets (negligible at z14; "
                        "Yandex already covers Tomsk densely), unrecoverable coverage request, bespoke "
                        "non-georeferenced grid, robots.txt bans ClaudeBot."),
    "ru09.ru (Novosibirsk)": ("", "skipped", "", "", "",
                              "Archived-only / likely defunct (per PLAN §2). Same dead Eniro-style family "
                              "pattern; not separately scouted."),
    "ru09.ru (Sochi)": ("", "skipped", "", "", "",
                        "Archived-only / likely defunct (per PLAN §2). Not separately scouted."),
    "EGmedia.se": ("egmedia", "dropped", "T3", "", "subplan docs/providers/egmedia.md (PR #7)",
                   "A small Gävle photo studio (Google-GSV-Trusted; domain now dead) that the inventory "
                   "conflated with CycloMedia's paid-B2B Swedish imagery. Neither is an in-scope "
                   "first-party coverage source."),
    "Eniro Kartor": ("eniro", "dropped", "T3", "", "subplan docs/providers/eniro.md (PR #4)",
                     "Eniro retired its 'gatuvy' feature themselves (help page says so); all gatuvy URLs "
                     "301-redirect away. Historical imagery was a CycloMedia/Blom re-host (paid-B2B), out "
                     "of scope regardless."),
    "HeliEngadin": ("", "skipped", "", "", "",
                    "Niche paid acquisition service; no public coverage layer. Not scouted."),
    "GlobalVision (VideoStreetView)": ("", "skipped", "", "", "",
                                       "Likely inactive since a 2009 launch; likely defunct. Not scouted."),
    "Dunya 360": ("", "skipped", "", "", "",
                  "Archive-only (2012 snapshots); likely defunct. Not scouted."),
    "Istanbul Metropolitan Municipality": ("istanbul_ibb", "deferred", "T3", "",
                                           "subplan docs/providers/istanbul_ibb.md (PR #4)",
                                           "The viewer is a CycloMedia Street Smart iframe driven by "
                                           "AES-encrypted IBB credentials; decrypting them to drive "
                                           "CycloMedia's WFS would violate ToS (hard guardrail). The only "
                                           "public endpoint returns one random panorama. Deferred pending an "
                                           "explicit decision on sampler-mode coverage."),
    "Mapilio": ("mapilio", "implemented", "T2", "vector_mvt", "PR #32",
                "Public platform + open SDK; MVT coverage layer. Implemented and merged."),
    "Eye2eye Software": ("", "skipped", "", "", "",
                         "Likely inactive; no active URL. Not scouted."),
    "BBC Domesday Reloaded": ("", "skipped", "", "", "",
                              "Archive-only / defunct. Not scouted."),
    "EveryScape": ("", "skipped", "", "", "",
                   "Status unclear / likely inactive. Not scouted."),
    "earthmine": ("", "skipped", "", "", "",
                  "Acquired by Nokia/HERE long ago; defunct as a standalone. Not scouted."),
    "Mapplo": ("", "skipped", "", "", "",
               "Closed 2012; defunct. Not scouted."),
    "Fotocalle": ("", "skipped", "", "", "",
                  "Not working since Nov 2020; defunct. Not scouted."),
    "Publiguías Street Diving": ("", "skipped", "", "", "",
                                 "Likely inactive; no active URL. Not scouted."),
    "XYGO": ("xygo", "deferred", "T3", "", "subplan docs/providers/xygo.md (PR #4)",
             "Viewer HTML still loads but every backend host (*.neonline.cl) has been NXDOMAIN since "
             "~2019; company pivoted to GIS consulting. Original JSONP coverage endpoint reconstructed "
             "from Wayback for the revival case."),
}

# Pre-existing global reference providers (registered in the codebase, not in
# the source inventory). (key, Region, Country, Provider, source_kind)
REFERENCE_PROVIDERS = [
    ("apple_lookaround", "Global", "—", "Apple Look Around", "vector_mvt"),
    ("baidu", "Asia", "China", "Baidu Maps (Baidu Total View)", "raster"),
    ("svmap_google", "Global", "—", "Google Street View (svmap)", "raster"),
    ("kartaview", "Global", "—", "KartaView", "raster"),
    ("mapillary", "Global", "—", "Mapillary", "vector_mvt"),
    ("panoramax", "Global", "—", "Panoramax", "vector_mvt"),
    ("yandex", "Global", "Russia+", "Yandex Panorama", "raster"),
]


def main() -> None:
    src = pd.read_excel(SOURCE)
    rows = []
    for _, r in src.iterrows():
        provider = str(r["Provider"]).strip()
        key, status, tier, kind, ref, reason = INVENTORY_STATUS.get(
            provider, ("", "skipped", "", "", "", "Not triaged; no clear in-scope first-party coverage signal.")
        )
        rows.append(
            {
                "Region": r["Region"],
                "Country": r["Country"],
                "Provider": provider,
                "provider_key": key,
                "status": status,
                "tier": tier,
                "source_kind": kind,
                "reason": reason,
                "reference": ref,
                "source_URL": r["URL"],
                "inventory_reachable": r["Reachable"],
                "inventory_scrapability": r["Scrapability"],
            }
        )

    for key, region, country, provider, kind in REFERENCE_PROVIDERS:
        rows.append(
            {
                "Region": region,
                "Country": country,
                "Provider": provider,
                "provider_key": key,
                "status": "reference",
                "tier": "ref",
                "source_kind": kind,
                "reason": "Pre-existing global reference provider already implemented in the codebase "
                "(predates the tiered T1/T2/T3 rollout).",
                "reference": "pre-existing",
                "source_URL": "",
                "inventory_reachable": "",
                "inventory_scrapability": "",
            }
        )

    out_df = pd.DataFrame(rows)
    status_order = {"implemented": 0, "reference": 1, "paused": 2, "deferred": 3, "dropped": 4, "skipped": 5}
    out_df = out_df.sort_values(
        by=["status", "Region", "Country"], key=lambda s: s.map(status_order).fillna(9) if s.name == "status" else s
    ).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        out_df.to_excel(writer, index=False, sheet_name="provider_status")
        counts = out_df["status"].value_counts().rename_axis("status").reset_index(name="count")
        counts.to_excel(writer, index=False, sheet_name="summary")

    print(f"wrote {OUT} ({len(out_df)} providers)")
    print(out_df["status"].value_counts().to_string())


if __name__ == "__main__":
    main()

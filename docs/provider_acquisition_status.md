# Provider acquisition status and next actions

Last updated: 2026-08-16

Print-friendly version: [provider_acquisition_status.pdf](provider_acquisition_status.pdf)
(reproducible source: [provider_acquisition_status.tex](provider_acquisition_status.tex)).

This table is the operational source of truth for the 16 implemented coverage
acquisition paths. It distinguishes implementation, acquired data and the next
fine-scale decision. Target levels remain provisional until cross-level review
is complete.

| Provider | Acquisition path and coverage form | Current progress | Provisional fine-scale target | Next action | Operational status | Owner |
|---|---|---|---|---|---|---|
| Google Street View | sv-map Google coverage overlay; raster PNG | Global z5 discovery complete; 63,728 positive z10 cells in the 13-source analysis | z13 raster; z14 only for selected areas | Audit negative-grid recall, then freeze a bounded z13 inventory | READY / LEVEL REVIEW | — |
| Apple Look Around | LookMap layered raster, MVT and coverage JSON | Global z5 discovery complete; 20,646 positive z10 cells; public-instance bulk use is not approved | z12 MVT; z13 or z17 only where justified | Confirm an authorized or self-hosted endpoint before a fine-scale run | ACCESS-GATED / LEVEL REVIEW | — |
| Baidu | Baidu-native raster tiles with alpha-pixel reprojection | z10 discovery corrected; 2,169 positive Web z10 cells; Hong Kong and other Chinese cities rebuilt | z13 raster; z14 for focal cities | Compare z13 and z14 road retention, then freeze the native-grid inventory | READY / LEVEL REVIEW | — |
| Tencent Street View | Local PMTiles archive containing MVT lines | Archive decoded and integrated; 4,932,670 features and 10,303 decoded native-z12 tiles | Native z12 archive | Verify archive provenance and retain native geometry; no network reacquisition | COMPLETE BASELINE | — |
| Naver | Street-only `mt=ps` raster with dynamic frontend version | Complete Korea z14 inventory: 29,313 tiles, 25,289 non-empty; included in the 13-source analysis | z14 baseline; z15 to be reviewed | Compare z14 and z15 across urban, rural and minor-road samples | COMPLETE BASELINE / LEVEL REVIEW | — |
| Kakao | `PNG_RV02` raster on the reversed Kakao native grid | Complete Korea L6 inventory: 27,190 tiles, 23,524 non-empty; included | Native L6 baseline; finer adjacent levels to be reviewed | Compare L6 with finer native levels using common ground-resolution metrics | COMPLETE BASELINE / LEVEL REVIEW | — |
| KartaView | Sequence coverage raster PNG | Endpoint and zoom behaviour validated; no complete bounded inventory; not in the 13-source analysis | z13 candidate | Define candidate scope first, then compare z13 with finer supported levels | PILOT ONLY / SCOPE REVIEW / LEVEL REVIEW | — |
| Mapillary | Public overview, sequence and image MVT layers | z5 overview discovery complete; 708,399 overview points and 48,882 positive z10 cells included | z10 sequence; z11 higher-fidelity candidate | Move zoom-aware layer routing into the shared library and test z10 versus z11 | READY / LEVEL REVIEW | — |
| Streetview.vn | `sequences` MVT lines | Vietnam z8 discovery complete; 47,901 features from 78 tiles; included | z11 sequence MVT | Compare adjacent levels and prepare the full Vietnam bounded job | READY / LEVEL REVIEW | — |
| Yandex | Street-view raster on the Yandex elliptic-Mercator grid | Discovery and HTTP 204 audit complete; 2,647 positive z10 cells included | z13 raster; z14 local option | Rebuild persisted empty-state artifacts offline, then review z13 versus z14 | READY / LEVEL REVIEW | — |
| Mappls RealView | Authorized Web Maps SDK capture producing line coverage | India z10 capture complete with audited boundary waivers; 2,396 positive cells included | z13 capture | Run a deterministic negative-grid audit before choosing filtered or full-scope z13 | ACCESS-GATED / LEVEL REVIEW | — |
| MapJack | `dots_r5` alpha GIF coverage raster | Chiang Mai endpoint and pilot behaviour validated; no full bounded run; not included | z16 candidate | Confirm service scope, compare adjacent levels and define a low-rate bounded job | PILOT ONLY / LEVEL REVIEW | — |
| Barikoi ThirdEye360 | `ThirdEye360` point MVT | z14 and z16 pilot decoding succeeded; service polygons not frozen; not included | z14 candidate | Freeze supported city polygons and test point-count stability across levels | PILOT ONLY / SCOPE REVIEW / LEVEL REVIEW | — |
| Panoramax | Local GeoParquet point export with optional MVT fallback | 115,998,261-point local projection acquired and integrated; 20,261 occupied z10 cells | Native point geometry; no routine tile zoom | Reconstruct trajectories from collection, links and time fields before tile fallback | COMPLETE BASELINE | — |
| Mapilio | `map_roads_line` MVT with non-standard path order | Global z6 recovery closed at zero unresolved; 2,786 positive z10 cells included | z10 MVT candidate | Validate local geometry retention and build the positive-cell bounded queue | READY / LEVEL REVIEW | — |
| Mapy.com | Panorama-line raster with redirect-based transparent empty tiles | Complete Czechia z14 inventory: 33,663 tiles, 29,424 non-empty; included | z14 baseline; finer adjacent levels to be reviewed | Compare z14 with finer levels across urban, rural and boundary samples | COMPLETE BASELINE / LEVEL REVIEW | — |

## Status vocabulary

- **COMPLETE BASELINE** — the current baseline input is acquired and usable.
- **READY** — the implementation is available and the next job can be prepared.
- **PILOT ONLY** — only local or case-level acquisition has been validated.
- **ACCESS-GATED** — production acquisition requires authorized access.
- **LEVEL REVIEW** — the provisional target resolution must be rechecked.
- **SCOPE REVIEW** — the service or candidate extent must be frozen first.

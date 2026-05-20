# Cross-Source SVI Coverage — Master Plan

Build a **global street-level imagery (SVI) availability database**: for any place
on Earth, which providers have imagery there. This plan covers expanding from the
7 working providers to ~25 new ones, the supporting infrastructure, and the
agent/skill tooling that makes the per-provider work repeatable and parallel.

## 1. Locked decisions (from requirements interview)

| Topic | Decision |
|---|---|
| Raster value | **Binary presence** — one raster per provider; 1 = imagery exists, nodata = none |
| Resolution | **z14 web-mercator grid** (~10 m/pixel), stored as a COG pyramid |
| Capture date | Optional **separate layer** only where a provider exposes dates |
| Provider scope | **Active + scrapable, tiered** (T1/T2/T3); skip defunct, re-hosters, paid-B2B-no-viewer |
| Spatial sequencing | **Pilot city first**, then full extent |
| Extent strategy | **Two-pass discovery** — low-zoom sweep finds coverage, then z14 fetch |
| `streetlevel` lib | Adopt as a **source kind** for the providers it supports |
| Vector → raster | **Burn geometry; buffer isolated points** by ~one cell |
| Point metadata | **Kept in `data/intermediate`** as source of truth; raster is published |
| Code layout | **Per-provider Python modules**, auto-registered (conflict-free parallel work) |
| Output package | Per-provider **COG + STAC catalog** in `data/processed` |
| Re-hosters | **Skip**, note in inventory (BusinessView, VisionTech → Google re-host) |
| Gated providers | **Attempt now** (login/app-gated worked alongside the rest) |
| Scrape posture | **Polite default** — descriptive UA, throttle, robots.txt, document ToS |
| CI | **Full CI gate** — lint + unit tests + import/register/dry-run smoke test |
| Testing | **TDD** — red-green-refactor; tests precede code; every PR ships tests (see §12) |
| Git isolation | **One worktree per provider** branch |
| Codex flow | **Claude scouts + writes subplan → Codex implements + debugs** |
| Per-provider subplan | One per provider; doubles as the **GitHub issue body** |
| Approval gate | Each subplan **requires human (user) approval** before any issue/branch/code |
| Batch size | **4–6 providers concurrently** |

## 2. Provider inventory & triage

Already done (reference implementations, **do not touch**): Yandex, Google/GSV,
Apple Look Around, Baidu, Mapillary, Panoramax, KartaView.

**Skip — defunct (14):** Moriwo, Tehran municipality, Position Images,
ru09.ru Novosibirsk, ru09.ru Sochi, GlobalVision, Dunya 360, BBC Domesday
Reloaded, EveryScape, earthmine, Mapplo, Fotocalle, Publiguías, Eye2eye.

**Skip — re-hoster (2):** BusinessView.bg, VisionTech.bg (imagery is Google's;
flag in inventory as `google_rehost`).

**Skip — paid B2B, no public viewer (6):** Geckomatics, COWI DDG, Urban Explorer,
HeliEngadin, MappointAsia, Rutmap (no URL / unidentifiable).

**In scope (~25):**

| Tier | Providers (proposed `key`) |
|---|---|
| **T1** streetlevel-native | `kakao`, `naver`, `mapy`, `ja360` |
| **T2** public / documented scrapers | `tencent`, `mapilio`, `streetview_vn`, `mappy`, `barikoi`, `dprk360`, `carte_ma` |
| **T3** likely / unverified / gated | `mappls`, `krak`, `tuttocitta`, `gjirafa`, `finn_no`, `eniro`, `asig`, `egmedia`, `ru09_tomsk`, `mapjack`, `myisfahan`, `istanbul_ibb`, `xygo`, `kuwait_finder`, `cyclomedia_phila` |

CycloMedia is paid-B2B but has a free public viewer (Philadelphia
`atlas.phila.gov`); scoped narrowly as `cyclomedia_phila`.

## 3. Target data model

- **Grid:** global web-mercator, analysis zoom **z14** (~9.5 m/px at equator).
- **Per provider:** one Cloud-Optimized GeoTIFF, single band, `uint8`
  (1 = covered, 0 = checked-empty, 255 = nodata), internal overviews to ~z6.
- **Optional date layer:** second COG `*_year.tif` only where dates are exposed.
- **Index:** a **STAC catalog** in `data/processed/stac/` — one Item per provider
  with extent, scrape date, provider tier, source endpoint, ToS notes.
- **Data directory contract:**
  - `data/external/` — inputs (the provider inventory xlsx).
  - `data/raw/<key>/` — scraped tiles/responses, gitignored.
  - `data/intermediate/<key>/` — decoded point/vector data (GeoParquet),
    the re-rasterizable source of truth, gitignored.
  - `data/processed/` — per-provider COGs + STAC catalog (tracked, or DVC later).

## 4. Phase 0 — foundation (must merge to `dev` before any provider PR)

One or a few `foundation`-labelled PRs, built by Claude (not parallelized):

1. **uv project** — finalize `pyproject.toml`, `uv sync`, `.venv` (done: draft
   exists; add `streetlevel`, `rasterio`, `geopandas`, `shapely`, `pystac`,
   `rio-cogeo`, `python-dotenv`).
2. **Provider registry refactor** — split `providers.py` into
   `providers/<key>.py`; each calls `register_provider(PROVIDER)`; a registry
   module auto-discovers them on import. Existing 7 migrate as-is.
3. **Pluggable source kinds** — move per-kind fetch/decode logic into
   `source_kinds/<kind>.py`, auto-registered, so `runners.py` becomes a thin
   dispatcher. A new kind = a new file = still conflict-free. Seed kinds:
   `raster`, `vector_mvt`, `coverage_json`, plus new `streetlevel`,
   `vector_geojson`, `json_api`.
4. **Rasterization module** (`rasterize.py`) — stored tiles **or** vector
   features → z14 binary COG; buffers isolated points by ~1 cell; uses
   `rasterio`/`shapely`/`geopandas`.
5. **STAC catalog module** (`catalog.py`) — create/update the catalog.
6. **Two-pass extent runner** — low-zoom discovery sweep → z14 fetch only where
   coverage was seen.
7. **Polite-scraper utilities** — shared throttle/retry/backoff, UA, robots.txt
   check, per-provider rate config.
8. **Secrets** — `.env` (gitignored) loaded via `python-dotenv`; tokens/cookies
   never committed.
9. **CI** — `.github/workflows/ci.yml`: ruff lint, pytest, and a smoke test that
   every provider module imports, self-registers, and passes a dry-run.
10. **Repo hygiene** — `.gitignore` (`.venv/`, `data/raw/`, `data/intermediate/`,
    `__pycache__/`), GitHub issue/PR templates, labels.
11. **Test scaffolding** — `tests/` with pytest config; unit tests covering every
    foundation module (registry, source kinds, polite, geo, rasterize, catalog).
    TDD (§12) is the working discipline from this point on.

## 5. The repeatable per-provider pipeline

Every provider goes through the identical 8 steps:

1. **Scout** — `provider-scout` reverse-engineers the coverage endpoint and
   drafts the subplan `docs/providers/<key>.md` (template in §9).
2. **Human approval gate** — the user reviews the drafted subplan and approves,
   revises, or rejects it. **No issue is published, no branch created, and no
   code written before the user approves.** Scout iterates until approved.
3. **Scaffold** — `add-provider` skill publishes the approved subplan as the
   GitHub issue and creates the `provider/<key>` branch + worktree + stub module.
4. **Implement (TDD)** — Codex follows red-green-refactor: writes the unit tests
   from the subplan's test plan **first** (red), then implements
   `providers/<key>.py` until green, then refactors. See §12.
5. **Pilot** — fetch the subplan's pilot-city bbox; confirm tiles fetch/decode.
6. **Rasterize** — `rasterize-coverage` produces the z14 COG for the pilot area.
7. **Verify** — `provider-verifier` runs quality checks; pass → continue.
8. **Full extent** — two-pass discovery + z14 scrape; refresh COG + STAC; PR
   reviewed by `pr-reviewer` and CI, then merged.

Batches move through the gate together: scout drafts 4–6 subplans, the user
approves the batch, then dispatch proceeds for the approved ones only.

## 6. Subagents to build (Phase 0)

Defined as `.claude/agents/<name>.md`:

- **`provider-scout`** — *Research a provider's coverage endpoint.* Tools: WebFetch,
  WebSearch, Bash, Read, Write. Inspects the viewer, identifies the tile/API
  endpoint, headers, coordinate scheme, zoom range, auth, response format;
  fills the `docs/providers/<key>.md` spec; never writes provider code.
- **`provider-verifier`** — *QA a finished provider.* Tools: Bash, Read, Grep.
  Runs the pilot fetch + rasterization, checks tiles decode, coverage is
  geographically plausible (lands on roads/land, not ocean), COG is valid;
  emits a pass/fail report, files defects as issue comments.
- **`pr-reviewer`** — *Review a provider PR.* Tools: Bash, Read, Grep. Checks the
  fixed checklist: exactly one new provider module, no shared-file edits,
  conventions followed, throttling present, CI green, and **TDD compliance** —
  meaningful tests exist and genuinely exercise the provider's logic.
- **`test-author`** — *Write the failing test suite first.* Tools: Read, Write,
  Bash. Given a subplan/spec, writes the unit tests (red) before any
  implementation, so Codex/Claude implement against a concrete target. Used for
  foundation modules and for providers whose subplan needs a richer test plan.

## 7. Skills to build (Phase 0)

Defined as `.claude/skills/<name>/SKILL.md`:

- **`add-provider`** — scaffold: `gh issue create`, create `provider/<key>`
  branch + `git worktree`, copy the stub module from a template.
- **`verify-provider`** — run the standard pilot fetch + quality-check sequence,
  print a pass/fail summary.
- **`rasterize-coverage`** — turn a provider's raw tiles/vector output into the
  z14 binary-presence COG on the shared grid.
- **`dispatch-codex`** — take a batch of 4–6 provider specs, open their
  issues/branches/worktrees, and hand each to a Codex agent with its spec.
- **`tdd-cycle`** — drive one red-green-refactor loop: confirm a failing test
  exists, implement the minimum to reach green, run the suite, then refactor.
  Refuses to write implementation code before a failing test exists.

## 8. Git & GitHub workflow

- **Branches** — `main` is stable; **`dev` is the integration branch**. Every PR
  targets `dev`, never `main`. `dev` is promoted to `main` at phase boundaries.
- **Issue per provider** — label `provider` + `tier-1|2|3`; tracks endpoint,
  status, scout notes.
- **Branch per provider** — `provider/<key>` off `dev`, in its own worktree.
- **One PR per provider** — opened **into `dev`**; `Closes #N`; adds exactly one
  `providers/<key>.py` (+ tests + `docs/providers/<key>.md`); **edits no shared file**.
- **Foundation/infra changes** — separate `foundation`-labelled PRs, merged
  before dependent provider work.
- **Gate** — CI green + `pr-reviewer` checklist before merge into `dev`.
- Milestones: `Phase 0 Foundation`, `Phase 1 T1`, `Phase 2 T2`, `Phase 3 T3`,
  `Phase 4 Aggregation`.

## 9. Per-provider subplan = the GitHub issue

Every provider gets its own **self-contained subplan** that is both committed as
`docs/providers/<key>.md` and **published verbatim as the provider's GitHub
issue body** (`gh issue create --body-file docs/providers/<key>.md`). It must be
complete enough that a Codex agent can implement the provider from the issue
alone — research findings, a step-by-step implementation subplan, and acceptance
criteria. `provider-scout` drafts it.

**Human approval is mandatory.** The drafted subplan is presented to the user;
it is published as an issue and handed to Codex **only after the user approves
it**. Approval status is recorded in the subplan's status log (§9 part 6) and in
the commit that adds the file. Unapproved subplans never reach `dispatch-codex`.

Template (`docs/templates/provider_subplan.md`):

```
# [<tier>] Provider: <Provider name> (`<key>`)

## 1. Summary
One paragraph: what the provider is, country/region, why it is in scope.

## 2. Research findings (filled by provider-scout)
- Homepage, public viewer URL, tier
- Coverage endpoint(s): URL template, method, headers, query params
- Coordinate scheme + zoom range + tile size/format
- Auth: token/cookie/none — how obtained, .env key name
- Response format → how "imagery present" is determined
- ToS / robots.txt notes, observed rate limit
- Known quirks / gotchas

## 3. Test plan (write these FIRST — red before green)
- [ ] `test_<key>_tile_url_build` — URL template fills correctly for sample z/x/y
- [ ] `test_<key>_decode_*` — response fixture decodes to expected presence
- [ ] `test_<key>_registers` — module self-registers in PROVIDERS
- [ ] <provider-specific cases: coordinate scheme, empty-tile, auth header, ...>
- Fixtures: small recorded response samples under `tests/fixtures/<key>/`

## 4. Implementation subplan (steps for Codex — TDD)
- [ ] Source kind: <existing kind> | NEW kind `<name>` (separate PR first)
- [ ] Write the §3 tests first; confirm they fail (red)
- [ ] Add `src/coverage_acquisition/providers/<key>.py` (ProviderDefinition)
- [ ] Implement until the §3 tests pass (green); refactor
- [ ] Pilot fetch: bbox <pilot city bbox>, expect coverage on known streets
- [ ] Rasterize pilot area to z14 COG; sanity-check
- [ ] Two-pass full extent: pass-1 region bbox <...> at discovery zoom <z>
- [ ] Update STAC item; update inventory status

## 5. Acceptance criteria (checked by provider-verifier)
- All §3 tests pass; module imports & self-registers; CI smoke test passes
- Pilot tiles fetch & decode; coverage lands on roads/land (not ocean)
- z14 COG is valid, correct CRS/extent
- Throttling + descriptive UA present; ToS caveats documented

## 6. Status log
Scout / implement / verify notes appended here.
```

Issue metadata: labels `provider` + `tier-1|2|3`; milestone = its phase;
title `[<tier>] <Provider name> (<key>)`. The PR for the provider uses
`Closes #<issue>`.

## 10. Codex dispatch model

1. Claude's `provider-scout` drafts subplans for a batch of 4–6 providers.
2. **The user reviews and approves the batch of subplans** (approval gate, §5
   step 2). Only approved subplans continue.
3. `dispatch-codex` publishes the approved subplans as issues and opens
   `provider/<key>` branches + worktrees.
4. Each provider → one Codex agent, working its worktree from the approved
   subplan/issue, implementing + self-debugging against acceptance criteria.
5. Codex opens the PR; CI + `pr-reviewer` gate; Claude merges.
6. `provider-verifier` runs the full-extent QA post-merge; aggregate into STAC.

## 11. Execution roadmap

- **Phase 0 — Foundation.** Items in §4. Claude-built. ~1 working block.
- **Phase 1 — T1 (4 providers).** streetlevel-native; validates the
  `streetlevel` source kind and the whole pipeline end-to-end. One batch. The
  first provider also wires the `rasterize` / `catalog` CLI integration
  (fetch-output → z14 COG → STAC) against real provider output.
- **Phase 2 — T2 (7 providers).** Public/documented scrapers. Two batches.
- **Phase 3 — T3 (~14 providers).** Likely/unverified/gated. Three batches;
  scout may downgrade unreachable ones to "skip — confirmed dead".
- **Phase 4 — Aggregation.** Full STAC catalog, global coverage QA, optional
  combined view, inventory xlsx updated with final status per provider.

## 12. Testing & TDD discipline

Unit tests are the project's primary quality assurance. **Test-driven
development is mandatory** for foundation code and every provider.

**Red-green-refactor.** Write a failing test that pins the desired behavior,
implement the minimum to make it pass, then refactor with the test as a safety
net. Implementation code is never written before a failing test exists.

**What gets tested**
- *Foundation modules* — registry auto-discovery, each source-kind decoder,
  `polite` throttle/retry/robots, `geo` coordinate math, `rasterize`, `catalog`.
- *Each provider* — tile-URL building, response decoding to presence,
  coordinate scheme, empty-tile handling, self-registration. Network calls are
  **not** made in unit tests: record small response samples as fixtures under
  `tests/fixtures/<key>/` and decode those.

**Layout**
- `tests/` mirrors `src/coverage_acquisition/`; `tests/conftest.py` for shared
  fixtures; `tests/fixtures/` for recorded response samples.
- `pytest` config in `pyproject.toml`; fast (no network), runs in CI on every PR.

**Roles**
- `tdd-cycle` skill drives one red-green-refactor loop on demand.
- `test-author` subagent writes the failing suite first from a spec/subplan.
- Each provider subplan's **§3 test plan** enumerates the tests to write first.
- `pr-reviewer` rejects PRs whose tests are missing, trivial, or written to
  rubber-stamp the implementation rather than pin behavior.
- CI fails the build on any failing or absent test.

**Definition of done** — a unit of work is done only when its tests exist, are
meaningful, and pass; coverage of new code is expected, not optional.

## 13. Risks & open items

- **Gated/app-only providers** (Kuwait Finder, Tencent app, Mappls) may need
  mobile-API reverse-engineering — time-boxed; downgrade to skip if blocked.
- **z14 global fetch cost** — bounded by two-pass discovery; most new providers
  are regional, so volume is manageable.
- **ToS** — record caveats per provider; drop any that explicitly forbid
  automation. CycloMedia limited to the public Philadelphia viewer only.
- **`data/processed` size** — if COGs grow large, move to DVC / external store
  (decide at Phase 4).

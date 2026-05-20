# CLAUDE.md

Guidance for Claude Code, subagents, and Codex working in this repository.

> Note: this file lives at the repo root (not `.claude/`) because Claude Code
> only auto-loads `CLAUDE.md` from the working directory and its parents.

## Project

Scrape **coverage maps** from street-level imagery (SVI) providers worldwide and
harmonize them into a **global street-level image availability database**.

- Goal: for any location on Earth, know which providers have imagery there.
- Target providers: those that are **active** and **scrapable** — see
  `data/external/street_view_providers.xlsx`. Skip defunct providers and
  paid-B2B-only providers with no public viewer.
- Output format: **raster is preferred over vector** (points/lines) for
  storage efficiency at global scale. Vector sources are rasterized onto a
  shared coverage grid.

## Environment

This project uses [uv](https://docs.astral.sh/uv/). Python >= 3.11.

```bash
uv sync --extra notebook --extra dev   # create .venv + install
uv run coverage-acquisition list-providers
uv run python -m coverage_acquisition.cli --help
```

Do not commit `.venv/`, `data/raw/`, or `data/intermediate/`.

## Repository layout

```
src/coverage_acquisition/   acquisition library + CLI
  providers/                provider registry package; one module per provider
    _registry.py            register_provider() + PROVIDERS dict
    _presets.py / _downloads.py   shared legacy tables
    <key>.py                one provider each; calls register_provider(PROVIDER)
  models.py                 dataclasses (ProviderDefinition, SourceDefinition, ...)
  runners.py                fetch loop: tiles -> stored files + CSV summaries
  geo.py                    tile math (web mercator, Yandex, Baidu schemes)
  mvt_decoder.py            vector MVT -> GeoJSON/WKT
  downloaders.py            direct-file + raw raster tile fetchers
  cli.py / __main__.py      argparse CLI
data/external/              inputs (provider inventory xlsx)
data/raw/                   scraped tiles per provider (gitignored)
data/intermediate/          decoded/normalized per-provider data (gitignored)
data/processed/             final coverage rasters + master DB (tracked or DVC)
```

A new provider is one new file `providers/<key>.py` defining a
`ProviderDefinition` as `PROVIDER` and calling `register_provider(PROVIDER)`.
The package auto-discovers it — no shared file is edited.

## Adding a new provider (the repeated workflow)

Every provider goes through the same pipeline. Each provider is a
**self-contained module** so multiple agents can work in parallel without
touching shared files. See `docs/PLAN.md` §5 for the full 8-step pipeline.

1. Scout the provider's coverage endpoint and draft the subplan
   `docs/providers/<key>.md` (also the GitHub issue body).
2. **Human approval gate** — the user must approve the subplan before any
   issue, branch, or code is created. Never skip this.
3. Publish the approved subplan as a GitHub issue; create the branch + worktree.
4. Add `src/coverage_acquisition/providers/<key>.py` (`ProviderDefinition`),
   auto-discovered by the registry; reuse `geo.py` coordinate helpers.
5. Pilot fetch → rasterize → verify → full-extent two-pass scrape.
6. Document quirks in the module docstring and the subplan status log.

## Parallel provider development — issues, branches, PRs

Subagents and Codex work on **one provider each, in isolation**:

- **Integration branch is `dev`.** All PRs target `dev`, never `main` directly.
  `dev` is promoted to `main` at phase boundaries.
- **Issue per provider.** One GitHub issue per provider, label `provider`,
  tracking research notes, endpoint, status. Use `gh issue create`.
- **Branch per provider.** Branch off `dev` named `provider/<key>`
  (e.g. `provider/kakao`). Never commit provider work to `dev`/`main` directly.
- **One PR per provider.** Open a PR from `provider/<key>` **into `dev`** that
  closes its issue (`Closes #N`). Keep the PR scoped to that one provider.
- **No shared-file edits.** A provider PR must not edit `providers.py`,
  `models.py`, or another provider's module — that is what makes concurrent
  branches conflict-free. New shared capabilities go in their own PR first.
- **Review before merge.** Run `/review` (and tests) on each PR before merging
  into `dev`.

GitHub: `origin` is the working fork `koito19960406/Cross-source-SVI-Coverage`
— push branches and open PRs (into `dev`) there. `upstream` is
`zichengfan/Cross-source-SVI-Coverage`.

## Conventions

- **TDD is mandatory.** Red-green-refactor: write a failing test first, then the
  minimum code to pass, then refactor. No implementation before a failing test.
  `tests/` mirrors `src/`; unit tests must not hit the network — decode recorded
  fixtures under `tests/fixtures/`. Run `uv run pytest`. See `docs/PLAN.md` §12.
- Match existing style: `from __future__ import annotations`, frozen
  `@dataclass`.
- Fetch through `polite.polite_fetch` (descriptive `User-Agent`, per-host
  throttle, retry/backoff) — never call `urllib`/`requests` directly in scrapers.
- Keep heavy deps (geopandas, rasterio) out of the hot fetch loop; use them in
  the rasterization/aggregation stage.
- Be a polite scraper: respect `robots.txt` and provider ToS; record any ToS
  caveats in the provider module docstring.
- Commit messages end with:
  `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- Only commit/push when asked; branch first if on `main`.

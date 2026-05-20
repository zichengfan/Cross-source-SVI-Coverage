<!-- Provider PRs: keep scoped to ONE provider. See docs/PLAN.md §8. -->

Closes #<issue>

## What this adds

<one-line summary — which provider / what coverage source>

## Checklist

- [ ] Adds exactly one provider: one new `providers/<key>.py`, its tests, its
      `docs/providers/<key>.md` — nothing else
- [ ] **No shared-file edits** (`runners.py`, `models.py`, `cli.py`,
      `providers/_*.py`, `source_kinds/` core, other providers)
- [ ] Built test-first (TDD); unit tests are meaningful and offline (fixtures,
      no network)
- [ ] Fetches via `polite.polite_fetch`; descriptive User-Agent; throttled
- [ ] ToS / robots.txt caveats recorded in the module docstring
- [ ] `uv run pytest` and `uv run ruff check src/ tests/` pass locally
- [ ] Pilot fetch verified; coverage is geographically plausible

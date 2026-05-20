---
name: tdd-cycle
description: Drive one red-green-refactor TDD cycle for a unit of work — confirm a failing test exists, implement the minimum to pass, then refactor. Use whenever writing or changing code in this project.
---

# tdd-cycle

Test-driven development is mandatory in the Cross-Source SVI Coverage project
(`docs/PLAN.md` §12). This skill enforces one red-green-refactor cycle.

## The cycle

### 1. RED — write a failing test first
- Pick the smallest next behavior to add.
- Write a unit test in `tests/` (mirroring `src/coverage_acquisition/`) that
  pins that behavior with concrete expected values.
- No network in tests — decode synthetic payloads or fixtures under
  `tests/fixtures/`; reuse `tests/conftest.py` factories.
- Run `uv run pytest <the test>` and **confirm it fails** for the right reason
  (missing/incorrect behavior). If it passes already, the behavior exists —
  pick a different next step.

**Do not write implementation code until a failing test exists.**

### 2. GREEN — make it pass
- Write the minimum implementation to make the test pass.
- Run `uv run pytest` — the new test and all existing tests must be green.

### 3. REFACTOR — clean up
- Improve names, remove duplication, tighten types, with the tests as a net.
- Run `uv run pytest` and `uv run ruff check src/ tests/` — both must stay green.

## Repeat
Loop until the unit of work is complete. A unit of work is **done** only when
its tests exist, are meaningful (they pin behavior, not mirror the code), and
pass.

## Reporting
For each cycle, state: the behavior added, the test name, that it went red then
green, and the final `pytest`/`ruff` status.

---
name: tdd
description: Drive test-driven development — red-green-refactor — for any code change in this project. Use whenever writing or modifying code; it is the implement step of the project's working process.
---

# tdd

Test-driven development is mandatory in the Cross-Source SVI Coverage project
(`docs/PLAN.md` §12). Red-green-refactor with an agent is the most consistent
way to raise output quality. This skill is the **implement** step of the working
process: `grill-me → to-prd → to-issues → tdd → improve-codebase-architecture`.

## The cycle

### 0. Frame the change
- Confirm the **interface changes** needed (new/changed functions, classes, CLI).
- List the concrete **behaviors** to test — happy path, edge cases, failures.
- Design **testable interfaces**: prefer dependency injection / pure decoders
  over hidden globals so a test can drive them offline.

### 1. RED — write a failing test first
- Pick the smallest next behavior. Write one unit test in `tests/` (mirroring
  `src/coverage_acquisition/`) that pins it with concrete expected values.
- **No network in tests** — decode synthetic payloads or recorded fixtures under
  `tests/fixtures/`; reuse `tests/conftest.py` factories.
- Run `uv run pytest <the test>` and **confirm it fails** for the right reason.
  If it already passes, that behavior exists — pick a different next step.

**Never write implementation code before a failing test exists.**

### 2. GREEN — make it pass
- Write the minimum implementation to make the test pass.
- Run `uv run pytest` — the new test and all existing tests must be green.

### 3. REFACTOR — clean up
- Improve names, remove duplication, deepen shallow abstractions, with the tests
  as a safety net.
- Run `uv run pytest` and `uv run ruff check src/ tests/` — both stay green.

## Repeat
Loop until the unit of work is complete. It is **done** only when its tests
exist, are meaningful (they pin behavior, not mirror the implementation), and
pass.

## Reporting
For each cycle: the behavior added, the test name, that it went red then green,
and the final `pytest`/`ruff` status.

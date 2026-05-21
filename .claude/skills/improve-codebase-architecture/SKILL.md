---
name: improve-codebase-architecture
description: Scan the codebase for structural weaknesses (shallow modules, over-extraction for testability, tight coupling) and propose deeper, clearer modules. Use at phase boundaries or after a development surge.
---

# improve-codebase-architecture

Keep the codebase **agent-friendly**. A garbage codebase makes an agent produce
garbage within it. This is the maintenance step of the working process —
`grill-me → to-prd → to-issues → tdd → improve-codebase-architecture` — run
**at phase boundaries** (`docs/PLAN.md` §11) or after a burst of development.

## What to scan for

Explore `src/coverage_acquisition/` and look for:

1. **Shallow modules / scattered concepts** — one idea smeared across many tiny
   files, forcing navigation across the repo to understand a single thing. The
   fix is usually a *deeper* module: more behavior behind a simpler interface.
2. **Pure functions extracted only for testability** — helpers split out solely
   so a test can reach them. This can *mask real bugs* (the integration path is
   never tested). Prefer testing through the real interface.
3. **Tight coupling / integration risk** — modules that reach into each other's
   internals, or shared mutable state, so a change in one silently breaks
   another.
4. **Dead / orphaned code** — modules with no remaining callers after a
   redesign (e.g. an obsoleted subsystem). Removing it is an architecture
   improvement.

## Procedure

1. Map the modules and their dependencies (imports, call graph).
2. For each weakness, write a short finding: the symptom, the files, and a
   concrete "deepen / merge / remove / decouple" proposal with the expected
   benefit.
3. **Present the findings to the user for approval** — do not refactor
   unilaterally. Architecture changes are deliberate.
4. Approved refactors become their own PRD (`to-prd`) → issues (`to-issues`) →
   `tdd`, or a focused `foundation`-labelled PR, with the test suite as the
   safety net.

## Output
A prioritized list of architecture findings, each with a recommended action,
for the user to approve. Never a silent rewrite.

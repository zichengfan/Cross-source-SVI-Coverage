---
name: to-issues
description: Break a PRD into independent, grabbable GitHub issues organized as vertical slices with blocking relationships. Use after a PRD exists, before implementation.
---

# to-issues

Convert a PRD into independent tasks that multiple agents can pick up in
parallel. Third step of the working process:
`grill-me → to-prd → to-issues → tdd → improve-codebase-architecture`.

## The core idea: vertical slices, not horizontal layers

Each issue is a **thin cut through all layers** — a "tracer bullet" that goes
end to end (e.g. *one provider*: its module + tests + fetch + rasterize). It is
**not** a horizontal layer ("write all the models", then "write all the
fetchers"). Vertical slices flush out unknown-unknowns early and stay
independently shippable.

## Procedure

1. **Locate the PRD** — `docs/prd/<slug>.md` (or fetch its GitHub issue).
2. **Explore the codebase** — confirm where each slice lands; find reusable
   code so issues don't re-specify existing utilities.
3. **Draft the vertical slices** — list issues, each a thin end-to-end cut.
   For each: a clear title, the scope, the acceptance criteria (from the PRD),
   and which files it adds/edits. Keep slices **conflict-free** — a slice should
   add its own files, not edit shared ones (`docs/PLAN.md` §8); shared-capability
   changes are their own slice that others depend on.
4. **Set blocking relationships** — note "blocked by #N" where a foundation
   slice must merge first. Order them so every intermediate `dev` is green.
5. **Create the GitHub issues** on `koito19960406/Cross-source-SVI-Coverage`
   with the repo's labels (`provider`, `tier-1|2|3`, `foundation`, ...) and the
   right milestone; record the blocking edges in the issue bodies. Every issue's
   eventual PR targets `dev`.

## Output
A table of the created issues (number, title, blocked-by) and the recommended
execution order. Next: scaffold + `dispatch-codex` (or `add-provider`) to
implement, each slice via `tdd`.

> The canonical vertical slice in this project is **one provider** = one issue =
> one `provider/<key>` branch = one PR. `to-issues` generalizes that to any PRD.

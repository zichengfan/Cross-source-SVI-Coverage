---
name: to-prd
description: Turn a discussion or idea into a Product Requirements Document with user stories, then publish it as a GitHub issue. Use after grill-me, before breaking work into tasks.
---

# to-prd

Transform a discussion into a formal **Product Requirements Document**. This is
the second step of the working process:
`grill-me → to-prd → to-issues → tdd → improve-codebase-architecture`.

A PRD describes *what* and *why* — never *how* in code. It is the durable
artifact the rest of the pipeline consumes.

## Procedure

1. **Get a detailed description.** Ask the user to describe the feature/change
   in depth — the problem, the users, the desired outcome.
2. **Explore the repo to validate claims.** Don't take the description at face
   value — read the code, confirm what exists, find reusable functions and
   patterns. Note constraints the PRD must respect.
3. **Run `grill-me`.** Interview the user relentlessly to resolve every branch
   of the design tree before writing anything down.
4. **Map the affected modules.** List the parts of `src/coverage_acquisition/`
   (and docs) the change touches.
5. **Write the PRD** to `docs/prd/<slug>.md`:
   - **Context** — the problem, what prompted it, the intended outcome.
   - **User stories** — Agile form: *"As a … I want … so that …"*.
   - **Scope / non-goals** — explicitly in and out.
   - **Acceptance criteria** — observable conditions that mean "done".
   - **Affected modules** — from step 4.
   - **Open questions** — anything still unresolved.
6. **Human approval gate.** Present the PRD; revise until the user approves.
7. **Publish** as a GitHub issue on `koito19960406/Cross-source-SVI-Coverage`
   (`gh issue create --body-file docs/prd/<slug>.md --label prd`).

## Output
The committed `docs/prd/<slug>.md`, the issue URL, and a one-line summary. Next
step: `to-issues` breaks the PRD into vertical-slice tasks.

> For a single street-view provider, the lighter `docs/providers/<key>.md`
> subplan (see `docs/templates/provider_subplan.md`) plays the PRD role — use
> `provider-scout` for that. Use `to-prd` for cross-cutting features and phases.

---
name: dispatch-codex
description: Take a batch of approved provider subplans, open their issues/branches/worktrees, and hand each to a Codex agent to implement in parallel. Use to start a batch of provider implementations.
---

# dispatch-codex

Dispatch a batch of 4–6 **approved** provider subplans to Codex agents for
parallel, test-driven implementation (`docs/PLAN.md` §10).

## Preconditions
- Each provider in the batch has an approved `docs/providers/<key>.md` (user
  approval recorded in its status log). **Never dispatch an unapproved subplan.**

## Steps

1. **Scaffold each provider** — run the `add-provider` skill per provider:
   creates the GitHub issue, the `provider/<key>` branch, the worktree, and the
   stub module.

2. **Dispatch one Codex agent per provider.** Launch them concurrently — one
   `codex:codex-rescue` agent per provider, each pointed at its own worktree.
   Give each agent a prompt that:
   - points to the provider's worktree path and `docs/providers/<key>.md`;
   - requires **TDD** — write the subplan's §3 test plan first (red), then
     implement until green, then refactor;
   - restricts edits to the provider's own files (one `providers/<key>.py`,
     its tests, its subplan) — no shared-file edits;
   - requires `uv run pytest` and `uv run ruff check` to pass;
   - requires fetching via `polite.polite_fetch` and a descriptive User-Agent;
   - ends by opening a PR **into `dev`** with `Closes #<issue>`.

3. **Track** the batch: list each provider with its issue, branch, worktree, and
   Codex agent id.

4. As each Codex agent finishes, route the provider through the
   `verify-provider` skill / `provider-verifier` subagent, then the
   `pr-reviewer` subagent, before merge.

## Output
A table of the dispatched batch (provider, issue #, branch, worktree, agent id)
and the next checkpoint for each.

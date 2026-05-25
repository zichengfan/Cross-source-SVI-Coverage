---
name: add-provider
description: Scaffold a new street-view provider once its subplan is approved — create the GitHub issue, the provider branch and worktree, and a stub provider module. Use after the user approves a docs/providers/<key>.md subplan.
---

# add-provider

Scaffold one provider for the Cross-Source SVI Coverage project. Run this only
**after the user has approved** the provider's subplan.

## Preconditions
- `docs/providers/<key>.md` exists and its status log records user approval.
- You are in the repo root with a clean tree. Provider branches and PRs use
  `dev` as their base — never `main`.

If the subplan is missing or not approved, **stop** and say so — never scaffold
an unapproved provider (`docs/PLAN.md` §5 step 2).

## Steps

1. **Read** `docs/providers/<key>.md` to get the provider name and tier.

2. **Create the issue** — the subplan *is* the issue body:
   ```
   gh issue create \
     --title "[T<tier>] <Provider name> (<key>)" \
     --body-file docs/providers/<key>.md \
     --label provider --label tier-<tier>
   ```
   Note the issue number.

3. **Create the branch + worktree** off `dev`:
   ```
   git worktree add ../svi-provider-worktrees/<key> -b provider/<key> dev
   ```

4. **Stub the module** — copy `docs/templates/provider_module_stub.py` to
   `../svi-provider-worktrees/<key>/src/coverage_acquisition/providers/<key>.py`
   and fill in the `<key>` / name placeholders only (no real logic — that is the
   implementer's job, test-first).

5. **Report** the issue URL, branch name, and worktree path so the work can be
   handed to an implementer (see the `dispatch-codex` skill for batches).

Do not implement the provider here. One provider = one issue = one branch =
one worktree = one PR.

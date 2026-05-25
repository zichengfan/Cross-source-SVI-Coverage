---
name: handoff
description: Write a compact handoff at a context switch — session end, planning→implementation, or handing work to another agent — so the next session resumes without re-reading the whole conversation.
---

# handoff

Agents have no memory, and a long conversation is expensive and lossy to
re-read. At a context switch, capture the project's **state and intent**
compactly so the next session — or another agent — picks up cleanly instead of
reconstructing everything from scratch. This is the continuity step of the
working process.

## When to use

- Ending a work session with unfinished work.
- Transitioning from planning (`grill-me` / `to-prd` / `to-issues`) to
  implementation (`tdd`), or back.
- Handing a scoped sub-task to another agent (e.g. a Codex implementation).
- Any moment the next actor would otherwise have to rebuild context by hand.

## What to do

1. **Ground it in live state — do not trust the conversation.** Skim the real
   sources: `git log --oneline -10`, `gh pr list`, `gh issue list`, the
   relevant `docs/providers/<key>.md` subplans, `docs/prd/<slug>.md`, and
   `docs/PLAN.md`. The handoff must match reality, not the chat.
2. **Write `docs/HANDOFF.md`** — overwrite it; it is the single *current*
   handoff. Use the template below.
3. **Reference, never duplicate.** Point to `PLAN.md` sections, subplans, PRDs,
   issue/PR numbers, commits, and memory files — do not copy their content. The
   handoff is a map, not a mirror; anything that lives in a PRD, issue, ADR,
   plan, commit, or diff stays there.
4. **If the handoff records something the next session must not miss** — a
   pause, a blocker, a decision that overrides the plan — also add or update a
   one-line pointer in the project memory index (`MEMORY.md`). That is the only
   channel auto-loaded every session. Rule of thumb: durable *facts* → memory;
   transient *"where we are / what's next"* → `docs/HANDOFF.md`.

## Template (`docs/HANDOFF.md`)

```
# Handoff — <YYYY-MM-DD>

## State
One short paragraph: where the project is right now.

## Decided this session
- <decision> — <why, in half a line>

## Open / pending
- <unresolved question or blocker — and what it waits on>

## Artifacts that matter (references, not copies)
- Plan: docs/PLAN.md §<n>
- Subplans / PRDs: docs/providers/<key>.md, docs/prd/<slug>.md
- Issues / PRs: #<n> — <one-line status>
- Memory: <relevant memory file names>

## Next steps
1. <concrete next action>
2. ...

## Skills the next session should use
- <skill> — for <what>
```

## Done when

`docs/HANDOFF.md` exists, is current, references rather than duplicates, and a
fresh agent could resume the work from it plus the artifacts it points to —
nothing else needed.

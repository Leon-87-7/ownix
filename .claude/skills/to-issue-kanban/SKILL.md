---
name: to-issue-kanban
description: Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker AND reflect the new issues into the project's ISSUE_KANBAN.md board (rows + Dependency Map). Use only when explicitly invoked as /to-issue-kanban — the kanban-aware variant of /to-issues for repos that keep an ISSUE_KANBAN.md.
---

# To Issues (kanban-aware)

A thin wrapper over `/to-issues` that adds a final board-sync step. It does NOT reimplement the breakdown logic — it runs `/to-issues` for the core flow, then syncs the new issues into `ISSUE_KANBAN.md`.

> **Prerequisite:** `to-issues` ([mattpocock/skills](https://github.com/mattpocock/skills/tree/main/skills/engineering/to-issues)) must be installed globally (`~/.agents/skills/to-issues/`). It is not vendored into this repo — see `.claude/skills/README.md`.

## Process

### 1. Run the source flow

Execute the full `/to-issues` flow by following its `SKILL.md` (at `~/.agents/skills/to-issues/SKILL.md`): gather context → explore codebase → draft vertical slices → **quiz the user** → publish issues with `needs-triage`.

**One addition to Step 4 (the quiz):** for each slice, also show the **proposed Area** (derived per `kanban-sync.md` §3 — labels → conventional-commit scope → `—`) so the user can correct it in-band before anything is written. Carry the approved Areas forward.

### 2. Sync the board

After the issues are published, apply the shared sync procedure in
[`kanban-sync.md`](../kanban-sync.md).

For this skill specifically:
- New issues are brand-new `#N`s → they **append** to the **Needs Triage** column (§2, §4).
- Carry each row's **Area** (from the quiz) and **Depends On** (the blocked-by edges).
- Update the **Dependency Map** per §5: append a new labeled block for this plan/spec/PRD, with `◄── also #N` cross-refs to any pre-existing blockers and a `Critical path:` line if the graph is linear.
- Auto-write, then print the diff summary (§6).

If no `ISSUE_KANBAN.md` exists, §1 of the sync doc handles bootstrap.

---
name: triage-kanban
description: Triage issues through the triage state machine AND reflect each state change into the project's ISSUE_KANBAN.md board (move rows between columns, sync closed issues to Done, mark dep-map nodes done). Use only when explicitly invoked as /triage-kanban — the kanban-aware variant of /triage for repos that keep an ISSUE_KANBAN.md.
---

# Triage (kanban-aware)

A thin wrapper over `/triage` that adds a final board-sync step. It does NOT reimplement the triage state machine — it runs `/triage` for the core flow, then syncs the outcome into `ISSUE_KANBAN.md`.

> **Prerequisite:** `triage` ([mattpocock/skills](https://github.com/mattpocock/skills/tree/main/skills/engineering/triage)) must be installed globally (`~/.agents/skills/triage/`). It is not vendored into this repo — see `.claude/skills/README.md`.

## Process

### 1. Run the source flow

Execute the full `/triage` flow by following its `SKILL.md` (at `~/.agents/skills/triage/SKILL.md`): show what needs attention, triage a specific issue (gather context → recommend → reproduce → grill → apply outcome), or apply a quick state override. The AI-disclaimer rules for GitHub comments still apply.

### 2. Sync the board

After the triage outcome is applied, apply the shared sync procedure in
[`kanban-sync.md`](../kanban-sync.md).

For this skill specifically:
- **Move** the affected issue's `#N` row to the column matching its new state (§2): `needs-info` → Needs Triage; `wontfix` → remove the row; otherwise the column named for the state.
- A move is **remove old row + insert in new column** — never leave a duplicate (§4).
- Derive **Area** silently (§3); carry **Depends On** over unchanged.
- When triaging touches an **already-closed** issue, sync it into **Done**: closed-as-completed → Done with Notes (PR #/commit/`closed on GH`); closed-as-`wontfix` → remove the row (§2).
- **Dependency Map:** the only edit is appending ` ✓` to the issue's existing `#N` node **when moving it to Done** (idempotent) (§5). Never restructure.
- Auto-write, then print the diff summary (§6). The disclaimer does **not** apply to the board file.

If no `ISSUE_KANBAN.md` exists, §1 of the sync doc handles bootstrap.

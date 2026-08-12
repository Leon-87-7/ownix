---
name: update-kanban
disable-model-invocation: false
description: On-demand reconcile of the project's ISSUE_KANBAN.md board against the authoritative GitHub state — discovers what drifted (issues closed/relabelled/deleted outside the normal flow), previews the delta, and on confirmation rewrites the affected rows and rebuilds an open/closed PR section. Use only when explicitly invoked as /update-kanban — for manual or drift-recovery syncs that aren't tied to a /to-issues or /triage run.
---

# Update Kanban (manual reconcile)

> **No external prerequisite.** Unlike the two wrappers, this skill has no source flow — it depends only on the bundled `kanban-sync.md` and `gh`, so it works on a fresh clone.

Unlike `to-issue-kanban` / `triage-kanban` — which know exactly which issues they touched and hand that set to the sync helper — `/update-kanban` is handed **nothing**. It _discovers_ the delta by diffing the whole board against GitHub, then applies it through the same shared helper. Use it when something changed on GitHub outside the normal flow (issues closed manually, labels edited, PRs merged) or when you just want a fresh sync.

**GitHub Issues is authoritative; the board is a snapshot.** This reconciles the board _toward_ GitHub. Hand-curated content (Done Notes, the Dependency Map, manual Ready-for-Agent ordering) is preserved — see `kanban-sync.md` §4–§5. The PR section is the one fully-derived block: Open PRs is rebuilt every run; Closed PRs is diffed against `gh` + the archive and only grows by genuinely new rows (`kanban-sync.md` §8).

## 1. Build the picture

- **GitHub side:** `gh issue list --state all --limit 500 --json number,title,state,stateReason,labels,title` (raise `--limit` if the repo has more). Also `gh pr list --state all --limit 500 --json number,title,headRefName,baseRefName,state,body,closingIssuesReferences` for the PR section.
- **Board side:** locate `ISSUE_KANBAN.md` (`kanban-sync.md` §1 — bootstrap if absent, which subsumes the first reconcile). Read every `#N` row and the column it sits in.

## 2. Compute the delta

Classify each issue by comparing GitHub state against the board. Column targets follow `kanban-sync.md` §2.

| Situation                                                                        | Action                                                                                             |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Open on GH, **not** on board                                                     | **add** to the column its triage label maps to (§2)                                                |
| Open on GH, on board, **wrong** column (label changed)                           | **move** (remove old row + insert — §4)                                                            |
| Open on GH, on board, correct column                                             | no-op                                                                                              |
| Open on GH, **no triage label**                                                  | **add/move → Needs Triage** (the untriaged bucket)                                                 |
| Closed-completed, on board but not Done                                          | **move → Done** + ` ✅-Done` on its dep-map node (§5); fill Notes from the close event / linked PR |
| Closed-completed, **not** on board, **not** in the archive                       | **backfill → Done** with Notes                                                                     |
| Closed-completed, **not** on board, **already in** `docs/archive/ISSUE_KANBAN-archive.md` | **no-op** — already accounted for, not a resurrection candidate                              |
| Closed-as-`wontfix`                                                              | **remove the row** (§2)                                                                            |
| On board but `#N` **absent from `gh issue list`** entirely (deleted/transferred) | **orphan** — **move → Needs Triage and flag loudly** in the report; never silently delete          |

Before applying either "move → Done" or "backfill → Done" for a closed-completed issue, check `docs/archive/ISSUE_KANBAN-archive.md` for that `#N` first. Only issues closed-completed and absent from **both** the live board and the archive get backfilled — the "move → Done" row still routes through `kanban-sync.md` §9's rolling window immediately after landing, so it can archive right back out on this same run if its group has aged out.

Derive **Area** silently (§3); carry **Depends On** over unchanged.

## 3. Dry-run preview → confirm

Reconcile is bulk and runs precisely when you're unsure what drifted, so **preview before writing.** Print the §6-style diff summary _first_, with these two buckets called out explicitly (not just counted):

- **🗑 wontfix removals** — list each `#N` that will be removed.
- **🔺 Needs Triage additions** — list each `#N` landing in Needs Triage, marking which are **orphans** (`⚠ #82 — not found on GitHub, moved here`) vs genuinely untriaged.

Then invoke `/sync-task-briefs` in preview mode using the same GitHub issue list
from step 1. Include its `TASK.md sync:` items in this confirmation gate.

Then ask: **"Apply these N changes?"** Write only on confirmation. Count both
board changes and `TASK.md` sync changes in `N`.

**Empty board delta:** if nothing about the issue rows drifted but
`/sync-task-briefs` found task changes, still ask for confirmation before
writing those task/archive edits. If neither the board nor `TASK.md` drifted,
skip the confirm — there's nothing destructive to preview — and just rebuild the
PR section (PRs change more often than the board). Report
`Board already in sync; TASK.md already in sync; PR section refreshed`.

## 4. Apply

On confirmation, apply each delta item through `kanban-sync.md` §2–§6 (column mapping, row fields, surgical safety, dep-map, write). Then invoke `/sync-task-briefs` apply mode for the confirmed task changes so closed-completed GitHub issues mark their linked `docs/TASK.md` briefs done and archive finished bodies through `/pre-grill --mark-a`. Then **refresh the PR section** via the helper's opt-in PR step (`kanban-sync.md` §8) — blow away and rebuild Open PRs; diff Closed PRs against `gh pr list` + the archive and append only new ones.

**Enforcing the §9 windows — use the scripts, don't hand-roll it.** The Done-row and Closed-PR-row archival (`kanban-sync.md` §9) is deterministic file math; a bundled set of single-concern helpers in `scripts/` does it and is validated to reproduce a hand pass byte-for-byte. After the row writes above land, run the orchestrator from the repo root:

```bash
# preview first (writes nothing)
python3 agent-knowledge/skills/update-kanban/scripts/run_window.py
# then apply
python3 agent-knowledge/skills/update-kanban/scripts/run_window.py --apply
```

It parses the Dependency Map into groups, keeps the last 3 done-groups + 4 highest Closed PRs live, ages out the rest to the archive (append-if-absent), and de-dupes any `#N` already present in the archive. It's idempotent — on an already-windowed board it writes nothing. See `scripts/README.md` for the per-concern breakdown and the one known simplification. Note that the GitHub-issue delta and TASK.md marking are **not** the scripts' job (they only move rows that already exist); those stay with the agent and `/sync-task-briefs`.

Finally print the §6 diff summary plus the task-sync summary.

The board is git-tracked — `git diff` / `git checkout ISSUE_KANBAN.md` is the undo. The AI-disclaimer applies to GitHub comments only, never to this file.

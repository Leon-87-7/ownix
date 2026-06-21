---
name: feature-fill
description: Reads the codebase state (PRD, ADRs, ISSUE_KANBAN.md, CONTEXT.md, open issues) and surfaces gaps, missing features, stale decisions, and next-move suggestions. The opposite of ponytail — additive, not reductive. Use when explicitly invoked as /feature-fill.
---

# Feature Fill — gap finder & feature radar

The anti-ponytail. Instead of deleting slop, this skill reads every decision
surface in the repo and asks: _what's missing, what's stale, what's next, what's unaddressed?_

## Inputs (read in parallel)

| Source                                      | What to extract                                                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `ISSUE_KANBAN.md`                           | Done vs In Progress vs Backlog vs Needs Triage — what's stuck, what has no owner, what's been sitting in triage          |
| `docs/adr/*.md`                             | Decisions that are superseded, have open "consequences" or "we'll revisit" language, or reference features not yet built |
| `CONTEXT.md`                                | Domain terms (glossary) that have no corresponding implementation, ADR, or board item                                    |
| Open GitHub issues (`gh issue list`)        | Issues with `needs-triage` or `needs-info` that are aging                                                                |
| Source tree (`src/`, `web/`)                | Modules referenced by an ADR or CONTEXT.md term but not yet implemented; TODO/FIXME/HACK comments                        |

## Process

### 1. Gather

Read all inputs above in parallel. The board, ADRs, and CONTEXT.md are the
living truth — the PRD at `docs/seed/PRD.md` is a frozen seed spec (its
forward-looking §9/§12 were removed) and is NOT a roadmap source; only consult
its still-live design sections (§13 Brain, §14 Mini-PRD) when an ADR or term
points there.

### 2. Cross-reference

Build a mental ledger:

- **Term gaps** — CONTEXT.md glossary terms with no implementation, ADR, or board item
- **Board state** — what's done, what's in flight, what's stuck
- **ADR drift** — decisions marked "proposed" or containing "revisit", "temporary", "when we have", "Phase 2"
- **Orphan TODOs** — `TODO`/`FIXME`/`HACK` in source that don't map to any open issue
- **Aging triage** — issues labeled `needs-triage` or `needs-info` older than 7 days

### 3. Report

Print a single structured report. No essays — tables and one-liners.

```
## Feature Fill Report — <date>

### Term Gaps (CONTEXT.md → Implementation)
Glossary terms or ADR-referenced features with no implementation, issue, or deciding ADR.
| Term / Feature | Source | Status |
|---|---|---|

### Stale Decisions
ADRs with "revisit" / "temporary" / "Phase 2" language, or superseded status.
| ADR | Decision | Staleness signal |
|---|---|---|

### Stuck Work
Board items in Backlog or Needs Triage for >7 days, or In Progress with no recent commit.
| # | Title | Column | Age |
|---|---|---|---|

### Orphan TODOs
Source TODOs/FIXMEs not linked to any open issue.
| File:Line | Comment |
|---|---|

### Suggested Next Moves
Top 3–5 highest-leverage things to build or decide, ranked by:
1. Unblocks other work
2. Closes a term/ADR gap
3. Resolves a stale decision
```

### 4. Offer

After the report, ask:

> "Want me to `/to-issue-kanban` any of these gaps into trackable issues?"

Do NOT auto-create issues. The user picks which gaps deserve tracking.

## Constraints

- Read-only. This skill never creates issues, edits files, or commits.
- Never read the full PRD. It's a frozen seed spec, not a gap source — touch only §13/§14 and only when an ADR/term points there (use the TOC + targeted offset reads).
- Keep the report under 80 lines. If there are >10 items in a section, show top 5 and note the count.
- Implementation subagents (if dispatched for parallel reads): sonnet.

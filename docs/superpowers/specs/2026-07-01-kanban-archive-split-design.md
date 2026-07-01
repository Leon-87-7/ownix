# ISSUE_KANBAN.md archive split — design spec

**Date:** 2026-07-01
**Status:** Approved (brainstorm)
**Area:** `ISSUE_KANBAN.md`, `agent-knowledge/skills/kanban-sync.md`, `agent-knowledge/skills/update-kanban/SKILL.md`

## Goal

`ISSUE_KANBAN.md` has grown to 253 issue/PR rows — the Done and Closed PRs
tables alone are 161 + 83 = 244 rows, dwarfing the 9 rows of genuinely
actionable work (Needs Triage + Ready for Agent + Ready for Human + Open PRs).
Split the historical rows out to `docs/archive/ISSUE_KANBAN-archive.md` and
keep them from ever re-accumulating, so the live board stays fast to scan.

The naive approach — a one-time cut, unchanged sync behavior afterward —
doesn't hold: `/update-kanban`'s reconcile pulls the full closed-issue/PR
history from GitHub on every run and currently has no concept of "already
archived," so it would silently re-add everything the next time it runs. This
spec fixes the root cause in `kanban-sync.md`, not just the one-time symptom.

## Scope decisions (from brainstorm)

- **Split boundary is by status, not by issue number.** Archive all of Done +
  all of Closed PRs; the four "live" columns (Needs Triage, Ready for Agent,
  Ready for Human, Open PRs) are untouched — that's the actionable work, and
  it's small (9 rows today).
- **A rolling window stays visible on the live board**, not zero:
  - **Done:** the last 3 Dependency Map "groups" that contain at least one
    `✅-Done` issue, walking the map bottom-up. A "group" is one of the
    blank-line-delimited blocks in the Dependency Map (the same unit
    `to-issue-kanban` appends per §5 of `kanban-sync.md`) — e.g. "Tooltip
    system", "Brain Links nav + graph controls".
  - **Closed PRs:** the 4 highest-numbered rows, flat (no grouping).
- **Orphan Done rows** — a Done issue with no corresponding Dependency Map
  node — are **appendages of the group immediately preceding them in the
  Done table's current row order**. They travel with that group: live while
  the group is in-window, archived in the same batch when the group ages
  out. (Rationale: they're one-off tasks with no lineage of their own: not
  worth inventing a synthetic group for.)
- **The Dependency Map tree itself is never trimmed or archived.** It's
  already tree-shaped and compact (not a flat row list), and it's the source
  of truth for group membership — archiving parts of it would break the
  windowing logic that reads it.
- **Archive file:** one file, `docs/archive/ISSUE_KANBAN-archive.md`, same
  table shapes as the live board (a Done table, a Closed PRs table). No
  rotation/chunking — revisit only if this file itself becomes unwieldy.
- **No separate "archived-IDs" ledger.** The archive file's own rows are the
  registry; `update-kanban` checks archive presence by looking up `#N` in that
  file directly.

### Deliberate omissions (YAGNI)

- No numeric cutoff (e.g. "issue # ≤ 250") — rows aren't numerically ordered
  in the tables, so this would cut awkwardly across in-flight groups.
- No archive chunking/rotation scheme yet.
- No changes to Needs Triage / Ready for Agent / Ready for Human / Open PRs
  handling — those already stay small by nature (things move out as they're
  resolved).
- No code — this is entirely a change to markdown-instruction skill files
  plus a one-time hand-applied data migration of `ISSUE_KANBAN.md`.

## Migration snapshot (computed against the current file, 2026-07-01)

**161 Done rows / 83 Closed PR rows today.** Walking the Dependency Map
bottom-up, the last 3 blocks containing a `✅-Done` issue are:

1. **Per-user export isolation** — #202 done (root); #204/#205/#206 still
   open. Orphan **#234** attaches here (immediately precedes it in the Done
   table).
2. **Brain Links nav + graph controls** — #238, #251, #252, all done. Orphan
   **#254** attaches here (immediately follows it — the last row in the Done
   table today).
3. **Tooltip system** — #243–#247, all done.

**Live Done window (11 rows):** #202, #234, #238, #243, #244, #245, #246,
#247, #251, #252, #254.

**Everything else in Done (150 rows) moves to archive** — including the
"Doc Parser dashboard page" block (#217–226, #228, #231, #240), which was in
the window during an earlier count of this same design and has since aged
out as newer groups landed.

**Live Closed PRs window (4 rows):** #261, #260, #258, #257. **The other 79
Closed PR rows move to archive.**

This snapshot is a point-in-time computation for the one-time migration.
`kanban-sync.md`'s ongoing windowing logic (below) recomputes it fresh on
every future write — the plan/migration step must re-run this walk against
whatever `ISSUE_KANBAN.md` looks like at execution time, not copy these exact
numbers if the board has moved again.

## Archive file format

`docs/archive/ISSUE_KANBAN-archive.md`:

```markdown
# Issue Kanban — Archive

> Rows moved out of `ISSUE_KANBAN.md` to keep the live board scannable.
> GitHub Issues remains authoritative — this file (and the live board) are
> both read-only snapshots. Rows are appended here as they age out of the
> live board's rolling window; nothing here is ever deleted or re-derived.

---

## Done

|   # | Title | Area | Notes |
| --: | ----- | ---- | ----- |

---

## Closed PRs

| # | Title | Branch→Base | Linked Issue | Status |
| --: | ----- | ----------- | ------------ | ------ |
```

Same column shapes as the live board's tables (`kanban-sync.md` §3, §8) so
rows move verbatim, no reformatting.

## Ongoing mechanism — `kanban-sync.md` changes

**New §9 "Archive rolling window,"** applied at the end of every Done-row
write and every Closed-PR-row write (i.e. inside the shared helper, so both
`triage-kanban` and `update-kanban` inherit it automatically — no per-caller
logic):

1. **After inserting/updating a Done row:** re-walk the Dependency Map
   bottom-up to find the last 3 blocks containing a `✅-Done` issue (the
   window). For every Done row on the live board whose issue is not in one
   of those 3 blocks and is not an orphan attached to one of them, remove it
   from the live Done table and append it to the archive file's Done table
   (skip the append if that `#N` is already present there — idempotent).
2. **After inserting a Closed-PR row:** keep only the 4 highest PR numbers on
   the live board; move any others to the archive file's Closed PRs table
   the same way (append-if-absent).
3. **Orphan handling:** a Done row with no Dependency Map node is evaluated
   against the group immediately preceding it in the live Done table's
   current order at the time of the walk (not a fixed assignment made once —
   if the board is later reordered this is recomputed, but in practice rows
   are appended in encounter order so this stays stable).

**§2 column mapping** — "closed-completed → Done" now means "route through
the §9 window," not "always land directly on the live board." A newly-closed
issue can still appear briefly on the live board and then archive out on the
very next sync if its group has already aged out.

**§8 PR section** — currently "blow away and rebuild every run from
`gh pr list --state all`." This is the actual root cause of the unbounded
growth and changes to: diff `gh pr list` output against (live Closed PRs ∪
archive file) by PR number; append only genuinely new closed PRs to the live
table; then apply the §9 window. The full-rebuild-every-run behavior is
retired.

## `update-kanban` changes

In the delta table (`update-kanban/SKILL.md` step 2), the rule
"Closed-completed, on board but not Done → move to Done" and "Closed-completed,
not on board → backfill Done" both gain a precondition: **check the archive
file for that `#N` first.** If present there, the issue is already accounted
for — no-op, don't backfill it back onto the live board. Only issues that are
closed-completed and absent from *both* the live board and the archive get
backfilled.

## Verification

No test suite applies (markdown skill instructions + one hand-applied data
migration, not application code). Verification is:

- After the one-time migration: live board's Done table has exactly the 11
  rows listed above (or the freshly recomputed equivalent at execution time),
  Closed PRs has exactly 4, and every row that moved out is present verbatim
  in `docs/archive/ISSUE_KANBAN-archive.md` (no row lost, none duplicated).
- Row count sanity check: `(live Done + live Closed PRs + archive Done +
  archive Closed PRs)` after migration equals `(live Done + live Closed PRs)`
  before migration.
- A subsequent dry run of `/update-kanban`'s delta computation (§1–§2 of its
  skill, read-only — do not apply) should show **zero** "backfill → Done"
  entries for anything already in the archive, confirming the resurrection
  bug is closed.

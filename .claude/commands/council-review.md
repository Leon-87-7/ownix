---
description: Council code review — 6 read-only reviewers in parallel, one synthesis, optional follow-up plan
---

Run a council code review of `$ARGUMENTS` (default: the current branch's diff vs `main`).

Dispatch these **6 subagents in parallel, in a single message**. Every agent is
**read-only**: it may Read/Grep/Glob and run its review skill, but MUST NOT Edit,
Write, or run any command that mutates the repo. State this in each prompt.

Each agent returns: findings only — `file:line`, severity, what's wrong, suggested fix.
No agent applies fixes.

1. **ponytail** — `subagent_type: general-purpose`. Invoke the `ponytail:ponytail-review`
   skill on the target. Hunt over-engineering only: what to delete/simplify.
2. **correctness** — `subagent_type: general-purpose`. Run the `/code-review` command
   (`~/.claude/commands/code-review.md`) on the target: bugs, security, perf, architecture.
3. **interfaces** — `subagent_type: general-purpose`. Invoke the
   `make-interfaces-feel-better` skill on any UI changed in the target.
4. **react** — `subagent_type: general-purpose`. Invoke the `react-component-review`
   skill on changed `.tsx`/`.jsx` components in the target.
5. **python** — `subagent_type: general-purpose`. Invoke the `python-backend-review`
   skill on changed `.py` files in the target.
6. **thermo** — `subagent_type: general-purpose`. Invoke the
   `thermo-nuclear-code-quality-review` skill on the target. Harsh maintainability
   rubric: abstraction quality, giant files, spaghetti conditions, code-judo
   restructurings. Overlaps ponytail (agent 1) by design — ponytail hunts what to
   delete, thermo hunts what to restructure; keep both voices in the synthesis.

If the target has no UI / no React changes, agents 3 and 4 report "nothing to review" —
still dispatch them. Same for agent 5 if the target has no Python changes.

After all 6 return, synthesize ONE report, de-duplicating overlapping findings
and noting where reviewers disagree. Do not edit anything yourself — this command
only reviews (the optional planner step below is the one exception, and it only
writes a plan document, never source).

## Output format

- Open with one summary line, colored-circle emoji + count per severity, always
  all four even if zero: `🔴 <n> · 🟠 <n> · 🟡 <n> · ⚪ <n>`.
- Group findings under headings with the emoji inline: `## 🔴 Blocker`, `## 🟠 Major`,
  `## 🟡 Minor`, `## ⚪ Nit` (omit empty groups from the body, but still count them
  in the summary line above).
- One bullet per finding, prose, no tables: `` `file:line` `` — one-line description
  — suggested fix — `(reviewer)` attribution.
- Merge duplicates into a single bullet listing every reviewer that raised it; call
  out disagreements explicitly (e.g. "ponytail says delete, react says keep").
- End with a one-line **Suggested order** of what to fix first.

## Optional: write an implementation plan for the findings

`<review-target>` = the current git branch name with every `/` replaced by `-`
(e.g. `claude/foo-bar` → `claude-foo-bar`) — always, regardless of what
`$ARGUMENTS` names as the review target, since that's what round-tracking below
keys off.

If the synthesis has at least one finding (any severity), determine which round
this is for `<review-target>` by checking, in order:

1. Does `docs/superpowers/council/<review-target>-council-fixes.md` exist?
   **No** → this is **round 1**.
2. Does `docs/superpowers/council/<review-target>-council-fixes-round2.md` exist?
   **No** → this is **round 2** (the intended final round).
3. Otherwise → this is **round 3+**.

**Round 1 or round 2:** ask the user whether they want an implementation plan
written for these findings, offering three options: **plan + parallel sub-plans**
(chunked for parallel agent execution — see "Chunking into parallel sub-plans"
below), **single plan only**, or **no plan**. If the user's invocation already
asked for a chunked/split/parallel plan, skip the question and chunk. If yes to
either plan option, dispatch ONE more agent
(`subagent_type: general-purpose`, after synthesis — not parallel with the 5
reviewers) that invokes the `superpowers:writing-plans` skill to turn the
synthesized findings into a task-by-task implementation plan (Global Constraints,
one Task per finding or logical group of related findings, checkbox steps, a test
step, a commit step — see `docs/superpowers/council/` for prior examples of this
format). This agent MAY write — it is the only step in this command permitted to.

The planner starts cold — its prompt MUST include the full synthesized report
verbatim (every finding with `file:line`, severity, reviewer attribution). Do
not tell it to re-derive findings from the diff. Also require of the plan:

- **Pinned context header**: open the plan with the reviewed commit
  (`git rev-parse --short HEAD`) and diff range (e.g. `main..HEAD`), so the
  executing agent knows whether `file:line` references have gone stale.
- **Contested findings are not tasks**: any finding where reviewers disagree,
  or that conflicts with known project policy/won't-fixes, goes in a
  **Skipped / needs user decision** section — never as a task the executing
  agent silently resolves.
- **Literal verification commands**: each task's test step names the exact
  command (e.g. `python -m pytest tests/test_x.py -q` — direct, never through
  rtk), not a generic "run the tests".

Save to:
- Round 1: `docs/superpowers/council/<review-target>-council-fixes.md`
- Round 2: `docs/superpowers/council/<review-target>-council-fixes-round2.md` —
  open this file with a one-line **Context** callout linking back to the round 1
  file, and a note that this is the intended final auto-generated round.

Deliberately **not** `docs/superpowers/plans/` — these are review artifacts for
agent handoff, not plans authored ahead of implementation. Report the saved path
back to the user.

### Chunking into parallel sub-plans

Only when the user chose it (or asked for it in the invocation). Runs AFTER the
master plan is written — the planner agent does it as a second step, or the
orchestrator does it directly. Mechanics:

1. **Map footprints**: for each task, collect every file it touches (the
   `Modify:`/`Create:`/`Delete:`/`Test:` lines). Tasks sharing ANY file form a
   conflict cluster and must land in different chunks.
2. **Assign greedily by priority order** into waves: walk tasks in the plan's
   fix order, placing each into the earliest chunk where it conflicts with
   nothing already there. Cap chunks at ~6-7 tasks. The largest conflict
   cluster sets the minimum number of chunks.
3. **Escape hatch**: if two same-file tasks can't be separated (e.g. both belong
   in the last chunk), put them in one chunk but assign BOTH to a single agent
   that runs them sequentially, and say so in a chunk-specific note.
4. **Write one file per chunk** to
   `docs/superpowers/council/sub-plans/<plan-name>-chunk<N>-<slug>.md`. Each is
   self-contained: a worker note (dispatch one subagent per task, all in
   parallel, in a single message; chunks execute strictly in order), a
   commit-discipline note (edits/tests run in parallel but commits are
   serialized by the orchestrator — parallel `git add`/`commit` races on
   index.lock), a parallel task map (task → files, proving disjointness), the
   master's Global Constraints verbatim, then the full task bodies copied
   verbatim (keep original task numbers). Split mechanically — a throwaway
   script splitting on `^## Task \d+` headings beats hand-copying a big plan.
5. **Rewrite the master plan's worker note** into an index: a table of chunk →
   sub-plan link → task numbers → theme, plus "do not execute this file
   top-to-bottom; work the sub-plans in order". The master stays the source of
   truth for finding details.

Report both the master path and the sub-plan paths back to the user.

**Round 3+:** do not offer to write a plan. End the synthesis with: *"This is
round 3+ for this branch — per policy, remaining findings should go through PR
review (open a PR, run `/greploop` or `/check-pr`), not another generated plan."*

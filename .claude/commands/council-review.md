---
description: Council code review — 4 read-only reviewers in parallel, one synthesis
---

Run a council code review of `$ARGUMENTS` (default: the current branch's diff vs `main`).

Dispatch these **4 subagents in parallel, in a single message**. Every agent is
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

If the target has no UI / no React changes, agents 3 and 4 report "nothing to review" — still dispatch them.

After all 4 return, synthesize ONE report grouped by severity (blocker → nit),
de-duplicating overlapping findings and noting where reviewers disagree. Do not
edit anything yourself — this command only reviews.

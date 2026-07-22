# Cloud Patch — prompt anatomy

Extracted from `docs/cloud-patch/codex-391-395-onboarding-hero.md` (cohesive
feature) and `docs/cloud-patch/codex-399-402-410-security-hardening.md`
(independent batch). Read both once before drafting a new one. Deviate only
when the batch genuinely doesn't fit either shape.

## 1. Title + hard-stop banner

```
# Codex prompt — implement issues #<range> (<short slug>)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.
```

This banner is load-bearing — it's the first thing Codex reads. Restate it
verbatim, don't paraphrase it away.

## 2. Required context

`## Required context — read these first, in this order` — a numbered list.
Order matters: put whatever is authoritative first (an ADR or plan overrides
"older wording elsewhere in the file" — say so explicitly if true), then
`CLAUDE.md`, then the concrete files being changed, then the GitHub issues
themselves last (`gh issue view <n> --repo Leon-87-7/ownix`), since their
acceptance criteria are the per-slice definition of done.

## 3a. Cohesive feature: key decisions

`## Key decisions already made (do not relitigate)` — bullet list of settled
calls (naming, file layout, behavior) so Codex doesn't re-derive or
contradict them mid-batch. Only include decisions that aren't already
obvious from the required-context docs.

## 3b. Independent batch: nature of this batch

`## Nature of this batch` — state plainly: these don't share a
migration/schema/helper; forbid inventing a shared abstraction across issues
unless one issue's own acceptance criteria calls for it; state the ordering
rationale (usually severity); explicitly grant permission to skip a slice
and note why if it needs a human design call, then continue to the next.

## 4. Per-issue/slice sections

`## Work order` (feature) or `## Issues` (batch), one `### #N — <short
title>` subsection per issue:

- Cite the **current** `path:line` finding — actual code, not paraphrase
  (SKILL.md step 3).
- A `Fix:` / `Fix direction:` paragraph that is prescriptive, not
  exploratory — if the repo already has a convention for this shape of
  problem, point Codex at it and say "mirror that pattern, don't invent a
  new one" (e.g. the `SpaceIcon` `Literal` convention, the existing
  `mint_handoff` TTL convention).
- An explicit regression clause: "existing valid `<X>` must keep working."
- A test-coverage requirement matching this repo's actual test conventions
  (colocated, naming pattern).
- Slices needing a non-code human call (art, copy, timing) get suffixed
  `(HITL — scaffold only)` / `(HITL — prepare only)` and state exactly what
  Codex's part is vs. what's deferred to a human.

## 5. Hard constraints

Always present, always includes:

- No commits, no pushes, no PRs, no branch creation — working tree only
  (yes, restate it a third time).
- A scope fence: don't touch files/areas outside what's named; don't
  refactor unrelated code in a file opened for one fix.
- For independent batches: don't merge issues into one shared helper/module
  unless an issue's own acceptance criteria calls for it.
- The exact test/lint commands from `CLAUDE.md`, plus: never through the
  `rtk` hook (see `.claude/rules/rtk-tests.md`).

## 6. Deliverable

`## Deliverable` — uncommitted working-tree changes implementing the stated
scope, regression tests per issue's acceptance criteria, and a short summary
of what was done per issue/slice plus anything that blocked (e.g. a missing
convention that needs a human call on where to source a secret from).

---
name: spec-to-kanban
description: Run the plan-to-board pipeline by creating GitHub issues, triaging them, reconciling ISSUE_KANBAN.md, and drafting the Codex Cloud handoff in one sequence.
disable-model-invocation: false
---

# spec-to-kanban

Wrapper that runs the full plan→board pipeline in one invocation:

1. `/to-issues` — break the spec/plan/PRD into GitHub issues
2. `/triage` — triage each new issue through the state machine
3. `/update-kanban` — one-shot reconcile of ISSUE_KANBAN.md against GitHub
4. `/cloud-patch` — draft the Codex Cloud handoff prompt for the batch, saved to `docs/cloud-patch/`

Invoke each skill sequentially via the Skill tool. Pass context forward between steps (the created issue numbers feed into triage, then into the cloud-patch batch). Do NOT use the `-kanban` variants of steps 1–2 — the single `/update-kanban` at the end handles all board writes in one pass.

Pass the issue numbers created in step 1 to `/cloud-patch` as its batch argument, so it never has to ask. `/cloud-patch` only drafts a document — it never implements the issues and never touches git.

Tell `/cloud-patch` which shape the batch is — **cohesive feature** (ordered slices, each building on the last) vs **independent batch** (unrelated fixes, no shared migration/helper) — and hand it the grounding it needs (ADRs, plan path, constraints worth pinning), so it never has to ask.

Skip step 4 when the run produced no new issues (e.g. a reconcile-only invocation): there is no batch to hand off.

## Usage

User invokes `/spec-to-kanban` (optionally pointing at a file or describing the spec). Follow the normal prompts of each sub-skill as they activate.

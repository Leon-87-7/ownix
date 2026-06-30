# spec-to-kanban

Wrapper that runs the full plan→board pipeline in one invocation:

1. `/to-issues` — break the spec/plan/PRD into GitHub issues
2. `/triage` — triage each new issue through the state machine
3. `/update-kanban` — one-shot reconcile of ISSUE_KANBAN.md against GitHub

Invoke each skill sequentially via the Skill tool. Pass context forward between steps (the created issue numbers feed into triage). Do NOT use the `-kanban` variants of steps 1–2 — the single `/update-kanban` at the end handles all board writes in one pass.

## Usage

User invokes `/spec-to-kanban` (optionally pointing at a file or describing the spec). Follow the normal prompts of each sub-skill as they activate.

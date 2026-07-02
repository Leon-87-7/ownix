---
name: pre-grill
disable-model-invocation: true
description: Fatten one-line feature ideas in docs/TASK.md into grounded technical briefs ready for a grilling session — anchored to real files via codegraph, with scope split by layer and the genuinely undecided calls surfaced as Open questions (not resolved). Use only when explicitly invoked as /pre-grill, or when the user asks to "fatten", "flesh out", "brief up", or "prep my ideas for grilling".
---

# pre-grill

Turn raw one-liners into agent-ready technical briefs. The output is **prep, not
answers**: pin scope to real code, surface what's undecided, and hand off to a
grill skill. Do **not** resolve the open questions — that is the grill's job.

## What counts as a "raw idea"

In `docs/TASK.md`, a raw idea is any entry that is still a one-liner — a bullet
under `## Inbox`, or a numbered task with no **Context / Wanted / Scope** body.
**Skip** anything marked `✅ DONE` or `✅ ISSUED #NNN` — never touch those.

## Workflow

0. **If invoked with an argument** (`/pre-grill "<one-line idea>"`), append it as a
   new `- ` bullet under `## Inbox` in `docs/TASK.md` first, then continue. With no
   argument, skip straight to step 1.
1. **Read `docs/TASK.md`.** Collect every raw idea. If there are none, say so and stop.
2. **Ground each idea before writing a word.** Never guess a path or symbol.
   Per idea, find the real code/docs it touches:
   - **Symbols/flow** → codegraph first (`codegraph_search`, `codegraph_explore`,
     `codegraph_trace`); fall back to Grep only for literal strings.
   - **Product/spec** → `docs/seed/PRD.md` via the two-step TOC lookup (see
     CLAUDE.md), plus `docs/adr/`, `CONTEXT.md`, `ISSUE_KANBAN.md`.
   - **Frontend** → `PRODUCT.md` + `DESIGN.md` tokens; the `web/` component/route.
   - **A PR/issue** (`#NNN`) → `gh pr view <n>` / `gh issue view <n>`.
   - **Third-party lib internals** → the opensrc cache paths in CLAUDE.md.
3. **Write the brief** for each idea using the house structure below.
4. **Detect entanglements.** When two briefs share state, ownership, ordering, or
   a schema, add a reciprocal `> **Grill together with task X.**` callout at the
   top of *both*, naming the shared decision.
5. **Move briefs into the numbered `## Briefs` list**; delete the consumed
   one-liners from `## Inbox`. Renumber only new entries; leave existing tasks' numbers stable.
6. **Stop and recommend a grill** (see "Handoff"). Do not start grilling.

## House structure for a brief

```md
## N. <clear, specific title>

> **Grill together with task X.** <the shared decision>   ← only if entangled

<Context: where this lives today, in 1-3 sentences, with real file refs
like `src/telegram/webhook.py` and the function/symbol names.>

**Wanted:** <one sentence — the outcome, not the implementation.>

**Backend / API / Data / UI**   ← use only the layers this idea actually touches
- <concrete scope, each bullet anchored to a real file/endpoint/component>
- <call out "reuse, don't fork" when logic already exists elsewhere>

**Open questions** (resolve in grill)
- <a genuinely undecided product/design/scope call — phrased as a question>
- <do NOT answer these; they are the grill's input>
```

## Rules (the pre-grill posture)

- **Clarity, not resolution.** Sharpen scope; leave product calls open.
- **Every claim cites code.** If you can't point to a file, it's an Open question,
  not a scope bullet.
- **Honor the design bar** for `web/` work: name the DESIGN.md tokens and the
  WCAG-AA / reduced-motion expectations rather than re-deciding them.
- **Don't invent requirements.** A vague idea yields a small brief with more Open
  questions — that's correct, not a failure.
- **Idempotent.** Re-running on an already-fattened task should be a no-op.

## Handoff

After writing, print a short summary: which tasks are now briefed, which are
flagged **grill-together**, and which grill skill fits each — then stop.

- Leans on a third-party API/SDK/integration → **`/grill-with-search-docs`**
- Leans on this repo's domain model / ADRs / terminology → **`/grill-with-docs`**
- Pure product/UX with no external or domain-model hinge → **`/grilling`**

Recommend grilling entangled tasks (shared `> Grill together` callout) in one
session. The user launches the grill themselves.

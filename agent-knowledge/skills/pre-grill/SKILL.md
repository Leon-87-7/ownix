---
name: pre-grill
disable-model-invocation: true
description: Fatten one-line feature ideas in docs/TASK.md into grounded technical briefs ready for a grilling session — anchored to real files via codegraph, with scope split by layer and the genuinely undecided calls surfaced as Open questions (not resolved). Also handles cleanup — mark a brief done and/or archive its finished body to docs/archive/TASK-archive.md, leaving a title-only stub behind in TASK.md. Use only when explicitly invoked as /pre-grill, or when the user asks to "fatten", "flesh out", "brief up", "prep my ideas for grilling", "mark this task done", or "archive finished briefs".
---

# pre-grill

Turn raw one-liners into agent-ready technical briefs, and keep `docs/TASK.md`
tidy once briefs are finished. The fattening output is **prep, not answers**:
pin scope to real code, surface what's undecided, and hand off to a grill
skill. Do **not** resolve the open questions — that is the grill's job.

## Two modes, chosen by the invocation

- **No args, or one or more quoted idea strings** → **fatten mode**.
- **`--mark-d`, `--mark-a`, or `--archive`** → **cleanup mode**. These never
  touch the Inbox or write briefs — they only change status markers and move
  finished bodies to the archive.

## Fatten mode

### What counts as a "raw idea"

In `docs/TASK.md`, a raw idea is any entry that is still a one-liner — a bullet
under `## Inbox`, or a numbered task with no **Context / Wanted / Scope** body.
**Skip** anything marked `✅ DONE` or `✅ ISSUED #NNN` — never touch those.

### Workflow

0. **If invoked with one or more quoted arguments**
   (`/pre-grill "<idea 1>" "<idea 2>" ...`), append each as its own new `- `
   bullet under `## Inbox` in `docs/TASK.md` first, then continue. With no
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
   one-liners from `## Inbox`. Renumber only new entries; leave existing tasks'
   numbers stable — numbers are permanent, even once a brief is later archived.
6. **Stop and recommend a grill** (see "Handoff"). Do not start grilling.

### House structure for a brief

```md
## N. <clear, specific title>

> **Grill:** `/<grill skill>` — <one-clause reason it fits (see Handoff mapping)>

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

### Rules (the pre-grill posture)

- **Clarity, not resolution.** Sharpen scope; leave product calls open.
- **Every claim cites code.** If you can't point to a file, it's an Open question,
  not a scope bullet.
- **Honor the design bar** for `web/` work: name the DESIGN.md tokens and the
  WCAG-AA / reduced-motion expectations rather than re-deciding them.
- **Don't invent requirements.** A vague idea yields a small brief with more Open
  questions — that's correct, not a failure.
- **Idempotent.** Re-running on an already-fattened task should be a no-op.

### Handoff

After writing, print a short summary: which tasks are now briefed, which are
flagged **grill-together**, and which grill skill fits each — then stop.

The recommendation is **also stamped on each brief** as its `> **Grill:**`
callout (see the house structure) so it survives the chat session — the
summary echoes it, TASK.md records it. Pick via this mapping:

- Leans on a third-party API/SDK/integration → **`/grill-with-search-docs`**
- Leans on this repo's domain model / ADRs / terminology → **`/grill-with-docs`**
- Pure product/UX with no external or domain-model hinge → **`/grilling`**

Recommend grilling entangled tasks (shared `> Grill together` callout) in one
session. The user launches the grill themselves.

## Cleanup mode

Task selectors are lenient: `"task 5"`, `"5"`, `"#5"`, `"Task 5"` all resolve
to brief number `5` — pull the first integer out of the string, ignore the rest.

A brief is **marked** when its `## N. <title>` header line ends with
`✅ <status>` (e.g. `✅ DONE`, `✅ ISSUED TO GITHUB #238`). A brief is
**archived** when it's marked *and* has no body left between its header and
the next `## ` header (or the section's closing `---`) in `TASK.md` — the
body already lives in `docs/archive/TASK-archive.md`.

### `--mark-d "task NN" ["task XX" ...]`

For each selector, in order:
- Resolve the brief number. If no such brief exists under `## Briefs`, skip it
  with a warning and keep processing the rest of the list.
- If already marked, no-op with a message ("task N already marked — nothing
  changed"). **Never overwrite an existing marker** — an `ISSUED #NNN` marker
  carries information a generic `DONE` would destroy.
- Otherwise append `✅ DONE` to the end of its header line. The body is
  untouched — this only changes the status.

Report what was marked, what was already marked (no-op), and what was skipped.

### `--mark-a "task NN" ["task XX" ...]`

Same selector resolution, not-found, and no-overwrite rules as `--mark-d`. For
each valid selector:
- If unmarked, stamp `✅ DONE` on the header (same as `--mark-d`). If already
  marked, leave the existing marker as-is.
- Move its full body (everything between the header and the next `## `/`---`)
  to the end of `docs/archive/TASK-archive.md`, verbatim, under its existing
  `## N. <title> ✅ <status>` header.
- Leave the bare header line behind in `TASK.md`, in its original position —
  title + marker only, no body.

Report what was marked+archived, and what was skipped.

### `--archive` (no selector — blanket sweep)

Scan every numbered brief under `## Briefs`. For every one that is **marked
but not yet archived** (a marker on the header, and a body still present),
move its body to the end of `docs/archive/TASK-archive.md` verbatim (same
archive step as `--mark-a`), leaving the bare header behind. This flag never
marks anything itself — it only archives what's already marked. If nothing
qualifies, say so and stop.

### Out of scope (deliberate)

- Does **not** self-heal a stub whose marker is missing despite having no body
  left — that state shouldn't occur going forward, since marking and
  archiving now always happen atomically in the same step.
- Does **not** scan other briefs for stale `> Grill together with task X`
  callouts pointing at a brief that just got archived — left for a human to
  notice and edit by hand.

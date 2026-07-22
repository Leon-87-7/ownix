---
name: cloud-patch
disable-model-invocation: true
description: Draft a Codex Cloud handoff prompt for a batch of GitHub issues and save it to docs/cloud-patch/. Use only when explicitly invoked as /cloud-patch — grounds Codex in the right ADRs/plans/CLAUDE.md, pins line-referenced findings and fix directions per issue, and forces working-tree-only (no commit/push/PR) output for human review.
---

# Cloud Patch

Codex Cloud is an external agent the user pastes this document into — it runs
unattended in its own working tree and hands back a diff for human review.
This skill only drafts that document; it never implements the issues itself
and never touches git.

## Process

### 1. Gather the batch

Args passed to `/cloud-patch` should be an issue number, range, or list (e.g.
`391-395` or `399, 402-410`). If missing, ask.

Determine which shape this batch is — it changes the template:

- **Cohesive feature** — issues are ordered slices of one plan, each building
  on the last (e.g. #391-395: restructure → orchestration → runtime →
  scenes → polish).
- **Independent batch** — issues share no migration/schema/helper; each is
  its own diff, ordered by severity/priority, none blocking the others (e.g.
  #399/#402-410: nine unrelated security-hardening fixes).

If unclear from the issue titles/labels, ask the user.

### 2. Fetch every issue

`gh issue view <n> --repo Leon-87-7/ownix` for each number in the batch —
treat each issue's own acceptance criteria as the definition of done for
that slice, not your paraphrase of it.

### 3. Re-verify every finding against the current code

Never trust line numbers or code excerpts pulled from an issue body or your
own memory of the conversation — grep/read the actual file now. Codex won't
have the conversation that produced the issue, only what's on the page, so a
stale line number sends it hunting instead of fixing.

### 4. Gather grounding docs

Whatever the batch actually depends on to be understood correctly, in
priority order: an authoritative ADR/plan if one exists (`docs/adr/`,
`docs/plans/`) and a note on where it overrides other wording, `CLAUDE.md`
(layout + test/lint commands), then the specific files being touched.
UI-flavored batches also want `DESIGN.md`/`PRODUCT.md`.

### 5. Write the document

Follow the structure and phrasing conventions in
[reference.md](reference.md) — extracted from the two prompts already in
`docs/cloud-patch/`. Save to `docs/cloud-patch/codex-<range>-<topic>.md`:
numbers ascending, no spaces, then a short kebab-case slug naming what the
batch is about — not "prompt" (that's true of every file in this
directory, so it says nothing) — e.g. `codex-415-417-addlink.md` for the
link-pipeline batch, `codex-391-395-onboarding-hero.md` for a landing-page
feature. Pick the slug from the batch's dominant theme: the feature name
for a cohesive batch, or the shared category for an independent one (e.g.
`codex-399-402-410-security-hardening.md`).

### 6. Hand it back for review

Show the user the file path and a one-line summary of what it covers. Don't
commit it — this is a working draft the user will read, edit, and paste into
Codex Cloud themselves.

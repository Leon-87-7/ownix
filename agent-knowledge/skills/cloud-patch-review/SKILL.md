---
name: cloud-patch-review
description: Reviews a diff that came back from Codex Cloud (via /cloud-patch) against its originating handoff doc in docs/cloud-patch/ — checks hard constraints, key decisions, per-issue fix directions, and test coverage were actually followed. Use when the user wants a Codex Cloud patch reviewed, asks "did Codex follow the prompt", or invokes /cloud-patch-review.
---

# Cloud Patch Review

Read-only adherence check. Never fixes anything itself — cloud-patch produced
an uncommitted diff for human review; this skill is that review, from the
"did it actually do what the prompt said" angle. Correctness/style bugs are
`/code-review`'s job, not this one.

## Process

### 1. Find the handoff doc

If the user names one, use it. Otherwise list `docs/cloud-patch/*.md` sorted
by mtime and pick the one matching the batch under review; if more than one
plausibly matches, ask.

### 2. Find the diff

cloud-patch forbids commits, so the diff is normally the working tree:
`git status` + `git diff`. If the user points at a branch/commit range
instead, diff that. Either way, check the **no commits / no pushes / no PRs
/ no branch creation** constraint first — `git log <base>..HEAD` should be
empty (or the user-given range only). A commit made where the prompt
forbade one is a hard-constraint failure, flag it before anything else.

### 3. Extract the checklist from the doc

Pull these sections verbatim (see `agent-knowledge/skills/cloud-patch/reference.md`
for what each should contain):

- **Key decisions already made** / **Nature of this batch** — settled calls
  that must not be relitigated or contradicted.
- One `### #N — <title>` block per issue — its `Fix:`/`Fix direction:`,
  the `path:line` it names, its regression clause, its test requirement.
- **Hard constraints** — scope fence, forbidden files, exact test/lint
  commands.
- **Deliverable** — tests present, summary given.

### 4. Walk the diff against the checklist

One pass per issue, one pass for hard constraints. For each item, find the
**current** file:line in the diff (files may have shifted since the doc was
written — don't trust the doc's line numbers, re-locate in the actual diff)
and mark:

- ✅ done as directed — cite the file:line that proves it
- ⚠️ done differently — describe the deviation; only a problem if it
  contradicts a key decision or acceptance criteria, say which
- ❌ missing / contradicts the doc — cite what's missing or what it
  contradicts (a forbidden file touched, a relitigated decision, a skipped
  regression test)

Also check the scope fence directly: diff the changed-file list against the
doc's named files + "don't touch X" bullets — anything outside that list
that isn't a mechanical side effect (e.g. a lockfile) is a scope violation.

### 5. Report

Per issue: verdict list of ✅/⚠️/❌ lines, each with its file:line evidence —
no prose paragraphs. Then a **Hard constraints** section, same format. Then
one line overall: clean / needs fixes before merge / needs a human call on
`<X>`. If anything is ❌, say what the fix is, but don't apply it — this
skill reports, it doesn't patch.

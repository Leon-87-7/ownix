---
name: cloud-patch-apply
description: Draft a Codex Cloud handoff doc for a batch of GitHub issues, submit it to Codex Cloud, wait for the run, and apply the resulting diff to the working tree after you approve it.
disable-model-invocation: true
---

# Cloud Patch Apply

End-to-end version of `/cloud-patch`: drafts the same handoff doc, then
submits it to Codex Cloud, waits for the run, and applies the diff once you
approve it — instead of leaving you to paste the doc in and the diff back
out by hand. Same working-tree-only, no-commit contract throughout.

## Inputs

Same as `/cloud-patch`: an issue number, range, or list (e.g. `391-395` or
`399, 402-410`). If missing, ask.

## Process

### 1. Draft the handoff doc

Invoke the `cloud-patch` skill via the Skill tool with the issue args
unchanged. It gathers the batch, fetches and re-verifies every issue against
current code, gathers grounding docs, and writes
`docs/cloud-patch/<range>-<topic>.md` per
[cloud-patch/reference.md](../cloud-patch/reference.md). Note the file path
it reports — that's the doc for the rest of this flow.

### 2. Submit it

Read the doc from step 1 into a shell variable first — feeding it straight
into a double-quoted command substitution re-parses any backticks the
markdown contains as a command substitution of its own:

```bash
PROMPT="$(cat docs/cloud-patch/<file-from-step-1>.md)"
BRANCH="$(git branch --show-current)"
codex cloud exec --env ownix --branch "$BRANCH" "$PROMPT"
```

`ownix` is this repo's Codex Cloud environment label (confirmed via
`codex cloud list --json` → `environment_label`). If `--env ownix` errors,
browse `codex cloud` interactively once to find the environment's real ID
and use that instead.

Capture the task ID (`task_...`) and task URL from the command's output —
both also show up per-task in `codex cloud list --json` if the direct
output is awkward to parse.

### 3. Wait for the run

Poll `codex cloud status <task_id>` until it reaches a terminal state (not
queued/running) — a few seconds between polls, this typically takes
minutes. `codex cloud list --json` shows `status` per task too, useful as a
cross-check.

### 4. Show the diff, then ask

Run `codex cloud diff <task_id>` and show it to the user in full — this is
the same diff `/cloud-patch-review` would check against the handoff doc's
checklist, so don't summarize it away.

Use `AskUserQuestion` with these options, recommended first:

- `Apply to working tree (Recommended)`
- `View diff again`
- `Discard`

Never apply without this confirmation. The point of `/cloud-patch`'s
working-tree-only, no-commit contract is a human reviewing before the patch
lands — skipping the ask defeats that silently.

### 5. Apply

On approval:

```bash
codex cloud apply <task_id>
```

This lands as an uncommitted working-tree diff — the same shape
`/cloud-patch` already produces when pasted manually. Committing, pushing,
or opening a PR from it stays the human's call, same as before.

## Completion criterion

Either the diff is applied to the working tree after the user was shown it
and approved, or the user explicitly discarded it. Suggest
`/cloud-patch-review` as the next step once applied — it checks the applied
diff against the same handoff doc's checklist.

---
adr: "0062"
title: Gardener (MCP) reuses hard-delete link removal, no new soft-delete tier
status: accepted
date: 2026-09-14
---

## Context

The MCP roadmap's Phase 1 ("Gardener") lets an AI agent flag Second Brain
links as dead/broken/not-worth-keeping for the user to approve, then delete.
The roadmap's first draft recommended a new soft-delete/archive column with
an undo window, reasoning that an agent misclassification followed by a
permanent delete is the failure mode most likely to destroy user trust.

That reasoning is sound in isolation, but the codebase already has an answer
to "hard delete vs. soft delete" for exactly this shape of endpoint. ADR-0042
rejected a trash tier for `DELETE /api/jobs/{job_id}`, for reasons that are
about the *delete*, not about who clicks the button: a trash tier means a
retention policy, a restore path, and a second set of filters on every list
query. `DELETE /api/brain/links/{link_id}` (`src/db/tags.py:199`) already
follows the same hard-delete pattern with no soft-delete column. `links` does
carry an `archived` column, but it holds GitHub-repo-archived-status metadata
(`src/brain.py:1049-1081`), unrelated to trash/undo.

Giving Gardener its own soft-delete tier would mean this codebase has two
delete semantics for conceptually the same action, distinguished only by
whether a human or an agent-plus-human-approval triggered it — a distinction
a future reader would have no way to guess without this ADR.

## Decision

Gardener's confirm-gated delete tool calls the existing `delete_link`
primitive as-is. No new soft-delete column, no trash tier, no undo window.

The safeguard against agent misclassification is the approval step itself,
not a recovery path after the fact: `flag_item` surfaces its reasoning to
the user at approval time (not just a bare verdict), and copy avoids
loaded framing ("not worth keeping," never "garbage"/"junk") so a flag reads
as a question the user is settling, not a verdict already reached. See
`docs/mcp-roadmap.md` Phase 1 UX requirements.

## Considered options

**New soft-delete/archive column on `links`, with an undo window.** Rejected:
duplicates ADR-0042's rejected trash-tier tradeoffs (retention policy, restore
path, extra list filters) for the same underlying action, just triggered by a
different caller. Two delete semantics in one codebase for the same resource
is the kind of thing that needs re-explaining every time someone touches
either path.

**Block Gardener from deleting at all — flag only, human deletes manually
via the dashboard.** Considered but rejected: the roadmap's own
confirm-gated design already puts a human decision between flag and delete;
routing that same click through a different UI doesn't add safety, only
friction, and defeats the point of an MCP tool.

## Consequences

- Gardener's `flag_item`/delete-confirm tools are a thin MCP wrapper over
  existing primitives (`delete_link`) — no new schema, no new migration.
- If real-world Gardener usage later shows misclassification is a bigger
  problem than the approval step alone handles, revisit this — the fix at
  that point is tightening the approval UX (e.g. requiring the reason to be
  read, not skippable), not resurrecting a trash tier.

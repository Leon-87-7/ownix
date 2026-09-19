---
adr: "0063"
title: Space MCP tools (Phase 4) pin existing jobs only, no optimistic-concurrency guard on blobs
status: accepted
date: 2026-09-19
---

## Context

The MCP roadmap's Phase 4 lets an AI agent manage a user's Spaces (create/
rename/delete a Space, pin/unpin/reorder jobs, create/edit/delete/reorder
context blobs) with the same propose-then-approve shape as Gardener: the
agent narrates the change, the user approves, a dedicated confirm-gated tool
executes it (grilled 2026-09-19, see `docs/mcp-roadmap.md` Phase 4).

Two scope questions came up that don't have an obvious default:

**Adding jobs to a Space.** `add_space_url(space_id, job_id)` only pins a job
that already exists — it doesn't create one. `create_and_enqueue_job()`
(`src/services/jobs.py`) is the only path that enqueues new work, and it
currently has exactly three callers (Telegram webhook, dashboard
`POST /api/jobs`, repo follow-up), each owning its own result notification.
Letting the "add URL to Space" MCP tool also ingest a brand-new URL would
make MCP a fourth, agent-triggered ingestion path — a bigger scope change
than "manage a collection," and one that runs against the roadmap's
"user-initiated only, no background execution" framing (job processing
happens on the worker queue, outside the conversation turn that approved it).

**Editing context blobs.** `update_context_blob` (`src/db/spaces.py`) is
unconditional last-write-wins — no version or `updated_at` check. That's
already true for the dashboard's own Milkdown autosave (two dashboard tabs
editing the same blob already clobber each other), so an MCP write path adds
a third writer to an existing race rather than a new failure mode.

## Decision

**Space MCP tools only pin/unpin jobs that already exist in the caller's
Index.** There is no MCP tool that enqueues a new job. Populating a Space
with a URL that doesn't have a job yet means ingesting it first through an existing
entry point, then pinning it — MCP-driven ingestion is out of scope for this
phase and would need its own grilling session if wanted later.

**Context-blob writes get no optimistic-concurrency check.** The MCP
`update_context_blob`/`create_context_blob` tools inherit the same
last-write-wins semantics the dashboard already has. No `updated_at`/version
parameter, no conflict rejection.

## Considered options

**Let the "add URL" tool ingest a new job when the URL isn't already a Brain
item.** Rejected: collapses two different concerns (curating existing
knowledge vs. adding new knowledge) into one tool, and hands MCP a job-queue
write path the roadmap's phases have deliberately avoided so far.

**Add an `expected_updated_at` guard to blob writes, reject on mismatch.**
Rejected for this phase: no other writer of `context_blobs` has this
protection, so building it only for MCP fixes an inconsistency nobody has
reported as a problem while leaving the dashboard's own two-tab race
unsolved. If clobbering shows up as a real complaint, it's a `context_blobs`
problem to fix once for every writer, not an MCP-specific patch.

## Consequences

- "Add URL to Space" stays a thin wrapper over `add_space_url`/
  `remove_space_url` — no new job-creation surface, no new caller of
  `create_and_enqueue_job`.
- An agent-approved blob edit can silently overwrite an unsaved dashboard
  edit in another tab, same as today. If usage shows this is a frequent,
  noticed problem, the fix is a shared concurrency guard on `context_blobs`
  that protects the dashboard too, not a Phase-4-only workaround.

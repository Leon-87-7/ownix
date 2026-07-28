---
adr: "0042"
title: Job hard delete with asynchronous cloud purge
status: accepted
date: 2026-07-27
---

## Context

Until now nothing in the product removed a job. `Clear failed` re-labels owned
`error` rows to `cancelled` (`src/services/job_recovery.py:156,209`) and the
dashboard filters `status != 'cancelled'` out of its lists — the row, its Drive
document, its Sheets line and its Brain node all survive. Task 33 asked for a
real delete on the job details page, and task 19 will put the same delete behind
more surfaces, so the endpoint contract had to be settled once.

Two things made "just `DELETE FROM jobs`" wrong:

1. **The cascade doesn't cover the Brain.** Five child tables cascade off `jobs`
   (`job_thumbnails`, `job_annotations`, `job_tags`, `space_urls`,
   `document_outputs`), but `links.source_job` (`src/database.py:179`) is
   `TEXT NOT NULL` with no foreign key. A row-only delete leaves the job
   returned by `/find` and drawn in the Brain graph, with its Obsidian `.md`
   still in Drive.
2. **The artifacts live outside SQLite.** `drive_url` / `drive_file_id` /
   `prd_auto_drive_*` / `prd_intent_drive_*` documents, the GCS objects behind
   `document_outputs.gcs_key` (`src/database.py:282` — the document pipeline's
   `raw_txt`/`raw_md`/`summary`/`clean`/`freestyle` outputs), and the job's
   Sheets row are all untouched by any SQL. Job thumbnails are *not* in this
   set: `job_thumbnails.bytes` is a SQLite BLOB (`src/database.py:101`), so the
   cascade already disposes of them. No delete primitive existed for any of the
   cloud artifacts: `storage.py` had only
   `upload`/`download`/`exists`, `drive.py` only upload/create/update, and
   `sheets.py` only append/update-row. The `jobs` table stores no sheet row
   index, so the Sheets line is not directly addressable and must be found by
   URL.

A third problem is timing: there is no live cancellation in this system. The
worker checks only process-level `asyncio.CancelledError`, and the video
pipeline is not idempotent (see invariant 12 / ADR-0010). Deleting a `pending`
job would leave its envelope in Redis and let the whole pipeline run afterwards,
uploading brand-new Drive and Sheets artifacts for a job the user just purged.

## Decision

`DELETE /api/jobs/{job_id}` — ownership via `get_owned_job`, `204 No Content` on
success, matching the existing `@spaces_router.delete(..., status_code=204)`
precedent. It is a **hard delete: no soft-delete column, no trash tier, no
undo.**

The delete is split across the two halves of the system:

- **Synchronous (request):** capture the job's artifact references, then
  `DELETE FROM jobs WHERE id = ?` (five tables cascade) **plus**
  `DELETE FROM links WHERE source_job = ?` to de-index the Brain. Return 204.
- **Asynchronous (worker):** enqueue a `job_purge` task envelope carrying those
  captured references, and delete the Drive documents, GCS objects and Sheets
  row from the worker. The references must travel *inside* the envelope — the
  row is already gone when the worker runs.

Deletion is allowed from **any** status. The worker re-checks that a job row
still exists after `BRPOP` and drops the envelope if it doesn't, which makes
deleting a `pending` job safe.

On the UI side: a quiet trigger at the bottom of the job details page (ghost
border + `text-status-error`, matching `spaces/[id]/page.tsx:78`) opening a new
reusable `web/components/ui/confirm-dialog.tsx`, whose confirm button is a
solid `#f87171` fill with near-black `#1b1309` text — the product's only filled
red, and it exists only behind a modal. On success the page calls
`router.back()`, falling back to `/feed` when there is no in-app history.

## Considered options

**Soft delete / trash tier.** Rejected: the user explicitly wanted permanent
removal, and a trash tier means a retention policy, a restore path and a second
set of filters on every list query.

**Row-only delete, honest label.** One SQL statement, but then the button cannot
claim to delete — the item stays searchable in the Brain and its Drive copy
lives on. Rejected as a support question waiting to happen.

**Fully synchronous purge.** Drive + GCS + Sheets inside the request. Rejected:
the click blocks on several Google API round trips, and a mid-way failure leaves
a half-purged job with no retry path.

**Fire-and-forget cloud purge.** Rejected: silently orphans artifacts whenever
Google hiccups, with nothing recording that it happened.

**Blocking deletes on non-terminal jobs (409).** Zero race and no worker change,
but a job wedged in `processing` is exactly the one users most want gone.

**`window.confirm`, matching the four existing call sites** (spaces delete,
Google disconnect, clear-failed ×2). Rejected in favour of a styled dialog, on
the grounds that a permanent cloud-wide delete deserves more weight than a
native alert. This deliberately splits the repo's confirm pattern: the other
four sites keep `window.confirm` and are **not** migrated.

## Consequences

- `status-error` (`#f87171`) is now an action color as well as a status hue.
  DESIGN.md defines no destructive button, so a `button-danger` token needs
  adding there; the Amber Rule is unaffected (amber still means "act", red now
  means "act destructively", and the two never appear as alternatives to each
  other).
- The repo now has two confirm patterns until someone migrates the rest.
- A job already mid-pipeline when deleted is not interrupted — the drop-if-
  missing guard fires at dispatch, not at each write point. That window can
  still orphan cloud artifacts. Closing it means an existence check before every
  artifact-creating step across `src/processors/`, deferred until it actually
  bites.
- Sheets rows are addressed by searching for the job's URL, since no row index
  is stored. A miss is logged and skipped, not retried forever.
- Purge is best-effort: a cloud failure never fails the user's click, so the DB
  can be clean while Drive/GCS/Sheets are not.

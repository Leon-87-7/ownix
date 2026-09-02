---
adr: "0057"
title: Symmetric transcript + enrichment Drive link tracking across pipelines
status: accepted
date: 2026-09-01
---

## Context

Two bugs were reported together: the short pipeline's Drive folder shows only
the digest/analysis doc, and the long pipeline's shows only the transcript.
Investigation found these are **two separate root causes**, not one shared bug:

- **Short pipeline** (`short_video.py`) already uploads both files to Drive —
  `{job_id}_short.md` (the Gemini Vision analysis) and `{job_id}_transcript.md`
  (the [[Short transcript step]], ADR-0020). But the `jobs` table has one
  `drive_url` column, and only the analysis doc's URL is ever stored there. The
  transcript doc's returned URL is discarded (`_deliver_transcript_doc`) — the
  file exists in Drive but nothing in the app tracks or surfaces it. A tracking
  gap, not a missing write.

- **Long pipeline**: Phase 1 (`long_video.py`) uploads the transcript and
  stores its URL as `drive_url`. Phase 2 (`enrichment.py`) — a separately
  queued task — has no Drive-write code at all. [[Enrichment]] output persists
  to SQLite and goes out via Telegram, but never reaches Drive. A missing
  feature, not a tracking gap.

On the dashboard job detail page, both the top "Open in Drive" button and the
transcript preview card's icon button read the same `job.drive_url` field.
That's coincidentally correct for the long pipeline's transcript card
(`drive_url` = transcript today) and for the short pipeline's top button
(`drive_url` = digest today), but wrong the other way round in each case —
which is the exact symptom reported.

The `jobs` table already has precedent for multiple purpose-specific Drive-URL
columns (`prd_auto_drive_url`, `prd_intent_drive_url`, `screenshots_drive_url`)
alongside the generic `drive_url`, rather than one column reused for different
meanings per content type.

## Decision

1. **`drive_url` always means the [[Enrichment]] doc**, for both pipelines.
   Short already writes it this way; long's Phase 2 (`enrichment.py`) now
   writes it too, once the enrichment doc is uploaded. This is a **semantic
   change for long jobs** — `drive_url` stops meaning "transcript" there.

2. **New column `transcript_drive_url` always means the transcript doc**, for
   both pipelines. Short's `_deliver_transcript_doc` now persists its return
   value here instead of discarding it. Long's Phase 1 (`long_video.py`) now
   writes here instead of into `drive_url`.

3. **File naming**, symmetric across pipelines:
   - Enrichment doc: `{job_id}_enriched_short.md` (renamed from
     `{job_id}_short.md`) / `{job_id}_enriched_long.md` (new).
   - Transcript doc: `{job_id}_transcript.md` for both — long's renamed from
     its previous `{slug}.md` (via the shared `build_transcript_markdown`
     helper) to match short's existing convention.

4. **Dashboard**: the top "Open in Drive" button is unchanged (still reads
   `drive_url`, label stays generic — it's the page's primary action). The
   transcript preview card's existing icon button is repointed from
   `job.drive_url` to `job.transcript_drive_url`, and its tooltip changes from
   "Open in Drive" to "Open transcript in Drive".

5. **Telegram**: `enrichment.py`'s completion message, which today links back
   to the transcript via `job.get("drive_url")`, now sends both links —
   transcript (`transcript_drive_url`) and the freshly-written enrichment doc
   (`drive_url`).

6. **Failure mode**: the long pipeline's new enrichment→Drive write is
   non-fatal (logged only), mirroring the short pipeline's existing
   best-effort precedent (ADR-0020). A Drive-write failure never blocks the
   job from reaching `done`.

7. **Scope**: new jobs only. No backfill or repair of historical `done` jobs.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Combine transcript + enrichment into one Drive doc per job | Same reasoning ADR-0020 already rejected for short (transcript stops being independently addressable for FTS5/NotebookLM ingest; mixes two concerns in one document) — extended here to long for consistency |
| Rename `drive_url` itself (e.g. to `enriched_drive_url`) and touch every existing call site | Unnecessary churn — short pipeline already uses `drive_url` with exactly this meaning; only long pipeline's usage needed to change |
| Give long's Drive write a fatal failure mode (block `done` on upload failure) | Inconsistent with the short pipeline's established best-effort precedent; enrichment already succeeded and was delivered via Telegram/DB — a Drive hiccup shouldn't regress the job |

## Consequences

- Historical long jobs completed before this ADR keep whatever they already
  have in `drive_url` — the transcript, not the enrichment doc. For those
  jobs, the top "Open in Drive" button opens the transcript; for jobs
  completed after this ADR, the same button opens the enrichment doc. This
  inconsistency is accepted as the cost of a new-jobs-only scope.
- Requires a migration: `ALTER TABLE jobs ADD COLUMN transcript_drive_url
  TEXT`, following the same pattern as the existing `screenshots_drive_url`
  addition.
- `enrichment.py` gains a Drive dependency it didn't have before (import of
  `src.services.drive`, an `upload_file` call).

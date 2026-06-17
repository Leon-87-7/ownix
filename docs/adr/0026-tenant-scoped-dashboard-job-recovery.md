---
adr: "0026"
title: Tenant-scoped dashboard job recovery
status: accepted
date: 2026-06-16
---

## Context

The dashboard surfaces `pending`, `error`, and in-flight job counts, but recovery behavior lived in worker startup reaping and Telegram callbacks, which made stuck work hard to reconcile from the web UI. ADR-0010 deliberately avoids automatic requeue of orphaned `processing` jobs because the processors are not idempotent, while ADR-0002 keeps Redis as a simple at-most-once list queue without dedupe.

## Decision

Add a tenant-scoped dashboard recovery panel that operates on the current visible content-type tab: `All` applies to all owned jobs, while `Short`/`Long`/`Article`/`Repo` scope by `content_type`; search text and status filters do not further scope recovery actions. V1 exposes explicit actions for retrying stale `pending` jobs, retrying `error` jobs, and clearing failed jobs; it relies on a shared 10-minute stale cutoff rather than Redis dedupe. `Clear failed` marks scoped `error` jobs as `cancelled` and never hard-deletes job rows.

## Recovery Semantics

`Retry pending` re-enqueues only scoped `pending` jobs older than the shared stale threshold. `Retry error` first runs tenant-scoped stale in-flight reaping for scoped `processing`/`enriching` jobs, then retries scoped `error` jobs conservatively: article errors retry the same job with `skip_document=true`; long-video errors with a stored transcript retry enrichment on the same job; short, repo, and long-without-transcript errors create a fresh replacement job from the original URL/template and mark the original failed row `cancelled` after successful enqueue. Non-retryable rows are skipped and reported as counts rather than failing the whole action.

## Notifications

Dashboard-triggered stale in-flight reaping sends the same Telegram recovery notifications as the worker startup reaper, because the user should still learn that previously in-flight work was converted to retryable failure. Other dashboard recovery actions do not send extra Telegram acknowledgements; the dashboard reports aggregate counts, and normal processors may still emit their usual messages after work is retried. V2 should add a Controls-page checkbox allowing users to opt out of Telegram notifications for dashboard-triggered recovery reaping.

## Consequences

`database.fetch_and_mark_stale_jobs()` should be generalized with optional `chat_id` and `content_type` filters so worker startup keeps the unscoped behavior and dashboard recovery uses the same policy tenant-scoped. The implementation should live behind a small `src/services/job_recovery.py` service, with thin endpoints in `src/api/jobs.py`, aggregate count responses, and a summary endpoint so the panel can show current-tab actionable counts without trusting the paginated feed.

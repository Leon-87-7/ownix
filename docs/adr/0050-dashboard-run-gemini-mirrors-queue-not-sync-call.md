---
adr: "0050"
title: Dashboard "Run Gemini" reuses the async enrichment queue, not a synchronous call
status: accepted
date: 2026-08-13
---

## Context

The job details page has no way to trigger enrichment on an existing job — `POST
/api/jobs` only creates new jobs. Telegram's equivalent gate (ADR-0012's template
picker keyboard) only ever appears for long-pipeline jobs sitting at
`transcript_done` (short jobs auto-enrich inline and never stop there), and enqueues
`{"task": "enrichment", "job_id": ...}` for the worker to pick up.

A second, more recent precedent exists on the same page: `POST
/api/jobs/{id}/checklists` calls `run_checklists()` **synchronously** inside the
HTTP request and returns the markdown directly — no queue, no Telegram involvement.

## Decision

The dashboard's "Run Gemini" trigger (`POST /api/jobs/{job_id}/enrich`) follows the
Telegram/queue shape, not the Checklists/synchronous shape: it validates the chosen
template (reusing `_resolve_job_template`, `src/api/jobs.py:173`), atomically claims
the job by changing `transcript_done` to `enriching`, and writes `jobs.template` plus
`jobs.freestyle_prompt` when Freestyle is selected. A non-Freestyle selection clears
any stale `freestyle_prompt`. Only a successful conditional claim may enqueue the same
`{"task": "enrichment", "job_id": ...}` envelope `_cb_template_pick` does
(`src/telegram/webhook.py:281`); an enqueue failure restores `transcript_done` so the
user can retry. The HTTP request returns immediately; the worker's existing
`enrichment.run()` does everything else, unmodified.

Because the details page has no live push, it polls while in-flight — `GET
/api/jobs/{id}` every 10s while `status === 'enriching'`, reusing `startPolling`
(`web/lib/polling.ts`) and the same in-flight-status convention Feed's
`useInFlightPolling` already established.

## Rationale

`enrichment.run()` unconditionally sends Telegram messages to the job's `chat_id` —
"🍪 now bakin'", the result, repo-followup offers (`src/processors/enrichment.py:470,
478,510,523`) — as an inherent part of running, not a caller-controlled option. Some
templates also run Brave-grounded search. Calling it synchronously from an HTTP
request would still fire every Telegram message mid-request and make the request
duration unbounded in a way Checklists (a single, side-effect-free Gemini call) never
has to handle. Reusing the queue keeps enrichment's one real implementation
untouched and treats the dashboard as a second trigger surface for the same
mechanism, not a parallel code path.

## Consequences

- A dashboard-triggered enrichment also lands in the user's Telegram chat — expected,
  not a leak: the chat is the job's existing history.
- No new "silent" enrichment path exists — `enrichment.run()` keeps exactly one
  calling convention regardless of trigger surface.
- The details page gains polling (`web/lib/fetch-utils.ts`'s `useFetchDetail` needs a
  `reload()` it didn't have before). Dashboard-triggered jobs use the same persisted
  `enriching` status as every other enrichment, so `reap_stale_jobs()` covers this
  flow: an orphan older than 10 minutes is reset to `error` and the user is notified.
  Details-page polling then stops when it observes that terminal status.
- The dashboard recipes panel mirrors Telegram's picker — the same five built-ins
  plus Freestyle — and does not list custom templates (`is_builtin=false` rows from
  `/api/templates`). This is a dashboard-selection limitation; the existing explicit
  `-name <url>` Telegram flow for user templates remains supported and unchanged.

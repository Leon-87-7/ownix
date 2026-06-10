---
adr: "0003"
title: Photo link extraction is inline (no DB job, no queue)
status: accepted
date: 2026-05-20
---

## Context

When a user sends a photo (e.g. a screenshot of a Reel), the bot should extract links from it. The question was whether this should go through the same job/queue machinery as video processing.

## Decision

Photo processing is inline: no `jobs` row is created, no Redis task is enqueued. The webhook handler downloads the photo, calls Gemini Vision, filters results, and replies to Telegram — all in a `asyncio.create_task` so the HTTP response to Telegram is immediate.

Brain ingest (`brain.ingest_links`) is fire-and-forget inside that task.

## Rationale

- **Photos complete in < 10s**: Gemini Vision responds fast. There is no long-running transcript download or multi-step enrichment pipeline. A queue adds latency and complexity with no benefit.
- **No retry value**: if Gemini fails, the user can re-send the photo. No state needs to survive a failure.
- **No audit trail needed**: photo link extraction is ephemeral. There is no user-facing job ID, no Drive document, no Sheets row.

## Trade-offs

- If the API container crashes mid-processing, the request is silently dropped. Acceptable given the low stakes (no Drive/Sheets output).
- Brain ingest failure is silent. Logged as a warning but not surfaced to the user.

## Consequences

- `_handle_single_photo` and `_process_batch` live in `webhook.py` (not in `processors/`).
- `gemini_photo.py` is a service, not a processor — it has no awareness of jobs or chat_id.

**Superseded (batch trigger only):** the explicit `/photoBatch-start` / `/photoBatch-end` window mechanism is replaced by Telegram `media_group_id` debounce — see ADR-0024. `_handle_single_photo` and the inline processing model are unchanged.

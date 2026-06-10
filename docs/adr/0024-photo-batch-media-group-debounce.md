---
adr: "0024"
title: Photo batch uses Telegram media_group_id with in-memory debounce, not explicit start/end commands
status: accepted
date: 2026-06-09
---

## Context

The initial batch design (ADR-0003 Consequences) used explicit `/photoBatch-start` / `/photoBatch-end` slash commands to open a 5-minute accumulation window. When a user sends multiple photos from the gallery as a single selection, Telegram already groups them natively via `media_group_id` — a shared field on every message in the selection. The explicit command approach required manual window management and was never shipped to users.

## Decision

Photo batch processing uses Telegram's native `media_group_id` field:

1. When a photo message carries a `media_group_id`, its file ID is appended to a Redis list (`photo_group_files:{media_group_id}`, short TTL).
2. A module-level task registry `_BATCH_TASKS: dict[str, asyncio.Task]` in `webhook.py` holds one debounce task per active group. Each new photo cancels the existing task for that group and creates a new 1-second sleep task.
3. When the sleep completes without cancellation, `_process_media_group` reads the Redis list, clears it, downloads all photos, and calls `call_gemini_photo_links` with all images in one shot.
4. One unified message is sent via `build_enriched_links_message`.

Photos without a `media_group_id` continue through `_handle_single_photo` unchanged — the two paths are fully parallel and independent.

The `/photoBatch-start` and `/photoBatch-end` commands are removed entirely.

## Rationale

- **Telegram already groups the photos**: `media_group_id` is the natural batch boundary — no user action required; the user already signals intent by selecting multiple photos in the gallery UI.
- **1-second debounce is sufficient**: Telegram delivers all photos in a media group within a few hundred milliseconds on normal connections. 1 second is a conservative upper bound.
- **In-memory task registry beats Redis timers**: the debounce window is 1 second — far too short for Redis TTL polling. An `asyncio.Task` per group is cancellable, zero-overhead, and simpler. Container restart within the window drops the task silently; the user re-sends — same resilience model as single-photo (ADR-0003).
- **Removing explicit commands reduces surface area**: the start/end commands were never shipped. Removing them eliminates a dead code path and two Redis key patterns.

## Trade-offs

- Photos sent from separate gallery sessions (not one media group) are processed as individual single-photo requests, not batched. Acceptable — the intended use case is a single gallery selection.
- Container restart within the 1-second debounce silently drops the in-flight batch. Acceptable — same resilience model as ADR-0003 (no retry value, user re-sends).
- Caption is not captured for media group batches (`None` passed to `call_gemini_photo_links`) — the common case for gallery multi-selects is no caption, and storing it adds a third Redis key per group for marginal benefit.

## Consequences

- `_BATCH_TASKS: dict[str, asyncio.Task]` added to `webhook.py` module scope.
- `_accumulate_media_group(chat_id, media_group_id, file_id)` is the new entry point for grouped photos.
- Deleted from `webhook.py`: `_cmd_photobatch_start`, `_cmd_photobatch_end`, `_is_batch_active`, `_add_to_batch`, `_get_batch_files`, `_clear_batch`, `_batch_auto_close`.
- Redis keys `photo_batch_active:{chat_id}` and `photo_batch_files:{chat_id}` replaced by `photo_group_files:{media_group_id}`.
- Brain ingest uses `source_job_id=f"photo_group_{media_group_id}"`.
- Supersedes the batch trigger mechanism described in ADR-0003 Consequences. The inline processing model (no DB job, no queue) is unchanged.

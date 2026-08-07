---
adr: "0048"
title: Bookmark import — a sibling task, not a seventh pipeline
status: accepted
date: 2026-08-07
---

## Context

A browser bookmark export is the one intake shape none of the six pipelines fit. The
reference file (`bookmarks_8_6_26.html`, 281 KB) holds 321 `<A>` tags — 318 http(s) URLs, 3
unusable (`chrome://`, `file:///`, a `javascript:` bookmarklet) — across 39 nested folders,
with an `ADD_DATE` epoch and a base64 favicon on every row.

Two shapes were available and both are wrong:

- **A seventh [[Content type]].** `jobs` carries `CHECK(content_type IN ('short','long',
  'unsized','article','repo','document','link'))`. SQLite cannot `ALTER` a `CHECK`, so a new
  content type means rebuilding a ~50-column table in a migration.
- **A branch inside `processors/link.py`.** Its `run()` is 38 lines doing one thing: fetch one
  page, ingest one link, verify one row landed. A bookmark job fetches nothing, ingests N, and
  verifies nothing.

Cost is the other half of the context. `ingest_links` (`brain.py:546`) is a sequential `for`,
and `_ingest_one_link` on a first sighting does a page fetch with Jina escalation
(`_resolve_identity`, `:208`), a Gemini embed, a full-table embedding scan, and a Drive
upload. At 318 links the first step alone — the only one measured in seconds, and the one
made redundant by a file that already carries every title — runs to tens of minutes, mostly
waiting on bookmarks that have rotted.

## Decision

**A sibling task, reusing `content_type = 'link'`.** A new `bookmarks` discriminator in
`_TASK_HANDLERS` (`worker.py:259`) and a new `src/processors/bookmarks.py`. The worker
dispatches on the [[Task envelope]]'s `task` string, not on `content_type`, and
`prd_auto` / `prd_auto_resend` / `prd_intent` / `job_purge` are already tasks that are not
content types. No migration.

**One [[Job card]], N standalone [[Link row]]s** — the same shape a [[Long video]] already
produces through `extract_description_links`, at a bigger N. Every bookmark is a full Brain
node with its own title, embedding, tags and graph presence; the card is a receipt, not a
container.

**Sliced so the links are usable first.** `list_links` (`brain.py:713`) searches with `LIKE`
over `url`, `title` and `description` and never reads `embedding`, so a row is fully
searchable the instant it is inserted:

1. parse → insert `url`, title, `topic` → **commit** → job `done`. Links are live.
2. a delayed, **import-scoped** enrichment pass reusing `_refresh_one_link` (`brain.py:1194`)
   resolves identity and embeds.

Embedding is *not* pulled forward into step 1. `_refresh_link_description` (`:1019`) returns
"the embedding must be invalidated" when the description lands, so embedding before the
description means embedding every link twice.

**Existing URLs are skipped, not touched.** A bookmark export is a snapshot of state, not a
stream of events: seeing a URL in August's export means the bookmark was never deleted, not
that it was encountered again. `seen_count` counts encounters, so a re-import bumps nothing.
Re-importing an unchanged export is N SELECTs and zero writes.

**Transport reuses `POST /api/intake/upload`.** `<!DOCTYPE NETSCAPE-Bookmark-file-1>` is a
magic-byte-grade signature every browser emits and nothing else does, so it becomes one
`_SIGNATURES` entry in `src/intake/mime_sniff.py` (`text/x-bookmarks`) plus one branch in
`uploads.py:33`. That inherits the rate limit, 20 MB cap, daily quota and idempotency cache
already built there, and makes the file work from Telegram, the share sheet and the Chrome
extension for free. The signature is specific enough that arbitrary HTML still sniffs to
`None` → 415.

**The HTML is not persisted.** The link rows are the parsed output; `jobs.url` gets
`bookmarks:<sha256[:16]>`.

**Folder names go to `links.topic`** (leaf, stripped), which is free and already the graph's
cluster key (ADR-0028). Promoting them to [[Link tag]]s is an opt-in checkbox form shown
*after* the import, pre-filled from `PRESET_COLORS` and `TAG_ICONS` (`tag-picker.tsx:39`,
`:55`) — never blocking the links from appearing, and re-openable later because `topic`
persisted the folder either way.

**`ADD_DATE` maps to `created_at`**, preserving real bookmark chronology, while
`last_seen_at` is set to now so a fresh import sorts to the top of the Links table.

## Considered options

- **Insert only, and let the global refresh loop do everything.** Rejected on measurement:
  `main.py:145` runs `refresh_stale_links` Sun/Wed at `effective_batch = 50`, and the live
  database already holds 449 rows in the repair set — every existing link has
  `description IS NULL`. Since `_select_refresh_batch` orders `updated_at ASC`, a fresh import
  sorts *behind* that entire backlog and would not be reached for roughly five weeks. The loop
  is also gated on `GOOGLE_DRIVE_FOLDER_BRAIN`, a Drive setting guarding DB repair work — it
  has resolved zero descriptions since May 2026. Deferring to it means deferring to something
  demonstrably not running.
- **Embed during step 1 so the graph is complete immediately.** Rejected: it doubles Gemini
  calls, because the description arriving later invalidates the embedding by design.
- **Fix the global refresh loop instead of scoping a pass to the import.** Rejected as
  coupling: a new feature would wait on a five-month-old backlog, and even repaired, the loop
  enriches May 2026's links before the ones just imported. The loop's Drive gate and dead
  backlog are a real bug, filed separately.
- **Persist the HTML to GCS like a PDF.** Rejected: a PDF is the artifact and gets re-read; a
  bookmark export is a transport envelope nobody opens twice.
- **A dedicated `POST /api/bookmarks/import`.** Rejected: re-implements the rate limit, size
  cap, quota and idempotency that `api/intake.py` already ships.

## Consequences

- **`_touch_existing_link` is bypassed on this path, which conceals a bug rather than fixing
  it.** `_rewrite_existing_md` (`brain.py:398`) calls `upload_file`, not `update_file`, so each
  rewrite creates a *new* Drive file. Had re-imports gone through it, a second import of 318
  unchanged bookmarks would have produced 318 duplicate Drive files, and a third 318 more. The
  bug still needs fixing for the paths that do touch existing links.
- **`topic` becomes user-authored for imported links**, where every other pipeline derives it
  from Gemini or OG tags. The Brain graph colors by *the user's own folder taxonomy* — better
  data than the scraper would produce, and the reason folder names are worth capturing even
  when the tag form is dismissed.
- **A re-import silently ignores bookmarks deleted since the last export.** Import is additive
  only; the Brain never shrinks to match the browser. Removing a link stays a deliberate act
  (ADR-0046).
- **`jobs.url` holds a non-navigable value** (`bookmarks:<hash>`), as it already does for
  `document` jobs (`parsed.py:62` stores a GCS key). The Feed must not render it as an `<a
  href>` for these cards.
- **The scoped enrichment pass is a second worker task**, so an import that is interrupted
  leaves links inserted and un-enriched — which is a valid resting state, indistinguishable
  from the repair backlog the refresh loop already handles.
- **Per-tenant correctness is inherited, not added.** `tags` already carries
  `chat_id NOT NULL` with `UNIQUE(chat_id, name)`, and links gain `chat_id` under ADR-0043.

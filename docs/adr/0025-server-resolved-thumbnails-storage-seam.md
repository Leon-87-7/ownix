---
adr: "0025"
title: Server-resolved thumbnails with a storage seam
status: accepted
date: 2026-06-13
---

## Context

The dashboard feed is moving from a content-type *filter bar* to content-type
*tabs*: the **All** tab keeps the list-of-rows view; each typed tab
(`short`/`long`/`article`/`repo`) renders jobs as a grid of preview cards, each
needing a preview image (a [[Thumbnail]]). No thumbnail data exists today — the
`jobs` table, the `/api/jobs` payload, and `JobSummary` carry no image field, and
the short-video "best frame" (`main_frame_index`) is sent to Telegram and
discarded, never persisted.

The four content types differ sharply in how a thumbnail can be obtained:

- **long** & **YouTube Shorts** — derivable for free from the URL
  (`img.youtube.com/vi/<id>/hqdefault.jpg`).
- **repo** — derivable for free from the URL; verified empirically that
  `opengraph.githubassets.com/<any-hash>/<owner>/<repo>` returns the OG image
  (HTTP 200, `image/png`) regardless of the hash segment, so no GitHub API token
  is needed.
- **IG/TikTok short** — no public image URL exists; the only source is the
  pipeline's best frame, which must be captured and stored.
- **article** — a public `og:image` URL exists but must be scraped at ingest.

Two questions had to be settled: (1) where thumbnail URLs are computed, and
(2) where the short-frame bytes live, given [ADR-0022] designates a GCS bucket as
the eventual home for uploaded files (not yet built — the app is still
SQLite + opt-in Drive).

## Decision

**1. Thumbnails are resolved server-side into one contract field.** `/api/jobs`
returns `thumbnail_url` (+ `thumbnail_kind`: `landscape`/`portrait`/`null`) for
every job, computed by a `_resolve_thumbnail(url, content_type)` helper. The
frontend is dumb: it renders `<img src={thumbnail_url}>` or a typed placeholder.
URL parsing is *not* duplicated in TypeScript — it reuses the Python URL logic
that already exists in `validators.py`.

**2. Short-frame bytes are stored behind a thin storage seam.** A
`save_thumbnail(job_id, bytes) -> url` / serve function backs the IG/TikTok best
frame. It is implemented over a SQLite blob now and served through an
ownership-guarded `GET /api/jobs/{id}/thumbnail` (reusing `get_owned_job`). When
GCS lands per [ADR-0022], only that one module changes — pipelines and the API
contract do not.

**3. Phasing.** Phase 1 (frontend + ~30-line `_resolve_thumbnail`, no migration)
lights up long, repo, and YouTube Shorts from URLs; IG/TikTok shorts and articles
show placeholders. Phase 2 (one migration + pipeline writes) persists the
IG/TikTok best frame and scrapes article `og:image`. No backfill of existing
short jobs (their frames are gone); article backfill is an optional separate
script.

## Consequences

- **Pro:** One contract — agents and the frontend build against
  `thumbnail_url`/`thumbnail_kind` once; Phase 2 fills in cases without touching
  the frontend. Avoids split-brain (some thumbnails client-derived, some
  server-served) and duplicated URL parsing in TS.
- **Pro:** The storage seam respects [ADR-0022]'s GCS direction without building
  GCS prematurely; the SQLite→GCS swap is localized to one module.
- **Pro:** Ownership is enforced on served frames via the existing
  `get_owned_job` guard — the feed is per-`chat_id` private.
- **Con:** SQLite-blob storage is interim migration-debt against [ADR-0022]
  until the seam is repointed at GCS.
- **Con:** URL-derived thumbnails depend on external hosts
  (`img.youtube.com`, `opengraph.githubassets.com`) and on the undocumented
  arbitrary-hash behavior of the GitHub OG endpoint; a typed placeholder is the
  fallback when an image 404s.

## Considered Alternatives

- **Client-side derivation (no backend field)** — TS builds the YouTube/GitHub
  URLs directly for a truly zero-backend Phase 1. Rejected: short/article can't
  be client-derived, so Phase 2 would introduce a second mechanism and a
  split-brain, plus re-implement `validators.py` URL parsing in TS.
- **Build GCS storage now** — Implement [ADR-0022]'s bucket as the first user of
  centralized file storage. Rejected: drags unbuilt infra (bucket, credentials,
  signed URLs) into a UI feature; large scope creep.
- **Drive hotlink for short frames** — Upload the frame via the existing
  `drive.upload_file` (already accepts bytes). Rejected: Drive returns a
  `webViewLink` viewer page, not a hotlinkable image URL; it won't render in an
  `<img>`.
- **Persist the Gemini summary as the short card title** — Rejected by the
  operator: the platform title (already stored in `jobs.title`) is sufficient, so
  no `ai_summary` column is added.

## Follow-up Notes

### 2026-06-14: Historical short thumbnails are re-derivable

ADR-0025 originally treated existing IG/TikTok short jobs as not backfillable
because their original frame bytes were not stored. That remains true: the
pipeline discarded the selected frame bytes after processing, so there is no
stored original frame artifact to copy into thumbnail storage.

However, historical short thumbnails can still be best-effort re-derived for
source URLs that remain public. The backfill path is to re-fetch frames through
the frame sidecar (`frames.fetch_frames` / `short_frames`) and persist a selected
frame via the same thumbnail storage seam introduced here. See
[`scripts/backfill_short_thumbnails.py`](../../scripts/backfill_short_thumbnails.py).

### 2026-07-26: Missing cache headers, not a rendering problem

A request to "make thumbnails SSR" (to fix a multi-second pop-in flash on the
feed's All tab) turned out to be a caching bug, not a rendering one. `/api/jobs`
already resolves `thumbnail_url` synchronously and cheaply (one batched
`get_thumbnail_job_ids` lookup, no per-item I/O) — the job list itself was never
the bottleneck. `GET /api/jobs/{id}/thumbnail`, which serves the persisted
IG/TikTok best-frame blob, had **no `Cache-Control` or `ETag`** — every page load
re-downloaded every short's thumbnail from scratch, uncached, queued behind the
browser's per-host connection cap. SSR would not have touched this: it only
changes when the `<img src>` HTML exists, not how long the browser's own image
fetch takes.

Fix: both `GET /api/jobs/{id}/thumbnail` and its anonymous-preview twin
`GET /api/preview/jobs/{id}/thumbnail` now share one response helper that adds
`Cache-Control: private, max-age=86400, must-revalidate` plus an `ETag`, and
handle `If-None-Match` with a bare `304`. (The preview twin previously had its
own `max-age=300` with no `ETag` — a drift from the owned route that predates
this fix; both now match.)

The ETag hashes the stored **bytes** (`sha256`) rather than reading
`job_thumbnails.created_at`: `save_thumbnail`'s `ON CONFLICT(job_id) DO UPDATE`
overwrites `bytes`/`mime`/`width`/`height` but never touches `created_at`, so a
reprocess (`/force <url>`, same `job_id` in place) or the backfill script can
silently swap the underlying frame without that column changing. A
timestamp-derived ETag would have kept validating a stale cached image forever
after such a swap; hashing the content is correct regardless of which write path
touched it. A 24h `max-age` was chosen over something shorter because
correctness no longer depends on it (the hash always self-corrects on the next
revalidation) — it only trades off request volume against how long a
reprocess-driven change might sit unnoticed in an already-warm browser cache,
which is an acceptable trade for a low-traffic, per-`chat_id` private dashboard.

---
adr: "0041"
title: Feed thumbnail preload (links-only SSR head start)
status: accepted
date: 2026-07-27
---

## Context

The Feed's first thumbnails are slow to appear on mobile because nothing about
them is on the early critical path. `web/app/(dashboard)/feed/page.tsx` is
`'use client'` end to end (deliberately — see [[Feed freshness model]]): on mount
`useFeedData` fetches the full job list, then cards render, and only *then* does
the browser discover each `<img>` — every one marked `loading="lazy"` — and start
a fresh connection to a third-party host (`img.youtube.com`,
`opengraph.githubassets.com`, article OG CDNs) or the same-origin stored-thumbnail
proxy. The image fetch cannot even begin until JS boots and `/api/jobs` returns.
The goal: the first thumbnails should feel effectively instant (target: visible
image well under the ~500ms+ the current chain costs before the first image byte),
across the **first 10 cards** on both mobile and desktop.

## Decision

Add a **links-only SSR head start** — not a server-rendered feed.

A small **server component** in the Feed layout fetches only the first 10 jobs
(`GET /api/jobs?limit=10`, forwarding the incoming session cookie;
`/api/preview/jobs` when only the `ownix_preview` cookie is present; emits nothing
when neither cookie exists) and renders **only** `<link rel="preload" as="image">`
tags for their `thumbnail_url`s. No cards are server-rendered; the client feed
architecture is untouched.

Four coordinated parts:

1. **Preload (step 1).** The 10 preload links let the browser download the first
   thumbnails in parallel with JS boot and the client `/api/jobs` fetch. Tiered:
   the first **4** carry `fetchpriority="high"`, the remaining **6** are plain
   preloads.
2. **Eager `<img>` (step 2).** The first **10** preview cards render their `<img>`
   `loading="eager"` (first 4 also `fetchpriority="high"`), threaded via an
   `index` prop down `PreviewGrid → PreviewCard → Thumbnail`. Cards 11+ stay
   `loading="lazy"`. This is required for the preloads to be *consumed*: a lazy or
   priority-mismatched `<img>` makes the browser discard the preloaded bytes.
3. **Preconnect (step 3).** Two static `<link rel="preconnect">` hints for
   `img.youtube.com` and `opengraph.githubassets.com` (helps cards past the
   preloaded 10). Instagram/TikTok thumbnails need none — served same-origin from
   `/api/jobs/{id}/thumbnail`, on an already-open connection. Article hosts are
   arbitrary and cannot be preconnected; the preload covers them regardless.
4. **Cache window (step 4).** Extend the stored (Instagram/TikTok) thumbnail
   `Cache-Control` from `max-age=86400` to `max-age=2592000` (30 days) so repeat
   views stay network-free for weeks. Third-party images are **not** shrunk.

Robustness: the server fetch lives in its own `Suspense` boundary with an
**800ms timeout**. The shell/skeleton always streams immediately; a slow or
cold backend simply skips the head start that once. The existing `/health`
keep-warm cron holds the tunnel/container hot so the fetch normally lands in
~250ms.

## Considered options

- **Full first-screen SSR** (render real cards server-side, hydrate over them):
  rejected. It puts the Vercel → Cloudflare-tunnel → self-hosted FastAPI round
  trip *ahead of first paint*, so the documented ~13s cold-start spike would blank
  the page — strictly worse than today's instant skeleton — and it forces a
  client/server handoff refactor of a deeply client-stateful page, contradicting
  [[Feed freshness model]].
- **No SSR, `<img>`/preconnect tuning only**: rejected as insufficient — the image
  fetch still can't start until JS boots and `/api/jobs` returns.
- **Mark stored thumbnails `immutable`**: rejected. Their bytes are *not*
  immutable — a reprocess/backfill can swap the frame at the same URL without
  bumping `created_at` (the reason the ETag hashes bytes; see ADR-0025 follow-up in
  `jobs.py:thumbnail_response`). `immutable` would pin a stale frame forever.
- **Mark stored thumbnails `public` for edge caching**: rejected. The endpoint is
  auth-gated per [[Tenant]], and a job id is a timestamp plus only 8 hex chars
  (`generate_id`) — weak entropy over a knowable timestamp. `public` would let a
  shared cache serve a tenant's image to anyone who guesses/enumerates a URL,
  breaking the tenancy boundary.
- **Shrinking YouTube/GitHub images** (`mqdefault` etc.): rejected. On the
  1-column mobile grid a card is near full phone width, so a 320px variant
  upscales blurry; the ~20KB images are latency-bound, not size-bound, so smaller
  bytes buy nothing.

## Consequences

- A single server-side fetch is added to the Feed's initial render, guarded by the
  800ms timeout and its own Suspense boundary — no effect on the client feed's
  behavior or the [[Feed freshness model]].
- Restricted-mode visitors get the same head start (their preview corpus), since
  first impressions matter most on the public demo.
- The list layout ([[Feed layout toggle]]) gets no benefit — it has no thumbnails,
  and its pref lives in `localStorage` (server-invisible). Grid is the default, so
  the common path is covered.

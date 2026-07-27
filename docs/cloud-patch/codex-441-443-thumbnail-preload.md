# Codex prompt — implement issues #441–#443 (Feed thumbnail preload — sub-300ms first thumbnails)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0041-feed-thumbnail-preload.md` — the accepted decision. This is
   **Option B** (a links-only SSR head start), explicitly *not* server-rendering
   the feed. It names the four coordinated steps, the two rejected caching
   tricks (`immutable`, `public`), and the rejected full-SSR alternative.
   Authoritative over any paraphrase below if the two disagree.
2. `CONTEXT.md` glossary entry **Feed thumbnail preload** (near **Bento feed
   grid** / **Short grid** / **Feed freshness model**). Use this vocabulary
   verbatim in code comments. Note especially: the feed is deliberately
   **all-client** (**Feed freshness model**) and must stay that way — this
   batch adds head hints, it does not server-render cards.
3. `CLAUDE.md` (repo root) — layout, test/lint commands; run pytest via the
   PowerShell path, never through the `rtk` hook (`.claude/rules/rtk-tests.md`).
4. The specific files each issue touches — line numbers are as of this writing
   and may have drifted; find the symbol by name if so.
5. GitHub issues #441, #442, #443 (`gh issue view <n> --repo Leon-87-7/ownix`)
   — each carries its own acceptance criteria; treat those as the definition
   of done per slice.

## Key decisions already made (do not relitigate)

- **Links-only SSR, not feed SSR.** No card is rendered on the server. A server
  component emits `<link rel="preload" as="image">` tags only; the existing
  client feed (`useFeedData`, `feed/page.tsx`) is untouched. Full first-screen
  SSR was rejected in ADR-0041 because it puts the Cloudflare-tunnel round trip
  (with its documented ~13s cold-start spike) ahead of first paint.
- **The 10 / 4 split is fixed.** Preload the first **10** thumbnails; the first
  **4** carry `fetchpriority="high"`, the other 6 are plain preloads. The first
  **10** cards render `loading="eager"`; the first **4** also
  `fetchpriority="high"`. These two numbers must match across the preload tags
  (#442) and the `<img>` tags (#441) or the browser discards preloaded bytes.
- **#442 is blocked by #441.** A preload is only *consumed* if the matching
  `<img>` is eager and priority-matched. Ship #441 first.
- **Dual-source by cookie** (#442): a `vig_session` cookie → `/api/jobs?limit=10`;
  else an `ownix_preview` cookie → `/api/preview/jobs?limit=10`; else emit
  nothing. Mirror the cookie-reading + server-fetch pattern already in
  `web/lib/restricted/server.ts` and `web/app/(dashboard)/layout.tsx`.
- **Preconnect only the two fixed third-party hosts** (`img.youtube.com`,
  `opengraph.githubassets.com`). Instagram/TikTok thumbnails are same-origin
  (`/api/jobs/{id}/thumbnail`) — already-open connection, no preconnect.
  Article thumbnails come from arbitrary hosts — can't preconnect, preload
  covers them.
- **Cache stays `private` + `must-revalidate`** (#443). Only the `max-age`
  extends (24h → 30d). `immutable` and `public` were both rejected in ADR-0041
  (bytes can be swapped by a reprocess/backfill; the route is per-tenant
  auth-gated with weak job-id entropy). Do not change those.

## Work order

Implement #441 first (root), then #442 (depends on #441). #443 is independent
and can be done in parallel with either — it shares no code with the frontend
slices.

### #441 — eager-load the first 10 feed preview cards (root)

- `web/components/feed/preview-grid.tsx:35` — the map callback is currently
  `{jobs.map((job) => (` with **no index**. Add the index parameter:
  `{jobs.map((job, index) => (` and pass `index={index}` down to `PreviewCard`.
  The grid renders `displayedJobs` in order, so `index` is the visible card
  position — the same order the #442 preload targets on first load.
- `web/components/feed/preview-card.tsx` — thread `index` through
  `PreviewCard` (props at `:20-27`, signature at `:80`) into the inner
  `Thumbnail` component (`:29-47`). In `Thumbnail`, the `<img>` at `:52-60`
  is currently:
  ```tsx
  <img
    src={job.thumbnail_url ?? ""}
    alt=""
    className="h-full w-full object-cover"
    loading="lazy"
    onError={() => setFailed(true)}
  />
  ```
  For `index < 10` render `loading="eager"`; for `index < 4` also add
  `fetchPriority="high"`. Add `decoding="async"` on the eager ones. `index >= 10`
  keeps `loading="lazy"` (and no `fetchPriority`). Keep the `onError`/`failed`
  fallback exactly as is.
- This applies uniformly across the `bento` / `uniform` / `compact` (shorts)
  variants — `index` is grid position regardless of variant, so no
  per-variant branching. The All-tab **list** layout renders `JobCard`
  (`feed/page.tsx:626`), which has **no thumbnail** and is untouched.
- Regression clause: cards 11+ must still lazy-load; the no-thumbnail fallback
  (`NoPreviewRing` + `PlatformGlyph`) path is unchanged.
- Tests (colocated, matching the existing `preview-card.test.tsx` /
  `preview-grid.test.tsx` conventions): render a job list of ≥11 items and
  assert `loading`/`fetchPriority` per index — first 4 `eager`+`high`, indices
  4–9 `eager` with no high priority, index 10+ `lazy`.

### #442 — thumbnail preload SSR head start — blocked by #441

- Create a new **server component** at
  `web/app/(dashboard)/feed/layout.tsx` (a route-scoped layout so the preload
  fires only on `/feed`, not every dashboard page). It reads cookies and
  fetches server-side exactly like `web/app/(dashboard)/layout.tsx:22-32`
  (`await cookies()`, `await headers()`) and `web/lib/restricted/server.ts`.
- Fetch the first 10 jobs server-side, forwarding the incoming cookie header,
  mirroring `fetchAuthStatus` in `restricted/server.ts:9-22` — same
  `API_INTERNAL_URL` base, `headers: { cookie: cookieHeader }`,
  `cache: 'no-store'`, and **`signal: AbortSignal.timeout(800)`** for the 800ms
  guard. Branch on cookies:
  - `vig_session` present → `GET ${API_INTERNAL_URL}/api/jobs?limit=10`
  - else `ownix_preview` === '1' → `GET ${API_INTERNAL_URL}/api/preview/jobs?limit=10`
  - else → render `children` with no preload tags.
  On any throw (timeout, non-ok, neither cookie) emit **zero** preload tags and
  render `children` normally — the head start is best-effort. Do **not** let a
  slow/failed fetch block the shell.
- Emit, into the document head, for the fetched `items[].thumbnail_url` (skip
  any null/empty `thumbnail_url`):
  - `<link rel="preload" as="image" href={url} fetchPriority="high">` for the
    first 4,
  - `<link rel="preload" as="image" href={url}>` for the next 6,
  - plus two static `<link rel="preconnect" href="https://img.youtube.com"
    crossOrigin="anonymous">` and the same for
    `https://opengraph.githubassets.com`.
  In the App Router, `<link>` elements rendered by a Server Component are
  hoisted to `<head>` by React — render them directly in the returned JSX
  (alongside `{children}`). If you prefer the `react-dom` resource APIs
  (`ReactDOM.preload(url, { as: 'image', fetchPriority: 'high' })` /
  `ReactDOM.preconnect`), that is acceptable **only** if it preserves the exact
  4-high / 6-plain tiering — otherwise use explicit `<link>` tags for precise
  control.
- **Isolation:** wrap the fetching part in its own `<Suspense>` boundary so the
  shell/`children` always stream immediately; the preload links appear in the
  head only if the fetch wins the race. The `AbortSignal.timeout(800)` is the
  hard cap. (`/health` keep-warm cron normally keeps this ~250ms.)
- **Known limitation — do not try to fix it:** a route `layout.tsx` cannot see
  `?type=`/`?status=` search params (only pages get `searchParams`), so the
  preload always targets the **unfiltered newest 10**. That is exactly the
  first-load default (no filter active), which is the target. On a filtered
  deep link (`/feed?type=short`) some preloads may go unconsumed — harmless
  (the browser drops speculative preloads after a few seconds). Do **not**
  thread searchParams into the layout or move the preload into the client page
  to "fix" this; it would defeat the whole point (SSR-early emission).
- Regression clause: with neither cookie, or on a timeout/failure, the page
  renders byte-for-byte as it does today (client feed unchanged).
- Tests: cover the three cookie branches (session → `/api/jobs`, preview →
  `/api/preview/jobs`, neither → no tags) and the timeout/throw path (no tags,
  no error). Match the repo's server-component test conventions; if none exist
  for a layout, unit-test the fetch/branch helper you extract rather than the
  JSX.

### #443 — extend stored thumbnail cache to 30 days (independent, parallel)

- `src/api/jobs.py:552-556` — the shared `thumbnail_response` helper currently
  sets:
  ```python
  headers = {
      "Cache-Control": "private, max-age=86400, must-revalidate",
      "ETag": etag,
      **(extra_headers or {}),
  }
  ```
  Change `max-age=86400` to `max-age=2592000` (30 days). Keep `private` and
  `must-revalidate` exactly as they are. Leave the ETag / `If-None-Match` 304
  branch (`:548-551`) untouched.
- This one helper backs **both** routes: `GET /api/jobs/{id}/thumbnail`
  (`jobs.py:574`) and `GET /api/preview/jobs/{id}/thumbnail`
  (`preview.py:243-257`, which calls `thumbnail_response(..., extra_headers=
  {"X-Robots-Tag": ...})` — that only adds a header, it does not override
  `Cache-Control`), so the change applies to both automatically. Do not
  duplicate the header logic into `preview.py`.
- Regression clause: 304-on-match behavior and the MIME allowlist fallback are
  unchanged; only the max-age value moves.
- Test: assert the response `Cache-Control` carries `max-age=2592000` on both
  the owned and the preview thumbnail routes (extend the existing thumbnail
  header test added by #436 rather than writing a parallel one).

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **Do not server-render feed cards** or otherwise alter the all-client feed
  data flow (`useFeedData`, `feed/page.tsx`). #442 adds a route layout that
  emits head links only.
- Do not change the thumbnail cache from `private` to `public`, and do not add
  `immutable` — both were explicitly rejected in ADR-0041.
- Keep the 10 / 4 boundaries identical between #441's `<img>` tags and #442's
  preload tags.
- Don't invent a shared abstraction spanning the three slices; #443 is backend
  and shares nothing with #441/#442.
- Don't refactor unrelated code in a file opened for one fix (e.g. don't
  restructure `preview-card.tsx`'s fallback block or `thumbnail_response`'s
  ETag logic while you're in there).
- Tests/lint: for #443 run `python -m pytest tests/test_jobs*.py -q` (or the
  file that covers the thumbnail route) and `ruff check src/` per `CLAUDE.md`,
  via PowerShell — never through the `rtk` hook (`.claude/rules/rtk-tests.md`).
  For #441/#442 run `npm run test:run`, `npm run lint`, and `npm run build`
  from `web/`.

## Deliverable

Uncommitted working-tree changes implementing #441–#443 in full, with
regression test coverage per each issue's acceptance criteria, plus a short
per-issue summary of what changed and anything that blocked you — in
particular, flag it if the App Router version in this repo does not hoist
`<link>` tags from a server-component layout as expected (so the preload
mechanism needs a human call between explicit `<link>` JSX vs. the
`react-dom` `preload`/`preconnect` APIs).

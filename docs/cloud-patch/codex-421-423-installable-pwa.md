# Codex prompt — implement issues #421–#423 (installable PWA: manifest, offline fallback, share-target intake)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/TASK.md` — **task 6** ("Make the web app an installable PWA",
   grilled 2026-07-23). Every open question is resolved inline there: no
   `next-pwa`/Workbox, hand-rolled ~20-line SW, no `/api/*` or payload
   caching, GET-based `share_target`, iOS out of scope, web push out.
   **Authoritative over any paraphrase below if the two disagree.** There is
   no ADR for this feature — the brief is the decision record.
2. `CLAUDE.md` (repo root) — Component layout (kebab-case files, colocated
   `.test.tsx`, no barrel files) and the web test/lint commands.
   `DESIGN.md` (repo root) — needed only for the `/offline` page: dark plate
   ladder, no decorative signal orange, JetBrains Mono for machine facts.
3. The specific files below — line numbers are as of this writing and may
   have drifted a line or two; find the symbol by name if so.
4. GitHub issues #421, #422, #423
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each issue's acceptance
   criteria are the definition of done for that slice.

## Key decisions already made (do not relitigate)

- **No new dependencies.** Chrome no longer requires a service worker for
  installability (manifest + HTTPS is the whole bar), so `next-pwa`,
  Workbox, and any SW toolchain buy nothing. The SW exists only for the
  offline fallback and is hand-written.
- **The SW caches exactly one thing: `/offline`.** No page caching, no
  `/api/*` caching, no payload caching — Ownix is a live-data console and
  stale data is worse than none. Do not add runtime caching "while you're
  in there".
- **`web/app/manifest.json` already exists and is mostly right** — name,
  maskable 192/512 icons (`web/public/web-app-manifest-*.png`),
  `display: standalone`, and `theme_color`/`background_color` `#0d0e10`
  (which matches the current `canvas` token in `web/tailwind.config.ts:9`
  — do **not** "fix" the colors). Next serves `app/manifest.json`
  automatically; no `layout.tsx` metadata wiring is needed for it.
- **`start_url` is `/feed`**, not `/` — `/` is the public landing and
  307s authenticated visitors to `/feed` (`web/middleware.ts`); the
  installed app skips that hop.
- **Share target is GET, action `/feed`**, params
  `share_title`/`share_text`/`share_url`. Android apps commonly put the
  shared URL in the *text* field, so the receiver must fall back to a URL
  regex over `share_text` when `share_url` is absent or not a URL.
- **A share arriving while logged out loses the URL — accepted.** The
  middleware's `/login` redirect drops the original query; do not build
  `returnTo` plumbing.
- **The share handoff opens the existing Submit URL dialog prefilled**
  (operator picks the template there) — no new submission UI, no
  auto-submit.
- **Web push is out of scope.** Do not add push/notificationclick handlers
  to the SW.
- **iOS is out of scope.** iOS Safari has no `share_target` for
  home-screen PWAs; iPhone intake stays the Telegram-bot share flow.

## Work order

Slices in issue order. #422 is independent of #421; #423 builds on #421's
manifest edit (same file).

### 1. #421 — complete the manifest for installability

- `web/app/manifest.json` — currently has `name`, `short_name`, `icons`,
  `theme_color`, `background_color`, `display` and nothing else. Add:
  - `"start_url": "/feed"`
  - `"id": "/feed"`
- That's the whole slice. Regression: the existing fields (icons, colors,
  `display: standalone`) must survive unchanged; the file stays plain JSON
  (do not convert it to a `manifest.ts` route).

### 2. #422 — offline fallback: `/offline` page + hand-rolled `sw.js`

- **New page `web/app/offline/page.tsx`** — static, on-brand per
  `DESIGN.md` (canvas plate, muted ink, mono for the "offline" status
  fact), zero data fetches, zero client hooks. One line of copy plus a
  "retry" affordance is plenty (a plain `<a href="/feed">` is fine — no
  JS required).
- **`web/middleware.ts:4`** — add `"/offline"` to `PUBLIC_PATHS`. Reason:
  the matcher (`:41-47`) already lets dotted asset paths (`/sw.js`,
  `/manifest.json`) bypass the session gate, but `/offline` has no dot —
  without this the SW's precache fetch would receive the `/login`
  redirect instead of the page.
- **New file `web/public/sw.js`** (~20 lines, plain JS):
  - `install` → `caches.open(...)` + `cache.add('/offline')`, then
    `self.skipWaiting()`.
  - `activate` → delete any old cache versions, `clients.claim()`.
  - `fetch` → **only** intercept `event.request.mode === 'navigate'`;
    respond `fetch(event.request).catch(() => caches.match('/offline'))`.
    All other requests fall through untouched — no `respondWith` for
    non-navigation fetches.
- **Registration** — new client component
  `web/components/shell/sw-register.tsx` rendered from
  `web/app/layout.tsx` (inside `<body>`, next to `MockProvider`,
  `:50-51`). It registers `/sw.js` in a `useEffect` and renders `null`.
  **Guard: skip registration entirely when
  `process.env.NEXT_PUBLIC_API_MOCK === '1'`** — mirror the `ENABLED`
  const convention in `web/components/shell/mock-provider.tsx:7`. MSW's
  `mockServiceWorker.js` owns scope `/` in mock mode and the two must not
  fight. Also skip when `navigator.serviceWorker` is undefined (jsdom,
  old browsers).
- Regression: online navigation and every `/api/*` call behave exactly as
  before; mock mode (`NEXT_PUBLIC_API_MOCK=1 npm run dev`) still boots
  with MSW intact.

### 3. #423 — share-target intake → Submit URL dialog prefill

- **`web/app/manifest.json`** — add (on top of #421's fields):

  ```json
  "share_target": {
    "action": "/feed",
    "method": "GET",
    "params": { "title": "share_title", "text": "share_text", "url": "share_url" }
  }
  ```

- **`web/components/feed/submit-job.tsx`** — the provider owns the Submit
  URL dialog's `url` state (`:305`) and its restricted-aware opener
  `setOpen` (`:254-265`), but the context (`SubmitJobContextValue`,
  `:59-70`) exposes no way to open it *prefilled*. Add
  `openSubmitWith(url: string)` — sets the `url` state then calls
  `setOpen(true)` (so restricted mode keeps its existing toast-and-refuse
  behavior for free) — and expose it through the context `value` memo
  (`:573-597`). Do not expose raw `setUrl`.
- **`web/app/(dashboard)/feed/page.tsx`** — extend the existing
  one-shot URL-cleanup effect (`:191-217` — the `?google=` / bad `?type=`
  handler; its comment explains why transient params are handled in a
  single `router.replace`) to also handle the `share_*` params:
  1. Read `share_url` and `share_text` from `searchParams`.
  2. Extract the shared URL: use `share_url` if it parses as http(s) via
     `new URL(...)`; otherwise take the **first** `https?://…` match from
     `share_text` (a small module-level helper, e.g.
     `extractSharedUrl(shareUrl, shareText): string | null` — exported for
     testing).
  3. If a URL was found, call `openSubmitWith(url)` (add it to the
     `useSubmitJob()` destructure, `:154-158`).
  4. Delete `share_title`, `share_text`, `share_url` in the same
     `params.delete(...)` + single `router.replace` pass the effect
     already does — so back/refresh never re-opens the dialog. Params are
     stripped even when no URL could be extracted.
- Regression: the existing `?google=` capture, bad-`?type=` cleanup, and
  restricted `?view=links` stripping in that effect must keep working —
  extend the effect, don't fork a second cleanup effect that races it.

### Tests

Colocated `.test.tsx` / `.test.ts`, matching the existing
`submit-job.test.tsx` and feed `page.test.tsx` conventions (Vitest + RTL +
MSW where a fetch is involved):

- `sw-register`: registers `/sw.js` when enabled; does **not** register
  when `NEXT_PUBLIC_API_MOCK === '1'` (mock `navigator.serviceWorker` and
  assert `register` calls).
- `extractSharedUrl`: unit-test the three shapes — valid `share_url`,
  URL embedded mid-`share_text` (e.g.
  `"Check this out https://www.instagram.com/reel/abc/ 😍"`), and neither
  → `null`.
- Feed share handoff: rendering the page with
  `?share_text=...https://example.com/x...` opens the Submit URL dialog
  with the URL prefilled, and the `share_*` params are removed via
  `router.replace`; a second render without params does not open the
  dialog.
- Existing suites stay green — especially `page.test.tsx`'s coverage of
  the `?google=` cleanup effect you're extending.

The manifest is static JSON — no test needed beyond it remaining valid
JSON (the build will catch syntax errors). `sw.js` itself is deliberately
too small to unit-test in jsdom; its logic lives in the three listeners
described above — keep it that small.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **No new dependencies** — no `next-pwa`, no Workbox, no `serwist`, no
  push libraries.
- Scope fence: touch only `web/app/manifest.json`, `web/middleware.ts`
  (the one `PUBLIC_PATHS` entry), the new `web/app/offline/page.tsx`,
  the new `web/public/sw.js`, the new
  `web/components/shell/sw-register.tsx`, `web/app/layout.tsx` (render
  the register component), `web/components/feed/submit-job.tsx`,
  `web/app/(dashboard)/feed/page.tsx`, and new/updated colocated tests.
  Do not refactor unrelated code in a file opened for one change.
- The SW must never cache or intercept `/api/*`, non-navigation requests,
  or any page other than `/offline`.
- Preserve DESIGN.md's bar on the `/offline` page: WCAG AA contrast, no
  signal orange except a genuine act-here affordance (the retry link does
  **not** qualify — keep it neutral), honor `prefers-reduced-motion` (no
  motion at all is simplest).
- Run `npm run test:run`, `npm run lint`, and `npm run build` from `web/`.
  (No Python touched in this batch. Never run tests through the `rtk`
  hook — `.claude/rules/rtk-tests.md`.)

## Deliverable

Uncommitted working-tree changes implementing #421–#423 in full — the two
manifest additions (`start_url`/`id`, then `share_target`), the `/offline`
page + `sw.js` + guarded registration, and the Feed's `share_*` param
handoff into a prefilled Submit URL dialog — with colocated regression
tests per each issue's acceptance criteria, plus a short summary of what
changed per slice and anything that blocked you (e.g. if the URL-cleanup
effect in `feed/page.tsx` has drifted from the cited shape).

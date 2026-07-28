# Handoff: migrate `web/` from Next 14.2.35 → 16.2.10

Status: planned; one prior attempt partially landed and was rolled back. Re-verified against `main` 2026-07-28. Work on a new branch off `main` (e.g. `chore/next16-migration`). Do NOT merge to main without the user's explicit say-so.

History: a first Next 16 attempt broke the job/space detail pages (async route params — fixed forward in PR #362, the `useParams()` cutover is already on `main`) and then the logout flow, which forced a revert to Next 14 (PR #363). The async-params fix survived the revert, so that part of the migration is already done; **logout is the proven regression surface** — it gets its own line in the verification checklist below.

## Context

- App: `web/` — Next.js App Router, standalone output, Dockerfile deploy, vitest + RTL + msw tests, middleware-based session gate.
- Source context is cached locally for both versions:
  - `C:\Users\leone\.opensrc\repos\github.com\vercel\next.js\14.2.35`
  - `C:\Users\leone\.opensrc\repos\github.com\vercel\next.js\16.2.10`
  - Authoritative upgrade guides: `<16.2.10>\docs\01-app\02-guides\upgrading\version-15.mdx` and `version-16.mdx`. Turbopack loader config: `...\01-next-config-js\turbopack.mdx`.
- The codebase is mostly 16-friendly: `app/(dashboard)/layout.tsx` and `app/(dashboard)/feed/layout.tsx` await `cookies()`/`headers()`; dynamic routes (`jobs/[id]`, `spaces/[id]`) are client components using `useParams()`/`useSearchParams()` (cut over by PR #362 after the first attempt broke them); no `useFormState`, no pages router, no fetch-cache reliance, no `images.domains`, no parallel routes. Node 23 and TS 5 meet the floors.
- **One known sync-API holdout** (added to the landing page after this plan was first written): `app/page.tsx:69` reads `cookies().get('vig_session')` **synchronously** in a sync server component. Next 16 removes sync `cookies()` — make `LandingPage` an `async function` and `await cookies()`. This is a required Step-1 companion fix, not a verify-only item.

Go 14 → 16 directly in one step; nothing here needs the Next 15 transitional shims.

## Step 1 — dependency bump

```
npm i next@16.2.10 react@19 react-dom@19
npm i -D @types/react@19 @types/react-dom@19
```

(or `npx @next/codemod@canary upgrade latest`, which also does some of the mechanical rewrites below).

Peer-dep watchlist — resolve on install, don't pre-bump: `lucide-react@^1.21`, `react-force-graph-2d`, `@milkdown/*`, `@paper-design/shaders-react`. Radix and `@testing-library/react@16.3` already support React 19.

## Step 2 — Turbopack is the default builder; the custom `webpack()` block breaks `next build`

`web/next.config.js:15-28` has a webpack SVGR rule. Next 16 fails the build when a webpack config exists (misconfiguration guard). Replace the whole `webpack()` block with the documented Turbopack rule (`@svgr/webpack` is on Turbopack's tested-loaders list):

```js
turbopack: {
  rules: {
    '*.svg': {
      loaders: ['@svgr/webpack'],
      as: '*.js',   // required — tells Turbopack the loader output is JS
    },
  },
},
```

SVGR consumers are TSX-only — seven imports of `@/app/ownix-logo.svg`, all under the post-#371 feature-folder layout: `app/page.tsx`, `components/shell/sidebar.tsx`, `components/shell/public-shell.tsx`, `components/ui/public-header.tsx`, `components/ui/footer.tsx`, `components/ui/no-preview-ring.tsx`, `components/ui/preview-motif.tsx`. No CSS `url()` consumers (the `/backgrounds/*.svg` in `auth-shell.tsx` is a plain `<img src>` public asset, untouched by the loader), so a blanket `*.svg` rule is safe. Keep `svgr.d.ts` as is. Tests are unaffected (vitest mocks the svg in `test/setup.ts`).

Fallback if SVGR misbehaves under Turbopack: keep the webpack block and set `"build": "next build --webpack"`. Try the Turbopack rule first.

## Step 3 — `middleware.ts` → `proxy.ts`

- Rename `web/middleware.ts` → `web/proxy.ts`; rename the exported function `middleware` → `proxy`. Keep the `config` matcher export (unchanged convention).
- Rename `middleware.test.ts` → `proxy.test.ts` and update its imports.
- Runtime becomes nodejs (edge unsupported in proxy) — the cookie-routing logic doesn't care.

## Step 4 — `next lint` is removed

`package.json` has `"lint": "next lint"` and there is **no eslint config file** in `web/`. `next build` no longer lints either. Either:
- run `npx @next/codemod@canary next-lint-to-eslint-cli .` (creates flat-config ESLint + rewrites the script), or
- drop the `lint` script.

Notes:

- The `eslint-disable @next/next/no-img-element` comment is now at `components/shell/sidebar.tsx:116`, and the same disable also appears in `components/feed/preview-card.tsx`, `components/feed/links-table.tsx`, `components/shell/auth-shell.tsx`, and `components/ui/platform-icon.tsx` — five files total. That tips the decision: the flat config must keep the `@next/next` plugin rules active (codemod path, not script deletion), or those five disables become dead comments over a rule that no longer fires.
- PR #401 (`chore(web): configure ESLint`, branch `chore/web-eslint-setup`) is open and touches this same gap on Next 14. Check its state before starting — either land/close it first or supersede it here; don't produce two competing ESLint configs.

## Verify-only items (don't pre-fix)

- `app/opengraph-image.tsx` sets `runtime = 'edge'` — root route, no params; should still build. If it complains, delete the `runtime` export (nodejs runs ImageResponse fine in 16).
- `next dev` now writes to `.next/dev` — irrelevant to the standalone Dockerfile.
- Fetch is uncached by default since 15 — `isRestrictedRequest`'s backend call becomes explicitly uncached, which is the desired behavior.
- `images.minimumCacheTTL` / `qualities` / `imageSizes` defaults changed — no configured remote images, no action.

## ~~Pre-existing bug found during planning~~ — RESOLVED

The `telegram-icon.tsx` remote-`next/image` bug flagged in the original plan is fixed: `components/svg/telegram-icon.tsx` is now a pure inline `<svg>` component with no `next/image` and no remote URL. No migration action; do not re-introduce a fix for it.

## Verification checklist

1. `npm run test:run` — full vitest suite green.
2. `npx next build` — must pass under Turbopack (this is the step most likely to surface issues).
3. `npx next dev`, then click through: landing `/` → login gate → `/feed` → `/jobs/[id]` → `/spaces/[id]` → `/restricted?exit` — exercises the proxy rename, SVGR components, and the restricted-mode cookie path (ADR-0035).
4. **Logout** — sign in, `/logout`, confirm the dedicated logout page renders and the session is gone. This is the regression that forced the PR #363 revert of the first Next 16 attempt; it is not optional.
5. Landing CTA both ways — `/` signed-out shows "Look inside", signed-in shows the feed CTA (exercises the `await cookies()` fix in `app/page.tsx`).
6. Docker build if touching the deploy: `docker build web/`.

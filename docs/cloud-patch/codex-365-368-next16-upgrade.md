# Codex prompt — implement issues #365–#368 (Next.js 14 → 16 upgrade)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/plans/2026-07-13-next14-to-16-migration.md` — the authoritative
   migration plan, **re-verified against `main` on 2026-07-31**. Its step
   order, the Turbopack SVGR rule, the sync-`cookies()` fix in
   `app/page.tsx`, and the "verify-only / don't pre-fix" list are binding
   where they differ from the issue bodies (the issues predate the
   re-verification).
2. `CLAUDE.md` (repo root) — the `web/` layout and the web commands
   (`npm run dev` / `test` / `test:run` / `test:coverage` / `lint` / `build`).
   Note `web/` components live under `web/components/<area>/` — kebab-case, no
   barrel files.
3. The files you are changing: `web/package.json`, `web/next.config.js`,
   `web/middleware.ts` + `web/middleware.test.ts`.
4. GitHub issues #365, #366, #367, #368
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each carries its own
   acceptance criteria; treat those as the per-slice definition of done. #366
   also has an AI-triage comment restating that the **Next.js ESLint plugin
   rules must stay active** in the new config (do not just delete linting).
   All four are still **OPEN** as of 2026-07-31 — nothing here has landed yet.

## Already-verified state (re-checked against `main`, 2026-07-31)

- `web/next.config.js:15-28` — the `webpack()` SVGR block is present exactly as
  the plan describes. Replace it (do not keep both — a webpack config present
  fails `next build` under Turbopack in 16).
- `web/package.json` — line 9 `"lint": "next lint"`; line 11
  `"test:run": "vitest run"`; deps still `next@^14.2.29`, `react@^18`,
  `react-dom@^18`. **No ESLint config file exists in `web/`** — PR #401 (the
  Next-14 ESLint config) was **closed unmerged on 2026-07-22**, so #366 has a
  clear field: there is no competing config to avoid.
- `web/middleware.ts` — exports `function middleware(...)` + `const config`
  matcher; `web/middleware.test.ts` exists. Both must be renamed.
- `web/app/page.tsx` — `export default function LandingPage()` at line 66 calls
  `cookies().get('vig_session')` **synchronously** at line 71. Next 16 removes
  sync `cookies()`; this must become `async function LandingPage` +
  `await cookies()` as part of #365. (The landing page has churned since the
  plan was written — recent onboarding-stepper work — so match on the symbol,
  not the line number.)
- The `eslint-disable @next/next/no-img-element` comment lives at
  `web/components/shell/sidebar.tsx:116` and also in
  `web/components/feed/preview-card.tsx`, `web/components/feed/links-table.tsx`,
  `web/components/shell/auth-shell.tsx`, and `web/components/ui/platform-icon.tsx`.
  Consequence: the new flat config **must keep the `@next/next` plugin's
  `no-img-element` rule active** so all five disables stay meaningful — don't
  produce a config where the rule no longer fires.
- `components/svg/telegram-icon.tsx` is a pure inline `<svg>` — the
  remote-`next/image` bug the plan once flagged is resolved. **No action; do
  not re-introduce a fix for it.**
- A first Next 16 attempt already happened: the async-route-params fix
  survived (PR #362 — `jobs/[id]` / `spaces/[id]` already use `useParams()`),
  but a **logout regression** forced the revert to Next 14 (PR #363). Logout
  is the known regression surface for this migration.

## Key decisions already made (do not relitigate)

- Go 14.2.35 → 16.2.10 **in one step**. Nothing here needs the Next 15
  transitional shims.
- **Turbopack replaces the webpack block outright.** The documented rule is
  `turbopack.rules['*.svg'] = { loaders: ['@svgr/webpack'], as: '*.js' }` (the
  `as: '*.js'` is required). A blanket `*.svg` rule is safe — all seven SVGR
  consumers are TSX imports of `@/app/ownix-logo.svg` (`app/page.tsx`,
  `components/shell/sidebar.tsx`, `components/shell/public-shell.tsx`,
  `components/ui/public-header.tsx`, `components/ui/footer.tsx`,
  `components/ui/preview-motif.tsx`, `components/ui/no-preview-ring.tsx`);
  there are no CSS `url()` consumers. Keep `svgr.d.ts` as-is; tests mock svg in
  `test/setup.ts`.
  - **Only** if SVGR misbehaves under Turbopack: fall back to keeping the
    webpack block and setting `"build": "next build --webpack"`. Try Turbopack
    first.
- **ESLint:** prefer running the codemod to a flat config
  (`npx @next/codemod@canary next-lint-to-eslint-cli .`) over dropping the
  script — #366's acceptance requires the Next.js ESLint plugin rules to stay
  active.
- **proxy rename** is a real Next 16 convention, not a cosmetic move: keep the
  `config` matcher export unchanged; runtime becomes nodejs (edge is
  unsupported for `proxy`) — the cookie-routing logic (session gate + ADR-0035
  restricted mode) does not depend on edge.
- **Peer-dep watchlist** — resolve on install, don't pre-bump: `lucide-react`,
  `react-force-graph-2d`, `@milkdown/*`, `@paper-design/shaders-react`. Radix
  and `@testing-library/react@16.3` already support React 19.

## Work order

Implement in issue order — #365 unblocks the rest; #366 and #367 are
independent of each other but both need #365 installed; #368 is the final
verification gate. Each slice must leave the app building and green
(`npm run build`, `npm run test:run` from `web/`).

### #365 — core upgrade: deps + Turbopack SVGR config

- `npm i next@16.2.10 react@19 react-dom@19`
- `npm i -D @types/react@19 @types/react-dom@19`
- Replace the whole `webpack()` block in `web/next.config.js:15-28` with the
  `turbopack.rules['*.svg']` rule above. Keep `output: "standalone"` and the
  `rewrites()` block untouched.
- Resolve peer-dep fallout on the watchlist packages at install time.
- Fix the sync-`cookies()` holdout: `app/page.tsx` (`LandingPage`) — make it
  an `async function` and `await cookies()`. Keep the session-aware CTA
  behavior (signed-in vs "Look inside") identical.
- `app/opengraph-image.tsx:7` sets `export const runtime = 'edge'`
  (**verify-only** — root route, no params, should still build). Drop the
  `runtime` export **only if** it breaks the build; nodejs runs `ImageResponse`
  fine in 16. Do not pre-remove it.

Regression bar: every SVGR import must still render as a React component;
`package.json` shows `next@16.2.10`, `react@19`, `react-dom@19`;
`npm run test:run` stays green.

### #366 — replace removed `next lint` with an ESLint flat config

- Run `npx @next/codemod@canary next-lint-to-eslint-cli .` to generate a
  flat-config ESLint setup and rewrite the `lint` script off `next lint`.
  Nothing to reconcile with — `web/` has no ESLint config today (PR #401
  closed unmerged).
- Confirm the generated config keeps the **`@next/next` plugin rules active**
  (five files rely on `no-img-element` disables — see Already-verified state),
  and that
  `npm run lint` runs the ESLint CLI directly and passes clean on current
  `web/` source.

Regression bar: `npm run lint` no longer shells out to `next lint`; zero lint
errors on current source; existing inline disables still apply.

### #367 — rename `middleware.ts` → `proxy.ts`

- Rename `web/middleware.ts` → `web/proxy.ts`; rename the exported
  `middleware` function → `proxy`. Keep the `config` matcher export exactly as
  written (the `.*\.` asset-exclusion clause is load-bearing — its comment
  explains why logged-out asset requests must not hit the gate).
- Rename `web/middleware.test.ts` → `web/proxy.test.ts` and update its imports
  (`middleware` → `proxy`).

Regression bar: `web/proxy.ts` exists with an exported `proxy`;
`middleware.ts` is gone; `npm run test:run` passes; the session gate and
ADR-0035 restricted-mode cookie routing behave identically (same
`vig_session` / `ownix_preview` logic, same redirects).

### #368 — end-to-end verification (HITL — mechanical checks only)

The manual click-through and the Docker standalone build are **human calls**
and not yours to sign off. Your part is the mechanical half:

- `npm run test:run` — full vitest suite green.
- `npx next build` — passes under Turbopack with no webpack config present
  (the step most likely to surface issues).

Then **report** what the human still needs to run themselves: `npx next dev`
click-through of `/` → login gate → `/feed` → `/jobs/[id]` → `/spaces/[id]` →
`/restricted?exit` (exercises the proxy rename, SVGR components, and the
ADR-0035 restricted-mode cookie path), the **logout flow** (sign in →
`/logout` → session gone — the regression that reverted the first Next 16
attempt, PR #363), the landing CTA in both signed-in/out states (the
`await cookies()` fix), plus `docker build web/` for the standalone deploy.
Do not fabricate results for these — flag them as pending human verification.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — **working tree only.**
- Touch only `web/` (and `docs/` if you must note something). Do not refactor
  unrelated components in a file you opened for one rename, and do not "fix"
  the already-resolved `telegram-icon.tsx` (see Already-verified state).
- Do not drop linting to satisfy #366 — the Next ESLint plugin rules stay on.
- Web commands are `npm run test:run` / `npm run build` / `npm run lint` from
  `web/`. If you run any **backend** Python tests, never route them through the
  `rtk` hook (`.claude/rules/rtk-tests.md`) — but this batch is web-only, so
  that should not come up.

## Deliverable

Uncommitted working-tree changes implementing #365–#367 fully and the
mechanical checks of #368, a colocated `web/proxy.test.ts` (renamed from
`middleware.test.ts`) passing, and a short per-issue summary of what changed —
plus an explicit "pending human verification" note listing the #368
click-through and Docker build, and anything that forced the SVGR
webpack-fallback path instead of the Turbopack rule.

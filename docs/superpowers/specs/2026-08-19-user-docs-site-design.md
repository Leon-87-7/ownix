# User docs site — design

Date: 2026-08-19
Status: approved, pending implementation plan

## Context

Ownix is preparing to open to users beyond the current invite circle. There is
currently no user-facing documentation — `docs/seed/*` and `CONTEXT.md` are
internal engineering references. Users need a place to learn how to get
access, submit their first URL, and understand what each pipeline (short
video, long video, article, repo, PDF, photo) returns.

## Decision: standalone Docusaurus site

A new, separate static site — not a `/docs` route inside the existing
`web/` Next.js dashboard. Keeps the docs build fully isolated from the
dashboard app (no shared risk, no shared deploy), and Docusaurus gives
MDX + sidebar navigation + build-time broken-link checking out of the box
without hand-rolling routing/nav in `web/`.

Rejected alternatives:
- **Integrated into `web/` (Nextra/MDX under a `/docs` route)** — couples
  docs deploys to the dashboard app's build/deploy; not chosen.
- **Hosted docs tool (Mintlify/GitBook)** — fastest to ship but recurring
  cost and vendor lock-in for content; not chosen.

## Stack & location

- New top-level folder `docs-site/`, sibling to `web/`.
- Docusaurus v3, TypeScript, npm (matches `web/`'s tooling).
- Own `package.json`, own `node_modules` — fully independent from `web/`.
- **No versioning** — Ownix is a single always-current product, not a
  versioned SDK/library.
- **No i18n** — single-language launch; add later if there's real demand.
- **No blog plugin** — the product already has `CHANGELOG.md`; a docs blog
  is speculative scope with no current user.
- **Dark mode only** — no light/dark toggle. The product itself is a fixed
  dark-canvas design (see `web/tailwind.config.ts`), and the docs site
  should read as the same product, not a generic light-first template.

## Content & information architecture

Hand-written MDX, not generated from `docs/seed/PRD.md`. The PRD is
internal/technical; user docs need the Constitution's product voice
(`docs/brand/CONSTITUTION.md`), not spec language.

Sidebar structure for v1:

- **Getting Started**
  - What is Ownix
  - Getting access (invite + Telegram Login)
  - Sending your first URL
  - Reading your results
- **Pipelines** (one page each)
  - Short Video (Reels / TikTok / YouTube Shorts)
  - Long Video
  - Articles
  - GitHub Repos
  - PDF Documents
  - Photos / Screenshots
- **Second Brain**
  - What it is
  - `/find`
  - Tags
  - Spaces
- **The Dashboard** (Operator's Console)
  - Feed
  - Brain graph
  - Controls
  - Doc Parser
- **FAQ / Troubleshooting**

Content authoring is out of scope for the implementation plan below — the
plan produces the scaffolded site with placeholder/stub pages per the IA
above; filling in final copy is a separate, subsequent pass.

## Theming (full custom)

- Tailwind CSS added to the Docusaurus build (`postcss` + `tailwindcss`
  plugin), configured with token **values copied** from
  `web/tailwind.config.ts` — not a shared package. The two projects are
  separate builds (Next.js vs Docusaurus); extracting a shared design-token
  package is not justified for a single consumer (this docs site).
  - Colors: `canvas #0d0e10`, `surface #16181c`, `raised #202329`,
    `ink #e6e6e6`, `body #b8b8b8`, `muted #948e84`, `signal #d99a45`
    (bright `#efb566` / deep `#a57534`), `contrasignal #94e6ee`
    (bright `#9ec9ff` / deep `#649ca1`), `line #30343d`.
  - Fonts: Inter (sans/body), JetBrains Mono (code), Montserrat (title,
    landing-only voice), Merienda (subtitle, landing-only voice) — same
    two-voice split as the dashboard's `DESIGN.md`.
- Swizzle (eject) `Navbar` and `Footer` to hand-built components matching
  the dashboard's dark aesthetic.
- Custom homepage (not Docusaurus's default template), styled after the
  landing references in `docs/design/*-landing.html`.
- Code blocks keep Docusaurus's built-in Prism highlighting, themed to the
  `canvas`/`ink` tokens above rather than a stock Prism theme.

## Search

`@easyops-cn/docusaurus-search-local` — builds a local search index at
build time, no external account or approval process. Algolia DocSearch
was considered and rejected: it requires an application/approval process
built around open-source projects, which this product isn't (yet, if
ever).

## Build & deploy

- **Host: Cloudflare Pages.** The project already has a Cloudflare account
  (the `cloudflared` tunnel exposing the API, see `docker-compose.yml`),
  making Cloudflare Pages low-friction to set up (same account, likely same
  DNS zone later) and free with unlimited bandwidth for a static site.
  Vercel (matches `web/`'s existing pattern) and GitHub Pages (Docusaurus's
  built-in `docusaurus deploy`) were considered and are documented here as
  the fallback options if Cloudflare Pages setup hits a blocker.
- Cloudflare Pages project rooted at `docs-site/`:
  - Build command: `npm run build`
  - Output directory: `build/`
- Initial deploy target is the Cloudflare Pages auto-generated
  `*.pages.dev` subdomain. A custom domain (e.g. `docs.ownix.app`) is
  attached via Cloudflare DNS once a domain is chosen/registered — domain
  selection is a user decision outside this spec's scope, not a blocker
  for standing up the site.
- `onBrokenLinks: 'throw'` set in `docusaurus.config.ts` is the build-time
  safety net for broken internal links/anchors — no separate link-check CI
  job is needed for a site this size.

## Testing / verification

Static content site — the Docusaurus build itself is the primary
correctness check (broken links, broken anchors, MDX syntax errors all
fail the build). No additional automated test suite is being added for
`docs-site/`.

## Out of scope for v1

- Versioning, i18n, blog/changelog integration.
- A shared design-token package between `web/` and `docs-site/`.
- Final page copy (the implementation plan scaffolds structure + stub
  content only).
- Custom domain DNS configuration (user follow-up after Cloudflare Pages
  project exists).

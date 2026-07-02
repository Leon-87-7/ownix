# vig — Feature ideation & task briefs

Canonical home for feature ideas, from one-line spark to grill-ready brief.

**How this file works**

1. **Dump** raw one-line ideas under `## Inbox` below — no structure needed.
2. Run **`/pre-grill`** — it grounds each one-liner in the real code, fattens it
   into a technical brief (Context · Wanted · Scope · Open questions), moves it
   into `## Briefs`, and clears it from the Inbox.
3. **Grill** the briefed tasks (`/grill-with-docs`, `/grill-with-search-docs`,
   or `/grilling`) to resolve the Open questions, then `/to-issue-kanban` or
   `/spec-to-kanban`.

Status markers on a brief: `✅ DONE` · `✅ ISSUED #NNN`. `/pre-grill` never
touches a marked task.

---

## Inbox

_Raw one-line ideas go here. `/pre-grill` consumes them._

<!-- - e.g. the feed should have a saved-filters dropdown -->

- add a link pipeline, user sends a URL the bot sends a native preview block and the dashboard has it in the links table.

---

## Briefs

## 1. Segmented tabs line breaks on mobile ✅ DONE

The new content-type segmented control (`web/components/feed/filter-bar.tsx`,
`SegmentedTabs`) overflows awkwardly on small screens,making a horizontal scroll.

**Wanted:** on small screens, render the tabs as separate tab buttons (stacked
or wrapped individual buttons) instead of one continuous segmented line.
with out the motion on hover. (just as it was pre-`SegmentedTabs`).

## 2. Tag creation modal not responsive ✅ DONE

The create-tag modal (`web/components/TagPicker.tsx`, `CreateTagModal`) and the `TagForm`, `web\app\(dashboard)\controls\page.tsx` don't adapt to small screens — the Name/Meaning row and the 9-column color grid don't
fit well on narrow viewports.

**Wanted:** make the create-tag form responsive (stack fields, reflow the color
grid) for small screens.

## 3. Extracted-links table in the Brain page ✅ ISSUED TO GITHUB #238

Surface every link discovered by the enrichment pipelines as a deduplicated
table in the dashboard.

**Data**

- Aggregate the links extracted across **all** pipeline runs (not a single run)
  into a deduplicated set keyed by canonical URL — one row per unique URL.
- Refresh the aggregation on a schedule of **every 6 hours** (reuse the existing
  APScheduler setup; add a job rather than a new scheduler). The table reads the
  last computed snapshot; it is not recomputed on each page load.
- Each row exposes at least: canonical URL, first-seen timestamp, and the count
  of pipeline runs / source videos it appeared in.

**API**

- Add a read endpoint (e.g. `GET /api/links`) returning the deduplicated rows,
  ordered most-recent-first, with pagination.

**UI**

- Add a **"Links"** tab to the Brain page (`web/app/(dashboard)/brain/...`)
  alongside the existing tabs.
- Render the rows in a table; URLs are clickable (open in a new tab,
  `rel="noopener"`). Follow DESIGN.md tokens.

**Open questions** (confirm before building)

- Canonicalization rules for dedupe — strip query params / tracking params, or
  exact-match only?
- Where are extracted links currently persisted (which table/column), or does
  this need a new store?

## 4. Dashboard URL submission — a second ingest surface

> **Grill together with task 5.** Web submissions need a `chat_id`, which is
> exactly what #208's `OPERATOR_CHAT_ID` export gate keys on — the ownership
> decision spans both tasks.
>
> **Grill together with task 9.** Both add a new caller of the create-job +
> enqueue core: task 4 from the web surface, task 9 from the post-enrichment
> repo follow-up. Decide the shape of the one shared service so neither forks it.

Today URLs only enter through the Telegram webhook
(`src/telegram/webhook.py`). PRODUCT.md calls for the operator to drive the
pipeline from the dashboard too ("submitting URLs, triggering and re-running
jobs … without leaving the dashboard").

**Wanted:** let the operator submit a URL from the web UI and get the same job
the Telegram path produces — including the per-template behavior exposed by the
slash commands (`/method`, `/review`, `/technical`, `/narrative`, `/summary`,
and `/freestyle`).

**Backend**

- Add a write endpoint (e.g. `POST /api/jobs`, in `src/api/jobs.py`) that
  classifies the URL with `detect_pipeline()` (`src/utils/validators.py`),
  creates the job row, and enqueues the worker task.
- **Reuse, don't fork:** the create-job + enqueue core currently lives inside
  `webhook.py`'s handlers (the `content_type` + `template` + `_task_for(...)`
  path). Extract it into a shared function/service so the Telegram and web
  surfaces share one code path and can't drift.
- Templates come from `PROMPT_TEMPLATES` (`src/templates.py`); accept an optional
  `template` field. Reject `rejected`/unsupported URLs with the same semantics
  the bot uses.

**UI**

- Add a submit control to the Feed page (`web/app/(dashboard)/page.tsx`): a URL
  input plus a template selector mirroring the slash commands. Follow DESIGN.md
  tokens (signal orange on the submit action only). New job should surface in the
  Feed (prepend / refetch).

**Open questions** (resolve in grill)

- Is `/freestyle` (custom prompt) in scope for v1, or templates-only?
- Ownership: what `chat_id` does a web-submitted job carry, and how does that
  interact with the `OPERATOR_CHAT_ID` export gate (#202 / #208, see task 5)?
- All pipelines (short/long/article/repo/document) on day one, or videos first?
- Optimistic insert vs. wait-for-`job_id` before showing the row.

## 5. Reconcile the export-isolation PRs (#207, #208) before building on them

> **Grill together with task 4.** The export gate's `chat_id` ownership model
> determines what a web-submitted job carries — decide both at once.

Both PRs are open against `main` and belong to epic #201 (per-user export
isolation):

- **#207** — docs-only: ADR-0027 (two-phase credential model) + `CONTEXT.md`
  `Operator` term + slices #201 into #202–#206 on the Kanban.
- **#208** — the "now" fix (closes #202): `settings.OPERATOR_CHAT_ID` +
  `export_blocked(chat_id)` gating every Drive/Sheets call site.

**Wanted:** confirm whether either PR needs updates before we merge and build on
them.

- Verify ADR-0027 still matches the intended approach and that #208 actually
  gates **every** Drive/Sheets export call site (cross-check against the
  acceptance list in the PR body).
- Decide merge order, and whether #208 should land **before** task 4 — web
  submissions need a `chat_id`, which is exactly what the gate keys on.
- Sweep any outstanding CodeRabbit / Greptile review comments on both PRs.

**Open questions**

- Does the (intentionally ungated) brain-rebuild aggregate collide with anything
  task 4 introduces?
- Anything in #207's later slices (#204–#206, OAuth) that task 4 should not
  pre-empt?

## 6. Make the web app an installable PWA

Scope is the `web/` Next.js app (app router).

**Wanted:** the dashboard is installable and has an offline app shell.

- Add a web app manifest (name, maskable icons, `theme_color`/`background_color`
  from DESIGN.md `#0b0c0f` + signal, `display: standalone`) and wire it via
  `web/app/layout.tsx` metadata.
- Add a service worker for installability + offline shell: precache the static
  shell/assets, network-first for `/api/*` so live data isn't served stale.
- Provide the required icon set (incl. maskable).

**Open questions**

- Offline scope: installable shell only, or also cache last Feed/Brain payloads
  for offline read?
- Hand-rolled SW vs. a dependency (`next-pwa`/Workbox) — prefer the minimum that
  makes it installable.
- Are web push notifications in scope, or explicitly out for now?

## 7. Better navigation for the Brain "Links" table

`LinksTable` in `web/app/(dashboard)/brain/page.tsx` paginates 25 rows with
Previous/Next only, backed by `GET /api/brain/links` (limit/offset + optional
`q`; response already includes `total`).

**Wanted:** richer navigation than prev/next.

- Page indicator / jump-to-page (using the `total` already returned), a
  selectable page size, and column sorting (Appearances, Last seen).
- Keep DESIGN.md tokens, a sticky header, keyboard operability, and preserve the
  active `q` filter across navigation.

**Open questions**

- Sort server-side (extend the endpoint) or client-side within the current page?
- Mirror the Feed's URL-state pattern (`?type=`) so page/sort are shareable?

## 8. Controls UI on the Brain search graph

`web/components/brain-graph.tsx` renders `react-force-graph-2d` from
`/api/brain/graph`, highlighting search matches in signal orange. There are no
user-facing controls today (no zoom, recenter, or filtering).

**Wanted:** an on-canvas controls overlay for navigating the graph.

- Zoom in/out, zoom-to-fit, and recenter via the ForceGraph ref methods
  (`zoom()`, `zoomToFit()`, `centerAt()` — source cached at the
  `react-force-graph-2d` opensrc path in CLAUDE.md).
- Consider a topic legend/filter (toggle topics on/off) and focus-on-match
  (center + zoom the matched node when a search runs).
- Ghost-style controls, signal orange only on the active control; honor
  `prefers-reduced-motion`; DESIGN.md tokens.

**Open questions**

- v1 scope: zoom/fit/recenter only, or also topic filtering and
  node-detail-on-click?
- Touch/mobile gestures alongside buttons?
- Is a fullscreen/expand mode wanted?

## 9. Offer extracted GitHub repos as a follow-up repo analysis

> **Grill together with task 4.** This is a third caller of the create-job +
> enqueue core (alongside the Telegram webhook and task 4's web surface). Settle
> the shared service shape so the repo follow-up reuses it instead of forking.

When a short-form video finishes, enrichment (`src/processors/enrichment.py`,
`enrich`) returns `tools_raw` — a list of `{name, type, url, description}` where
`type` can be `"repo"`. Today those repo URLs are surfaced in the result text
only; nothing offers to analyze them. The repo pipeline already exists end to
end: `detect_pipeline()` (`src/utils/validators.py`) classifies
`github.com/{org}/{repo}` as `"repo"`, and `_route_repo` /
`_enqueue_simple_job` (`src/telegram/webhook.py`) create + enqueue a `"repo"`
job processed by `enrich_repo` (`src/services/github.py`).

**Wanted:** after a short video is processed, if its enrichment yielded one or
more GitHub repos, the bot prompts the operator to pick which repo(s) to analyze
next, and enqueues a repo job for each chosen one.

**Backend**

- In the short pipeline (`src/processors/short_video.py`), after enrichment,
  collect candidate repo URLs from `tools_raw` and present them via the existing
  inline-keyboard machinery (`send_inline_keyboard` + `CallbackCtx` /
  `_handle_callback` / `answer_callback_query`, `src/telegram/sender.py` +
  `webhook.py`). Validate each candidate with `detect_pipeline()` /
  `normalize_repo_url` before offering it.
- On selection, **reuse, don't fork** the repo create+enqueue path that
  `_route_repo` already drives — route the chosen URL(s) through the same shared
  service task 4 extracts, not a parallel copy.
- The spawned repo job inherits the same `chat_id`; honor the existing
  recent-job cache (`database.find_recent_job_by_url`) so an already-analyzed
  repo isn't re-queued.

**Open questions** (resolve in grill)

- Multi-select on a Telegram inline keyboard is not native (one tap = one
  callback). Toggle-state checkboxes + a "Confirm" button (re-render the keyboard
  per tap), or one tap = enqueue that repo immediately and allow repeated taps?
- Which `tools_raw` entries qualify — only `type == "repo"`, or any entry whose
  `url` `detect_pipeline()` resolves to `"repo"` (Gemini sometimes labels a repo
  as `"library"`)?
- Cap on how many repo buttons to show when enrichment returns many; dedupe by
  normalized URL.
- Scope to the short pipeline only (as asked), or also offer this after long /
  article jobs that extract repos?
- Encoding selected repos in callback data given Telegram's 64-byte limit — index
  into a cached candidate list, or pack the URL?

## 10. Char-count truncation for the links-table description (ui/ux)

In the Brain "Links" table (`web/app/(dashboard)/brain/page.tsx`, `LinksTable`),
each row's URL cell renders the URL string with CSS `truncate` (width-based, so
truncation length floats with container width) plus a secondary `title · topic`
line at `page.tsx:336`. The data comes from `GET /api/brain/links`
(`src/api/brain.py`); rows expose `url`, `title`, `topic` (`LinkRow`, `page.tsx:13`).

**Wanted:** the link's description text truncates at a fixed **40 characters on
mobile, 60 on desktop**.

**UI**

- The cell already uses `font-mono`, so a `ch`-unit cap maps cleanly to character
  count — native approach is `max-w-[40ch] md:max-w-[60ch]` alongside the existing
  `truncate`, rather than slicing strings in JS. Confirm against DESIGN.md tokens;
  keep the full value reachable (e.g. `title` attribute / accessible name) so the
  truncation is presentational only (WCAG-AA).
- Tailwind's default `md:` breakpoint is the mobile/desktop split unless the repo
  uses a different convention.

**Open questions** (resolve in grill)

- Which text is "the description" — the URL string itself (line 330/334), the
  `title · topic` secondary line (line 336), or both? They truncate differently.
- 40/60 **characters** vs. CSS `ch` (advance width of `0`): with `font-mono` these
  are near-identical, but is exact character count required (forcing JS slicing) or
  is `ch` good enough?
- Does the truncated value still need to be fully visible on hover/focus or via the
  row expanding, or is the existing `target=_blank` link enough?

## 11. Tags should follow the URL, not the job (many-to-many)

Tags today attach to **jobs**: the `job_tags` join table
(`src/database.py:205`, `job_id ↔ tag_id`, issue #88 / S5) keyed off a single job,
with the `tags` vocabulary in the `tags` table (`src/database.py:171`, issue #87).
The links table (`src/brain.py`, `ingest_links` / the `links` table at
`src/database.py:151`) is already deduplicated by canonical `url` — one row per
unique URL — and the same URL can surface across many jobs. So a tag pinned to a
job can't express "this URL is ui/ux" once that URL recurs in other jobs.

**Wanted:** model tags as following the canonical URL (many-to-many URL ↔ tag),
independent of how many jobs a URL appears in.

**Data**

- A URL appears in many jobs and a job extracts many URLs (many-to-many);
  `links.url` is the stable key. Tagging at the URL level needs a `link_tags`
  (`url`/`link_id ↔ tag_id`) join rather than overloading `job_tags`.
- **Reuse, don't fork:** the `tags` vocabulary table and `TagPicker`
  (`web/components/TagPicker.tsx`) already exist — reuse the vocabulary; only the
  _attachment_ target changes from job to URL.

**Open questions** (resolve in grill)

- Does this **replace** job-level tagging (`job_tags`) or coexist with it? If both,
  what's the relationship when a job's tag and its URL's tag disagree?
- Key the join on `links.id` or on canonical `url`? (Dedup canonicalization rules
  here echo task 3's open question — same canonical form must be used.)
- Surface/edit URL tags where: the Brain Links table (new column / `TagPicker`
  inline), the existing controls page, or both?
- Migration: do existing `job_tags` rows get projected onto their URLs, or do URL
  tags start empty?

## 12. Repalette: new signal orange + dark plate tokens

The design tokens have a single source: `web/tailwind.config.ts` defines
`signal.DEFAULT: '#f6921e'` plus the cool plate ladder `canvas: '#0b0c0f'` →
`surface: '#14161a'` → `raised: '#1c1f25'` (`tailwind.config.ts:12-27`). The same
values are normative in `DESIGN.md`'s frontmatter, and the ~39 `web/` consumers
use Tailwind classes (`bg-signal`, `text-signal`, `bg-canvas`…), so they inherit
the change without edits. `DESIGN.md` also pins a derived signal ramp:
`signal-bright #ffa83d`, `signal-deep #b96a06`, `onsignal #16100a`.

**Wanted:** the signal color becomes `#FFBE0B` and "the dark color" becomes
`#2A2312`, applied at the token source so the whole console repalettes.

**UI / Design tokens**

- Update `web/tailwind.config.ts` and mirror into `DESIGN.md`'s frontmatter
  (normative per CLAUDE.md) — one change at the source, not per-component.
- DESIGN.md prose hardcodes the hexes in many places (the Signal Rule, button
  specs, plate-ladder descriptions); those references and any logo SVGs under
  `web/images/` / `web/public/images/` that bake in the orange need a sweep too.

**Open questions** (resolve in grill)

- "The dark color" is ambiguous — the plate ladder is three cool darks
  (`canvas`/`surface`/`raised`). Does `#2A2312` replace `canvas` (the page floor),
  the whole ladder (re-derive all three), or a specific plate?
- `#2A2312` is a **warm** near-black (yellow/red cast), which breaks DESIGN.md's
  stated "cool near-black chassis" identity. Intended pivot to a warm chassis, or
  should the cool ladder stay and only the signal change?
- `#FFBE0B` is brighter/yellower than `#f6921e` — does the derived ramp
  (`signal-bright`, `signal-deep`, `onsignal`) get recomputed around it? The
  "dark-on-orange ≥7:1" contrast (`onsignal #16100a`) and WCAG-AA bar must be
  re-verified against the new hue.
- Does `#FFBE0B` collide with the **pending-yellow** status hue? The Signal Rule
  forbids signal and pending-yellow trading places — a yellower signal narrows
  that gap.

## 13. Brand the /privacy and /terms pages

> **Grill together with task 14.** Both reuse the login page's
> background+logo treatment — a public home page makes it four consumers, so
> the "extract `<BrandBackground>` or duplicate once more" call must be made
> once, for both.

The two legal pages (`web/app/privacy/page.tsx`, `web/app/terms/page.tsx`, added
for OAuth verification, issue #203) are plain `prose prose-invert` text blocks on
bare `bg-canvas` — no background art, no logo, no plate. By contrast
`web/app/login/page.tsx` (the other unauthenticated page, exempted in
`web/middleware.ts`'s `PUBLIC_PATHS` alongside `/privacy`/`/terms`) renders the
`/backgrounds/layered-waves-log.svg` waves image with a fade mask + opacity/
saturation treatment, plus the `vig_logo_lockup.svg` lockup. The authenticated
dashboard instead uses per-route `PageBackground` (`web/components/page-background.tsx`)
webp images layered under a radial + linear gradient — a different pattern, built
for the sidebar-having dashboard shell, not a standalone page.

**Wanted:** `/privacy` and `/terms` look on-brand instead of like an unstyled
document — reuse the login page's background/brand treatment rather than
inventing a third pattern.

**UI**

- Reuse the `layered-waves-log.svg` background + fade-mask/opacity treatment
  from `login/page.tsx:56-68`. Since it would now back three pages, factor it
  into a shared piece (component or small snippet) rather than copy-pasting the
  `<img>` + className block a third time — reuse, don't fork.
- Reuse the `vig_logo_lockup.svg` brand mark the same way `login/page.tsx` does.
- The legal copy itself (long-form text) likely wants a `bg-surface`/`bg-raised`
  plate card wrapping the `prose prose-invert` block so it reads as a panel
  sitting on the dark-plate-ladder chassis, rather than text floating directly
  over the background image — consistent with DESIGN.md's plate-ladder identity.
- Keep the existing `max-w-2xl` reading width and `text-ink`/`text-muted` tokens.

**Open questions** (resolve in grill)

- Extract the background+logo block into a shared component (e.g.
  `<BrandBackground>`) now that three pages use it, or is duplicating it once
  more acceptable until a fourth page shows up?
- Does the legal text sit inside a `surface`/`raised` plate card, or directly on
  the background like the login page's logo/CTA do?
- Any navigation back to `/login` or the dashboard from these pages, or are they
  meant to be dead-end pages a cold visitor (e.g. a Google reviewer) lands on
  directly?
- Same logo treatment as login (full lockup), or a smaller/plainer mark since
  these are read-only legal pages, not a branded entry moment?

## 14. Public home page — fix Google OAuth branding verification rejection

> **Grill together with task 13.** Both reuse the login page's
> background+logo treatment — a public home page makes it four consumers, so
> the "extract `<BrandBackground>` or duplicate once more" call must be made
> once, for both.

Google rejected the OAuth app's branding verification (the consent-screen
review tracked in issue #203, epic #201): the submitted homepage must be
reachable without login and represent the app. Today there is no such page —
`/` is the authenticated Feed (`web/app/(dashboard)/page.tsx`), and
`web/middleware.ts` (`PUBLIC_PATHS = ["/login", "/logout", "/privacy",
"/terms"]`) 307s every logged-out visit to `/login`, which renders only the
`vig_logo_lockup.svg`, one tagline line, and the Telegram login widget
(`web/app/login/page.tsx:70-88`) — it does not explain what VIG does.

**Wanted:** a public, on-brand home page that renders without login, acts as
the face of the project (visuals + brand feel), and explains VIG's purpose —
satisfying Google's homepage requirements so branding verification passes.

**UI**

- **Reuse, don't fork:** the brand treatment already exists on
  `login/page.tsx:56-77` — `layered-waves-log.svg` with the fade-mask/opacity
  treatment plus the `vig_logo_lockup.svg` lockup. Task 13 already asks
  whether to extract this into a shared `<BrandBackground>`; a fourth consumer
  answers it — settle in the joint grill.
- New public route registered in `web/middleware.ts` `PUBLIC_PATHS` (or `/`
  itself goes public — see open question). If `/` changes meaning, the
  sidebar's Feed link and `isActive` special-case for `/`
  (`web/components/sidebar.tsx:27-34,180-184`) are the touchpoints.
- Content must cover Google's branding checklist: what the app does, app
  identity matching the consent screen, and a visible link to `/privacy` (and
  `/terms`) on the same domain (`web/app/privacy/page.tsx`,
  `web/app/terms/page.tsx` already exist and are public).
- DESIGN.md is normative: dark plate ladder, signal orange rationed to the
  single primary CTA (sign in / open console), JetBrains Mono for machine
  facts, WCAG-AA contrast, `prefers-reduced-motion` honored for any hero
  motion.

**Open questions** (resolve in grill)

- Where does the landing live: `/` becomes public (Feed moves to `/feed`, or
  `/` renders landing vs. Feed conditionally on the `vig_session` cookie), or
  a separate path (e.g. `/home`) with that URL submitted to Google as the
  homepage? The middleware matcher and sidebar `isActive('/')` both hinge on
  this.
- How much content is "the face of the project": logo + purpose paragraph +
  legal links + sign-in CTA only, or also a feature overview of the pipelines
  / dashboard screenshots?
- What does a logged-in operator see at the landing URL — auto-forward to the
  Feed, or the landing with an "open console" CTA?
- Does Google's sensitive-scope disclosure (how the app uses Google user
  data / Limited Use statement) need to appear on the homepage itself, or is
  the `/privacy` link sufficient for the branding review?
- Does `/login` itself also gain the purpose copy, or does it stay minimal
  once the landing page exists upstream of it?

## 15. Sidebar links to Terms & Privacy (one row, between GitHub and Sign out)

The sidebar drawer's footer (`web/components/sidebar.tsx:413-436`) stacks a
GitHub external link (with `GithubIcon`, `sidebar.tsx:414-423`) above the
Sign out form/button (`sidebar.tsx:424-435`, currently text-only, no icon).
The legal pages exist at `/privacy` and `/terms` and are public
(`web/middleware.ts` `PUBLIC_PATHS`), but nothing in the app links to them —
the only reference in `web/` is the middleware constant. The collapsed rail's
footer (`sidebar.tsx:322-352`) shows only GitHub + the expand chevron.

**Wanted:** Terms and Privacy links in the sidebar footer, two buttons
sharing one row, placed between the GitHub link and Sign out, with icon(s).

**UI**

- Insert one row containing two `next/link` entries (`/terms`, `/privacy`) in
  the expanded drawer footer between the GitHub anchor and the sign-out form.
  Internal routes — no `target="_blank"`/`rel` (that's GitHub-only).
- Match the existing footer row idiom: `text-muted`, `hover:bg-raised
  hover:text-ink`, `transition-ui`, and the drawer's tabbability pattern
  (`tabIndex={open ? undefined : -1}`).
- Icons come from lucide-react, the icon source for all nav items
  (`sidebar.tsx:7-18`; simple-icons is the GitHub-only exception). Sized
  `h-[18px] w-[18px]` like the rest.
- Real links with accessible names; keyboard operable per the drawer's
  existing focus management. DESIGN.md: no signal orange here — footer rows
  are muted utility.

**Open questions** (resolve in grill)

- "Add an icon to this btn" — which button: each of the two new Terms/Privacy
  buttons, or the Sign out button (currently the only footer row without an
  icon)?
- Do Terms/Privacy also get icon-only entries in the collapsed rail footer
  (with tooltips, like GitHub), or expanded drawer only?
- Row layout: two equal half-width buttons (`grid-cols-2`), or a compact
  inline pair (`Terms · Privacy`) since two half-width rows break the
  footer's full-width-row pattern?
- Icon choice — lucide has no canonical legal glyphs; `ScrollText` for terms
  and `Shield`/`FileText` for privacy, or one shared glyph?

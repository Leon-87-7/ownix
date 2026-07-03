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
fattens a marked task. Once marked, `/pre-grill --mark-a`/`--archive` moves
its body to `docs/archive/TASK-archive.md`, leaving the title behind here.

---

## Inbox

_Raw one-line ideas go here. `/pre-grill` consumes them._

<!-- - e.g. the feed should have a saved-filters dropdown -->

- in the job details page add navigation btns (previous / next).
- add a delete btn for the jobs (in every instance of a job, row or card) and the job should be deleted from the DB and the telegram chat. On the desktop mode on mobile it should be the sweep left motion. AND it should be with warning (can be selected as "don't show again" checkbox)
- the feed should have a Docs tab that redirects to the doc parser page

---

## Briefs

## 1. Segmented tabs line breaks on mobile ✅ DONE

## 2. Tag creation modal not responsive ✅ DONE

## 3. Extracted-links table in the Brain page ✅ ISSUED TO GITHUB #238

## 4. Dashboard URL submission — a second ingest surface

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

## 5. Reconcile the export-isolation PRs (#207, #208) before building on them ✅ DONE

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

## 16. Link pipeline — bare URLs get a native Telegram preview + a Brain Links row

`detect_pipeline` (`src/utils/validators.py:50`) only recognizes short/long/article/repo/document
(`Pipeline = Literal[...]`, `validators.py:8`) — anything else is `"rejected"`, and `_route_url`
(`src/telegram/webhook.py:1348`) sends every rejected URL straight to `_reject_url`
(`webhook.py:1274`): a canned "Unsupported URL" reply, no job, no persistence. Meanwhile the
`links` table (`src/database.py:151`) and `ingest_links` (`src/brain.py:282`) already do exactly
"capture a URL, dedupe by canonical URL, store title/topic" — but today only get fed from
enrichment output, 5 callers all in `src/processors/article.py` and `src/processors/prd.py`,
never from a raw user-pasted link.

**Wanted:** sending a bare URL that isn't a video/article/repo/document gets a native Telegram
link-preview card in reply and a row in the Brain Links table on the dashboard — capture only, no
enrichment job.

**Backend**

- Extend `Pipeline` (`validators.py:8`) with a new value (e.g. `"link"`), or repurpose part of the
  current `"rejected"` tail of `detect_pipeline` (`validators.py:73-100`) — decide which URLs move
  from rejected to accepted (see Open questions).
- New branch in `_route_url` (`webhook.py:1348`) beside `_route_document_url`/`_route_article`/
  `_route_repo` that calls `ingest_links` (`src/brain.py:282`) with a single-item list, then
  replies via `send_message` (`src/telegram/sender.py:101`) with the raw URL as the message text —
  no caller currently sets `disable_web_page_preview`, so Telegram's default native preview card is
  the off-the-shelf behavior here; no custom preview rendering needed.
- `ingest_links` requires `topic` and `source_job_id` (used to look up the source job's URL for the
  Obsidian `.md`, `_get_source_job_info`, `brain.py:423`) — a bare link has neither. Resolve before
  wiring the call (see Open questions).

**UI**

- No new component: `LinksTable` (`web/app/(dashboard)/brain/page.tsx`) and `GET /api/brain/links`
  (`src/api/brain.py`) already render the `links` table as-is. Confirm whatever `topic`/`title`
  Backend resolves for link-only rows doesn't break that table's existing display assumptions.

**Open questions** (resolve in grill)

- Scope: every URL `detect_pipeline` currently rejects, or a narrower class (exclude bare domains,
  search-result URLs, non-http schemes)?
- What populates `ingest_links`'s `topic` and `source_job_id` for a link with no enrichment job —
  empty/placeholder topic, a lightweight job row created just to anchor `source_job_id`, or does
  `ingest_links`/`_build_obsidian_md` get adapted to tolerate a missing source job?
- Precedence: if a pasted URL also matches an allowlisted article domain, does full article
  enrichment still win, or does "just save + preview" only apply when nothing else claims the URL?
- Spam/dedup: does this need the same recent-submission guard other pipelines get
  (`find_recent_job_by_url`), scoped to `links.url` instead of `jobs`?

## 17. Persistent account/status affordance — Google connection state + Telegram identity ✅ DONE — issued #292–#295, merged PR #296

The Feed page (`web/app/(dashboard)/page.tsx:167-176`) renders a "Connect Google" panel
unconditionally — hardcoded `<h2>Connect Google</h2>` plus an `/api/google/connect` link — with no
fetch of `GET /api/google/status` (`src/api/google_oauth.py:96`, returns `{"connected": bool}`)
anywhere in `web/`. The OAuth callback (`google_oauth_callback`, `google_oauth.py:60`) redirects to
`/?google=connected` or `/?google=denied` on completion, but nothing in `web/` reads that
`?google=` param, so a successful connect silently lands back on a page that still says "Connect
Google." Session identity (`first_name`, `username`, `photo_url`) is already available via
`GET /api/auth/me` (`src/api/auth.py:138`) and is already fetched once by `InviteGate`
(`web/components/invite-gate.tsx:164`) for approval-gating — but it stays in that component's local
state (its `InviteUser` type doesn't even include `photo_url`) and nothing downstream, including
`web/components/sidebar.tsx`, surfaces it.

**Wanted:** a persistent affordance showing who's signed in (Telegram avatar/name) and whether
Google export is connected, with connect/disconnect actions, and a one-time success/denied message
on OAuth return instead of a page that looks stuck.

**Backend**

- None needed — `GET /api/google/status`, `POST /api/google/disconnect`
  (`google_oauth.py:96,102`) and `GET /api/auth/me` (`auth.py:138`) already cover status,
  disconnect, and identity.

**UI**

- Feed panel (`page.tsx:167-176`): fetch `/api/google/status` on mount; when `connected: true`,
  swap the "Connect Google" CTA for a connected state + a disconnect action
  (`POST /api/google/disconnect`).
- Read `?google=connected`/`?google=denied` via `useSearchParams` (already imported, `page.tsx:7`),
  show a one-time toast/banner, then strip the param with `router.replace` so a refresh doesn't
  re-trigger it.
- Identity affordance: reuse the `/api/auth/me` fetch `InviteGate` already performs instead of
  adding a second one — lift it into context `InviteGate` provides to children, or a sibling hook
  both consume (reuse, don't fork). Render name + `photo_url` in `sidebar.tsx`'s footer (same
  drawer area as the GitHub/Sign out rows, `sidebar.tsx:413-436`), matching that area's muted
  footer-row idiom per DESIGN.md.

**Resolved decisions** (grilled 2026-07-02 — terms captured in CONTEXT.md: Session identity,
Google connection, Account affordance)

- **Placement:** sidebar footer is the persistent home (identity + Google state, visible
  everywhere). The Feed's "Connect Google" panel becomes a **disconnected-only nudge** — renders
  only while disconnected, disappears once connected. Not a second source of truth.
- **Identity plumbing:** `InviteGate` exposes the user it already fetches via a session-user
  context + `useSessionUser()` hook (its `InviteUser` type gains `photo_url`, already in the API
  response). No second `/api/auth/me` fetch.
- **Google status state:** one shared provider in the dashboard layout —
  `{ connected, disconnect, refresh }` — consumed by both the sidebar and the Feed nudge, so
  connect/disconnect updates every surface instantly.
- **Footer layout:** expanded drawer = one row, avatar + first_name/username, with a simple-icons
  Google mark next to the name; "Connected to Google" in **Google brand blue `#4285F4`** (new
  deliberate off-system token — not signal orange, not the status ramp) and a muted Disconnect
  action. Collapsed rail = avatar only, static brand-blue glow when connected, tooltip carries
  name + connection state.
- **Disconnect UX:** `window.confirm` first (repo precedent: space delete), then POST with a
  'Disconnecting…' disabled state and a visible failure message on error.
- **OAuth return:** handled on the Feed page — `useSearchParams` reads `?google=connected|denied`,
  renders a one-time **inline banner** (no toast system exists), strips the param with
  `router.replace`. No task-14 dependency: if `/` stops meaning Feed, the backend redirect
  constant moves then (one line).

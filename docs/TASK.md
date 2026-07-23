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



---

## Briefs

## 1. Segmented tabs line breaks on mobile ✅ DONE

## 2. Tag creation modal not responsive ✅ DONE

## 3. Extracted-links table in the Brain page ✅ ISSUED TO GITHUB #238 - ✅DONE

## 4. Dashboard URL submission — a second ingest surface

> **Grilled together with task 9** on 2026-07-04. Both add a new caller of the
> shared job-creation core: task 4 from the web surface, task 9 from the
> post-enrichment repo follow-up. See ADR-0032 (dashboard supersedes
> read-mostly) and ADR-0033 (shared core shape) in `docs/adr/`.

> **Grill together with task 28.** Task 28 ("mirror the bot flow on the web")
> is largely _this_ task plus task 24's shipped command launcher — settle
> what, if anything, task 28 adds beyond the two before spec'ing it.

Today URLs only enter through the Telegram webhook
(`src/telegram/webhook.py`). PRODUCT.md calls for the operator to drive the
pipeline from the dashboard too ("submitting URLs, triggering and re-running
jobs … without leaving the dashboard"). This was previously deferred (see
CONTEXT.md `Web dashboard` entry) — now unblocked by an upcoming conference
demo + parity with the Doc Parser page, and treated as a permanent capability,
not a demo-scoped exception.

**Wanted:** let the operator submit a URL from the web UI and get the same job
the Telegram path produces — including the per-template behavior exposed by the
slash commands (`/method`, `/review`, `/technical`, `/narrative`, `/summary`,
and `/freestyle`).

**Backend**

- Add `POST /api/jobs` (in `src/api/jobs.py`) that classifies the URL with
  `detect_pipeline()` (`src/utils/validators.py`) and calls the shared
  `create_and_enqueue_job` core (new `src/services/jobs.py`, ADR-0033) —
  same function the webhook and task 9's repo follow-up use.
- `chat_id` comes from `request.state.user["id"]` (the session's tenant),
  identical to every other `/api/jobs/*` endpoint. No `OPERATOR_CHAT_ID`
  interaction — that gate governs Drive/Sheets export writes only (ADR-0030),
  not job creation.
- Templates come from `PROMPT_TEMPLATES` (`src/templates.py`); accept an optional
  `template` field, including `freestyle` (custom prompt — in scope for v1).
  Reject `rejected`/unsupported URLs with the same semantics the bot uses.
- Pipelines: `short`/`long`/`article`/`repo` on day one. `document` stays on
  its own Doc Parser page (`/doc-parser`, `/api/parsed/*`) — not folded in.

**UI**

- Add a submit control to the Feed page (`web/app/(dashboard)/page.tsx`): a URL
  input plus a template selector mirroring the slash commands (incl.
  Freestyle). Follow DESIGN.md tokens (signal orange on the submit action
  only). Insert an optimistic placeholder row on submit, reconciled with the
  real `job_id` once `POST /api/jobs` resolves.

## 5. Reconcile the export-isolation PRs (#207, #208) before building on them ✅ DONE

## 6. Make the web app an installable PWA ✅ ISSUED TO GITHUB #421 #422 #423

> **Grilled 2026-07-23** — all open questions resolved below.

Scope is the `web/` Next.js app (app router).

**Wanted:** the dashboard is installable, has a minimal offline fallback, and is
an Android share-sheet URL intake target.

**Already shipped** (found in grill): `web/app/manifest.json` exists with name,
maskable 192/512 icons (`web/public/web-app-manifest-*.png`), `display:
standalone`, and `theme_color`/`background_color` `#0d0e10` — which matches the
current `canvas` token (`web/tailwind.config.ts:9`; the brief's `#0b0c0f` was
pre-repalette). Next serves `app/manifest.json` automatically — no
`layout.tsx` wiring needed.

**Remaining work**

- Manifest: add `start_url: "/feed"` (per task 14's routing — sidesteps the
  `/` redirect), `id`, and the `share_target` below.
- **SW (resolved): tiny hand-rolled `web/public/sw.js`, no dependency.**
  Verified in grill: Chrome (108+ mobile / 112+ desktop) no longer requires a
  service worker for installability — manifest + HTTPS is the whole bar, so
  `next-pwa`/Workbox has nothing to buy. The SW exists only for the offline
  fallback: precache one `/offline` page, serve it when a navigation fetch
  fails. No `/api/*` caching, no payload caching — live-data console, stale
  data is worse than none. Skip SW registration when `NEXT_PUBLIC_API_MOCK=1`
  (MSW's `mockServiceWorker.js` owns scope `/` in mock mode).
- **Share target (resolved):** manifest-only, `method: "GET"`,
  `action: "/feed"`, params `share_title`/`share_text`/`share_url`. iOS Safari
  has no `share_target` for home-screen PWAs — iPhone intake stays the
  Telegram-bot share flow (already works); an iOS Shortcut opening
  `/feed?share_url=…` is a zero-code user-side option later.
- **Receiving handoff (resolved):** Feed reads the `share_*` params, extracts
  the first URL (`share_url`, falling back to a URL regex over `share_text` —
  Android apps commonly put the URL in `text`), opens the existing Submit URL
  dialog (`SubmitJobProvider`) prefilled so the operator picks the template,
  then `router.replace('/feed')` strips the params. A share arriving while
  logged out loses the URL (middleware drops the query on the `/login` 307) —
  accepted; installed PWAs hold their session cookie.
- **Web push (resolved): out.** Telegram is the notification channel; push
  handlers can be added to the SW later without rework.

## 7. Better navigation for the Brain "Links" table ✅ ISSUED TO GITHUB #306 - ✅DONE

## 8. Controls UI on the Brain search graph

> **Grill:** `/grilling` — pure product/UX; the ForceGraph ref methods are
> already pinned in the brief.

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

> **Grilled together with task 4** on 2026-07-04. This is a third caller of the
> shared job-creation core (alongside the Telegram webhook and task 4's web
> surface). See ADR-0033 in `docs/adr/` and the CONTEXT.md `Repo follow-up`
> entry for the resolved shape.

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
next, and enqueues a repo job for each chosen one. Ships for all three
non-document text/URL-derived pipelines: short, article, and long-video —
three trigger sites feeding the same offer + enqueue mechanism.

**Backend**

- **Trigger sites** (data shape differs per pipeline):
  - Short (`processors/short_video.py`): candidates from `enrichment.tools_raw`.
  - Article (`processors/article.py`): candidates from its own Gemini `tools` list.
  - Long-video (`processors/long_video.py`): candidates from
    `extract_description_links` + `enrich_github_links` output (not a Gemini
    tools list — a different mechanism, same repo-offer outcome).
- **Candidate filter:** any candidate entry whose `url` resolves to `"repo"`
  via `detect_pipeline()` — not Gemini's own `type` label (which can mislabel
  a repo as `"library"`).
- **Dedupe + cap:** dedupe by `normalize_repo_url`, cap at 5 buttons (matches
  the template-picker keyboard's precedent).
- **Selection UX:** one tap = enqueue that repo immediately (no toggle/confirm
  step — avoids needing new `editMessageReplyMarkup` plumbing this codebase
  doesn't have yet). Present via `send_inline_keyboard` +
  `CallbackCtx`/`_handle_callback`/`answer_callback_query` (all in
  `src/telegram/webhook.py` + `sender.py` — see CONTEXT.md `Webhook dispatch
table`, there is no separate `dispatch.py`/`callbacks.py`).
- **Callback encoding:** `repo_pick:{job_id}:{idx}`, indexing into a short-TTL
  Redis-cached candidate list keyed by the source `job_id` — stays well under
  Telegram's 64-byte `callback_data` limit and fits `CallbackCtx`'s existing
  single-payload-after-`:` convention.
- On selection, **reuse, don't fork**: route the chosen URL through the same
  `create_and_enqueue_job` core task 4 extracts (`src/services/jobs.py`,
  ADR-0033), which already owns the `find_recent_job_by_url` dedup check — an
  already-analyzed repo isn't re-queued for free.
- The spawned repo job inherits the same `chat_id` as the source job.

## 10. Char-count truncation for the links-table description (ui/ux) ✅ ISSUED TO GITHUB #305 - ✅DONE

## 11. Tags should follow the URL, not the job (many-to-many)

> **Grilled (partially) 2026-07-11** — session closed early; resolved decisions
> below, remaining opens listed. Scope grew: the grill surfaced that `links` has
> no `chat_id` (global inventory) while `tags` are per-chat, and resolving that
> expanded this task into **per-tenant Brain + an opt-in Community Brain tab**.
> Consider splitting the Community Brain into its own task before issuing.

> **Grill together with task 30.** Task 11 owns the data model (URL ↔ tag
> join); task 30 owns the Links-table surface + the mobile color-badge
> redesign that renders it. Same feature, two layers — decide the
> attachment key once.

Tags today attach to **jobs**: the `job_tags` join table
(`src/database.py:227`, `job_id ↔ tag_id`, issue #88 / S5) keyed off a single job,
with the `tags` vocabulary in the `tags` table (`src/database.py:193`, issue #87).
The links table (`src/brain.py`, `ingest_links` / the `links` table at
`src/database.py:173`) is deduplicated by canonical `url` via `normalize_url`
(`src/brain.py:136` — strip query/fragment/trailing slash; soft dedup, no UNIQUE
constraint) — and the same URL can surface across many jobs. So a tag pinned to a
job can't express "this URL is ui/ux" once that URL recurs in other jobs.

**Wanted:** model tags as following the canonical URL (many-to-many URL ↔ tag),
independent of how many jobs a URL appears in.

**Resolved 2026-07-11** (grill session 1)

- ~~Replace or coexist?~~ → **Coexist.** `job_tags` stays as-is (workflow
  surface, shipped UI); `link_tags` is a second attachment target (inventory
  surface). Job tags and link tags may disagree — no reconciliation semantics.
- ~~Join key: `links.id` or canonical `url`?~~ → **`links.id` FK.**
  `link_tags(link_id REFERENCES links(id) ON DELETE CASCADE, tag_id REFERENCES
tags(id) ON DELETE CASCADE, PRIMARY KEY(link_id, tag_id))` — mirrors
  `job_tags` exactly. Safe because `rebuild_graph` (`src/brain.py:637`) never
  deletes rows. Canonicalization stays owned by `ingest_links`/`normalize_url`.
- ~~Tag visibility across users~~ → **Per-tenant Brain.** `links` gains
  `chat_id`; dedup key becomes `(chat_id, url)`; related-computation, search,
  graph, and the links API filter by viewer. Backfill existing rows via
  `source_job → jobs.chat_id`.
- **Community Brain (new concept):** a new tab on the Brain page showing the
  communal pool, viewable by everyone. **Sharer model, forward-only:** opting
  in makes you a sharer; links you ingest _while opted in_ are stamped shared
  at ingest time (e.g. `shared_at` on the link row). Opt-in does **not** share
  your back-catalog; opt-out does **not** withdraw already-shared links — they
  stay put. Community tab = all shared rows across users, merged by canonical
  URL. Tags stay private in all views (restated in-session, not contested —
  re-confirm). Opt-in is a **timed action** (~8–12h sharing window), state in
  the existing `get_user_setting`/`set_user_setting` store
  (`src/database.py:1232`).

**Open questions** (next grill session)

- **Timer semantics** (where the session stopped): fixed window with silent
  expiry (recommended — one `sharer_until` timestamp, checked at ingest, no
  background jobs), fixed window + Telegram expiry notice (needs a scheduled
  check), or activity-extended sliding TTL? Is 8–12h fixed or user-chosen?
- Confirm: tags never appear in the Community tab (private-only), correct?
- Where does the opt-in/sharer toggle live in the UI (Brain page header,
  Community tab itself, controls page)?
- Migration mechanics: schema version bump for `links.chat_id` + backfill +
  `link_tags` + UNIQUE index decision on `(chat_id, url)` (harden the soft
  dedup while migrating?).
- Do `search_links`, `get_graph`, and `/api/brain/*` endpoints all gain viewer
  scoping in this task, or does the Community tab ship read-only from the
  shared pool first?
- Surface/edit URL tags where: the Brain Links table (task 30), the controls
  page, or both?
- Migration: do existing `job_tags` rows get projected onto their URLs, or do
  URL tags start empty?
- **ADR candidate** once the opens close: per-tenant Brain + forward-only
  community sharing is hard to reverse, surprising without context, and a real
  trade-off — write it up when the next session finishes.

## 12. Repalette: new signal orange + dark plate tokens

> **Grill:** `/grilling` — pure design decisions (which plate `#2A2312`
> replaces, ramp re-derivation, WCAG re-verification).

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

## 13. Brand the /privacy and /terms pages ✅ DONE

## 14. Public home page — fix Google OAuth branding verification rejection

> **Grilled 2026-07-06** — all open questions resolved below. Task 13 shipped
> meanwhile: `PublicShell` (`web/components/public-shell.tsx`) is the shared
> public-page chrome for `/terms`+`/privacy`, but the **waves background**
> still lives inline in `login/page.tsx` + `logout/page.tsx` only — the
> landing is its third consumer, so extraction into a shared
> `<BrandBackground>` is now settled: extract.

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

- ~~Where does the landing live~~ → **Resolved 2026-07-06: `/` is always the
  public landing route; the Feed moves to `/feed`.** The middleware (which
  already reads the `vig_session` cookie on every request) 307s
  _authenticated_ visitors from `/` to `/feed`, so logged-out visitors and
  Google's crawler get the landing and the operator never sees it after
  login. `/` joins `PUBLIC_PATHS`; the landing stays fully static. Sweep:
  sidebar Feed link + `isActive('/')` special-case
  (`web/components/sidebar.tsx:27-34,180-184`) retarget to `/feed`, plus any
  internal `href="/"` and route-pinning tests. Task 6's PWA `start_url`
  points at `/feed` directly, sidestepping the redirect.
- ~~What does a logged-in operator see at the landing URL~~ → resolved by the
  same decision: auto-forward (307) to `/feed`.
- ~~How much content~~ → **Resolved 2026-07-06: full marketing page.** Waves
  hero (via the extracted `<BrandBackground>`) + purpose paragraph + feature
  overview of the pipelines + dashboard visuals + one signal-orange CTA +
  legal footer reusing `PublicShell`'s links. Section ordering is design
  execution, not spec.
- **Visuals (new, resolved): staged screenshots.** Seed a demo account with
  curated fake jobs/links, capture Feed + Brain graph + a job details page,
  ship as static assets. Never real operator data (no live captures, no
  blur-redaction), re-capturable after UI changes.
- ~~Limited Use disclosure~~ → **Resolved: privacy page only.** The landing
  carries just the visible `/privacy` + `/terms` links. Gap found in grill:
  `web/app/privacy/page.tsx` describes the scopes but lacks the explicit
  "adheres to the Google API Services User Data Policy, including the
  Limited Use requirements" affirmation — add that paragraph (with policy
  link) to `/privacy` as part of this task.
- ~~Does `/login` gain purpose copy~~ → **Resolved: stays minimal, plus one
  quiet "What is VIG?" back-link to `/`** so a direct `/login` visit is
  never a dead end. No copy duplication — the landing does the explaining.

## 15. Sidebar links to Terms & Privacy (one row, between GitHub and Sign out) ✅ ISSUED TO GITHUB #307, #308 - ✅DONE

## 16. Link pipeline — bare URLs get a native Telegram preview + a Brain Links row

> **Grill:** `/grill-with-docs` — domain-model call (extending the `Pipeline`
> enum and the `ingest_links` contract).

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

## 18. Job details page — previous/next navigation buttons ✅ ISSUED TO GITHUB #309 - ✅DONE

## 19. Delete button for jobs — DB + Telegram message, with confirm/"don't show again", swipe-to-delete on mobile

> **Grill:** `/grilling` — UX semantics (swipe, confirm, undo); no external or
> domain-model hinge.

> Touches the same job-card real estate as task 7's dense-table thinking and task 11's per-URL
> tagging — no shared decision, just adjacent surface area.

Jobs render as cards in two places: `JobCard` (`web/components/job-card.tsx:22-51`, Feed's list
view) and `PreviewCard` (`web/components/feed/preview-card.tsx:53-119`, Feed's grid view via
`PreviewGrid`, `web/components/feed/preview-grid.tsx`), plus the full job details page
(`web/app/(dashboard)/jobs/[id]/page.tsx`). Both card components already carry a
`pointer-events-auto` overlay island for `JobCardTags` (`job-card.tsx:45-47`,
`preview-card.tsx:109-114`) sitting above a full-card `<Link>` overlay (`job-card.tsx:30`,
`preview-card.tsx:75-79`) — the established pattern for "an interactive control on a
whole-card-is-a-link card."

There is **no DELETE endpoint for jobs today** (`src/api/jobs.py` only has
`DELETE /{job_id}/tags/{tag_id}`, line 342-354). The `jobs` table
(`src/database.py:35-92`) has `chat_id` (line 37), `message_id` (line 38, the operator's original
Telegram message) and `bot_message_id` (line 74, the bot's reply) — both are plain `INTEGER`
columns with no Telegram-side deletion ever issued against them. Five child tables cascade on job
delete already (`ON DELETE CASCADE`): `job_thumbnails` (line 99), `job_annotations` (line 220),
`job_tags` (line 227), `space_urls` (line 248), `document_outputs` (line 268) — a `DELETE FROM
jobs WHERE id = ?` is enough on the DB side. `src/telegram/sender.py` has no `deleteMessage` call;
every Bot API call goes through `_post_and_parse` (`sender.py:70-98`), the same helper
`send_message` (`sender.py:101`) uses — a `delete_message(chat_id, message_id)` following that
pattern is the natural way to add it. Auth/ownership for a job lookup already exists via
`get_owned_job` (`src/api/deps.py:7`).

**Wanted:** a delete action reachable from every job instance (Feed row, Feed grid card, job
details page) that removes the job from the DB and deletes its message(s) from the Telegram chat,
gated by a confirm-with-warning that can be dismissed permanently via a "don't show again"
checkbox. Desktop gets a delete control; mobile gets a swipe-left-to-delete gesture instead/in
addition.

**Backend**

- Add `DELETE /api/jobs/{job_id}` to `src/api/jobs.py`, reusing `get_owned_job`
  (`src/api/deps.py:7`) for ownership, then `DELETE FROM jobs WHERE id = ?` (cascades cover the
  five child tables above).
- Add `delete_message(chat_id, message_id)` to `src/telegram/sender.py` following the
  `_post_and_parse` pattern (`sender.py:70-98`, same shape as `send_message`, `sender.py:101`),
  calling it for both `message_id` and `bot_message_id` when present. Telegram's `deleteMessage`
  can fail (message too old, already deleted, etc.) — decide whether that's swallowed (DB delete
  still succeeds) or surfaced.
- **"Don't show again" persistence:** `src/database.py` already has a generic per-chat
  `get_user_setting`/`set_user_setting` (`database.py:1232-1249`, used today for the Brain links
  view and recovery-notification toggle) — reuse that instead of introducing browser
  `localStorage` (grep confirms **no** `localStorage` usage anywhere in `web/` today, so there's no
  existing client-side preference pattern to fork either way).

**UI**

- Desktop: a delete control in the same `pointer-events-auto` overlay slot `JobCardTags` occupies
  on `JobCard`/`PreviewCard`, plus one on the job details page's `JobActionsBar`
  (`page.tsx:223-235`).
- Confirm dialog: the repo's only existing confirm pattern is a bare `window.confirm()`
  (`web/components/sidebar.tsx:290-291`, Google disconnect) — no "don't show again" checkbox
  support in that primitive, so this needs a real dialog (candidate: extend
  `web/components/ExportModal.tsx:38-80`'s focus-trap/Escape pattern rather than forking a new
  one).
- Mobile swipe-left: **no gesture library is installed** (`web/package.json` has no
  framer-motion/react-use-gesture/similar) — this is native touch-event handling (`touchstart`/
  `touchmove`/`touchend`) or a new dependency, not a drop-in.

**Open questions** (resolve in grill)

- Swipe-left reveals what — an inline delete button (still confirmed), or does the swipe itself
  trigger the confirm dialog directly?
- Does "don't show again" skip the dialog for all future job deletes for that chat permanently, or
  is it resettable somewhere (a controls/settings toggle)?
- If `delete_message` fails against Telegram (message already gone, >48h old, etc.), does the DB
  delete proceed anyway, or does the whole operation fail and roll back?
- Any distinction between deleting from the details page (single job, full-page context) vs. a
  card in a list (row disappears from an in-memory list) — does the Feed need an optimistic
  removal + undo, or is a hard confirm-then-gone sufficient?

## 20. Feed — a Docs tab that redirects to the Doc Parser page ✅ ISSUED TO GITHUB #310 - ✅DONE

## 21. Lightweight CRM for invite-gate contacts + two-way email under leondev.xyz

> **Resolved 2026-07-05** — decision in `docs/headless CRM.md`. Operator
> constraints: manage contacts (email + chat_id), address + real receiving
> mailbox under leondev.xyz, broadcast newsletter, **outside the dashboard**
> (contact data must never reach the `web/` client), **$0 only**. Pick:
> **Brevo free** (hosted contacts + campaigns; one-way push from
> `_cb_invite_decision` on approve — the only vig code) + **Zoho Mail free**
> (real leondev.xyz inbox). Approval stays Telegram one-tap; no CRM/contacts
> surface in `web/`. Remaining open: the mailbox name.

The invite gate (ADR-0031, `docs/adr/0031-invite-gate-and-onboarding.md`) captures
one email per user into `users.email` (`src/database.py:141`) with
`status IN ('pending','approved','blocked')`, via the bot's `awaiting_email`
chat state (`src/database.py:124`) or the dashboard modal
(`web/components/invite-gate.tsx` → `PUT /api/auth/email`, `src/api/auth.py:151`).
Approval is a one-shot Telegram push to `OPERATOR_CHAT_ID` with inline
✅ Approve / 🚫 Block buttons (`_notify_operator_invite`,
`src/telegram/webhook.py:1384`; `_cb_invite_decision`, `webhook.py:448`).
There is **no management surface**: `list_pending_users`
(`src/database.py:1773`) has zero production callers (tests only), no
`/api/users` admin endpoint exists, and if the operator misses the push there
is no way to see or act on pending users. ADR-0031 explicitly deferred email
infra ("no SMTP infra; email is for Operator outreach, not authentication") —
the outreach channel was never built. The `leondev.xyz` domain already carries
`app.` and `api.` subdomains (`docs/ops/oauth-verification.md:25-28`); no
mailbox or MX/SPF/DKIM records exist for it anywhere in the repo.

**Wanted:** a small, low-overhead, not-built-from-scratch CRM-like place to see
and manage invite-gate contacts (pending/approved/blocked) and to send _and
receive_ email with them — likely from a new address under `leondev.xyz`.

**Backend / Data**

- The contact source of truth is the `users` table (`tg_id`, `first_name`,
  `username`, `email`, `status`, timestamps — `src/database.py:1743`). Any CRM
  must mirror or read these rows; primitives already exist and are unused:
  `list_pending_users` (`database.py:1773`), `get_user` (`database.py:1739`),
  `set_user_status` (`database.py:1752`). **Reuse, don't fork.**
- If the CRM can flip approval, it must converge on the same state machine the
  Telegram buttons use (`_cb_invite_decision`, `webhook.py:448` — flips
  `users.status` _and_ notifies the user in Telegram). A CRM-side approve that
  skips the Telegram notify would silently diverge from ADR-0031's flow.
- Email send/receive is net-new infrastructure: nothing in `src/` imports
  smtplib/an email SDK, and there is no inbound-mail webhook. Provider choice
  (full mailbox vs. transactional API + inbound parse) drives the whole shape —
  resolve in grill with docs search.

**Ops**

- A new address under `leondev.xyz` needs MX/SPF/DKIM/DMARC DNS records —
  managed wherever `app.`/`api.` DNS lives today (outside this repo; deploy
  docs at `docs/handoff/VPS to prebuilt docker images via GHCR.md` describe the
  VPS but not DNS).

**Open questions** — resolved 2026-07-05 (full rationale in `docs/headless CRM.md`)

- ~~Buy vs. thin-build~~ → **buy hosted-free, build only a one-way push.** No
  Contacts page in the dashboard (violates the never-client-side constraint);
  Brevo's console is the management surface. vig-side code is a single Brevo
  contact-upsert added to the approve path.
- ~~Mailbox vs. transactional API~~ → **real mailbox (Zoho Mail free).**
  Inbound-parse webhooks deliver events, not an inbox, and Postmark's inbound
  is paid-tier anyway — fails the receive and $0 requirements.
- ~~Does the CRM flip `users.status`?~~ → **No.** Approval stays Telegram
  one-tap (`_cb_invite_decision`); Brevo is a read-mostly mirror, so
  ADR-0031's state machine cannot diverge.
- ~~Scope of "customers"~~ → invite-gate users (`users` rows pushed on
  approval); Brevo can hold a broader list later without vig changes.
- **Still open:** the mailbox name under `leondev.xyz` (one address is enough
  to start; Zoho free allows 5).

## 22. Operator-only `/pending` bot command — re-surface missed invite approvals

> **Grill:** `/grill-with-docs` — hinges on ADR-0031's invite-gate flow.

Closes the missed-push gap recorded in task 21 / `docs/headless CRM.md`: when a
`pending` user submits their email, `_notify_operator_invite`
(`src/telegram/webhook.py:1384`) pushes the Operator **one** message with inline
✅ Approve / 🚫 Block buttons — and if that push is missed, nothing re-surfaces
it. `list_pending_users` (`src/database.py:1773`, oldest-first) still has zero
production callers.

**Wanted:** the Operator types `/pending` and gets the approve/block card
re-sent for every user still awaiting a decision.

**Backend**

- New handler registered in `_SLASH_TABLE` (`webhook.py:1078`), dispatched by
  `_dispatch_slash` (`webhook.py:1098`) with the existing `SlashCtx`.
- **Reuse, don't fork — the whole feature is plumbing that exists:**
  `list_pending_users` supplies the rows; the per-user card (name · email ·
  @username + `invite_approve:{chat_id}` / `invite_block:{chat_id}` buttons) is
  exactly what `_notify_operator_invite` renders — loop it (or extract its
  rendering) per pending row via `send_inline_keyboard`
  (`src/telegram/sender.py:160`). The callback side (`_cb_invite_decision`,
  `webhook.py:448`) needs **zero** changes.
- **Gate is the one new pattern:** no slash command is Operator-gated today —
  `OPERATOR_CHAT_ID` is only checked in the callback handler (`webhook.py:452`)
  and in `_notify_operator_invite`. `/pending` is the first Operator-only
  command, so the `ctx.chat_id != settings.OPERATOR_CHAT_ID` refusal happens
  inside the handler (mirroring `webhook.py:452`'s check + log-and-refuse
  shape).

**Open questions** (resolve in grill)

- Non-operator sends `/pending`: silent ignore (like an unknown command) or an
  explicit "not authorized" reply? (The callback path answers "Not
  authorized." — same posture here?)
- One message per pending user (N pushes for N users) or one message listing
  all with per-row button pairs stacked in a single keyboard? Any cap for a
  long backlog (the repo-picker precedent caps at 5)?
- Empty state: what does `/pending` say when nobody is waiting?
- Does `/pending` get a line in `_HELP_TEXT` (visible to everyone) or stay an
  undocumented Operator command?

## 23. Gemini resilience — model downgrade, 429 requeue-with-backoff, second provider

> **Grill:** `/grill-with-search-docs` — hinges on google-genai SDK error
> types and OpenRouter/Groq API docs.

Every Gemini call funnels through `_call_with_fallback`
(`src/services/gemini.py:164`): it tries `GEMINI_FREE_API_KEY` then
`GEMINI_PAID_API_KEY`, catches **every** exception identically (no 429/quota
inspection, no backoff), and raises `GeminiUnavailableError`. Callers in
`src/processors/*` catch that and fail the job; the worker's `_handle_*`
wrappers (`src/worker.py:45-131`) then send the user "❌ … Please try again."
Model census: 9 call sites hardcode `gemini-2.5-flash`, one uses
`gemini-2.5-flash-lite`, PRD uses `PRD_AUTO_MODEL` (flash) /
`PRD_INTENT_MODEL` (pro) from `src/config.py:82-83`, embeddings
`GEMINI_EMBEDDING_MODEL`. The queue envelope is `{task, job_id}` only
(`src/queue.py:48`) — no attempt counter, no delayed-requeue mechanism.

**Wanted:** a Gemini quota hit or outage degrades (cheaper model → wait and
retry → other provider) instead of failing the job on first contact.

**Backend**

- **Model-downgrade rung** in `_call_with_fallback`: on quota/429, step down a
  model chain before giving up. Reality check from the census: most calls
  already sit at `flash`, so the meaningful rungs are `pro → flash` (PRD
  intent only) and `flash → flash-lite` (everything else). The chain likely
  belongs in config next to the existing model settings, not hardcoded.
- **429 retry-after → requeue, not fail:** distinguish quota errors from other
  failures in the fallback loop (the google-genai SDK's error types — source
  cached at the `google-genai` opensrc path in CLAUDE.md), and let the worker
  requeue the task with backoff instead of `_notify_failure`. Needs an
  `attempt` field in the queue envelope (`queue.py:48` validates only
  `task`/`job_id` today) and a delayed-requeue mechanism — none exists
  (options: `asyncio.sleep` in-worker, a Redis zset delay queue, or the
  already-in-stack APScheduler).
- **Second provider (text only):** an OpenAI-compatible fallback
  (OpenRouter/Groq) behind the same `generate()` seam (`gemini.py:185`) as the
  last rung. Nothing in `src/` imports an OpenAI SDK today — net-new client +
  env keys. Vision (`call_gemini_vision`) and embeddings stay Gemini.

**Open questions** (resolve in grill)

- Downgrade semantics: is a `flash-lite` result acceptable for every text call
  site, or do some (e.g. PRD intent) prefer wait-and-retry at full strength
  over a weaker answer?
- Retry budget: how many requeues, what backoff curve, and when does the user
  finally see a failure message? Does the in-flight job show a "waiting for
  quota" status anywhere?
- Delayed-requeue mechanism: in-worker sleep (blocks a worker slot), Redis
  zset delay queue, or APScheduler — which fits the single-worker loop
  (`worker.py:253`)?
- Second-provider scope: which provider/model, and what happens to
  Gemini-specific features at that rung — `schema` structured output
  translates to OpenAI-style JSON schema, but calls relying on Google-side
  grounding (`_filter_grounded_links`, `resolve_tool_urls`) can't port — are
  they excluded from the provider fallback?
- Is the free→paid **key** rung kept as-is inside each model rung (key × model
  matrix), or does the order become model-first/key-second?

## 24. Feed inventory IA — Links view, Docs ingest action, command launcher ✅ ISSUED #333-#336 - ✅DONE

## 25. Migrate the canonical app URL `app.` → `ownix.leondev.xyz`

> **Grill:** `/grill-with-search-docs` — hinges on external integration config
> (Google OAuth consent verification, Vercel domain, Telegram Login Widget
> domain check) rather than repo internals.

> **Grill together with tasks 26 and 27** — the Ownix rebrand. Shared decisions:
> the new brand string, the cutover ordering (URL vs. code-rename vs. new bot),
> and whether old hosts keep redirecting.

Today the browser only ever talks to `app.leondev.xyz` (Vercel: Next.js +
middleware), which rewrites `/api/*` to `api.leondev.xyz` (Cloudflare Tunnel →
FastAPI) — see `docs/ops/vercel-deploy.md:9-19`. The host is baked into: the
Google OAuth client (JS origin + redirect URI
`https://app.leondev.xyz/api/auth/google/callback`, `docs/ops/oauth-verification.md:25-28,54-55`),
the Telegram Login Widget domain check (`vercel-deploy.md:56`), the `WEB-PRD.md`
spec (`docs/seed/WEB-PRD.md:40,333`), `CONTEXT.md:98`, and `ADR-0016:10`.
`api.leondev.xyz` is a **separate** decision — the memory note pins the prod
webhook host to `api.leondev.xyz` and it is not obviously in scope here.

**Wanted:** the dashboard is reachable at `ownix.leondev.xyz`, with OAuth and the
Telegram login widget still working, and docs/env updated to match.

**Ops / Config**

- New Vercel domain `ownix.leondev.xyz` (CNAME); decide the fate of the old
  `app.` host (permanent 308 redirect vs. retire).
- Google OAuth: add the new JS origin + redirect URI to the "Web client 1"
  credentials, and update the consent-screen homepage/privacy/terms URLs
  (`oauth-verification.md:25-28`). This re-touches the branding verification
  from task 14 — a homepage-URL change may re-trigger review.
- Telegram Login Widget: re-point the widget's allowed domain to the new host
  (`vercel-deploy.md:56`).
- Doc/env sweep: `WEB-PRD.md`, `vercel-deploy.md`, `oauth-verification.md`,
  `CONTEXT.md`, `ADR-0016`, and any `*_URL` env vars.

**Open questions** (resolve in grill)

- Does `api.leondev.xyz` also rebrand (e.g. `api.ownix…`), or does only the
  public app host move while the API host stays?
- Old `app.` host: 308-redirect forever, or hard cutover?
- Does changing the OAuth homepage URL force a fresh Google verification cycle
  (the task 14 pain), and can that be sequenced to avoid downtime?

## 26. Rename VIG → Ownix across code, packages, deployment, and repo metadata

> **Grill:** `/grill-with-docs` — repo-internal rename touching the domain
> model's names, ADRs, and CONTEXT.md terminology.

> **Grill together with tasks 25 and 27** — the Ownix rebrand. Ordering matters:
> a code/service rename, the URL move (25), and a new bot handle (27) should
> cut over in a deliberate sequence, not piecemeal.

"vig" is stamped across build/deploy identifiers, not the API surface. Known
occurrences: `web/package.json` name `vig-web`; `docker-compose.yml` image
`vig-app`, containers `vig-api`/`vig-worker`/`vig-transcript`/`vig-cloudflared`/`vig-redis`,
network `vig-network`; the session cookie `vig_session` (`src/api/auth.py`); the
GitHub repo `Leon-87-7/vig`; the SVG lockup `vig_logo_lockup.svg`; and `CLAUDE.md`/docs
prose. HTTP paths are already brand-neutral (`/api/*`), so routes likely need no
change.

**Wanted:** internal identifiers, package/deploy names, and repo metadata read
"Ownix" instead of "vig", without breaking sessions or deployments.

**Scope (confirm each in grill)**

- **Package/deploy names:** `web/package.json`, docker-compose image/container/network
  names — cosmetic but touch CI, GHCR image tags, and the VPS compose file.
- **Session cookie `vig_session`:** renaming it logs everyone out on cutover
  (the cookie name is the session key). Rename vs. keep-as-legacy-name is a real call.
- **GitHub repo rename** `vig` → `ownix`: GitHub auto-redirects old remotes, but
  issue/PR references, badges, and `docs/agents/*` `Leon-87-7/vig` literals need a sweep.
- **Docs/terminology:** `CLAUDE.md`, `CONTEXT.md`, ADRs — the domain vocabulary.

**Open questions** (resolve in grill)

- Is "VIG" (the product) fully retired, or does it remain an internal
  codename while "Ownix" is the public brand? (Determines how deep the rename goes.)
- Rename the `vig_session` cookie (forces re-login) or leave it for continuity?
- Rename the GitHub repo now, or defer to avoid churning every doc link mid-flight?
- Do docker image tags / GHCR paths rename in lockstep with the VPS deploy, or
  is there a compatibility window?

## 27. New Telegram bot aligned to the Ownix brand

> **Grill:** `/grill-with-search-docs` — hinges on BotFather setup and the
> webhook re-registration flow (external Telegram API), not repo internals.

> **Grill together with tasks 25 and 26** — the Ownix rebrand. A new bot handle
> is the third cutover surface alongside the URL (25) and the code rename (26).

The bot is a single webhook service (`src/telegram/webhook.py`), with
user-facing brand strings in help/command copy (e.g. the intake help text at
`webhook.py:1555`). The BotFather identity (bot username, display name, token)
lives outside the repo; the token is an env var consumed by `sender.py`.

**Wanted:** a Telegram bot whose handle/name/branding reads "Ownix", so the bot
and dashboard present one brand.

**Scope (confirm in grill)**

- BotFather: new bot vs. rename the existing one (display name + @handle +
  about/description + botpic). A brand-new bot means a new token and webhook
  re-registration.
- In-repo copy: brand strings in help/command/reply text (`webhook.py:1555` and
  siblings) — a copy sweep, not logic.
- Config: `TELEGRAM_BOT_TOKEN` (and any hardcoded bot username) if the token changes.

**Open questions** (resolve in grill)

- Rename the existing bot (keeps chat history + user base, zero migration) or
  stand up a brand-new bot (clean handle, but every user must re-/start and the
  webhook + token rotate)?
- If new bot: how do existing users migrate, and does the invite-gate state
  (`users` table, per-`tg_id`) carry over or reset?
- Does the `OPERATOR_CHAT_ID` change with a new bot?

## 28. Web page mirroring the Telegram bot flow — scope against tasks 4 + 24

> **Grill together with task 4** (and shipped task 24). This is very likely
> _task 4_ (web URL submission producing the same job as the bot, incl. per-template
> behavior) plus _task 24_'s already-shipped command launcher (`Submit URL`,
> `Ingest Docs`, `Open Links` — issued #333–#336). Grill's first job is to find
> what, if anything, remains once those two are counted.

The bot flow is: send a URL → `detect_pipeline` classifies it
(`src/utils/validators.py`) → a job is created + enqueued → templates
(`/method`, `/review`, …) shape enrichment. Task 4 already briefs bringing that
to the web via `POST /api/jobs` + a Feed submit control with a template
selector. Task 24 already shipped the command launcher entry points.

**Wanted:** (to be defined in grill) full web parity with the bot's _interaction_
flow — beyond one-shot URL submit — e.g. the bot's follow-up inline prompts
(repo-analysis offer / task 9, PRD "Build Spec" offer, template pickers) surfaced
as web interactions.

**Open questions** (resolve in grill)

- What does this add over task 4 (web submit) + task 24 (launcher)? If nothing,
  close it as a duplicate.
- If there's a real delta, is it the bot's _post-job inline follow-ups_ (repo
  offer, Build Spec, template re-pick) rendered in the dashboard rather than only
  in Telegram? That's the only bot behavior not covered by 4/24.
- Real-time parity: does the web flow need live status push (the bot edits its
  message as the job progresses), or is Feed's existing polling enough?

## 29. Test a new user-approval workflow

> **Grill:** `/grill-with-docs` — hinges on ADR-0031's invite-gate flow and the
> `users.status` state machine.

The current approval flow (ADR-0031): a `pending` user submits an email
(`awaiting_email` chat state, `src/database.py:124`; or the dashboard modal
`web/components/invite-gate.tsx` → `PUT /api/auth/email`, `src/api/auth.py:151`),
which sets `users.email`/`users.status` (`src/database.py:141`). The Operator
gets a one-shot push (`_notify_operator_invite`, `src/telegram/webhook.py:1384`)
with ✅ Approve / 🚫 Block buttons handled by `_cb_invite_decision`
(`webhook.py:448`). Task 22 already briefs an Operator `/pending` command to
re-surface missed approvals.

**Wanted:** unclear from the one-liner — either (a) trial/design a _different_
approval workflow, or (b) add test coverage for the existing one. Resolve before
scoping.

**Open questions** (resolve in grill)

- "Test a new workflow" = prototype a _changed_ approval UX (e.g. self-serve,
  auto-approve rules, a web approval surface), or write _tests_ for today's flow?
- If a new workflow: what's wrong with the current Telegram one-tap gate that a
  new one fixes? (Task 22 already addresses the "missed push" gap.)
- Does it stay Telegram-only, or move approval into the dashboard (which task 21
  explicitly ruled out for contact data)?

## 30. Link-level tags in the Links table + mobile color-badge redesign ✅ ISSUED TO GITHUB #382 #383 #386 #387 - ✅DONE

## 31. Fold Instagram `/p/` carousels into the short pipeline; drop PRD creation from the long pipeline

> **Grill:** `/grill-with-docs` — two changes to the pipeline domain model (the
> `Pipeline` classifier and a processor's post-job offer).

Two independent pipeline edits bundled in one idea:

1. **IG carousels are currently rejected.** `_match_short`
   (`src/utils/validators.py:123-133`) matches `instagram.com/reel/` only;
   `instagram.com/p/{id}` falls through to `"rejected"` (docstring `validators.py:90`),
   and the bot help text advertises "Instagram Reels (not /p/ carousels)"
   (`src/telegram/webhook.py:1555`).
2. **The long pipeline offers PRD creation.** After a long video processes,
   `src/processors/long_video.py:145` presents a "📐 Build Spec" inline button
   (`prd_build_spec:{job_id}`) alongside "Run Gemini", wired to the PRD flow
   (`src/processors/prd.py`).

**Wanted:** `instagram.com/p/` carousels get accepted by the short pipeline, and
the long pipeline stops offering PRD/spec creation.

**Backend**

- Extend `_match_short` (`validators.py:131`) to also match `instagram.com/p/`,
  and update the `detect_pipeline` docstring + the help copy (`webhook.py:1555`).
- Remove the "Build Spec" offer from `long_video.py:145` and trace the now-dead
  `prd_build_spec` callback handler + whether `src/processors/prd.py` still has
  any caller afterward (short/article PRD paths, if any, must not break).

**Open questions** (resolve in grill)

- Can the short _processor_ (`processors/short_video.py`, Gemini Vision on a
  single video) actually handle a multi-image `/p/` carousel, or does accepting
  the URL just move the failure downstream? (This is the real risk — routing is
  one line; processing a carousel may not be.)
- "Remove PRD from the long pipeline" — remove only the _offer_ on long videos,
  or retire the PRD feature entirely (does anything else still create PRDs)?
- Does dropping `prd_build_spec` leave orphaned code (`prd.py`, callback
  registration, `PRD_*` config in `src/config.py`) to clean up, or stay for
  other callers?

## 32. Standalone link identity — per-URL description + search that doesn't leak siblings ✅ ISSUED TO GITHUB #381 #384 #385 - ✅DONE

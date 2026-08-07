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

- Browser extension / share-target for one-click capture (see task 34 for the sibling idea from the same Youwee comparison) — Youwee's biggest UX win over raw yt-dlp is "right-click → send to app" instead of copy-pasting URLs. Ownix's ingestion is currently Telegram-only; a tiny extension (or even a bookmarklet hitting `POST /api/jobs`) that fires the existing `create_and_enqueue_job()` would remove real friction and fits the "drive the pipeline from the web" direction already in PRODUCT.md.
- Vimeo support needs an authenticated session — deferred out of task 34 after exhaustive probing (2026-08-01). Every anonymous route is closed: default `macos` client 401s because Vimeo revoked the app credential yt-dlp impersonates (`{"developer_message": "The request includes an unauthorized client.", "error_code": 8001}`), `player.vimeo.com` embed URLs hit the same 401, `client=android`/`client=ios` are cache-only ("unable to fetch new OAuth tokens"), and `client=web` reports "only works when logged-in". Doing it means: own a Vimeo account, add its cookies to the sidecar credential checkout (the Instagram mechanism at `transcript_server.py:124` already exists), **and extend `_with_cookies` to `/metadata`** — today it only wraps `_download_audio_b64` (`:192`), so the unsized resolver runs cookie-less. That last part is the reusable half: any future auth-gated host needs it too.
- ~~Pin `yt-dlp`~~ → **resolved 2026-08-02: expose, don't pin.** Pinning yt-dlp freezes site *breakage* rather than behaviour — extractors rot as sites change and yt-dlp ships fixes within days, so newest-is-correct. The real bug was invisibility plus an accidental freeze: `--no-cache-dir` is pip's cache, not Docker's, so the single `pip install` layer was reused forever and yt-dlp never actually updated — pinned in practice, to an unknown version. Shipped: `GET /health` returns the `yt_dlp` version (`transcript_server.py`), and `Dockerfile.transcript` installs yt-dlp in its own layer behind an `ARG YTDLP_REFRESH` cache-buster so it refreshes without rebuilding the ffmpeg/apt layers. Deliberately not automated: a rebuild cadence (cron/CI) — add one only if manual rebuilds get tedious. Surfaced by task 34's host probe.
- Tag-filtered feed view (`?tag=<name>`) — you have a curated tag vocabulary with `meaning`, icons and colors, and **no way to browse by one**. `web/app/(dashboard)/feed/page.tsx` reads only two URL params (`params.set` appears exactly twice: `type` at `:262`, `view` at `:283`) — no search or tag param exists, so a tag is un-linkable. Wanted from two directions: clicking a tag pill (`web/components/feed/job-card-tags.tsx`, `web/components/ui/tag-picker.tsx`) should filter the feed to it, and the [[Intake console]]'s unknown-[[Tag token]] path wants to deep-link "show me everything tagged X" instead of telling the user to type it into a search box. Note the split the filter has to answer: `job_tags` and `link_tags` are separate vocabularies over the same `tags` table (CONTEXT.md **Link tag**: "coexists … no reconciliation"), so `?tag=GoTo` on a job tab and on the Links tab mean different sets. Surfaced 2026-08-06 by the intake-makeover grill, which took the lazy path (a plain warning, no link) rather than block on this.

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

## 7. Better navigation for the Brain "Links" table ✅ ISSUED TO GITHUB #306 - ✅DONE

## 8. Controls UI on the Brain search graph

> **Grill:** `/grilling` — pure product/UX; the ForceGraph ref methods are
> already pinned in the brief.

> **Grounded:** 2026-07-27

`web/components/brain/brain-graph.tsx` renders `react-force-graph-2d` from
`GET /api/brain/graph` (`src/api/brain.py:34`), highlighting search matches in
signal orange. There are no user-facing controls today (no zoom, recenter, or
filtering).

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

> **Grilled 2026-07-31 (session 2) — per-tenant half CLOSED, split done.**
> This task now covers **only** the per-tenant Brain; Community Brain + Sharer
> window are deferred to their own task (opens preserved at the bottom).
> Every session-1 decision was independently re-derived and confirmed. Written
> up as **ADR-0043**; `CONTEXT.md`'s [[Second Brain]] entry updated. Five things
> session 1 did not have:
>
> 1. **137 orphan links** (`source_job` → no `jobs` row) — the session-1 backfill
>    rule `source_job → jobs.chat_id` yields `NULL` for them. Fixed with
>    `COALESCE(..., <operator chat_id>)`; they are demonstrably the Operator's
>    own May-2026 content from deleted jobs.
> 2. **A second tenant already owns a link** (`6388384480` /
>    `github.com/openai/openai-cookbook`). A literal "backfill everything to me"
>    would have silently absorbed it — the exact leak this task removes.
> 3. **Live Drive leak.** `brain.py` calls `upload_file()` with no `chat_id`;
>    `drive.py:72` documents "System calls (no chat_id) pass", and
>    `config.py:157` `export_blocked(None)` returns `False`. So every tenant's
>    Brain `.md` lands in the Operator's Drive folder today. `brain.py` is
>    ADR-0030's last uncovered caller. Session 1 never mentioned Drive.
> 4. **`get_link_preview` IDOR** — `src/api/brain.py:57` takes no viewer, so any
>    tenant can read any link by id.
> 5. **`idx_links_url_unique` already exists** (migration v31). The soft dedup
>    was hardened on the *wrong* key; migration must DROP it, not merely add one.
>
> Also: the scoping note at `src/api/brain.py:5-8` ("intentionally... the single
> shared Second Brain... see PRD §5") is **stale and wrong** — it contradicts
> this task's session-1 resolution, and PRD §5 is *Deployment & Operations*. The
> Brain spec is §13, which assumes a single user rather than deciding anything.
> ARCHITECTURE D7 ("single-user portfolio tool — harden when: tool goes
> multi-user") and D8 ("switch when per-user partitioning is needed") both point
> the same way. Delete the note during implementation.
>
> **Resolved this session:**
>
> - ~~One canonical row + membership table, or a row per owner?~~ → **Row per
>   owner.** `UNIQUE(chat_id, url)`, duplicate rows accepted. A shared canonical
>   row leaves `title`/`description` mutable by whichever tenant re-scrapes last,
>   which is the same leak one level down; it also forces `link_tags.link_id` to
>   re-point off `links.id`, contradicting session 1's join-key decision.
> - ~~Cost of duplicate rows?~~ → **Duplicate the row, never the work.** Before
>   fetching or embedding, `SELECT title, description, og_image_url, embedding
>   FROM links WHERE url = ? AND embedding IS NOT NULL LIMIT 1` and reuse it. No
>   refetch, no second Gemini call. Residual cost is ~3 KB of blob per duplicate
>   row; revisit at ~100k rows (`ponytail:` the ceiling in code).
> - ~~First scrape vs re-scrape on a second tenant's ingest?~~ → **First scrape
>   wins.** Re-scraping would mutate content another tenant already sees. Repo
>   `stars`/`pushed_at` refresh (ADR-0027) stays, being objective facts.
> - ~~How does `ingest_links` learn `chat_id`?~~ → **Derives it** from
>   `source_job_id` (`SELECT chat_id FROM jobs WHERE id = ?`). Signature and all
>   7 callers unchanged; a caller cannot pass a mismatched owner. Job missing →
>   skip the ingest, which also guards against creating new orphans.
> - ~~FK on `source_job`?~~ → **No.** Enforcing it would fail the migration on
>   the 137 orphans. `chat_id` carries ownership now; `source_job` degrades to
>   the Obsidian backlink it always really was.
> - ~~Drive vault after scoping?~~ → **Operator-only, via the gate that already
>   exists.** Pass `chat_id=` at the four `brain.py` upload sites. Non-Operator
>   tenants get the DB Brain (Links table, graph, `/find`) and `drive_file_id`
>   stays `NULL`, so `_touch_existing_link`'s rewrite branch no-ops. Free bonus:
>   `export_blocked` already exempts token-holders and `drive.py:78` routes them
>   to `user_folder_id(chat_id)`, so a tenant who has connected Google gets their
>   own folder with no extra work. Also removes the `{slug}.md` collision.
>   Aggregates (`rebuild_graph`, `refresh_stale_links`) now pass each row's own
>   `chat_id`, so they stop relying on the None-passes branch.
> - ~~Restricted mode Brain (ADR-0035 "remains as-is")?~~ → **Operator's graph,
>   read-only** — `preview.py:124` already uses `OPERATOR_CHAT_ID` for the Feed
>   corpus, so Brain becomes consistent with Feed rather than special-cased.
>
> **Implementation order** (one migration, `PRAGMA user_version` bump):
>
> 1. `ALTER TABLE links ADD COLUMN chat_id INTEGER` → backfill
>    `COALESCE((SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job),
>    <operator>)` → `DROP INDEX idx_links_url_unique` →
>    `CREATE UNIQUE INDEX idx_links_chat_url ON links(chat_id, url)`.
>    (`chat_id NOT NULL` needs a table rebuild in SQLite — acceptable at 449 rows;
>    decide rebuild-vs-leave-nullable at implementation time.)
> 2. `ingest_links` derives `chat_id`; add the reuse `SELECT`; scope
>    `_ingest_one_link`'s existence check and `_compute_related` to the owner.
> 3. Add `WHERE l.chat_id = ?` to `list_links`, `search_links`, `get_graph`,
>    `rebuild_graph`, `get_link_preview`; thread the viewer through
>    `src/api/brain.py` (404, not 403, on another tenant's link — don't leak
>    existence) and through `/find` + `/rebuild-graph` in the Telegram webhook.
> 4. Pass `chat_id=` at the four `brain.py` Drive sites; delete the stale
>    scoping note at `src/api/brain.py:5-8`.
> 5. Restricted mode: Brain reads `OPERATOR_CHAT_ID`.
>
> **Verification:** seed two chat_ids with an overlapping URL and assert — each
> sees exactly its own rows in `list_links`/`search`/`graph`; the second ingest
> makes zero Gemini and zero HTTP calls; deleting tenant A's job leaves tenant
> B's row intact (today it does not — `database.py:2253` deletes by `source_job`);
> a non-Operator ingest writes no Drive file.

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
- ~~Migration mechanics~~ → **closed 2026-07-31**, see the session-2 note above
  (drop `idx_links_url_unique`, create `(chat_id, url)`, `COALESCE` backfill).
- ~~Do `search_links`, `get_graph`, and `/api/brain/*` gain viewer scoping in
  this task?~~ → **Yes, all of them, in this task.** The Community tab is split
  out and no longer gates the scoping work.
- Surface/edit URL tags where: the Brain Links table (task 30), the controls
  page, or both?
- Migration: do existing `job_tags` rows get projected onto their URLs, or do
  URL tags start empty?
- ~~**ADR candidate**~~ → **ADR-0043** written 2026-07-31 for the per-tenant
  half. Forward-only community sharing still needs its own ADR when that task
  is grilled.

**Deferred to a separate task — Community Brain + Sharer window.** Both concepts
stay defined in `CONTEXT.md`; nothing about them is being built here. Their opens:

- **Timer semantics:** fixed window with silent expiry (recommended — one
  `sharer_until` timestamp, checked at ingest, no background jobs), fixed window
  + Telegram expiry notice (needs a scheduled check), or activity-extended
  sliding TTL? Is 8–12h fixed or user-chosen?
- Confirm: tags never appear in the Community tab (private-only), correct?
- Where does the opt-in/sharer toggle live in the UI (Brain page header,
  Community tab itself, controls page)?
- With `(chat_id, url)` rows, the Community tab must merge N owner-rows per URL
  at read time — decide whether `shared_at` lives on the link row (per owner) or
  in a separate table.

## 12. Repalette: new signal orange + dark plate tokens

> **Grill:** `/grilling` — pure design decisions (which plate `#2A2312`
> replaces, ramp re-derivation, WCAG re-verification).

> **Grounded:** 2026-07-27 — re-vision: a repalette has **already shipped**
> since this brief was written; the values below are the current source of truth.

The design tokens have a single source: `web/tailwind.config.ts`
(`tailwind.config.ts:9-29`) now defines `signal.DEFAULT: '#d99a45'` (ramp
`bright #efb566`, `deep #a57534`, `onsignal #1b1309`), the plate ladder
`canvas: '#0d0e10'` → `surface: '#16181c'` → `raised: '#202329'`, **plus a new
`contrasignal` family** (`#94e6ee` / `#9ec9ff` / `#649ca1`) this brief predates.
The same values are normative in `DESIGN.md`'s frontmatter, and `web/` consumers
use Tailwind classes (`bg-signal`, `text-signal`, `bg-canvas`…), so they inherit
any change without edits.

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
- **Is this task still wanted at all?** A repalette to `#d99a45` shipped after
  this brief was written — was that the answer to this idea (making this
  superseded), or is the `#FFBE0B`/`#2A2312` direction still the goal?
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

> **Grill:** `/grill-with-docs` — domain-model call (what auto-routes into the
> ADR-0039 link pipeline vs. staying rejected).

> **Grounded:** 2026-07-27 — re-vision: **most of this shipped as ADR-0039.** A
> full link pipeline now exists: `src/processors/link.py` (fetches OG tags,
> ingests one Brain link, verifies persistence), worker dispatch `"link"`
> (`src/worker.py:100,209`), fed by the explicit `/addlink` command
> (`_cmd_addlink`, `src/telegram/webhook.py:751`) via
> `create_and_enqueue_job(chat_id, url, "link", ...)` (`webhook.py:762`) —
> `"link"` is a content_type assigned outside `detect_pipeline` (the `Pipeline`
> literal at `validators.py:8` is unchanged). **The remaining delta is only the
> trigger:** bare unrecognized URLs still die in `_reject_url`.

`_route_url` (`src/telegram/webhook.py:1564`) still sends every URL
`detect_pipeline` (`src/utils/validators.py:89`) rejects straight to
`_reject_url` (`webhook.py:1489`): a canned "Unsupported URL" reply
(`webhook.py:1500`), no job, no persistence — even though the machinery to
capture it now exists one call away.

**Wanted:** sending a bare URL that isn't a video/article/repo/document gets a native Telegram
link-preview card in reply and a row in the Brain Links table on the dashboard — capture only, no
enrichment job.

**Backend**

- **Reuse, don't fork:** new branch in `_route_url` (`webhook.py:1564`) that routes would-be-rejected
  URLs through the exact call `/addlink` makes — `create_and_enqueue_job(chat_id, url, "link",
  message_id=...)` (`webhook.py:762`). No new processor, no `Pipeline` extension needed;
  `create_and_enqueue_job` already owns dedup (ADR-0033 — a URL already captured under any
  content_type returns the existing job).
- Native preview reply via `send_message` (`src/telegram/sender.py:130`) with the raw URL as the
  message text — no caller sets `disable_web_page_preview`, so Telegram's default preview card is
  the off-the-shelf behavior.
- ~~topic/source_job_id for a jobless link~~ — answered by shipped code: the link *job* anchors
  `source_job_id`, and `ingest_links` (`src/brain.py:542`) takes the flattened OG collection as
  `topic` (see `link.py:37-41`).

**UI**

- Nothing to build: `/addlink` rows already render in the Links table (`GET /api/brain/links`,
  `src/api/brain.py:39`); auto-routed rows are the same shape.

**Open questions** (resolve in grill)

- Scope: every URL `detect_pipeline` currently rejects, or a narrower class (exclude bare domains,
  search-result URLs, non-http schemes)? `/addlink` gates on `is_fetchable_url` — same bar here?
- Precedence: if a pasted URL also matches an allowlisted article domain, does full article
  enrichment still win, or does "just save + preview" only apply when nothing else claims the URL?
- Does `/addlink` stay as the explicit escape hatch once bare URLs auto-capture, or retire?

## 17. Persistent account/status affordance — Google connection state + Telegram identity ✅ DONE — issued #292–#295, merged PR #296

## 18. Job details page — previous/next navigation buttons ✅ ISSUED TO GITHUB #309 - ✅DONE

## 19. Delete button for jobs — DB + Telegram message, with confirm/"don't show again", swipe-to-delete on mobile

> **Grill:** `/grilling` — UX semantics (swipe, confirm, undo); no external or
> domain-model hinge.

> **Grill together with task 33.** Task 33 is the narrow first slice (details
> page only, dashboard-only, no Telegram deletion, no swipe) and owns the shared
> `DELETE /api/jobs/{job_id}` endpoint; this task extends the surface (cards,
> swipe, Telegram message deletion, "don't show again"). Decide the endpoint
> contract once.
>
> **Endpoint contract settled 2026-07-27 in task 33's grill** — `DELETE
> /api/jobs/{job_id}` → 204, hard delete (job row + cascades + `links`
> de-index), cloud artifacts purged asynchronously via a `job_purge` envelope,
> allowed from any status. See ADR-0042. Two carry-overs for this task: the
> reusable `web/components/ui/confirm-dialog.tsx` it introduces (reuse it for
> swipe/cards rather than forking), and the note that the five-table cascade
> does **not** cover `links` — this task's grounding says otherwise.

> Touches the same job-card real estate as task 7's dense-table thinking and task 11's per-URL
> tagging — no shared decision, just adjacent surface area.

> **Grounded:** 2026-07-27

Jobs render as cards in two places: `JobCard` (`web/components/feed/job-card.tsx`, Feed's list
view) and `PreviewCard` (`web/components/feed/preview-card.tsx`, Feed's grid view via
`PreviewGrid`, `web/components/feed/preview-grid.tsx`), plus the full job details page
(`web/app/(dashboard)/jobs/[id]/page.tsx`). Both card components carry a
`pointer-events-auto` overlay island for `JobCardTags` sitting above a full-card `<Link>`
overlay — the established pattern for "an interactive control on a whole-card-is-a-link card."

There is **no DELETE endpoint for jobs today** (re-verified 2026-07-27: `src/api/jobs.py` has only
`DELETE /{job_id}/tags/{tag_id}`, `jobs.py:423`). The `jobs` table (`src/database.py:35`) has
`chat_id`, `message_id` (the operator's original Telegram message) and `bot_message_id` (the bot's
reply) — plain `INTEGER` columns with no Telegram-side deletion ever issued against them. Five
child tables cascade on job delete already (`ON DELETE CASCADE`): `job_thumbnails`,
`job_annotations`, `job_tags` (`database.py:238`), `space_urls`, `document_outputs` — a `DELETE
FROM jobs WHERE id = ?` is enough on the DB side. `src/telegram/sender.py` still has no
`deleteMessage` call; every Bot API call goes through `_post_and_parse` (`sender.py:98`), the same
helper `send_message` (`sender.py:130`) uses — a `delete_message(chat_id, message_id)` following
that pattern is the natural way to add it. Auth/ownership for a job lookup already exists via
`get_owned_job` (`src/api/deps.py`).

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
- **"Don't show again" persistence:** `src/database.py` has a generic per-chat
  `get_user_setting`/`set_user_setting` (`database.py:1326-1341`, used today for the Brain links
  view and recovery-notification toggle). Drift note 2026-07-27: `localStorage` **is** now used in
  `web/app/(dashboard)/feed/page.tsx`, so a client-side preference pattern exists too — pick
  server-side (`user_setting`, follows the chat across devices) vs. the feed page's `localStorage`
  precedent in grill.

**UI**

- Desktop: a delete control in the same `pointer-events-auto` overlay slot `JobCardTags` occupies
  on `JobCard`/`PreviewCard`. The job details page's delete control is owned by task 33 —
  this task adds the card surfaces on top of it.
- Confirm dialog: `window.confirm()` is used in three places now (`web/components/shell/sidebar.tsx:252`,
  `web/app/(dashboard)/spaces/[id]/page.tsx:31` — a delete confirm, `web/components/feed/submit-job.tsx`),
  but none supports a "don't show again" checkbox — so this needs a real dialog. Drift note
  2026-07-27: a shared `web/components/ui/dialog.tsx` primitive has shipped since this brief —
  reuse it (don't extend `ui/export-modal.tsx` as originally suggested).
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

> **Grounded:** 2026-07-27 — re-vision: **this feature has effectively
> shipped**, on the Ops bot rather than the main bot. `src/services/ops_bot.py`
> now handles `/pending` (lists all pending users, `ops_bot.py:305-306`),
> `/users [pending|approved|blocked|email …]` (`ops_bot.py:313`), and
> `/approve_pending <domain>` with a confirm step and batch approve
> (`ops_bot.py:326`, `_approve_pending_ids` `ops_bot.py:236`,
> `approve_pending_domain` `ops_bot.py:289`). Invite cards go out via
> `src/services/invite_notifications.py` with `ops_invite_approve` /
> `ops_invite_block` callbacks (`ops_bot.py:115`). The original premise — "if
> the push is missed, nothing re-surfaces it" — no longer holds.

**Wanted (original):** the Operator types `/pending` and gets the approve/block
card re-sent for every user still awaiting a decision.

**Remaining delta, if any:** the Ops-bot `/pending` output is a text listing
(`deliver_rows`/`format_rows`), not re-sent per-user cards with inline
✅ Approve / 🚫 Block buttons — one-tap approval exists only on the original
invite card and via the `/approve_pending <domain>` batch path.

**Open questions** (resolve in grill — or skip the grill entirely)

- Is the text listing + domain-batch approve enough to close this task as
  shipped, or is per-row one-tap approve/block in the `/pending` output still
  wanted?
- If kept: does that belong in the Ops bot (`handle_ops_command`) — the main
  bot (this brief's original home) is presumably wrong now that user admin
  lives on the Ops bot?

## 23. Gemini resilience — model downgrade, 429 requeue-with-backoff, second provider

> **Grill:** `/grill-with-search-docs` — hinges on google-genai SDK error
> types and OpenRouter/Groq API docs.

> **Grounded:** 2026-07-27 — re-verified: no retry/backoff/attempt logic has
> been added anywhere in `gemini.py` or the queue envelope since the brief.

Every Gemini call funnels through `_call_with_fallback`
(`src/services/gemini.py:167`): it tries `GEMINI_FREE_API_KEY` then
`GEMINI_PAID_API_KEY`, catches **every** exception identically (no 429/quota
inspection, no backoff), and raises `GeminiUnavailableError`. Callers in
`src/processors/*` catch that and fail the job; the worker's `_handle_*`
wrappers (`src/worker.py:47-187`) then send the user "❌ … Please try again."
Model census: 9 call sites hardcode `gemini-2.5-flash`, one uses
`gemini-2.5-flash-lite`, PRD uses `PRD_AUTO_MODEL` (flash) /
`PRD_INTENT_MODEL` (pro) from `src/config.py:95-96`, embeddings
`GEMINI_EMBEDDING_MODEL`. The queue envelope is `{task, job_id}` only
(`src/queue.py:48-51`) — no attempt counter, no delayed-requeue mechanism.

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

> **Grounded:** 2026-07-27 — re-verified: `ownix.leondev.xyz` appears nowhere in
> `docs/ops/` — the migration hasn't started. Sequencing input: the GitHub repo
> already renamed `vig` → `ownix` (2026-07-18, old URLs redirect), so the
> rebrand trio is no longer starting from zero.

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

> **Grounded:** 2026-07-27 — re-vision: the **GitHub repo rename is already
> done** (`Leon-87-7/ownix` since 2026-07-18, old URLs redirect), and the
> new-brand naming already has a precedent in code: the `ownix_preview` cookie
> (ADR-0035). Everything else below re-verified as still `vig`.

"vig" is stamped across build/deploy identifiers, not the API surface. Known
occurrences: `web/package.json` name `vig-web` (`package.json:2`);
`docker-compose.yml` — 15 `vig-*` occurrences (image, containers, network); the
session cookie `vig_session` (`COOKIE_NAME`, `src/auth/middleware.py:12` — not
`src/api/auth.py` as previously cited); the SVG lockup `vig_logo_lockup.svg`;
and `CLAUDE.md`/docs prose. HTTP paths are already brand-neutral (`/api/*`), so
routes likely need no change.

**Wanted:** internal identifiers, package/deploy names, and repo metadata read
"Ownix" instead of "vig", without breaking sessions or deployments.

**Scope (confirm each in grill)**

- **Package/deploy names:** `web/package.json`, docker-compose image/container/network
  names — cosmetic but touch CI, GHCR image tags, and the VPS compose file.
- **Session cookie `vig_session`:** renaming it logs everyone out on cutover
  (the cookie name is the session key). Rename vs. keep-as-legacy-name is a real call.
- **GitHub repo rename** `vig` → `ownix`: ~~done 2026-07-18~~ — what remains is
  the literal sweep: issue/PR references, badges, and any `Leon-87-7/vig`
  literals still in `docs/agents/*` and elsewhere.
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

> **Grounded:** 2026-07-27 — drift note: there are **two** bots now, not one —
> the main intake bot (`src/telegram/webhook.py`) and the Ops bot
> (`/webhook/ops`, handlers in `src/services/ops_bot.py`). The rebrand scope
> must decide whether the Ops bot's BotFather identity rebrands too.

The main bot is a webhook service (`src/telegram/webhook.py`), with
user-facing brand strings in help/command copy (the intake/help text at
`webhook.py:584`, `:707`, `:833`, `:1430`, `:1500`). The BotFather identity
(bot username, display name, token) lives outside the repo; the token is an
env var consumed by `sender.py`.

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

> **Grounded:** 2026-07-27 — re-vision: **`POST /api/jobs` already exists**
> (`src/api/jobs.py:206`) and the Feed's Submit URL dialog (`SubmitJobProvider`,
> `web/components/feed/submit-job.tsx`) already shipped with task 24 — so task
> 4's core deliverable appears largely built, which shrinks this task's
> possible delta even further. Task 4 should probably be audited for DONE
> before this is grilled at all.

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

## 29. Streamline new-user signup — pending is a preview, not a wall ✅ ISSUED TO GITHUB #449 #450 #451 #452

## 30. Link-level tags in the Links table + mobile color-badge redesign ✅ ISSUED TO GITHUB #382 #383 #386 #387 - ✅DONE

## 31. Fold Instagram `/p/` carousels into the short pipeline; drop PRD creation from the long pipeline

> **Grill:** `/grill-with-docs` — two changes to the pipeline domain model (the
> `Pipeline` classifier and a processor's post-job offer).

> **Grounded:** 2026-07-27 — drift note: the "Build Spec" offer is **not
> long-video-only**. It's rendered from three sites: `long_video.py:146`,
> `enrichment.py:404,517` (the short-pipeline enrichment path), and
> `prd.py:326,446` (the PRD flow re-offering itself). Removing it from the long
> pipeline alone leaves the others — the "retire PRD entirely?" open question
> below is now the load-bearing one.

Two independent pipeline edits bundled in one idea:

1. **IG carousels are currently rejected.** `_match_short`
   (`src/utils/validators.py:146`) matches `instagram.com/reel/` only;
   `instagram.com/p/{id}` falls through to `"rejected"` (docstring `validators.py:110`),
   and the bot help text advertises "Instagram Reels (not /p/ carousels)"
   (`src/telegram/webhook.py:1500`).
2. **The long pipeline offers PRD creation.** After a long video processes,
   `src/processors/long_video.py:146` presents a "📐 Build Spec" inline button
   (`prd_build_spec:{job_id}`) alongside "Run Gemini", wired to the PRD flow
   (`src/processors/prd.py`; callback `_cb_prd_build_spec`, `webhook.py:297`,
   registered at `webhook.py:490`).

**Wanted:** `instagram.com/p/` carousels get accepted by the short pipeline, and
the long pipeline stops offering PRD/spec creation.

**Backend**

- Extend `_match_short` (`validators.py:146`) to also match `instagram.com/p/`,
  and update the `detect_pipeline` docstring (`validators.py:110`) + the help
  copy (`webhook.py:1500`).
- Remove the "Build Spec" offer from `long_video.py:146` — but note the same
  button is also rendered from `enrichment.py:404,517` and `prd.py:326,446`, so
  the `prd_build_spec` callback (`webhook.py:297,490`) is **not** dead after
  this removal; only a full PRD retirement would orphan it.

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

## 33. Permanent delete button at the bottom of the job details page (dashboard-only)

> **Grilled 2026-07-27.** ~~Pure product/UX; the endpoint shape and cascade
> mechanics are already pinned below.~~ It was not pure product/UX — the grill
> found the cascade claim incomplete and the scope grew to a full cloud purge.
> See the Correction and Resolved blocks below, plus ADR-0042.

> **Grill together with task 19.** This is the narrow first slice of task 19's
> full delete surface: details page only, dashboard-only (Telegram messages
> deliberately untouched), no swipe gesture, no "don't show again". This task
> owns the shared `DELETE /api/jobs/{job_id}` endpoint; task 19 extends the UI
> surfaces on top of it. Decide the endpoint contract once.

> **Grounded:** 2026-07-27

The job details page is `web/app/(dashboard)/jobs/[id]/page.tsx` (actions
cluster `JobActionsBar`, `page.tsx:497`, rendered at `page.tsx:676`). There is
no DELETE endpoint for jobs in `src/api/jobs.py` (verified 2026-07-27). Five
child tables already cascade on job delete (`ON DELETE CASCADE` — task 19's
grounding): `job_thumbnails`, `job_annotations`, `job_tags`, `space_urls`,
`document_outputs`. Ownership lookup exists via `get_owned_job`
(`src/api/deps.py`).

> **Correction (grill, 2026-07-27):** "a `DELETE FROM jobs WHERE id = ?` is
> complete on the DB side" was wrong. `links.source_job` (`database.py:179`) is
> `TEXT NOT NULL` with **no FK** and does not cascade, so a row-only delete
> leaves the job in `/find` and the Brain graph. Cloud artifacts are likewise
> untouched — Drive docs, the GCS objects behind `document_outputs.gcs_key`
> (`database.py:282`), and the Sheets row — and **no delete primitive exists**
> in `storage.py` / `drive.py` / `sheets.py` today. Job thumbnails are *not*
> cloud artifacts: `job_thumbnails.bytes` is a SQLite BLOB (`database.py:101`),
> so the cascade already disposes of them.

**Wanted:** a delete button at the bottom of the job details page that, behind a
hard confirmation, permanently deletes the job from the DB (no soft-delete/trash
tier) and leaves the page.

**Resolved 2026-07-27 (grill).** Full rationale in ADR-0042; glossary terms
[[Job delete]] / [[Job purge]] and invariants 15–16 in `CONTEXT.md`.

**Backend — `DELETE /api/jobs/{job_id}`, 204 No Content**

- Ownership via `get_owned_job`; `204` matches the existing
  `@spaces_router.delete(..., status_code=204)` precedent (`src/api/spaces.py:129`).
- Synchronous half: capture the job's artifact refs, then `DELETE FROM jobs
  WHERE id = ?` (five tables cascade) **plus** `DELETE FROM links WHERE
  source_job = ?` to de-index the Brain.
- Asynchronous half: enqueue a `job_purge` task envelope **carrying those refs**
  (the row is gone by the time the worker runs) and delete the Drive documents,
  GCS objects and Sheets row from the worker — retryable, never fails the click.
  Needs three new service functions; Sheets rows are found by URL (no row index
  is stored), miss is logged and skipped.
- Allowed from **any** status. Add a drop-if-missing guard in `src/worker.py`
  after `BRPOP`: if the job row is gone, log and skip the envelope. This is what
  makes deleting a `pending` job safe — the pipeline is not idempotent, so
  re-running it would upload fresh artifacts for a purged job. A job already
  mid-pipeline is not interrupted (no live cancellation exists); that window can
  still orphan artifacts, accepted for now.
- No Telegram-side calls (task 19 owns message deletion).

**UI**

- Trigger at the **bottom** of the details page, below the existing content —
  not inside `JobActionsBar`. Quiet treatment: ghost border + `text-status-error`,
  identical to `spaces/[id]/page.tsx:78`, so it never competes with the amber in
  `JobActionsBar`.
- Delete-zone layout (2026-07-27): one row — **trigger · 1px vertical divider ·
  warning text** — under a hairline top border. Divider is `border-line`,
  `align-self: stretch`; the trigger is `flex-shrink: 0` so the warning wraps
  instead of squeezing it. Stacks to a column below ~620px, divider hidden.
- Confirmation: new reusable `web/components/ui/confirm-dialog.tsx` built on the
  `ui/dialog.tsx` primitive, with an explicit destructive button. This is the
  repo's **first** styled confirm — the four existing `window.confirm` sites
  (spaces delete, Google disconnect `sidebar.tsx:252`, clear-failed ×2 in
  `submit-job.tsx`) are deliberately **not** migrated. Task 19 reuses this
  component for its surfaces.
- Destructive color: the dialog's confirm button is a solid `#f87171` fill with
  near-black `#1b1309` text — the product's only filled red, existing only
  behind a modal. Add a `button-danger` token to DESIGN.md, which currently
  defines no destructive button (note: DESIGN.md's action color is Index Amber
  `#d99a45`, not the `#f6921e` quoted in older briefs).
- Failure: mirror the spaces pattern — a small `text-status-error` line under
  the button, no toast.
- Post-delete: `router.back()`, guarded — `if (window.history.length > 1)
  router.back(); else router.push('/feed')`, so a deep link, bookmark or hard
  refresh doesn't strand the user on a dead page or bounce them out of the app.

## 34. Widen video source coverage — an `unsized` content_type resolved by duration ✅ ISSUED TO GITHUB #466 #467 #468 #469

> **Grill:** `/grill-with-search-docs` — in progress 2026-08-01. Origin: a
> competitor comparison against **Youwee** (`vanloctech/youwee`), a Tauri
> desktop GUI wrapping yt-dlp/FFmpeg that advertises 1800+ supported sites.
> Sibling idea from the same comparison (browser extension / share-target for
> one-click capture) sits in the Inbox.

> **Grounded:** 2026-08-01

> **Grilled 2026-08-01** — classification shape, the `unsized` content_type, the
> worker duration resolution and the failure mode are all closed. Written up as
> **ADR-0045**; `CONTEXT.md` gains an [[Unsized video]] glossary entry, a third
> worker-dispatch branch in the architecture diagram, and invariant 17 (180s is
> the single short/long boundary). Remaining opens are the four listed at the
> bottom — all implementation-adjacent, none blocking.

`detect_pipeline` (`src/utils/validators.py:89`) routes only four video URL
shapes today: `_match_short` (`validators.py:146`) matches
`youtube.com/shorts/`, `instagram.com/reel/`, `tiktok.com/@u/video/id`,
`vt.tiktok.com/*`; `_match_long` (`validators.py:164`) matches
`youtube.com/watch?v=` and `youtu.be/*`. Everything else is `rejected`.

**The pipelines are already platform-agnostic — only the front door isn't.**
Verified 2026-08-01:

- `long_video.py` has **zero** YouTube-specific code — it calls
  `transcript_svc.fetch_transcript(url)` / `fetch_metadata(url)` (`long_video.py:35-38`),
  the same generic sidecar the short pipeline uses.
- `transcript_server.py`'s `_generic_transcript` (`:254`) is explicitly written
  for "Non-YouTube (TikTok, Instagram Reels, …)" — yt-dlp captions, then audio
  fallback. YouTube is the special case (`_youtube_transcript`, `:231`, prefers
  `YouTubeTranscriptApi`), not the other way round.
- Residual platform coupling is cosmetic and lives in two spots:
  `_should_persist_thumbnail` (`short_video.py:205`, substring-matches
  `instagram`/`tiktok`) and `_detect_platform` (`transcript_server.py:344`,
  returns `"unknown"` for anything not Youtube/TikTok/Instagram).

**Resolved 2026-08-01 (grill)**

- ~~Widen the curated regex list, or replace it with a runtime "ask yt-dlp"
  check?~~ → **Widen the curated list.** `detect_pipeline` stays a pure,
  offline, synchronous classifier — it is called inside
  `create_and_enqueue_job` (ADR-0033) before a job row exists, so a network
  call there would put yt-dlp latency and failure modes on the intake path.
  More decisive: **yt-dlp cannot answer "is this supported?" reliably.** Its
  own FAQ (context7 `/yt-dlp/yt-dlp`, 2026-08-01) states detection is only
  possible by *attempting* extraction, because the **generic extractor**
  matches almost any URL as a fallback (scraping embedded video / OG tags), and
  disabling it (`--ies default,-generic`) is discouraged. An offline
  `InfoExtractor.suitable(url)` scan over `gen_extractor_classes()` does exist
  and is network-free, but inherits the same generic-extractor false-positive
  problem — it would classify ordinary article pages with an embedded video as
  `short`/`long`. This matches the precedent already recorded in CONTEXT.md
  invariant 10: the article pipeline has an allowlist *because* "is this an
  article?" is fuzzy across thousands of hosts; the repo pipeline has none
  because `github.com` has no fuzziness. Video-host detection has the article
  pipeline's fuzziness, so it gets the article pipeline's answer.
- ~~Which domains land in batch 1, and does each need a clean short-vs-long path
  signal?~~ → **No per-platform short/long guessing at all.** The
  duration check (below) is **folded into batch 1**, which makes the
  "unambiguous path signal" bar obsolete for new hosts. An earlier draft of this
  brief proposed Twitch clips + Facebook Reels → `short` and Vimeo → `long` on
  path shape alone; that was **rejected in-grill as wrong, not merely
  conservative**. "Vimeo is always long" is a UI fact (Vimeo ships no Shorts
  product), not a duration fact — Vimeo hosts 20-second clips routinely. Same
  hole on Twitch: `twitch.tv/<ch>/clip/<slug>` is capped, but
  `twitch.tv/videos/<id>` VODs run for hours. Guessing from the path would
  misroute long content into the Vision-frame pipeline.
- **Batch 1 shape:** `detect_pipeline` gains **one new host set** —
  `facebook.com` and `x.com`/`twitter.com` (Vimeo and Twitch dropped, see the
  probe results below) — returning a single
  length-unknown content_type. `_match_short` / `_match_long`
  (`validators.py:146,164`) are **not touched**: YouTube's `/shorts/` vs
  `/watch` stays a hardcoded regex because there the path signal is a genuine
  product distinction, and those content_types already carry dedup/FSM history.
  X/Twitter and Facebook Watch — deferred in the earlier draft for lack of a
  path signal — come back in scope for free, since nothing now depends on one.
- ~~What is the length-unknown content_type called?~~ → **`unsized`.** Not
  `"video"`: the queue envelope's *task discriminator* is already `"video"`
  (`worker.py:210`), so `{"task": "video"}` carrying `content_type="video"`
  reads as a tautology in logs and in the CONTEXT.md glossary. `unsized` names
  the actual property (length not yet known) rather than the medium.
- ~~Is `unsized` persisted, or transient?~~ → **Transient — the worker rewrites
  the row.** On resolution, `UPDATE jobs SET content_type = 'short'|'long'`
  before dispatch. Three reasons, all existing behavior rather than
  speculation: (a) the Feed badge renders raw content_type — `labelFor` in
  `web/components/ui/platform-icon.tsx:76` falls back to
  `return contentType || 'Source'`, so a row left at `unsized` shows a card
  badge literally reading **"unsized"** (`job-card.tsx:43` and the grid card);
  rewriting means **zero `web/` changes**. (b) `unsized` never becomes a fifth
  persistent content_type alongside `short`/`long`/`article`/`repo` — the job
  FSM and glossary stay as they are. (c) Reruns work for free: `/force <url>`
  resets the row in place and re-enqueues, and an already-rewritten row re-runs
  as `short`/`long` with no second `/metadata` call. Rejected alternative:
  keeping `unsized` as an audit trail of "length was unknown at intake" —
  recoverable from `jobs.url` + the host set anyway, so it buys nothing.

- ~~Do the two cosmetic platform couplings ship in batch 1?~~ → **Yes.** The
  `unsized` shape made this worse, not better: under the earlier path-regex
  plan only Twitch/FB Reels would have hit it, but now **any** of the four new
  hosts can resolve to `short`, so Vimeo and X clips reach `short_video.run`
  too. That path calls `_persist_best_frame_thumbnail` (`short_video.py:211`),
  which no-ops unless `_should_persist_thumbnail` (`:205`) sees `instagram` or
  `tiktok` in the platform string — and that string comes from
  `_detect_platform` (`transcript_server.py:344`), which returns the constant
  `"unknown"` for every extractor that is not Youtube/TikTok/Instagram. Left
  alone, every new host renders a Feed card with **no thumbnail and a badge
  reading "unknown"** while every existing short has an image — a visible
  regression against DESIGN.md's Feed, not deferrable polish. Fix, ~4 lines
  across two files: `_detect_platform` returns `extractor.lower()` for
  unrecognized extractors (yt-dlp already supplies `extractor_key` —
  `Twitch`, `Vimeo`, `FacebookReel` — and the code already reads it at
  `transcript_server.py:451`), and `_should_persist_thumbnail` keeps its
  **allowlist**, extended from two entries to four — `instagram`, `tiktok`,
  plus `facebook`, `twitter`/`x`.
- ~~Allowlist or denylist for `_should_persist_thumbnail`?~~ → **Explicit
  allowlist.** A denylist ("persist for everything except YouTube") was
  proposed first, because it means a future host needs no edit here at all.
  Rejected on the failure asymmetry: thumbnails are not URLs, they are **image
  bytes written into SQLite** (`job_thumbnails.bytes` is a BLOB,
  `database.py:101`). An allowlist fails **visibly and cheaply** — a blank
  card, nothing written. A denylist fails **invisibly and expensively** — every
  future host silently writes frame bytes into the DB, including hosts whose
  extracted frame is a black frame, a "video unavailable" placeholder or an
  age-gate interstitial, and nobody finds out until the table is large. Since
  hosts are added deliberately anyway (that is the whole point of decision 1 in
  ADR-0045 — classification is a human decision, not an automatic one), the
  one-line-per-host cost is already being paid next door in `detect_pipeline`.
  Keeping both lists explicit also keeps them reviewable side by side.

**Design note — the duration check (folded into batch 1)**

Routing a host whose URL shape does not reveal length needs the video's actual
duration, which is only knowable after a network call — so it cannot live in
`detect_pipeline`.

- **The data is already fetched, just discarded.** `GET /metadata`
  (`transcript_server.py:296`) already runs
  `yt_dlp.extract_info(url, download=False)` (`:318`) and yt-dlp already
  populates `duration` in that `info` dict — the endpoint's response
  (`:322-330`) simply doesn't include it. Exposing it is a one-line change plus
  the matching key in the error-path schema (`:332-341`) so callers see a
  consistent shape.
- **The boundary already exists and is not a new invention.** `/frames`
  (`transcript_server.py:440-446`) hard-rejects `duration > 180` with
  `"Video duration {duration}s exceeds 180s limit"`. The short pipeline
  therefore *already* cannot process anything over 3 minutes — 180s is the
  system's de facto short/long line, and the resolver must reuse that constant
  rather than pick a second one.
- **Where the branch goes:** `_handle_video` (`src/worker.py:79-87`) already
  branches on `content_type` with an `else` that logs `unknown_content_type` —
  a third branch slots in there: call `/metadata`, rewrite `content_type` on
  the 180s boundary, then dispatch to `short_video.run` / `long_video.run`.
  This keeps intake offline and synchronous and puts the network call where
  network calls already live.
- **Cost:** one extra `extract_info` round-trip per unsized job. The short
  pipeline's `/frames` call re-extracts anyway, so on the short branch this is a
  duplicate — acceptable (`ponytail:` note the ceiling; cache the `info` dict in
  Redis keyed by URL for the life of the job if it ever matters).
- ~~**Failure mode**~~ → **Default to `short`, log loudly.** `/metadata` returns
  `200` with an `error` key and empty fields rather than a non-2xx
  (`:331-341`), so a failed lookup yields no number. On a missing/zero
  `duration`, resolve to `short` and emit an explicit structured log line
  naming the URL, the host, and the sidecar's `error` string — the log, not the
  user-facing message, is what identifies the real cause. Rationale: `unsized`
  hosts are new and low-volume, so a wrong guess is cheap, and `short` is the
  cheaper pipeline; `/frames` (`transcript_server.py:440`) still bounds the
  damage by rejecting anything over 180s. Known wart to accept knowingly: when
  the metadata failure was a cookie-gated or geo-blocked host, the user sees
  `/frames`' "exceeds 180s limit" message, which points at the wrong cause —
  the log is the disambiguator. Rejected: failing the job outright (honest
  message, but a hard failure is a poor first impression on a
  freshly-supported platform), and defaulting to `long` (runs a full transcript
  fetch on what may be a 15-second clip).

**Open questions** (continue grill)

- **`/metadata` failure mode** — see the design note above; nothing resolved yet.
**Probe results — 2026-08-01 (run before shipping, per the gate below)**

Decision: **hosts are gated on a live cookie-less reachability probe; only
hosts returning a real `duration` ship.** Rationale — `_with_cookies`
(`transcript_server.py:124`) is applied in exactly one place,
`_download_audio_b64` (`:192`). It is **not** applied to `/metadata`
(`:303-317`) or `_fetch_vtt_text` (`:213-222`), so the `unsized` resolver runs
on the sidecar's one cookie-less path. An auth-gated host therefore fails at
resolve, falls to default-`short`, and fails again in `/frames` — the user sees
"exceeds 180s limit" for a URL that was never reachable.

The probe mirrors `/metadata`'s opts exactly, so a PASS means the resolver gets a
real number in prod. Re-run it whenever a host is added or `yt-dlp` is upgraded:

```python
import yt_dlp  # no cookies — /metadata doesn't use them
with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
    info = ydl.extract_info(url, download=False) or {}
print(info.get("extractor_key"), info.get("duration"))  # duration is a float
```

To test a host's **auth layer** without a valid URL, pass a deliberately
nonexistent id (`x.com/i/status/1`): a "does not exist"/"no video found" reply
proves the request reached the content API, a 401/login-required proves it did
not.

| Host | Verdict | Detail |
|---|---|---|
| YouTube (control) | **PASS** | `extractor=Youtube duration=213s -> long` — confirms network + harness sound |
| Vimeo | **FAIL (terminal)** | `Failed to fetch macos OAuth token: HTTP Error 401` on **three** different URLs, on both yt-dlp 2026.03.17 and 2026.07.04. Direct query of the token endpoint returns `{"developer_message": "The request includes an unauthorized client.", "error_code": 8001}` — Vimeo rejecting the credentials themselves, not a rate limit/IP/geo block. Fires before any video is looked at, so **no Vimeo URL can work**. |
| **Facebook** | **PASS** | real URL (`/share/v/1ESoxBa1H2`) → `extractor=Facebook duration=19.201s -> short` |
| **X / Twitter** | **PASS** | real URL (`x.com/tailwindcss/status/…`) → `extractor=Twitter duration=30.583s -> short` |
| Twitch | **dropped** | auth layer passed (`Video 1 does not exist`), but deemed not relevant to Ownix's content 2026-08-01 |

Auth-layer screening used deliberately **nonexistent IDs**
(`twitch.tv/videos/1`, `x.com/i/status/1`, `facebook.com/reel/1`) to test
reachability without valid URLs: a "does not exist" reply proves the request
reached the content API, whereas a 401/login-required proves it did not. Both
survivors were then confirmed end to end with real URLs.

**Final batch 1 host set: `facebook.com` + `x.com`/`twitter.com`.**

Two findings from the real-URL run:

- **The Facebook URL was a `/share/v/<id>` link**, not `/reel/` or `/watch/` — a
  third FB shape nobody anticipated. It resolved only because matching is on
  **host**, not path; the rejected Q2 path-regex plan would have rejected this
  exact URL. Independent confirmation that the host-set decision was correct.
- **`duration` is a float** (`19.201`, `30.583`), not an int. `duration > 180`
  is unaffected and `/frames` already compares the same float, but the resolver
  must not assume `int`.

**This killed the host the grill was most confident about, and spared the two it
doubted.** The earlier path-regex draft rated Vimeo the safest of the four ("no
Shorts product, always long") and flagged Facebook/X as the doubtful pair.
Vimeo is the only one confirmed non-working; X reached the API fine.

**Why Vimeo is structurally different** (from `yt_dlp/extractor/vimeo.py`, read
2026-08-01 — this is the part a future reader would otherwise re-derive):
yt-dlp does not scrape Vimeo's site, it **impersonates Vimeo's native apps**.
`_CLIENT_CONFIGS` (`vimeo.py:58-115`) holds four profiles — `android`, `ios`,
`macos`, `web` — each carrying a hardcoded `AUTH` (base64
`client_id:client_secret` lifted from the real app binaries) plus a matching
fake User-Agent. `android`/`ios` are `CACHE_ONLY: True` (usable only with a
previously cached token — never true in a fresh container), and `web` is
`REQUIRES_AUTH: True` (needs a real logged-in Vimeo account). That leaves
`macos` as the only profile able to mint a token anonymously
(`_DEFAULT_CLIENT = 'macos'`, `:52`), so every cold extraction POSTs
`grant_type=client_credentials` to `api.vimeo.com/oauth/authorize/client` with
those baked-in macOS credentials (`:386-395`) — **which Vimeo has revoked**.
Consequences: (a) it is not "Vimeo requires login", it is a vendor killing a
leaked app secret, a cat-and-mouse cycle nobody can schedule; (b) **cookies are
not the fix** — the cookie path selects the `web` client
(`_DEFAULT_AUTHED_CLIENT = 'web'`, `:53`), which needs an owned Vimeo account
kept alive in the sidecar, a much heavier lift than Instagram's; (c) upgrading
does not help, since 2026.07.04 ships the same revoked secret. By contrast
Twitch uses a **public** client-id (`twitch.py:58`) with nothing to revoke, and
X uses an official guest-token path (`twitter.py:104`) rather than impersonation
— which is exactly why those two passed.

**Related finding — `yt-dlp` is unpinned.** `Dockerfile.transcript:7` runs
`pip install --no-cache-dir flask waitress youtube-transcript-api yt-dlp Pillow`
with no version constraint, so the deployed version is frozen at whenever the
transcript image was last built and site support silently rots between rebuilds.
"Which hosts work" is a function of a version nobody currently controls or
observes. Not this task's problem to fix, but it bounds every claim this task
makes — worth its own Inbox entry.

- Does Facebook (and Twitch/X) need cookies the way Instagram does
  (`_with_cookies`, `transcript_server.py:124`)? If FB/X needs an authenticated
  session, those hosts may not be as free as their URL shape suggests — and
  unlike the old path-regex plan, a cookie-gated host now fails at the
  `/metadata` resolve step, which is the failure mode above.
- Help/rejection copy sweep: `webhook.py:1500` advertises the supported list to
  users and would go stale.
- Does `GENERIC_ROOTS` (`validators.py:226`) need the new hosts? It filters
  social links out of YouTube descriptions — `twitch.tv`/`vimeo.com` appearing
  there is plausible.

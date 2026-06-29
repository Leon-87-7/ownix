# vig — Feature ideation & task briefs

Canonical home for feature ideas, from one-line spark to grill-ready brief.

**How this file works**

1. **Dump** raw one-line ideas under `## Inbox` below — no structure needed.
2. Run **`/pre-grill`** — it grounds each one-liner in the real code, fattens it
   into a technical brief (Context · Wanted · Scope · Open questions), moves it
   into `## Briefs`, and clears it from the Inbox.
3. **Grill** the briefed tasks (`/grill-with-docs`, `/grill-with-search-docs`,
   or `/grilling`) to resolve the Open questions, then `/to-issue-kanban`.

Status markers on a brief: `✅ DONE` · `✅ ISSUED #NNN`. `/pre-grill` never
touches a marked task.

---

## Inbox

_Raw one-line ideas go here. `/pre-grill` consumes them._

<!-- - e.g. the feed should have a saved-filters dropdown -->

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

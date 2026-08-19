# Codex prompt — implement issue #540 (Spaces redesign: preview cards, icon-aware detail page, merged add-search)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. GitHub issue #540 (`gh issue view 540 --repo Leon-87-7/ownix`) — the full
   spec: Problem Statement, Solution, User Stories, Implementation Decisions,
   Testing Decisions, Out of Scope. Its acceptance criteria (the 20 user
   stories) are the definition of done. **This document adds the concrete
   `path:line` detail the issue deliberately omits — where the two disagree
   on a line number or exact code shape, trust this document (re-verified
   against the tree at the time this was written), but trust the issue for
   *intent* and scope.**
2. `CLAUDE.md` (repo root) — Component layout (`ui/` = shared primitives,
   `spaces/` = feature folder, kebab-case files, colocated `.test.tsx`, no
   barrel `index.ts`), and the exact test/lint commands.
3. `web/CLAUDE.md` — design context pointers (`DESIGN.md`, `PRODUCT.md`,
   `agent-knowledge/skills/impeccable/SKILL.md`) — read `DESIGN.md`'s Signal
   Rule and flat-by-default/reduced-motion bar before the UI slices (2, 4).
4. `CONTEXT.md` glossary entries **Markdown editor (dashboard)** and **Space
   export** — the Milkdown/Crepe rationale (slice 3) and how space content
   composes for export (unaffected by this batch, but explains why context
   blobs are ordered by `sort_order` — that ordering is what slice 4's
   preview-card join also relies on).
5. The specific files named in each slice below — line numbers are as of
   this writing (verified by direct read immediately before drafting this
   document); if they've drifted a line or two, find the symbol by name.

## Key decisions already made (do not relitigate)

- **`PageShell` has no `"wide"` option** — only `'default' | 'narrow'`
  (`web/components/shell/page-shell.tsx:18`, `'default'` = `max-w-5xl`,
  `'narrow'` = `max-w-3xl`). Job detail pages (`jobs/[id]/page.tsx:873,952`)
  use `width="narrow"` and **stay that way** — this batch does not touch
  them. Widening the space detail page means dropping its `width="narrow"`
  prop so it falls through to `'default'`. This deliberately makes the space
  detail page match **list-page** width, not job-detail-page width — spaces
  and jobs stop matching each other on this axis. Do not "fix" this by
  inventing a new width variant or by touching the jobs page.
- **No new backend endpoint for the merged search.** All three sources
  already exist: client-side Fuse.js job filter (`useFuseSearch`), `GET
  /api/brain/links?q=` (Links tab's endpoint), `GET /api/brain/search?q=`
  (Brain's semantic endpoint). The merge/dedupe/resolve logic is 100%
  frontend. Do not add a `jobs.embedding` column or a combined search route
  — issue #540's Out of Scope explicitly forbids this.
- **"Save & Add" reuses `POST /api/jobs`** (`src/api/jobs.py:218`,
  `create_job`) with just `{url}` (no `content_type`) — the same dashboard
  path a normal "paste a URL" submission uses, going through
  `_create_pipeline_job` → `detect_pipeline` → `create_and_enqueue_job`
  (ADR-0033). Do not call `_create_link_job` (that requires
  `content_type: "link"` and is for the "Ingest Link" no-processing flow,
  a different feature). Both response shapes include `"job_id"` (and `"id"`,
  same value) synchronously — read it off the response, do not poll for the
  job to reach `done`.
- **`database.get_space` and `database.list_spaces` already select `icon`**
  (`src/database.py:2536-2551`) — only the frontend `SpaceDetail` type is
  missing the field. Slice 1 is frontend-only; do not touch these queries
  for the icon (you will touch `list_spaces` in slice 4, for an unrelated
  reason — the blob-preview join).
- **`SpaceUpdateIn.icon` and `database.update_space` already accept and
  persist `icon`** (`src/api/spaces.py:43-46`, `src/database.py:2554-2565`)
  — slice 5 is frontend-only (hook state + form UI), no backend change.
- **Dedup key is the raw lowercased URL, nothing fancier.** No trailing-
  slash or query-string normalization. This is a deliberate, accepted
  ceiling (issue #540 Implementation Decisions), not something to improve.

## Work order

Slices are independent of each other except where noted; do them in this
order (cheapest/most-foundational first, riskiest last), but a partial
result (e.g. slices 1–5 done, 6 skipped) is still a valid, reviewable
delivery — do not block earlier slices on slice 6 being hard.

### 1. Detail-page `SpaceDetail` type gains `icon`

**Current state.** `web/lib/hooks/useSpaceDetail.ts:5-12` — `SpaceDetail`
lacks `icon` even though the API response already carries it (see Key
decisions).

**Fix.** Add `icon?: string;` to the `SpaceDetail` interface, matching
`SpaceSummary`'s `icon?: string` in `web/components/spaces/space-card.tsx:12`.

**Regression:** no runtime change — purely typing. Existing consumers of
`space.color`/`space.name` etc. are unaffected.

**Tests:** none needed for a type-only change; slice 2's tests cover the
consumer.

### 2. Detail-page icon, tab order/default, page width

**Current state**, all in `web/app/(dashboard)/spaces/[id]/page.tsx`:

- Line 25: `const [activeTab, setActiveTab] = useState<ActiveTab>("urls");`
- Line 63: `<PageShell width="narrow">`
- Line 71: `<span className="inline-block h-4 w-4 flex-shrink-0 rounded-full" style={{ backgroundColor: space.color }} />` — the flat dot.
- Lines 104-109:
  ```tsx
  <TabBar
    tabs={["urls", "context"] as const}
    active={activeTab}
    onChange={setActiveTab}
    labels={{ urls: "URLs", context: "Context" }}
  />
  ```

**Fix:**

- Line 25 → `useState<ActiveTab>("context")`.
- Line 63 → `<PageShell>` (drop the `width` prop entirely; see Key decisions).
- Line 71 → replace the flat `<span>` with the resolved icon component:
  import `spaceIcon` from `@/lib/space-icons` (the same resolver
  `web/components/spaces/space-card.tsx:6,20` already uses), render
  `const Icon = spaceIcon(space.icon);` then `<Icon className="h-5 w-5 flex-shrink-0" style={{ color: space.color }} aria-hidden="true" />` in place of the span. Keep it inside the same
  `flex items-center gap-3` row as the `<h1>` (lines 70-73).
- Lines 104-109 → swap tab order to `tabs={["context", "urls"] as const}`
  and `labels={{ context: "Context", urls: "URLs" }}`. `ActiveTab` (line 15,
  `type ActiveTab = "urls" | "context";`) needs no change — it's a union,
  order doesn't matter there.
- Line 111-112 (`{activeTab === "urls" && <UrlsTab .../>} {activeTab === "context" && <ContextTab .../>}`)
  — reorder the JSX to `context` first, `urls` second, matching the new tab
  order (cosmetic for behavior, but keep source order matching visual/tab
  order per repo convention — check a couple of other tabbed pages if
  unsure, don't invent a new convention).

**Regression:** Export/Edit/Delete buttons (lines 74-81), the edit form
(lines 83-102), and both tab bodies' own data-fetching are untouched —
only the *default* selected tab and *order* change, not their content.
`SpaceCard` on the list page already renders icon-in-color via a different
path (`space-card.tsx:83`, flat `text-ink`, not colored) — **do not**
change `SpaceCard`'s icon color in this slice; issue #540 only asks for the
*detail page* dot to become icon-in-color. (If you notice the inconsistency
— list card icon is `text-ink`, not tinted by `space.color` — leave it;
that's not in scope here.)

**Tests:** `web/app/(dashboard)/spaces/[id]/page.test.tsx` (existing file)
— assert: default `activeTab` renders `ContextTab` content, not `UrlsTab`;
clicking the "URLs" tab switches; the header renders the space's icon
(mock `useSpaceDetail` to return a space with a known `icon` value and
assert the corresponding Lucide icon renders, e.g. by test id or the
resolved component, not a raw `<span>` with a `backgroundColor` style).

### 3. Milkdown mobile padding

**Current state:**

- `web/components/ui/markdown-editor.tsx:77` —
  `<div className="rounded-lg border border-line bg-surface p-4">` (the
  outer wrapper around the "Notes" label + editor mount point). Fixed `p-4`,
  no responsive variant.
- `web/app/(dashboard)/spaces/[id]/ContextTab.tsx:11-15` — the `dynamic()`
  loading placeholder duplicates the same fixed classes:
  `className="rounded-lg border border-line bg-surface p-4 text-xs text-muted"`.

**Fix:** change both to a responsive padding scale, e.g. `p-2 sm:p-4`, so
they stay in sync (the placeholder should visually match the real editor's
padding at every breakpoint, or the loading→loaded swap jitters). If, after
this change, Crepe's own internal editor chrome (toolbar/content padding
inside `.milkdown-editor`, shipped via
`@milkdown/crepe/theme/common/style.css` + `frame-dark.css`, imported at
`markdown-editor.tsx:9-10`) still reads as oversized on a narrow viewport,
add a small scoped override in `web/app/globals.css` targeting `.milkdown-editor`'s
own padding at a mobile breakpoint — do not edit the imported package CSS
files, and do not remove/replace the Crepe theme imports.

**Regression:** desktop padding (`sm:` and up) is unchanged from today's
`p-4`. The editor's debounced save (`markdown-editor.tsx:46-53`, 800ms) and
StrictMode-safe teardown (`:67-71`) are untouched — this slice only touches
`className` strings.

**Tests:** none required for a pure padding/className change (trivial,
matches this repo's existing bar for what needs a test).

### 4. List-page preview cards

**Current state:**

- `src/database.py:2536-2542` —
  ```python
  async def list_spaces(chat_id: int) -> list[dict]:
      """Return all spaces for chat_id ordered newest-first."""
      return await _fetch_dicts(
          "SELECT id, chat_id, name, color, icon, created_at, updated_at "
          "FROM spaces WHERE chat_id = ? ORDER BY created_at DESC",
          (chat_id,),
      )
  ```
  No join to `context_blobs` (schema at `src/database.py:273-282`: `id,
  space_id, name, content, sort_order, created_at, updated_at`, indexed on
  `space_id`).
- `web/components/spaces/space-card.tsx:8-14` — `SpaceSummary` interface
  (`id, name, color, icon?, created_at`).
- `web/components/spaces/space-card.tsx:63-87` — the card body: a
  low-opacity color wash (`:66-70`), a delete button carve-out (`:71-78`),
  then the `<Link>` rendering `<Icon>` + `<span>{space.name}</span>`
  (`:79-85`).

**Fix — backend.** Extend the `list_spaces` query with a correlated
subquery pulling the first context blob per space (by `sort_order ASC`,
then `id` as a stable tiebreak if `sort_order` ties — mirror however
existing tiebreaks in this codebase handle equal sort_order, or just add
`, id` after `sort_order ASC` if none exists), returning that blob's
`name`, a truncated `content` (`SUBSTR(content, 1, 140)` — raw substring,
no markdown stripping, per issue #540), and its `updated_at`. Something
like:

```sql
SELECT s.id, s.chat_id, s.name, s.color, s.icon, s.created_at, s.updated_at,
       (SELECT name FROM context_blobs WHERE space_id = s.id ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_name,
       (SELECT SUBSTR(content, 1, 140) FROM context_blobs WHERE space_id = s.id ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_snippet,
       (SELECT updated_at FROM context_blobs WHERE space_id = s.id ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_updated_at
FROM spaces s WHERE s.chat_id = ? ORDER BY s.created_at DESC
```

Adapt to however `_fetch_dicts` expects the query (check its signature —
it's used identically elsewhere in `database.py`, mirror an existing
multi-column caller rather than guessing the interface). In the API layer
(`src/api/spaces.py:91-94`, `list_spaces` endpoint — same name as the DB
function, don't confuse the two), shape the three `note_*` columns into a
nested object only when `note_name` is non-null: `{"first_note": {"name":
..., "snippet": ..., "updated_at": ...} }` merged into each space dict, or
omit `first_note` entirely when the space has zero blobs. Keep the flat
`note_*` columns internal to the DB layer; the API/frontend contract is the
nested `first_note` shape (matches issue #540's stated frontend type).

**Fix — frontend.** `SpaceSummary` (`space-card.tsx:8-14`) gains
`first_note?: { name: string; snippet: string; updated_at: string };`.
`SpaceCard` renders the preview when `first_note` is present — title =
`first_note.name`, body = `first_note.snippet` (already truncated
server-side, so just render it; add a trailing `…` in the component if the
snippet was truncated — the backend doesn't know if it truncated mid-word
without an extra length check, so either have the SQL return
`LENGTH(content) > 140` as a fourth column to gate the ellipsis, or do the
"was this truncated" check client-side by comparing snippet length to 140
minus a small margin; pick whichever is less code and say which you picked
in your summary), and a small "Updated `<relative or short date>`" line
using `first_note.updated_at` (check if the repo has an existing date-
formatting helper — `web/components/ui/date-time.tsx` is listed in
`CLAUDE.md`'s component-layout as a `ui/` primitive — reuse it, don't add a
new date formatter). When `first_note` is absent, render exactly what
`SpaceCard` renders today (icon + name tile, `:83-84`) — this is the
fallback path, not a separate component.

**Regression:** the card's click target (whole tile `<Link
href="/spaces/${space.id}">`, `:79-81`) and the delete button's `z-10`
carve-out (`:71-78`) are unchanged in both the preview and fallback
renders. The color wash (`:66-70`) still renders behind either variant.

**Tests:** `tests/test_spaces.py` (existing file, `FastAPI TestClient` +
`FakeRedis` pattern already in use) — extend for `list_spaces`: a space
with one blob returns `first_note` with the right fields; a space with
multiple blobs returns the one with the lowest `sort_order`; a space with
zero blobs has no `first_note` key (or it's `null` — pick one, be
consistent, and match whatever `get_space`/other optional-field endpoints
in this file already do for "field absent" vs `null`). Frontend: a new
`web/components/spaces/space-card.test.tsx` if one doesn't already exist
(check first) — render with and without `first_note`, assert the preview
vs. fallback markup, assert the click target and delete button are present
in both.

### 5. Edit Collection icon picker

**Current state:**

- `web/lib/hooks/useSpaceEdit.ts:12-13,19-21,25,43` — tracks `editName`/
  `editColor` only; the `PUT` body at line 43 is
  `JSON.stringify({ name: editName.trim(), color: editColor })`.
- `web/app/(dashboard)/spaces/page.tsx:83-111` — the Create form's inline
  icon grid: iterates `SPACE_ICONS` (`web/lib/space-icons.ts:11-32`),
  renders an 8x8 button per icon, `aria-pressed` on the active one, using
  `newIcon`/`setNewIcon` from `useCreateSpace`.
- `web/app/(dashboard)/spaces/[id]/page.tsx:83-102` — the Edit form (the
  `editing` branch), currently only Name + Color fields.

**Fix.** Extract the icon-grid JSX (`spaces/page.tsx:83-111`) into a small
shared component, e.g. `web/components/spaces/icon-picker.tsx`, taking
`value: string`, `onChange: (name: string) => void` (matching the
`newIcon`/`setNewIcon` and to-be-added `editIcon`/`setEditIcon` shapes) —
same markup, same `SPACE_ICONS` iteration, same `aria-pressed`/active
styling. Use it from both the Create form (`spaces/page.tsx`, replacing
`:83-111` with a call to the new component) and the Edit form.

- `useSpaceEdit.ts` — add `editIcon`/`setEditIcon` state, seeded from
  `space.icon` wherever `editName`/`editColor` are seeded (the `useEffect`
  at `:17-22` and `startEdit` at `:24-27`), and include `icon: editIcon` in
  the `PUT` body at line 43 (backend already accepts it — see Key
  decisions). Note `useSpaceEdit`'s `space: SpaceDetail | null` parameter
  now has `.icon` available after slice 1.
- `spaces/[id]/page.tsx` Edit form (`:83-102`) — add the icon picker
  between Name and Color (or wherever reads best next to the existing
  fields — match the Create form's field order for consistency), wired to
  `editIcon`/`setEditIcon` from the hook.

**Regression:** Create form behavior is unchanged (same component, same
props, just relocated) — if you break `newIcon`/`setNewIcon` wiring while
extracting, the Create form's icon selection silently stops working; test
for it explicitly (see below). Saving Name/Color without touching the icon
must leave the space's existing icon untouched (the backend's `COALESCE`
only applies when `icon` is omitted from the body — since the frontend now
always sends `editIcon`, it will always be the currently-selected icon,
which starts as `space.icon`, so this is naturally correct as long as the
seeding effect actually runs before save).

**Tests:** `web/app/(dashboard)/spaces/page.test.tsx` (existing) — Create
form still selects an icon correctly via the extracted component.
`web/app/(dashboard)/spaces/[id]/page.test.tsx` (existing) — Edit form
shows the icon picker seeded to the space's current icon, selecting a
different one and saving includes it in the `PUT` body. New
`web/components/spaces/icon-picker.test.tsx` for the extracted component
in isolation (renders all `SPACE_ICONS`, `aria-pressed` on the active one,
`onChange` fires with the clicked icon's name) — colocated per repo
convention.

### 6. Merged add-search in `UrlsTab`

**Current state**, `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx`:

- Lines 12-17: `useSpaceUrls(spaceId)` returns `spaceUrls, allJobs, loading,
  addJob, removeUrl, reorderUrl`; `allJobs` filtered by `pinnedIds` into
  `availableJobs`.
- Lines 73-93: the `<select>` of `availableJobs` + "Add" button, calling
  `handleAddJob` → `addJob(selectedJobId)`.
- `web/lib/hooks/useSpaceUrls.ts:32-38` — `fetchAllJobs` hits `GET
  /api/jobs?limit=50` uncached, unfiltered.
- `web/lib/hooks/useFuseSearch.ts:7-21` — `useFuseSearch(jobs)`: `new
  Fuse(jobs, { keys: ['title', 'url'], threshold: 0.4 })`, returns
  `{query, setQuery, displayedJobs}`.
- `web/lib/hooks/useLinksTable.ts:149-183` (the fetch effect) — the pattern
  for hitting `GET /api/brain/links?limit=&offset=&order=&q=` with a 250ms
  debounce on `query` (`:139-142`); response shape `{items: LinkRow[],
  limit, offset, total}`, `LinkRow` at `:14-24` (`id, url, title?, topic?,
  description?, seen_count, first_seen, last_seen?, tags?`) — no `job_id`.
- `web/lib/hooks/useSemanticSearch.ts:20-42` — the pattern for `GET
  /api/brain/search?q=`, response `BrainResult[]` (`:5-10`: `title, url,
  topic, score`) — no `job_id`.
- `src/api/jobs.py:218-225` (`create_job`) and `:135-139`
  (`JobCreateRequest`) — the "Save & Add" target (see Key decisions).

**Fix.** This is the one genuinely new piece of frontend logic in this
batch — write it as a small, independently-testable hook (e.g.
`useAddSearch(spaceId)` in `web/lib/hooks/`, following this repo's
one-hook-per-concern convention) rather than inlining it in the component,
so the merge/dedupe/resolve logic can be unit-tested without rendering:

- Fetch the job list via the existing `GET /api/jobs?limit=` call
  (`useSpaceUrls.ts:33`), but raise the limit well past 50 (e.g. `500`) —
  no backend change, the param already exists.
- On a debounced query (reuse the 250ms debounce pattern from
  `useLinksTable.ts:139-142`), fire all three lookups together: `Fuse`
  search over the raised-limit job list (reuse `useFuseSearch` as-is, don't
  fork its logic); `GET /api/brain/links?q=<query>`; `GET
  /api/brain/search?q=<query>`.
- Normalize each source's hits to one shape, e.g. `{ url: string; title:
  string; jobId?: string }` — Fuse hits already carry `id` (→ `jobId`) and
  `url`; Links/Brain hits carry only `url`/`title`, no `jobId`.
- Dedupe by `url.toLowerCase()` (exact match, no normalization — Key
  decisions). On a collision, the hit carrying a `jobId` wins.
- Resolve `jobId` for any hit that doesn't already have one by matching its
  `url` (lowercased) against the same raised-limit job list fetched above —
  client-side only, no backend join.
- Render as a **flat list** (no source grouping, no modal — issue #540 is
  explicit: variant "flat list + Save & Add" was the validated choice from
  the throwaway prototype). Replace the `<select>` + "Add" button
  (`UrlsTab.tsx:73-93`) with a single search `<input>` + the result list
  below it.
- A result with a resolved `jobId`: an "Add" button calling the existing
  `addJob(jobId)` (`UrlsTab.tsx` already imports this from `useSpaceUrls`).
- A result with no resolved `jobId`: a "Save & Add" button that calls
  `POST /api/jobs` with `{ url: result.url }` (no `content_type`), reads
  `job_id` off the response, then calls `addJob(job_id)`. **Handle the
  failure case explicitly** — `create_job` can 422 (`"Document URLs belong
  in the Doc Parser"` for a PDF URL, `"Unsupported URL"` for an
  undetectable pipeline) or 409 (a link/article/etc. URL that's already
  tracked under a different `content_type`, surfaced via `_create_link_job`'s
  same-URL-different-type guard doesn't apply here since you're not sending
  `content_type: "link"`, but `create_and_enqueue_job`'s own dedup can still
  return an existing job of a different type — read its response either
  way and use whatever `job_id`/`content_type` comes back rather than
  assuming success shape) — show an inline error on that row rather than a
  silent failure or a thrown exception.

**Regression:** `spaceUrls` (the pinned list, `UrlsTab.tsx:41-70`) and its
reorder/remove behavior are completely untouched — this slice only replaces
the "add new content" control at the bottom of the tab.

**Tests:** primarily unit-test the new `useAddSearch`-equivalent hook's
merge/dedupe/resolve logic directly (mock `fetch` for the three sources,
assert the merged/deduped/resolved output for cases: same URL from two
sources dedupes to the `jobId`-carrying one; a Links-only hit stays
unresolved; a Brain hit whose URL matches a loaded job resolves). Then
`web/app/(dashboard)/spaces/[id]/UrlsTab.test.tsx` (existing file, currently
mocks `useSpaceUrls` — extend the mocking approach to also mock the new
search hook, matching this file's existing `vi.mock` pattern) for the
component-level behavior: typing a query renders results; a resolved
result's "Add" calls `addJob`; an unresolved result's "Save & Add" calls
`fetch('/api/jobs', ...)` then `addJob` with the returned id; a 422/409
from the save call renders an inline error and does not call `addJob`.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Scope fence: touch only the files named in the six slices above (plus new
  files explicitly called for: `icon-picker.tsx`, the new search hook, and
  their colocated tests). Do not refactor `SpaceCard`'s existing icon-color
  handling, `ContextTab`'s blob CRUD, `useSpaceUrls`'s reorder/remove logic,
  or any other Spaces code not named above.
- Do not add a new npm dependency. `fuse.js` is already used
  (`useFuseSearch.ts:4`); no debounce library needed (`useLinksTable.ts`'s
  inline `setTimeout` pattern is the existing convention).
- Do not add a new backend endpoint, a new DB column beyond what slice 4
  names, or any embedding/vector infrastructure for `jobs` — issue #540's
  Out of Scope is explicit on this.
- Migrations: slice 4's SQL change is to an existing query, not a schema
  change (no new column, no new table) — no migration entry needed. If you
  find yourself wanting a schema change to make slice 4 easier, stop and
  say so in your summary instead of adding one — the correlated-subquery
  approach in issue #540 was a deliberate choice to avoid a migration.
- Commands (from `CLAUDE.md`), **never through the `rtk` hook** — see
  `.claude/rules/rtk-tests.md`:
  - `python -m pytest tests/test_spaces.py -q` (and the full
    `python -m pytest tests -q` before calling this done)
  - `ruff check src/`
  - from `web/`: `npm run test:run`, `npm run lint`, `npm run build`

## Deliverable

Uncommitted working-tree changes implementing all six slices of #540 (or as
many as land cleanly — a partial delivery that clearly states which
slice(s) were skipped and why is acceptable; slice 6 is the one most likely
to need a human follow-up call), with regression tests per slice matching
the Testing Decisions in issue #540, plus a short summary of what was done
per slice and anything that blocked you — especially any ambiguity in the
"was this snippet truncated" ellipsis logic (slice 4) or the `create_job`
error-shape handling (slice 6) that this document didn't pin down closely
enough.

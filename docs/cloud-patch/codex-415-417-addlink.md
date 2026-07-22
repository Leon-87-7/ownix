# Codex prompt — implement issues #415–#417 (Link pipeline: sixth content_type for direct-add URLs)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0039-link-pipeline-direct-add.md` — the accepted decision:
   `link` as a sixth `content_type` dispatched through the ordinary job
   machinery, the two explicit-only entry points, why `source_job` stays
   `NOT NULL`, and the consequences list (no Sheets/Drive export,
   content-type-agnostic dedup, `og_image_url` written at ingest time).
   Authoritative over any paraphrase below if the two disagree.
2. `CONTEXT.md` glossary entries: **Content type** (now six values), **URL
   deduplication** (content-type-agnostic caveat), **Link pipeline**,
   **Essential OG collection**. Use this vocabulary verbatim in code
   comments, log events, and UI copy.
3. `CLAUDE.md` (repo root) — layout, test/lint commands; never run pytest
   through the `rtk` hook (`.claude/rules/rtk-tests.md`).
4. The specific files each issue below touches — line numbers are given as
   of this writing but may have drifted a line or two; find the function by
   name if so.
5. GitHub issues #415, #416, #417 (`gh issue view <n> --repo Leon-87-7/ownix`)
   — each carries its own acceptance criteria; treat those as the
   definition of done per slice. **Exception:** #417's own body claims Feed
   parity with "short/long/article/repo/document" — that's stale, see the
   #417 section below for the correction found by re-reading the current
   Feed code.

## Key decisions already made (do not relitigate)

- `link` is a sixth `content_type`, dispatched through the existing job
  machinery (`create_and_enqueue_job` → worker `_TASK_HANDLERS` → a new
  `src/processors/link.py`) — not a fabricated job row, not a nullable
  `source_job`. This was the explicit tradeoff in ADR-0039's "Considered
  options" section; don't re-derive it.
- Exactly two entry points, both explicit, both bypass
  `validators.detect_pipeline` entirely: Telegram `/addlink <url>` and the
  dashboard's `U`-triggered "Add Link" modal. Neither infers content_type
  from the URL — a Reel/repo/video URL added this way becomes a plain
  `link` job.
- `link` jobs skip Sheets export and Drive export entirely — no
  `append_*_row`, no `_sheets_task`-style fire-and-forget. The
  `brain.ingest_links` Obsidian `.md` upload (already inside `ingest_links`)
  is the only durable artifact.
- `find_recent_job_by_url` (`src/database.py:1670`) itself is **not**
  changed — it stays content-type-agnostic by design. The burden is on both
  `link` entry points to inspect the returned row's `content_type` and
  branch to a **hard, explicit warning** instead of the soft "already
  processed" ack (`_reply_cached_job`, `src/telegram/webhook.py:760`) when
  it differs. Same content_type (`link` hit `link`) still gets the normal
  soft ack.
- `ingest_links`' `topic` argument for this pipeline is the flattened
  Essential OG tag string (e.g. `"og:title: … · og:type: … · og:site_name:
  … · twitter:card: …"`), not a Gemini-derived topic like every other
  caller passes.

## Work order

Implement in issue order — #416 and #417 both depend on #415's schema/API
surface existing first.

### #415 — link pipeline core + /addlink command

- `src/utils/og_image.py:15` — `extract_og_image_url` only extracts
  `og:image` from the parsed `<meta>` tags; the attr-parsing loop already
  walks every tag (`_META_TAG_RE`/`_ATTR_RE`), it just discards everything
  but `og:image`. Extend it (or add a sibling function) to also collect
  `og:title`, `og:description`, `og:site_name`, `og:type`, `twitter:card`,
  `twitter:site` in one pass over the same tags — don't re-parse the
  document per field.
- `src/brain.py:436` — `ingest_links(links, topic, source_job_id)`. The
  `INSERT INTO links` at `:483-494` has no `og_image_url` column; add an
  optional `og_image_url` key per `link` dict (default `None`) and write it
  at insert time (`links` table already has this column — `get_link_preview`
  at `:802` reads/writes it lazily today). Existing callers that don't pass
  it must keep working (`None` → same lazy-fetch-on-preview behavior as
  now).
- `src/database.py` — widen the `jobs.content_type` CHECK constraint to
  include `'link'`. Mirror the `_migrate_v16_v17` / `_V17_CREATE` /
  `_V17_COLS` convention (`:744-855`, "widen content_type CHECK to include
  'document' via selective column copy") — SQLite can't `ALTER` a `CHECK`,
  so it's a full-table rebuild via a versioned `_V<N>_CREATE` DDL string +
  column list + `_rebuild_jobs_table`, appended as the next `_MIGRATIONS`
  entry. Also update the live `SCHEMA_SQL` CHECK (the one used for fresh
  installs, currently `CHECK(content_type IN ('short', 'long', 'article',
  'repo', 'document'))` near `:960`) to match.
- `src/worker.py:196-205` — `_TASK_HANDLERS` dict maps discriminators to
  handlers (`"document": _handle_document`, etc). Add `"link":
  _handle_link`, modeled on `_handle_document` (`:120-131`, simplest
  existing handler — no transcript, no template chain): load the job, call
  `processors.link.run(job)` in a try/except that sets `status="error"` and
  notifies on failure.
- New `src/processors/link.py`: fetch the page (`fetch_public_html`, same
  as `og_image.py`/`brain.py` already use), extract the essential OG
  collection, mark the job `done` via `database.update_job_status` (FSM:
  `pending → processing → done`, no intermediate states — set `processing`
  first like every other processor does at the top of `run()`), then call
  `brain.ingest_links` with a **real** `source_job_id` (this job's own id)
  and `topic` = the flattened OG tag string. Unlike `article.py`'s
  fire-and-forget `asyncio.create_task(brain.ingest_links(...))`
  (`article.py:322-326`, guarded by `if settings.GOOGLE_DRIVE_FOLDER_BRAIN`)
  — for `link` jobs the ingest **is** the job's entire purpose, not a
  side-effect, so `await` it directly rather than fire-and-forget; note
  this deviation from the article.py pattern in a one-line comment so a
  future reader doesn't "fix" it back to fire-and-forget.
- `src/services/jobs.py:13-16` — `task_for_content_type` currently returns
  `content_type` unchanged for anything not `{"short", "long"}`, so `"link"`
  already dispatches to task `"link"` with zero changes needed here — just
  confirm this in a test rather than adding a branch.
- `src/api/jobs.py:491-495` — `detail_fields_for(content_type)` only
  branches `short` vs everything-else (`_DETAIL_FIELDS_COMMON +
  _DETAIL_FIELDS_LONG`). Decide whether `link` jobs need their own detail
  field set (they have no transcript/ai_* fields) or can reuse the "long"
  branch harmlessly (fields just come back `null`) — acceptance criteria
  only requires the job detail endpoint not error; prefer reusing the
  existing branch over adding a third one unless a field actually leaks
  something wrong.
- New `/addlink <url>` command: register `_cmd_addlink` in
  `src/telegram/webhook.py`'s `_SLASH_TABLE` (`:1072-1089`, e.g.
  `"\addlink": _cmd_addlink`). Model the body on `_cmd_force`
  (`:791-806`, the `find_recent_job_by_url` + branch-on-existing pattern)
  rather than `_cmd_freestyle`/`_cmd_download_md` (those call
  `detect_pipeline`, which `/addlink` must **not**):
  1. `url = ctx.parts[1]` (usage message if missing, same shape as
     `_cmd_force`/`_cmd_ignore`).
  2. `existing = await database.find_recent_job_by_url(ctx.chat_id, url)`.
  3. If `existing` and `existing["content_type"] != "link"`: send the hard
     warning (e.g. `⚠️ This URL already exists as a {content_type} job
     (job_xxxx) — no link entry was created.`) and **return** — do not
     enqueue.
  4. If `existing` and `existing["content_type"] == "link"`: normal soft
     ack via `_reply_cached_job`.
  5. Otherwise: `await create_and_enqueue_job(ctx.chat_id, url, "link",
     skip_cache=True)` (skip_cache since step 2 already made the dedup
     decision — don't let `create_and_enqueue_job`'s own cache check
     re-run and diverge from it) and reply with the received-ack, **plus**
     the explicit "not the detect-pipeline flow" warning (e.g. `/addlink`
     saves the link as-is; it does not process it.) every time, success or
     not.

Add regression tests: essential-OG extraction returns all seven fields from
a fixture HTML doc; `ingest_links` with `og_image_url` writes it at insert
time and a call without it leaves the lazy-fetch behavior unchanged;
`/addlink` end-to-end creates a `link` job with the right `topic`; `/addlink`
against a URL with an existing job of a different content_type produces the
hard warning and creates no new job; the CHECK-constraint migration accepts
`'link'` and rejects unknown values.

### #416 — Add Link modal (U shortcut) — blocked by #415

- `web/components/feed/submit-job.tsx` — `SubmitJobProvider` already owns
  three dialogs (Submit URL / Ingest Docs / Command launcher) and a single
  `keydown` listener (`:250-342`) with per-key branches, each guarded by
  `shouldIgnoreGlobalShortcut` (`:77-88`) and the `restricted` gate
  (`:207-217`). Keys currently bound: `n`, `d`, `l`, `c`, `/`, `*`,
  `cmd/ctrl+shift+k` — **`u` is free**, confirmed by reading the full
  handler. Add a fourth dialog (`addLinkOpen`/`setAddLinkOpen`, same
  `restricted`-gated `setOpen`-style wrapper as `docsOpen`) and a `u`
  branch identical in shape to the existing `d` branch (`:264-274`).
- The modal's form is simpler than `SubmitUrlForm` (`submit-url-form.tsx`)
  — just a URL input, no template picker — but should visually match it
  (same input classes, same `Dialog`/`DialogContent`/`DialogTitle` usage as
  every other dialog in this file). Submit copy must carry the same "not
  the `N` / pipeline-detection flow" warning as the Telegram side (mirror
  the wording decided for #415's `/addlink` reply).
- `src/api/jobs.py:132-179` — `POST /api/jobs` (`JobCreateRequest`,
  `create_job`) is **entirely** `detect_pipeline`-driven today: it has no
  `content_type` field, explicitly 422s on `pipeline == "document"`, and
  422s on anything outside `{short, long, article, repo}`. This needs a new
  branch, not a tweak to the existing one: add an optional
  `content_type: Literal["link"] | None = None` to `JobCreateRequest`, and
  when it's `"link"`, skip `detect_pipeline` entirely and call
  `create_and_enqueue_job(chat_id, url, "link", skip_cache=True)` directly
  — mirroring the `/addlink` dedup-branch logic from #415 (inspect
  `find_recent_job_by_url` first, return a distinct hard-warning response —
  not a plain 200 — when the existing job's content_type differs, so the
  modal can render the hard warning instead of treating it as a normal
  accepted submission).
- Existing `N` Submit URL dialog and its dedup/accept flow must keep
  working unchanged — this is strictly additive.

Add regression tests (colocated `.test.tsx`, matching `submit-job.tsx`'s
existing test conventions): `u` opens the Add Link modal and not the `N`
dialog; submitting posts `content_type: "link"`; a dedup hit against a
different content_type renders the hard warning and does not clear the
modal as if it succeeded.

### #417 — Feed content-type support for link jobs — blocked by #415

- **Correction to the issue's own wording:** re-reading
  `web/app/(dashboard)/feed/page.tsx:47-55`, `CONTENT_TYPE_FILTERS` /
  `CONTENT_TYPES` today only cover `short`/`long`/`article`/`repo` —
  `document` jobs have their own page (`/doc-parser`, per `CLAUDE.md`'s
  route list) and were never a Feed filter tab. The issue's "matching the
  existing short/long/article/repo/document treatment" is stale; the real
  target is the existing **four**-tab array plus one new `Link` entry, not
  five going on six.
- Add `{ label: 'Link', value: 'link' }` to `CONTENT_TYPE_FILTERS`
  (`:49-55`) and `'link'` to the `CONTENT_TYPES` set (`:47`) so
  `normalizeContentType` (`:70-72`) accepts it as a valid `?type=` value.
  `contentTypeCounts`/`by_content_type` (`src/api/jobs.py` stats endpoint,
  `:73-78`) is a dynamic `GROUP BY content_type` — no server-side enum to
  touch, the count chip will populate itself once `link` jobs exist.
- `web/components/ui/platform-icon.tsx` — `Platform` type union (`:10-17`)
  and `platformFromUrl` (`:37-55`) currently fall through to `'unknown'`
  for anything that isn't a recognized video/repo host, with `'article'`
  as the one content_type-driven special case (`:53`, `if (contentType ===
  'article') return 'article'`). A `link` job's URL is exactly as arbitrary
  as an article's — extend that same branch to also match `contentType ===
  'link'` (reusing the article treatment: host-favicon glyph, `labelFor`
  falls back to the hostname) rather than inventing a distinct icon,
  unless you have a concrete reason a shared glyph would be confusing next
  to real article rows (if so, a plain `Link2`-style glyph — already used
  elsewhere in this codebase, e.g. `submit-job.tsx`'s "Open Links" command
  — is the fallback).
- No regression to existing content-type filtering/rendering for the other
  five types — this is additive to the tab list and the icon branch only.

Add a regression test that the Feed's content-type filter accepts `?type=
link` and that `PlatformBadge`/`PlatformGlyph` render something other than
the raw `unknown` fallback for a `link` job.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- The `content_type` CHECK migration is exactly one new step, mirroring the
  `_migrate_v16_v17` convention — do not touch any closed/prior migration.
- Don't invent a shared abstraction across #415/#416/#417 beyond what
  ADR-0039 already specifies (e.g. don't factor a generic "direct-add
  pipeline" helper spanning Telegram and web — the two entry points share
  `create_and_enqueue_job`, nothing more).
- Don't touch Sheets/Drive export code paths for the other five pipelines.
- Run `python -m pytest tests -q` and `ruff check src/` per `CLAUDE.md` for
  #415 (never through the `rtk` hook — `.claude/rules/rtk-tests.md`); run
  `npm run test:run`, `npm run lint`, and `npm run build` from `web/` for
  #416/#417.
- Don't refactor unrelated code in a file opened for one of these slices
  (e.g. don't touch `submit-job.tsx`'s command-launcher group unless
  #416's own acceptance criteria calls for a "Add Link" command entry
  there).

## Deliverable

Uncommitted working-tree changes implementing #415–#417 in full, with
regression test coverage per issue's acceptance criteria, plus a short
summary of what was done per issue and anything that blocked you (e.g. if
the exact wording/status-code shape of the hard dedup-warning response
needs a human call to keep the Telegram and dashboard copy consistent).

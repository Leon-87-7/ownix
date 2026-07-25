# vig — Backend Glue-Layer Index

**Last Updated:** 2026-07-25

Covers `src/processors/`, `src/api/`, `src/auth/`, `src/telegram/`,
`src/main.py`, `src/worker.py` — the orchestration layer `FUNCTION_INDEX.md`
explicitly excluded. Cross-references that file by name for anything in
`src/services/`/`src/utils/` rather than repeating it (e.g.
`create_and_enqueue_job`, `drive.upload_file`, `sheets.append_*_row`,
`compose_space_export` are all documented there).

---

## Read this first — surprising findings

1. **`POST /api/jobs` is wired to the wrong function — confirmed live bug.**
   In `src/api/jobs.py`, the `@jobs_router.post("")` decorator (line 139) sits
   directly above the private helper `_create_link_job(chat_id: int, url: str)`,
   not above `create_job(request: Request, body: JobCreateRequest)` (line 206,
   undecorated, zero callers per CodeGraph). As written, FastAPI registers
   `_create_link_job` as the `POST /api/jobs` handler — it treats `chat_id`
   and `url` as required query params and never sees `JobCreateRequest`'s body
   or `request.state.user`, so short/long/article/repo job creation from the
   dashboard (the whole point of `create_job`/`_create_pipeline_job`) can't
   run as intended. No test file hits `POST /api/jobs` (checked
   `tests/test_jobs_api.py` and a repo-wide grep). **Not yet fixed** — flagged
   for a deliberate decision, not touched by this documentation pass.
2. **The "Freestyle" flow is one shared arming mechanism reused by five content
   types.** `chat_state` (`awaiting_freestyle` / `awaiting_intent`) is armed by
   three different entry points (`/freestyle <url>`, the `✍️ Freestyle` button,
   a template-callback) and resolved by one function, `_handle_awaiting_freestyle`,
   which then branches on `content_type` to decide which queue task to enqueue
   (video/repo/article/document/enrichment). Miss this and you'll think each
   pipeline has its own freestyle re-run path — they don't.
3. **`_handle_awaiting_intent` doubles as a URL-interrupt handler.** If a user
   texts a URL while a PRD-intent prompt is armed, it silently cancels the
   pending intent and routes the URL as a brand-new job instead of erroring —
   easy to miss when tracing "what happens if I send a link while `/spec` is
   waiting for text."
4. **Two independent "template" concepts share the word "template" in the same
   file.** `webhook.py`'s `_ALLOWED_TEMPLATE_CALLBACKS`/`_cmd_template` deal
   with built-in Gemini analysis templates (`PROMPT_TEMPLATES`), while
   `_handle_user_template_shortcut` (`-mytemplate <url>`) deals with a
   *different*, per-user DB-backed template table (`database.get_user_template_by_name`,
   also the CRUD surface in `src/api/templates.py`). They're deliberately kept
   separate (a user template can't collide with a built-in name — enforced in
   `templates.py`'s `create_template`) but the naming makes them easy to conflate.
5. **The ops bot and the main bot share one webhook module but two secrets and
   two dispatch tables.** `webhook.py` hosts both `POST /webhook` (main bot,
   `_CALLBACK_TABLE`/`_SLASH_TABLE`) and `POST /webhook/ops` (ops bot,
   `_handle_ops_callback`'s if/elif chain) — separate HMAC secrets
   (`TELEGRAM_WEBHOOK_SECRET` vs `OPS_WEBHOOK_SECRET`), separate admin gating
   (`ops_bot.can_admin`), no shared dispatch code beyond the file they live in.
6. **`resolve_thumbnail` (in `src/api/jobs.py`) is reused verbatim by the
   Restricted-preview API** (`src/api/preview.py`'s `_load_corpus`), which then
   rewrites any `/api/jobs/{id}/thumbnail` URL it returns into
   `/api/preview/jobs/{id}/thumbnail` — an ownership-gated route would 401 an
   anonymous preview visitor otherwise. Easy to miss that `preview.py` imports
   three helpers straight out of `jobs.py` rather than duplicating them.

---

## Short Video Pipeline

`src/processors/short_video.py` — Reels/TikTok/YouTube Shorts. Two phases: an
immediate Gemini-Vision analysis (frames → links → Drive), then an
always-runs transcript phase (audio/caption transcript → optional template
enrichment → transcript doc delivery).

#### `run(job: dict) -> None` — `src/processors/short_video.py`
**Does:** End-to-end short-video pipeline. 1) fetch extracted frames from the
transcript sidecar 2) Gemini Vision analysis of the frames (title/summary/links)
3) persist the best frame as a stored thumbnail for Instagram/TikTok jobs only
4) optional Brave Search link enrichment 5) upload an analysis markdown to Drive
6) mark the job `done` 7) send the best-frame photo + enriched links message to
Telegram 8) fire-and-forget Sheets logging + Brain link ingest, then unconditionally
runs the Phase-2 transcript phase (`_transcript_phase`) regardless of template.
**Called from:** `_handle_video` in `src/worker.py` (dispatched for `content_type == "short"`).
**Usage:** Enqueued as `{"task": "video", "job_id": ...}` for a short-pipeline job.

#### `_fetch_validated_frames(url, chat_id, tag) -> dict` — `src/processors/short_video.py`
**Does:** Calls the frame-extraction sidecar; on a `too_long`/other error or an
empty frame list, messages the user and raises so `run()` aborts cleanly.
**Called from:** `run`.

#### `_deliver_media(chat_id, tag, raw_frames, main_idx, summary, links) -> tuple[int|None, list[dict]]` — `src/processors/short_video.py`
**Does:** Sends the best frame as a photo, then (if links exist) enriches them
via GitHub metadata and sends a links message — that message's id wins as the
"anchor" `bot_message_id` used later for the `show_done` dedup button.
**Called from:** `run`.

#### `_should_persist_thumbnail(platform)` / `_persist_best_frame_thumbnail(job_id, platform, raw_frames, main_idx) -> None` — `src/processors/short_video.py`
**Does:** Persists the best Vision frame to the `thumbnails` table, but only for
Instagram/TikTok platforms (YouTube Shorts already has a stable `img.youtube.com`
thumbnail URL, so storing bytes would be wasted). Decode/save failures are
logged and swallowed, never fail the pipeline.
**Called from:** `run`.

#### `_acquire_transcript(job, url, chat_id, tag, title, template) -> tuple[str|None, dict|None, bool]` — `src/processors/short_video.py`
**Does:** Fetches a transcript from the sidecar; if the sidecar signals an audio
fallback, transcribes (or, when a template is set, does a *fused* Gemini call via
`enrichment.enrich_audio` that returns both transcript and template analysis in
one round trip) instead of two separate Gemini calls. Returns `wordless=True` for
a silent clip rather than raising.
**Called from:** `_transcript_phase`.

#### `_run_template_enrichment(job_id, chat_id, tag, title, template, template_analysis, transcript_text) -> object` — `src/processors/short_video.py`
**Does:** Caption-path template enrichment: if a template is set but no analysis
was produced by the (audio) fused call, runs `enrichment.enrich()` on the
caption-derived transcript, sends the formatted section, and persists it.
**Called from:** `_transcript_phase`.

#### `_deliver_transcript_doc(job, job_id, chat_id, platform, video_id, transcript_text) -> None` — `src/processors/short_video.py`
**Does:** Uploads the transcript markdown to Drive and sends it as a Telegram
document — always the last step, independently guarded so a Drive or Telegram
failure never rolls back the already-`done` job.
**Called from:** `_transcript_phase`.

#### `_transcript_phase(job, url, chat_id, tag, title, platform, video_id) -> None` — `src/processors/short_video.py`
**Does:** Orchestrates the Phase-2 sequence: acquire transcript → persist it
immediately (even if enrichment later fails) → run template enrichment → deliver
the transcript doc → offer the dashboard button row.
**Called from:** `run` (unconditionally, at the end).

---

## Long Video Pipeline

`src/processors/long_video.py` — YouTube long-form. Single phase that ends at
`transcript_done`; Gemini enrichment is a separate, chainable Phase-2 task.

#### `run(job: dict) -> None` — `src/processors/long_video.py`
**Does:** 1) fetch transcript + metadata in parallel (`asyncio.gather`) 2)
auto-detect a template from title/description when the job has none explicit
3) extract + enrich description links (never blocks the pipeline on failure)
4) build transcript markdown, upload to Drive 5) mark job `transcript_done`
6) send the transcript document, then (unless the job came from an explicit
slash command) a "Run Gemini analysis?" keyboard 7) fire-and-forget Sheets
logging + Brain ingest of description links.
**Called from:** `_handle_video` in `src/worker.py` (dispatched for `content_type == "long"`).
**Usage:** Enqueued as `{"task": "video", "job_id": ...}` for a long-pipeline job.

#### `detect_template(title, description) -> str` — `src/processors/long_video.py`
**Does:** Scores each built-in template's `trigger_patterns` against the
lowercased title+description and returns the highest scorer, or `"summary"`
if nothing matches. Pure text heuristic, no I/O.
**Called from:** `run` (only for jobs without an explicit template).

#### `_fetch_transcript_or_fail(job_id, chat_id, tag, url) -> tuple[dict, dict] | None` — `src/processors/long_video.py`
**Does:** Parallel-fetches transcript + metadata; on an empty transcript, marks
the job `error` and messages the user (auto-captions may be disabled), returning
`None` so `run()` bails out early.
**Called from:** `run`.

#### `_collect_description_links(description, job_id) -> list[dict]` — `src/processors/long_video.py`
**Does:** Extracts links from the video description and enriches GitHub ones;
any extraction exception is logged and swallowed (empty list), never blocks the pipeline.
**Called from:** `run`.

#### `_maybe_auto_enqueue_enrichment(job, job_id) -> None` — `src/worker.py`
**Does:** After a long-video Phase-1 run with an *explicit* template (not
auto-detected), immediately chains the Phase-2 `enrichment` task onto the queue
— unless the template is `freestyle` with no prompt yet (that path waits for
the user's freestyle reply instead). This is what makes `/technical <url>`
feel like one continuous pipeline instead of two separate steps.
**Called from:** `_handle_video` (only on the `content_type == "long"` branch, after `long_video.run`).

---

## Link Pipeline

`src/processors/link.py` — "Add Link" direct-to-Brain ingest, no Gemini call.

#### `run(job: dict) -> None` — `src/processors/link.py`
**Does:** 1) best-effort fetch the page's Open Graph tags (a failed fetch still
saves the link, per ADR-0039 — no tags, not an error) 2) opportunistically
backfill the job's `title`/`og_image_url` from OG tags 3) ingest exactly one
link into the Second Brain via `brain.ingest_links` 4) **verifies** the row
actually landed in the `links` table before marking the job `done` — unlike the
fire-and-forget Brain ingests elsewhere, this pipeline's whole purpose is the
Brain row, so a swallowed ingest failure is promoted back into a raised error
(and the worker's standard error path) instead of a silent `done`.
**Called from:** `_handle_link` (`_make_handler("link", ...)`) in `src/worker.py`.
**Usage:** Enqueued as `{"task": "link", "job_id": ...}`; created via `/addlink <url>` or the dashboard "Add Link" content_type.

---

## Article Pipeline

`src/processors/article.py` — Jina-fetched article → Gemini analysis, with a
markdown cache shared across re-runs.

#### `run(job: dict, *, skip_document: bool = False) -> None` — `src/processors/article.py`
**Does:** 1) markdown cache lookup, else fetch via Jina (`services/jina.fetch_markdown`)
and cache it 2) resolve `og:image` (only after a successful fetch, so a Jina
failure never pays for a discarded lookup) 3) heuristic paywall check (never
aborts, just adds a warning) 4) send the raw article as a Telegram document
(skippable via `skip_document`, used on freestyle re-runs) 5) build and send the
Gemini prompt (freestyle-aware) 6) persist `done` with topic/objective/action
points/tools 7) fire-and-forget Sheets write that **updates in place** on a
freestyle re-run instead of appending a duplicate row 8) send the enrichment
message + Freestyle button, then best-effort offer repo follow-ups 9)
fire-and-forget Brain ingest of just the article URL (not body links).
**Called from:** `_handle_article` (`_make_handler("article", ..., pass_skip_document=True)`) in `src/worker.py`; also directly re-enqueued by `_cb_article_retry` in `webhook.py` with `skip_document=True`.
**Usage:** Enqueued as `{"task": "article", "job_id": ..., "skip_document": bool}`.

---

## Document Pipeline

`src/processors/document.py` — PDF parse cache (content-addressed in GCS) +
Gemini enrichment. Mirrors `article.py`'s shape; shares the parse cache with
the Doc Parser dashboard API (`src/api/parsed.py`).

#### `run(job: dict, *, skip_document: bool = False) -> None` — `src/processors/document.py`
**Does:** 1) parse-cache lookup/populate via `_cached_parse` (shared by sha
across tenants — the parsed text isn't chat_id-owned even though the job row is)
2) Gemini structured-extraction call, plus a second Gemini call that produces a
full markdown summary uploaded to GCS as a document output 3) persist `done`
(no `promise_gap` — "documents don't pitch") 4) register both outputs
(`raw_txt`, `summary`) in `document_outputs` 5) fire-and-forget Sheets
index (update-in-place on freestyle re-run) 6) deliver via `_deliver`, unless
the job's `telegram_delivery` is `"off"` (dashboard-originated uploads default
to off; the user opts in per-job).
**Called from:** `_handle_document` (`_make_handler("document", ..., pass_skip_document=True)`) in `src/worker.py`.
**Usage:** Enqueued as `{"task": "document", "job_id": ...}`.

#### `_cached_parse(sha, ext, *, output_format="text") -> str` — `src/processors/document.py`
**Does:** Content-addressed parse cache: serves `parsed/<sha>.<ext>` from GCS if
present, else downloads the source PDF, parses via `services.parse.parse_pdf`,
and caches the result. Raises `ParseError` (never caches an empty parse — usually
a scanned/image-only PDF).
**Called from:** `run`, `deliver_markdown` (this file); `_generate_output` in `src/api/parsed.py`.

#### `deliver_markdown(job: dict) -> None` — `src/processors/document.py`
**Does:** On-demand: serves the cached/freshly-parsed `.md` rendering of a
document job as a Telegram document (the "📄 Get Markdown" button).
**Called from:** `_cb_document_md` in `src/telegram/webhook.py`.

#### `_deliver(job, text, tools, references) -> None` — `src/processors/document.py`
**Does:** Sends the raw parsed `.txt`, then the enrichment summary, then the
"Get Markdown"/"Freestyle" button row — each send independently `try/except`-guarded
so one delivery failure never rolls back the job's already-persisted `done` state.
**Called from:** `run` (when `telegram_delivery != "off"`).

---

## Enrichment (Phase 2 Gemini Analysis)

`src/processors/enrichment.py` — the Gemini analysis step shared by long-video
and (for template analysis) short-video jobs; also hosts the audio-path Gemini
helpers `short_video.py` reuses.

#### `run(job_id: str) -> None` — `src/processors/enrichment.py`
**Does:** Loads the job, marks `enriching`, warns on an explicit-command
template/content mismatch (`validate_template_choice`, from `FUNCTION_INDEX.md`),
calls `enrich()`, persists the result fields, sends the (possibly multi-chunk,
`_split_message`-aware) enrichment message, offers the dashboard row + repo
follow-ups.
**Called from:** `_handle_enrichment` in `src/worker.py`.
**Usage:** Enqueued as `{"task": "enrichment", "job_id": ...}` — either auto-chained after an explicit-template long video, or via the "✨ Run Gemini" button, `/spec`, or a retry callback.

#### `enrich(job: dict) -> tuple[Enrichment, dict | None, dict | None]` — `src/processors/enrichment.py`
**Does:** Builds the template-aware prompt from title+transcript and calls
Gemini with free→paid key fallback; raises `EnrichmentUnavailableError` if both
keys fail. Splits `template_analysis` and `promise_gap` out of the parsed JSON.
**Called from:** `run` (this file); `_run_template_enrichment` in `short_video.py` (caption-path template analysis).

#### `enrich_audio(job, audio_b64, mime_type) -> tuple[dict | None, str]` — `src/processors/enrichment.py`
**Does:** Fused Gemini call for the audio-fallback path: inline audio + template
prompt in one round trip, returning `(template_analysis, transcript_text)`
together — callers must not make a separate transcription call after this.
**Called from:** `_acquire_transcript` in `short_video.py` (audio fallback with a template set).

#### `transcribe_audio(audio_b64, mime_type, title="") -> str` — `src/processors/enrichment.py`
**Does:** Transcription-only Gemini call (no template) for the audio-fallback
path when no template is set; returns `""` for a silent/wordless clip rather than raising.
**Called from:** `_acquire_transcript` in `short_video.py` (audio fallback, no template).

#### `_format_template_analysis(template, analysis) -> str` — `src/processors/enrichment.py`
**Does:** Renders a template's structured analysis dict into a Telegram-ready
text block via one of `_TEMPLATE_FORMATTERS` (method/technical/review/narrative).
**Called from:** `_build_enrichment_message` (this file); `_run_template_enrichment` in `short_video.py` — the one formatting helper worth noting because it's genuinely cross-domain, not just intra-file.

---

## Mini-PRD

`src/processors/prd.py` — generates a "Mini-PRD" markdown doc from a long
video's transcript+enrichment, in two independently-locked "slots" (`auto` /
`intent`) so a fresh intent doesn't clobber an in-flight auto-generation.

#### `run_prd(job_id, *, slot, model, build_prompt) -> None` — `src/processors/prd.py`
**Does:** The unified pipeline both `run_auto` and `run_intent` funnel through,
parameterized by `slot` so all column names (`prd_{slot}_status` etc.) derive
from one string. Steps: a) fetch job b) atomically acquire the slot lock
(`_acquire_prd_lock`, no-op with a user notice on contention) c) build the
prompt d) call Gemini (free→paid fallback) e) parse JSON f) render markdown
g) Drive upload-or-update-in-place (keyed by a cached file id) h) non-fatal
Sheets append i) persist JSON + Drive ids, mark slot `done` j+k) fire-and-forget
Brain ingest of the PRD's tech-stack links, then Telegram delivery.
**Called from:** `run_auto`, `run_intent` (thin wrappers in this file).

#### `run_auto(job_id) -> None` / `run_intent(job_id) -> None` — `src/processors/prd.py`
**Does:** Thin entry points that call `run_prd` with `slot="auto"`/`slot="intent"`
and the appropriate prompt builder; `run_intent` additionally validates the job
has a transcript and a non-empty `prd_intent_text` before calling in.
**Called from:** `_handle_prd_auto`/`_handle_prd_intent` in `src/worker.py`.
**Usage:** Enqueued as `{"task": "prd_auto"|"prd_intent", "job_id": ...}` — from the "📐 Build Spec" button, `/spec`, or a retry callback.

#### `run_auto_resend(job_id) -> None` — `src/processors/prd.py`
**Does:** Re-delivers an already-generated `auto`-slot PRD **without** re-calling
Gemini — re-renders markdown from the cached `prd_auto_json`, updates the Drive
file in place, resends the Telegram document. Falls back to a full `run_auto`
regeneration if the cache is missing or unparseable.
**Called from:** `_handle_prd_auto_resend` in `src/worker.py`; also `_cb_prd_auto` in `webhook.py` enqueues the `prd_auto_resend` task directly when the slot is already `done`.

#### `_acquire_prd_lock(job_id, slot, lock_col, is_intent, chat_id) -> bool` — `src/processors/prd.py`
**Does:** Atomically flips `{lock_col}` to `'generating'` in one `UPDATE ... WHERE` —
the intent slot additionally enforces a cooldown window since the last
completion. Zero rows affected means contention; messages the user (intent only) and returns `False`.
**Called from:** `run_prd`.

#### `reaper() -> None` / `reaper_intent() -> None` — `src/processors/prd.py`
**Does:** Reset any slot stuck in `'generating'` for >10 minutes back to
`'error'` — recovers PRD generations orphaned by a worker crash.
**Called from:** `worker.loop()` startup sequence (once, before the dequeue loop starts).

---

## Repo Pipeline

`src/processors/repo.py` — GitHub repo → Gemini structured analysis + rendered
markdown doc.

#### `run(job: dict) -> None` — `src/processors/repo.py`
**Does:** 1) fetch the repo bundle (README, tree, manifests, metadata) via
`services.github.fetch_repo_bundle` — on failure, classifies the exception into
a user-facing message (`_classify_github_error`: rate limit / 404 / auth / generic)
and marks the job `error` 2) build the repo prompt (repo-size-aware tree
prioritization, `flags={"no_readme": ...}`) and call Gemini against
`REPO_ANALYSIS_SCHEMA` 3) persist `done` with tagline/action-points/tech-stack
4) send the rendered markdown as a document (non-fatal) 5) send the summary +
Freestyle button, prefixed with archived/no-README warnings 6) fire-and-forget
Sheets append-or-update (branches on whether `sheets_row_id` already exists —
i.e. a freestyle re-run) 7) fire-and-forget Brain ingest of the normalized repo URL.
**Called from:** `_handle_repo` (`_make_handler("repo", ...)`) in `src/worker.py`.
**Usage:** Enqueued as `{"task": "repo", "job_id": ...}` — from a GitHub URL, `/freestyle <repo-url>`, or a repo follow-up pick.

#### `_brain_ingest_safe` / `_sheets_append_safe` / `_sheets_update_safe` — `src/processors/repo.py`
**Does:** Exception-swallowing wrappers around the corresponding service calls
so a Brain/Sheets failure only logs a warning, never fails the (already-`done`)
job — the fire-and-forget pattern this whole layer uses, made explicit here as
named functions instead of inline `try/except`.
**Called from:** `run` (via `spawn_background`).

---

## Second Brain (dashboard API)

`src/api/brain.py` — the dashboard's read/search/tag surface over the single,
operator-wide Second Brain link graph (only `/links/view`, a display
preference, is per-user-scoped).

#### `search_links` / `get_graph` / `list_links` — `GET /api/brain/search`, `/graph`, `/links` — `src/api/brain.py`
**Does:** Thin route wrappers over `brain.search_links`/`brain.get_graph`/`brain.list_links`
(documented in `FUNCTION_INDEX.md`); `list_links` passes the caller's chat_id as
`viewer_chat_id` for tag-payload scoping even though the link inventory itself is shared.
**Entry point:** dashboard Brain page fetches.

#### `get_link_preview` / `get_link_preview_image` — `GET /api/brain/links/{id}/preview[/image]` — `src/api/brain.py`
**Does:** Returns a link's cached OG preview, or (for `/image`) proxies the
resolved OG image through our own origin via `fetch_public_image` — needed
because some hosts reject hotlinking from the browser directly.
**Entry point:** dashboard Brain link cards.

#### `get_link_tags` / `attach_link_tag` / `detach_link_tag` — `GET/POST/DELETE /api/brain/links/{id}/tags[/{tag_id}]` — `src/api/brain.py`
**Does:** Standard tag-attachment CRUD scoped to the caller's tags; `attach`
maps an FK violation (link doesn't exist) to a 404 rather than a 500.
**Entry point:** dashboard Brain link tag picker.

#### `get_links_view` / `update_links_view` — `GET/PUT /api/brain/links/view` — `src/api/brain.py`
**Does:** Per-user display preference (sort order, page size) — the one
per-user-scoped thing on this router.
**Entry point:** dashboard Brain page load / sort-order change.

#### `rebuild_graph()` — `POST /api/brain/rebuild` — `src/api/brain.py`
**Does:** Triggers `brain.rebuild_graph()`; maps a `RuntimeError` (already
rebuilding) to 409.
**Entry point:** dashboard "Rebuild Graph" button; same underlying job as `/rebuild-graph` in the Telegram bot (`_cmd_rebuild_graph`).

---

## Dashboard Jobs API

`src/api/jobs.py`, `src/api/deps.py` — job listing/stats/detail/annotations/tags
for the Feed and per-job pages, plus dashboard-submitted job creation.

#### `get_owned_job(job_id, request) -> dict` — `src/api/deps.py`
**Does:** Shared ownership guard: 404 if the job doesn't exist, 403 if it
belongs to a different chat_id. The one dependency both `jobs.py` and `parsed.py` build on.
**Called from:** Nearly every job-scoped route in `jobs.py` and `parsed.py` (`get_owned_document_job` wraps it with a content_type check).

#### `get_job_stats` — `GET /api/jobs/stats` — `src/api/jobs.py`
**Does:** Hero counts for the Feed: a status breakdown scoped to the active
content-type tab (if any), plus an always-global content-type breakdown so tab
count chips don't shift when a tab filter is applied.
**Entry point:** dashboard Feed page load.

#### `get_recovery_summary` / `retry_recovery_pending` / `retry_recovery_error` / `clear_recovery_failed` — `GET/POST /api/jobs/recovery/*` — `src/api/jobs.py`
**Does:** Thin wrappers over `services.job_recovery` (`FUNCTION_INDEX.md` territory)
that translate its `ValueError` into a 422.
**Entry point:** dashboard "stuck jobs" recovery panel.

#### `create_job(request, body) -> dict` — intended `POST /api/jobs` — `src/api/jobs.py`
**Does:** Dashboard job creation using the shared Telegram ingest core
(`create_and_enqueue_job`). Branches on `body.content_type == "link"` to
`_create_link_job` (Add-Link, no pipeline detection) vs `_create_pipeline_job`
(detects short/long/article/repo from the URL, rejects `document` — those
belong in the Doc Parser). **See finding #1 above — the route decorator is
misapplied to `_create_link_job`, so this function currently has zero real callers.**
**Called from:** (intended) `POST /api/jobs`; actually uncalled per CodeGraph, and no test exercises the route.

#### `resolve_thumbnail(job, stored_ids=None) -> tuple[str|None, ThumbnailKind|None]` — `src/api/jobs.py`
**Does:** Server-side thumbnail URL resolution per content type: article →
`og_image_url`, long/short YouTube → `img.youtube.com`, repo →
`opengraph.githubassets.com`, persistable short platforms (Instagram/TikTok) →
the stored-thumbnail route if one was saved. `stored_ids` lets a list endpoint
batch the "has a stored thumbnail" check instead of one query per row.
**Called from:** `list_jobs` (this file), `_load_corpus` in `src/api/preview.py` (see finding #6).

#### `list_jobs` — `GET /api/jobs` — `src/api/jobs.py`
**Does:** Paginated, content-type/status-filterable job list for the Feed;
batches thumbnail resolution after the main query via `get_thumbnail_job_ids`.
**Entry point:** dashboard Feed page.

#### `get_annotation` / `upsert_annotation` — `GET/PUT /api/jobs/{id}/annotations` — `src/api/jobs.py`
**Does:** Per-job free-text notes, ownership-gated via `get_owned_job`.
**Entry point:** dashboard job detail notes field.

#### `get_job_tags` / `attach_tag` / `detach_tag` — `GET/POST/DELETE /api/jobs/{id}/tags[/{tag_id}]` — `src/api/jobs.py`
**Does:** Job-tag CRUD, structurally identical to `brain.py`'s link-tag CRUD.
**Entry point:** dashboard job detail tag picker.

#### `get_adjacent_jobs` — `GET /api/jobs/{id}/adjacent` — `src/api/jobs.py`
**Does:** Chronological (not feed-order) prev/next job ids within the same
Feed-scope filter as `list_jobs` — shares `_job_scope_where` with it so
prev/next navigation can't drift from what's actually visible in the list.
**Entry point:** dashboard job detail page "Previous/Next" buttons.

#### `get_job` — `GET /api/jobs/{id}` — `src/api/jobs.py`
**Does:** Full job detail, field set chosen by `detail_fields_for(content_type)`
(short jobs get `summary`/`transcript`/`links`; everything else gets the
AI-enrichment field set).
**Entry point:** dashboard job detail page load.

---

## Spaces API

`src/api/spaces.py` — Spaces (user-curated collections) CRUD + pinned-URL
ordering + Context blobs + export.

#### `list_spaces` / `create_space` / `get_space` / `update_space` / `delete_space` — `GET/POST/PUT/DELETE /api/spaces[/{id}]` — `src/api/spaces.py`
**Does:** Standard ownership-gated CRUD via `_get_owned_space`; `create_space` maps a name-collision `IntegrityError` to 409.
**Entry point:** dashboard Spaces page.

#### `list_space_urls` / `add_space_url` / `remove_space_url` / `reorder_space_url` — `GET/POST/DELETE/PATCH /api/spaces/{id}/urls[/{job_id}]` — `src/api/spaces.py`
**Does:** Pinned-job sub-resource; `add_space_url` cross-checks the job belongs
to the same caller before pinning it. `reorder_space_url` sets an explicit sort_order.
**Entry point:** dashboard Space detail "URLs" tab.

#### `list_blobs` / `create_blob` / `get_blob` / `update_blob` / `delete_blob` / `reorder_blob` — `GET/POST/PUT/DELETE/PATCH /api/spaces/{id}/blobs[/{blob_id}]` — `src/api/spaces.py`
**Does:** Context-blob (free-text notes attached to a space) CRUD, structurally
identical shape to the URLs sub-resource above.
**Entry point:** dashboard Space detail "Context" tab.

#### `_enrich_space_jobs(space_urls) -> list[dict]` — `src/api/spaces.py`
**Does:** Batches 3 queries (jobs, annotations, tags) instead of N+1 to build
the job list an export needs — the pinned jobs plus their notes and tags.
**Called from:** `get_export_markdown`, `export_space`.

#### `get_export_markdown` / `export_space` — `GET /api/spaces/{id}/export/markdown`, `POST /api/spaces/{id}/export` — `src/api/spaces.py`
**Does:** Both compose the same markdown via `compose_space_export` (`FUNCTION_INDEX.md`);
`get_export_markdown` just returns it for client-side md/txt/pdf download,
`export_space` additionally pushes it to Drive as a real Google Doc via
`drive.export_to_gdoc`, gated by `settings.export_blocked()` (ADR-0027 — same
gate `drive.upload_file` uses).
**Entry point:** dashboard Space detail "Export" button.

---

## Controls / Templates API

`src/api/controls.py`, `src/api/templates.py` — user-owned settings: tags,
domain allow/ignore lists, recovery notification preference, and user-defined
Gemini prompt templates. Almost entirely parallel CRUD blocks.

#### `list_tags` / `create_tag` / `update_tag` / `delete_tag` — `GET/POST/PUT/DELETE /api/controls/tags[/{id}]` — `src/api/controls.py`
**Does:** Tag CRUD; `create_tag` maps a UNIQUE-constraint failure to 409.
**Entry point:** dashboard Controls page "Tags" section.

#### `list_allowed_domains` / `add_allowed_domain` / `remove_allowed_domain` and the ignored-domain mirror — `GET/POST/DELETE /api/controls/{allowed,ignored}-domains[/{domain}]` — `src/api/controls.py`
**Does:** Two structurally identical domain-list CRUD blocks (allow-list gates
which non-default domains route to the article pipeline; ignore-list hides a
domain from Vision-extracted links). Both normalize via `_normalize_domain`
(strip scheme, lowercase, drop `www.`) and validate via `is_valid_domain_name`.
**Called from (cross-domain):** same normalization/validation logic is duplicated by `_cmd_allowlist`/`_cmd_ignore` etc. in `webhook.py` — the Telegram-side equivalent of this settings surface.
**Entry point:** dashboard Controls page "Domains" section.

#### `get_recovery_settings` / `update_recovery_settings` — `GET/PUT /api/controls/recovery-settings` — `src/api/controls.py`
**Does:** Toggles whether stuck-job recovery notifications are sent to Telegram.
**Entry point:** dashboard Controls page.

#### `list_templates` / `create_template` / `update_template` / `delete_template` — `GET/POST/PUT/DELETE /api/templates[/{name}]` — `src/api/templates.py`
**Does:** User-defined enrichment template CRUD, merged with built-ins
(`_builtin_to_dict`) on list. Name validation forbids anything colliding with
a built-in template name (409 on create) or targeting one for update/delete (403).
**Entry point:** dashboard Prompts page; consumed by `-mytemplate <url>` in `webhook.py` via `database.get_user_template_by_name` (see finding #4).

---

## Doc Parser API

`src/api/parsed.py` — dashboard-native PDF upload/URL-fetch, parse cache reuse
with `document.py`, on-demand Gemini re-generation ("Clean"/"Freestyle"), and
per-job Telegram delivery toggle.

#### `upload_pdf` / `upload_url` / `_create_document_job` — `POST /api/parsed/upload`, `POST /api/parsed/url` — `src/api/parsed.py`
**Does:** Both funnel into `_create_document_job`: validate the PDF, store it
content-addressed in GCS, create a `document` job, **default `telegram_delivery`
to `"off"`** (dashboard uploads don't spam Telegram unless the user opts in —
unlike bot-submitted jobs, which keep the DB default of `"on"`), enqueue it.
**Entry point:** dashboard Doc Parser page, drag-drop upload or "paste a URL".

#### `_generate_output(job, kind, prompt=None) -> dict` / `clean` / `freestyle` — `POST /api/parsed/{id}/clean`, `/freestyle` — `src/api/parsed.py`
**Does:** Re-runs Gemini against the cached parsed text (`document._cached_parse`,
shared with the processor) with either a fixed "clean into markdown" instruction
or the user's freestyle prompt; stores the result as a new `document_outputs` row
and (if delivery is on) sends it to Telegram.
**Entry point:** dashboard Doc Parser detail page "Clean"/"Freestyle" actions.

#### `telegram_delivery` — `PUT /api/parsed/{id}/telegram-delivery` — `src/api/parsed.py`
**Does:** Sets the per-job delivery toggle; `state="retroactive"` additionally
walks every existing output and sends each one to Telegram now, then leaves the
toggle `on` going forward.
**Entry point:** dashboard Doc Parser per-job delivery switch.

#### `outputs` / `output_content` — `GET /api/parsed/{id}/outputs[/{output_id}]` — `src/api/parsed.py`
**Does:** Lists all generated outputs for a document job (concurrently
downloading previews via `asyncio.gather`, not sequential N round-trips), or
serves one output's full content.
**Entry point:** dashboard Doc Parser detail page.

#### `events` — `GET /api/parsed/events` — `src/api/parsed.py`
**Does:** Server-Sent-Events long-poll (2s interval, one shared DB connection
for the stream's lifetime) pushing the caller's document-job status list
whenever it changes — lets the Doc Parser page update live without a client polling loop.
**Entry point:** dashboard Doc Parser page (background EventSource connection).

---

## Restricted Preview API

`src/api/preview.py` — public, cookie-gated read-only sample of the Operator's
jobs for anonymous "Restricted mode" visitors (ADR-0035). Everything here must
be safe to expose with no auth beyond a functional cookie gate.

#### `_require_preview_access` (`_require_preview` + `_enforce_preview_rate_limit`) — `src/api/preview.py`
**Does:** Gate chain for every preview route: the `ownix_preview=1` cookie must
be set and `OPERATOR_CHAT_ID` configured, then a per-client (proxy-aware,
`X-Forwarded-For`-trusting-only-from-known-CIDRs) sliding-window rate limit
(120 req/60s) is enforced before any DB work.
**Called from:** every route in this file.

#### `_load_corpus()` / `_corpus()` — `src/api/preview.py`
**Does:** `_load_corpus` builds the diversified sample (≤50 jobs total, ≤20
per content-type tab, preferring the last 12h and backfilling older items) via
one ranked-window SQL query, then resolves thumbnails through `jobs.resolve_thumbnail`
and rewrites owned thumbnail URLs to the preview-gated twin (finding #6).
`_corpus()` wraps it in a 60s TTL cache (`asyncio.Lock`-guarded) so public reads
can't hammer the DB.
**Called from:** all four preview routes below.

#### `list_preview_jobs` / `get_preview_stats` / `get_preview_thumbnail` / `get_preview_job` — `GET /api/preview/jobs[/stats|/{id}[/thumbnail]]` — `src/api/preview.py`
**Does:** Public twins of the owned Jobs API, scoped to the cached corpus only
(a job_id outside the corpus 404s even if it exists) and stripping
`PRIVATE_DETAIL_FIELDS` (drive_url, sheets_row_id, error_msg, telegram_delivery)
plus a transcript-length cap. Every response sets `noindex` + short-lived cache headers.
**Entry point:** the public marketing/restricted dashboard shell for anonymous visitors.

---

## Google OAuth

`src/api/google_oauth.py` — per-user Google OAuth connect flow (Drive/Sheets
scopes), backing `services/google_tokens.py` and `services/google_auth.py`
(both in `FUNCTION_INDEX.md`).

#### `connect_google` — `GET /api/google/connect` — `src/api/google_oauth.py`
**Does:** Mints a CSRF `state` nonce (`store_google_oauth_state`), redirects to
Google's OAuth consent screen with `access_type=offline&prompt=consent` (forces
a refresh token every time, needed since Ownix stores no access-token cache).
**Entry point:** dashboard "Connect Google" button; also reachable via a single-use handoff token for the Telegram Mini App's `openLink` flow (see `_HANDOFF_TOKEN_PATHS` in `middleware.py`).

#### `google_oauth_callback` — `GET /api/google/callback` — `src/api/google_oauth.py`
**Does:** Redeems the `state` nonce (one-shot — a replayed callback 400s),
exchanges the code for a refresh token via a direct `httpx` POST to Google's
token endpoint, stores it encrypted (`store_google_token`), redirects back into
the dashboard with `?google=connected` or `?google=denied`.
**Entry point:** Google's OAuth redirect after user consent.

#### `google_status` / `google_folder` / `google_disconnect` — `GET /api/google/status`, `GET /api/google/folder`, `POST /api/google/disconnect` — `src/api/google_oauth.py`
**Does:** Connection-state check, the user's resolved `/Ownix` Drive folder URL
(via `google_workspace.user_folder_id`, sync-wrapped in a thread), and
disconnect (delegates to `services.google_auth.disconnect_google`).
**Entry point:** dashboard Controls/settings Google-connection panel.

---

## Auth & Sessions

`src/api/auth.py`, `src/auth/hmac_verify.py`, `src/auth/telegram_miniapp.py`,
`src/auth/middleware.py`, `src/auth/session.py` — how a Telegram identity
becomes a dashboard session cookie, and how every `/api/*` request is gated.

#### `verify_telegram_auth(payload, bot_token) -> dict | None` — `src/auth/hmac_verify.py`
**Does:** Pure HMAC verifier for the Telegram Login Widget: rebuilds the
sorted `key=value` data-check string, compares SHA-256-of-bot-token-keyed HMAC
against the payload's hash (constant-time), and rejects payloads older than 24h.
**Called from:** `telegram_login` in `src/api/auth.py`.

#### `verify_init_data(init_data, bot_token, *, now=None) -> dict | None` / `trusted_chat_id(verified) -> int` — `src/auth/telegram_miniapp.py`
**Does:** Same HMAC shape but for Telegram Mini App `initData` (a different
signing key derivation — `HMAC(b"WebAppData", bot_token)` — and a 1h window with a
60s clock-skew allowance). `trusted_chat_id` always resolves to the verified
individual `user.id`, never a group `chat.id`, since Google token storage is per-user.
**Called from:** `miniapp_session` in `src/api/auth.py`.

#### `SessionMiddleware.dispatch` — `src/auth/middleware.py`
**Does:** Gates every `/api/*` route (webhook/health/login endpoints are
exempt via `_OPEN_PATHS`/`_OPEN_API_PATHS`/`_OPEN_API_PREFIXES`): resolves the
`vig_session` cookie to a user, falls back to a one-shot Google-connect handoff
token for `_HANDOFF_TOKEN_PATHS` when the cookie fails, 401s if no user, then
401→403s pre-approval routes vs approval-required routes (`_PRE_APPROVAL_AUTH_PATHS`
is the exact allowlist of what an un-approved-but-logged-in user can hit).
**Entry point:** every FastAPI request via `app.add_middleware(SessionMiddleware)` in `main.py`.

#### `mint` / `resolve` / `revoke` — `src/auth/session.py`
**Does:** Opaque session store (Redis in prod, in-process dict for local dev,
switched by `settings.SESSION_BACKEND`), 30-day TTL, JSON-serialized user dict as the value.
**Called from:** `_login_telegram_user`/`miniapp_session`/`redeem_handoff_login` (mint), `SessionMiddleware` (resolve), `logout` (revoke) — all in `src/api/auth.py`/`middleware.py`.

#### `mint_handoff` / `redeem_handoff` / `mint_dashboard_handoff` / `redeem_dashboard_handoff` — `src/auth/session.py`
**Does:** Two single-use, short-TTL token flows built on the same
fetch-and-delete (`GETDEL`) primitive: one hands a *live session* across
Mini-App-`openLink`'s cookie-jar boundary (60s TTL) without putting the real
session id in a URL; the other hands a bare *chat_id* to a Telegram-message
"open your dashboard" link (`redeem_dashboard_handoff`, longer TTL — can sit unread in chat history).
**Called from:** `miniapp_session`/`SessionMiddleware` (handoff); `handoff_login`/`redeem_handoff_login` in `src/api/auth.py` (dashboard handoff).

#### `miniapp_session` — `POST /api/auth/miniapp/session` — `src/api/auth.py`
**Does:** Verifies Mini App `initData`, upserts the user, mints a session with
`samesite="none"` (needed inside Telegram's webview), and also mints a
Google-connect handoff token so the client can immediately offer "Connect Google" via `openLink`.
**Entry point:** Telegram Mini App bootstrap (fires once per Mini App open).

#### `telegram_login` / `_login_telegram_user` — `POST /api/auth/telegram` — `src/api/auth.py`
**Does:** Verifies the Login Widget payload, upserts the user, mints a
same-site session cookie, clears any stale preview cookie.
**Entry point:** the web dashboard's Telegram Login Widget (non-Mini-App browser login).

#### `handoff_login` / `redeem_handoff_login` — `GET/POST /api/auth/handoff` — `src/api/auth.py`
**Does:** A same-origin POST-confirmation page (GET, renders a self-submitting
form) then the actual redemption (POST): swaps a dashboard handoff token for a
session and 303-redirects straight to `/jobs/{job_id}` — the "open your
dashboard" link sent alongside job-completion Telegram messages.
**Entry point:** tapping a job's dashboard link from Telegram chat.

#### `dev_login` / `dev_approve` — `POST /api/auth/dev-login`, `POST /api/auth/dev-approve` — `src/api/auth.py`
**Does:** Local-dev-only bypasses (gated by `settings.DEV_LOGIN_ENABLED`,
404 otherwise) — a fake Telegram identity with a random id, auto-approved via
a synthetic email, optionally notifying the operator bot.
**Entry point:** local dev tooling only; never reachable in production config.

#### `logout` / `me` / `set_email` — `POST /api/auth/logout`, `GET /api/auth/me`, `PUT /api/auth/email` — `src/api/auth.py`
**Does:** `logout` revokes the session + clears the cookie; `me` returns the
session user merged with DB email/status (and opportunistically clears a stale
preview cookie for an approved user); `set_email` validates + stores an email
and, if the user is still `pending`, notifies the operator for approval.
**Entry point:** dashboard auth bootstrap (`me`), settings page (`set_email`), logout button.

---

## Telegram Webhook Dispatch

`src/telegram/webhook.py` (2003 lines — the main bot's entire command surface)
and `src/telegram/sender.py` (outbound Telegram Bot API wrappers this whole
file, and every processor, calls into).

#### `send_message` / `send_photo` / `send_document` / `send_inline_keyboard` / `send_force_reply` / `edit_message_text` / `edit_message_reply_markup` / `answer_callback_query` / `forward_message` / `download_photo` / `download_file` — `src/telegram/sender.py`
**Does:** Thin wrappers over the Telegram Bot HTTP API, all funneled through
one `_post_and_parse` helper (shared error/logging/retry shape) and one shared
`httpx.AsyncClient`. `send_document` handles the Gemini-generated-markdown
dash-translation + UTF-8 BOM quirks (`_telegram_document_payload`) so downstream
apps open the file correctly.
**Called from:** every processor in `src/processors/`, `webhook.py`, `main.py` (`register_webhook`), `services/google_auth.py` (refresh-failure notifications).

#### `webhook` — `POST /webhook` — `src/telegram/webhook.py`
**Does:** Main bot's single Telegram entry point: verifies the shared-secret
header, then routes by update shape — `callback_query` → `_webhook_route_callback`;
a message with `photo` → `_webhook_route_photo`; a message with `document` →
`_webhook_route_document` (checked *before* the text guard, since a file
message has no `.text`); otherwise `_webhook_route_text`. Each route is
individually exception-guarded so one bad update can't 500 the whole webhook.
**Entry point:** Telegram's servers POST every update here (registered at
startup by `main._register_webhook`).

#### `_CALLBACK_TABLE` + `_handle_callback` — `src/telegram/webhook.py`
**Does:** `data.partition(":")` splits `"prefix:payload"`; `_CALLBACK_TABLE`
maps the prefix to one of 17 `_cb_*` handlers (all take a `CallbackCtx`). Every
callback except `invite_approve`/`invite_block` re-checks the invite gate
before dispatching — a blocked/unapproved user's stale inline keyboard can't be
used to bypass the gate.
**Entry point:** every inline-keyboard button tap in the main bot.

Handler groups (all `(ctx: CallbackCtx) -> None`, all in `webhook.py`):
- **Gemini/template flow** — `_cb_gemini_no` (mark done, skip enrichment),
  `_cb_gemini_yes` (offer the 5-template keyboard), `_cb_template_pick`
  (persist template, enqueue `enrichment`), `_cb_template_freestyle` (arm
  `awaiting_freestyle` chat state).
- **Mini-PRD flow** — `_cb_prd_build_spec` (offer auto/intent choice),
  `_cb_prd_auto` (enqueue `prd_auto` or `prd_auto_resend` depending on cached
  state — also used as `_cb_prd_retry_auto`, same callback name reused for
  both `prd_auto` and `prd_retry_auto` prefixes), `_cb_prd_intent_prompt`
  (arm `awaiting_intent`), `_cb_prd_retry_intent` (re-enqueue `prd_intent` with the stored intent text).
- **Retry callbacks** — `_cb_enrichment_retry`, `_cb_article_retry`, all
  status-gated (only retry from `error`/appropriate states) then re-enqueue the
  same task type; `_cb_reprocess` is the one exception — it creates a **brand-new**
  job row from the orphaned job's URL rather than re-enqueuing the same job_id,
  so a crashed job's Drive/Sheets rows are never re-touched (ADR-0010).
- **Delivery callbacks** — `_cb_show_done` (forward the cached completion
  message + collapse the dedup keyboard), `_cb_document_md` (on-demand markdown render, delegates to `document.deliver_markdown`).
- **Invite callbacks** — `_cb_invite_approve`/`_cb_invite_block`
  (`functools.partial` of `_cb_invite_decision` — both are now **deprecated
  no-ops**; real invite decisions moved to `/webhook/ops`), `_cb_invite_status` (ack-only).
- **`_cb_repo_pick`** — resolves a numbered repo-followup choice via
  `services.repo_followup.enqueue_repo_pick` and enqueues the analysis.

#### `_SLASH_TABLE` + `_dispatch_slash` — `src/telegram/webhook.py`
**Does:** Maps `/command` text to a `_cmd_*` handler (`(ctx: SlashCtx) -> None`);
clears any pending chat_state/template on every command except `/cancel`
(which reads the state first, to report what it's canceling).
**Entry point:** any message starting with `/`, routed through `_route_text` step 1.

Handler groups (all in `webhook.py`):
- **Job creation shortcuts** — `_cmd_addlink` (`/addlink <url>` → Add-Link,
  same dedup semantics as the dashboard's `_create_link_job`), `_cmd_force`
  (`/force <url>` — three-way branch: existing job → reset+reprocess in place;
  cache-only → clear cache; neither → create fresh), `_cmd_freestyle`
  (`/freestyle` with no arg arms a 2-minute "next URL gets this template"
  window via a Redis key `pending_template:{chat_id}`; with a URL, routes
  straight into the freestyle flow), `_cmd_template` (the same
  pending-template-arming pattern, one instance registered per built-in
  template name via `**{f"/{t}": _cmd_template for t in PROMPT_TEMPLATES}`).
- **Domain list management** — `_cmd_ignore`/`_cmd_unignore`/`_cmd_ignore_list`
  and `_cmd_allowlist`/`_cmd_unallowlist`/`_cmd_allowlist_list` — Telegram-side
  mirror of `controls.py`'s domain CRUD, sharing the same normalize/validate
  shape but calling `database.*` directly instead of through the API layer.
  `_cmd_ignore` additionally protects `github.com` from being ignored (`_PROTECTED_DOMAINS`).
- **`_cmd_spec`** (→ `_handle_spec`) — `/spec <suffix> [intent...]`: resolves a
  4-char job-id suffix to a long-video job (rejects shorts with a specific
  message), then enqueues either `prd_intent` (if intent text given),
  `prd_auto_resend` (if already generated), or `prd_auto`.
- **`_cmd_find`** — `/find <query>` — semantic search via `brain.search_links`
  (0.58 similarity floor, top 5), GitHub-enriches results, formats stars/forks/language/age inline.
- **`_cmd_rebuild_graph`** — `/rebuild-graph` — same underlying job as the
  dashboard's `POST /api/brain/rebuild`, guarded by `brain._rebuild_lock` so a second tap while running just reports "in progress."
- **`_cmd_download_md`** — `/download_md <url>` — cache-or-fetch-via-Jina, same
  cache table `article.py` uses, sent back as a Telegram document.
- **`_cmd_cancel`/`_cmd_start`/`_cmd_help`** — chat-state cleanup and static help text.

#### `_route_url` / `_route_video` / `_route_article` / `_route_repo` / `_route_document_url` — `src/telegram/webhook.py`
**Does:** The plain-URL (non-slash-command) routing engine: reads and clears
any `pending_template:{chat_id}` Redis key, runs `detect_pipeline`, then
dispatches by pipeline. `_route_video` special-cases a pending `freestyle`
template into `_handle_freestyle_url` instead of a normal enqueue; `_route_repo`
notes when a pending template doesn't apply to repos (but leaves it armed for
the next video/article); `_route_document_url` fetches the PDF itself
(`_safe_get_pdf`, SSRF-guarded, manually-followed redirects so each hop is
re-validated) before handing off to `_enqueue_document_job`.
**Called from:** `_route_text` (step 4, the final fallback after slash/chat-state/user-template checks).

#### `_route_text` — `src/telegram/webhook.py`
**Does:** The top-level per-message router, in order: 1) invite gate 2) slash
command 3) armed chat_state (`awaiting_freestyle`/`awaiting_intent` —
delegates to `_handle_awaiting_freestyle`/`_handle_awaiting_intent`) 3b)
plain-text command shortcut (`"find x"` → `/find x`) 3c) user-template shortcut
(`-mytemplate <url>`) 4) plain URL routing.
**Called from:** `_webhook_route_text` (wraps it in a top-level exception guard that messages the user on any unhandled error).

#### `_handle_awaiting_intent` / `_handle_awaiting_freestyle` — `src/telegram/webhook.py`
**Does:** Resolve an armed chat_state against the user's next text message.
`_handle_awaiting_intent` special-cases a URL reply as an *interrupt* — cancels
the pending intent and starts a new job instead of treating the URL as intent
text (finding #3). `_handle_awaiting_freestyle` validates length, persists the
prompt, then branches on the job's `content_type`/`status` to pick which queue
task to fire (finding #2 — the one function every content type's freestyle path funnels through).
**Called from:** `_route_text`.

#### `_invite_gate_allows` / `_remember_invite_identity` — `src/telegram/webhook.py`
**Does:** The access-control gate every text/photo/document message and most
callbacks pass through: `approved` → proceed; `blocked` → refuse; unset email
→ arm `awaiting_email` and prompt; email set but not yet approved → "waiting on
operator" message. Opportunistically upserts the user's display identity on
every pass (skipped if unchanged, to avoid a write per message).
**Called from:** `_route_text`, `_webhook_route_photo`, `_webhook_route_document`, `_handle_callback`.

#### `_handle_user_template_shortcut` — `src/telegram/webhook.py`
**Does:** `-mytemplate <url>` syntax: looks up a **user-defined** template
(distinct from built-ins — finding #4) by name, and if found, runs it through
`create_and_enqueue_job` with the template's `extra_instructions` as a
freestyle prompt (repo URLs skip this — they always run the standard repo prompt).
**Called from:** `_route_text` (step 3b, before falling through to plain URL routing).

#### Media-group / photo ingest — `_accumulate_media_group`, `_process_media_group`, `_handle_photo_update`, `_handle_single_photo`, `_report_photo_links` — `src/telegram/webhook.py`
**Does:** Telegram sends each photo in a multi-image send as a separate update
sharing a `media_group_id`; `_accumulate_media_group` appends file_ids to a
Redis list and restarts a 1-second debounce task per group (canceling any
prior one) so `_process_media_group` fires once with the full batch. A single
photo (no group id) skips straight to `_handle_single_photo`. Both paths run
Gemini link-extraction over the image(s) and report results via `_report_photo_links`.
Per ADR-0003, this whole path runs inline in the webhook request (via
`spawn_background`), never through the job queue.
**Called from:** `_webhook_route_photo`.

#### Document ingest — `_handle_document_update`, `_enqueue_document_job`, `_ingest_document`, `_safe_get_pdf` — `src/telegram/webhook.py`
**Does:** Validates a Telegram-uploaded file is a PDF by mime/extension and
under the 20MB Bot API `getFile` cap, then downloads it in the background
(`spawn_background`, mirroring the photo path) and verifies the `%PDF` magic
bytes before enqueuing — `_enqueue_document_job` is the shared
store-content-addressed-then-queue step also used by the URL path (`_route_document_url`).
**Called from:** `_webhook_route_document`.

#### `POST /webhook/ops` + `_handle_ops_callback`, `_ops_cb_invite_decision`, `_ops_cb_approve_pending[_cancel]`, `_settle_ops_invite_card` — `src/telegram/webhook.py`
**Does:** The Ops bot's separate webhook (own HMAC secret
`OPS_WEBHOOK_SECRET`, own admin gate `ops_bot.can_admin`, own if/elif callback
dispatch rather than a table — finding #5). `_ops_cb_invite_decision` does an
atomic `UPDATE ... WHERE status='pending'` so two admins racing an approval
can't double-process the same invite; a 0-row update means someone else
already decided, so it reports the actual current status back instead of a generic error.
**Entry point:** the Ops Telegram bot's own webhook registration (`main._register_ops_webhook`).

---

## Startup & Worker Loop

`src/main.py` (API process) and `src/worker.py` (worker process) — both built
from the same image, per `CLAUDE.md`'s architecture summary.

#### `lifespan(app) -> AsyncIterator[None]` — `src/main.py`
**Does:** FastAPI startup/shutdown hook: `database.init_db()`, then (only if
`GOOGLE_DRIVE_FOLDER_BRAIN` is set) `brain.init_db()` + starts an
`AsyncIOScheduler` cron job (`brain.refresh_stale_links`, Sun/Wed 9am) — the
one scheduled job in the whole system — then registers both Telegram webhooks.
On shutdown: closes the sender's HTTP client, the Redis queue client, and the session store.
**Entry point:** FastAPI's `lifespan` context, run once per API process start/stop.

#### `register_webhook` / `_register_webhook` / `_register_ops_webhook` — `src/main.py`
**Does:** Calls Telegram's `setWebhook` for the main bot and (if
`OPS_BOT_TOKEN`/`OPS_WEBHOOK_SECRET`/`OPS_WEBHOOK_URL` are all set) the ops
bot, each with its own secret and `allowed_updates=["message","callback_query"]`.
**Called from:** `lifespan`.

#### Router mounting — `src/main.py` (module level, not a function)
**Does:** `app.add_middleware(SessionMiddleware)` then
`include_router(...)` for `webhook.router` + 9 API routers
(auth/brain/controls/jobs/google_oauth/parsed/spaces/templates/preview) — this
is the literal wiring point that turns all the route handlers documented above
into a live HTTP surface. Worth knowing as the one place that proves a router
is actually mounted (e.g. confirms `jobs_router` is live even though `create_job`'s handler binding is broken — finding #1).

#### `loop() -> None` — `src/worker.py`
**Does:** Worker process entry: `database.init_db()` (idempotent, safe if the
API container already ran it), runs the two PRD reapers + `reap_stale_jobs()`
once, then loops forever: `queue.dequeue()` (BRPOP-based, see `FUNCTION_INDEX.md`)
→ `_dispatch(task)` → log duration. A bare `except Exception` logs and sleeps
2s rather than crashing the loop — the worker must keep dequeuing even if one task's handling blows up unexpectedly.
**Entry point:** `main()` (module `__main__`, i.e. `python -m src.worker` / the `worker` Docker Compose service).

#### `_dispatch(task) -> None` + `_TASK_HANDLERS` — `src/worker.py`
**Does:** The task-discriminator dispatch table documented in this file's own
module docstring (`video`/`enrichment`/`article`/`repo`/`document`/`link`/`prd_auto`/`prd_auto_resend`/`prd_intent`).
Unknown discriminators are logged and dropped, not raised — a malformed
envelope can't crash the loop.
**Called from:** `loop`.

#### `_make_handler(module_name, error_event, error_message, *, pass_skip_document=False)` — `src/worker.py`
**Does:** Factory that builds `_handle_article`/`_handle_repo`/`_handle_document`/`_handle_link`
from one shared shape: load job → lazy-`importlib.import_module` the processor
(from a **hardcoded whitelist** `_PROCESSOR_MODULES`, never a task-controlled
string — worth noting as the deliberate guard against dynamic-import injection)
→ call `.run(job)` → on any exception, mark the job `error` and best-effort-notify the chat.
**Called from:** module-level assignment of the four handlers above.

#### `_handle_video` — `src/worker.py`
**Does:** The one task type that isn't a 1:1 processor mapping — branches on
`job["content_type"]` (`short`/`long`) to call the matching processor, then (long
only) calls `_maybe_auto_enqueue_enrichment` to chain Phase 2.
**Called from:** `_dispatch` (task `"video"`).

#### `reap_stale_jobs()` — `src/worker.py`
**Does:** Startup-only crash recovery (ADR-0010): resets any row still
`processing`/`enriching` (impossible in steady state — the worker is the only
writer of those states and dequeues sequentially) to `error` and sends a
state-appropriate retry button (`reprocess` for `processing`, `enrichment_retry` for `enriching`, since a transcript may already be safely stored).
**Called from:** `loop` (once, before entering the dequeue loop).

---

## See also

- `FUNCTION_INDEX.md` — the utility/service layer this file builds on top of.
- `CAPABILITY_MAP.md` — top-down capability → owning module lookup.
- `MODULE_MAP.md` — per-module reference (what each file owns, inbound paths).

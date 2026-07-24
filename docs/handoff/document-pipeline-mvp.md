# Handoff — Document pipeline MVP (issues #150–#155)

**Status:** not started. This is a build plan, not code.
**Scope decision (2026-06-18):** PDF-only, liteparse inline in the worker, **no
`vig-document` sidecar**. See the "MVP scope" addendum in
[ADR-0023](../adr/0023-liteparse-document-pipeline.md).
**Target:** all six issues land on **one PR**, one commit per issue.

---

## Decisions already made (don't re-litigate)

1. **Trimmed to 6 issues: #150 → #155.** #156 (on-demand Markdown), #157
   (Freestyle re-run), #158 (Drive/Sheets export) are a **fast-follow PR**, not
   this one.
2. **PDF-only.** liteparse parses PDF with zero native binaries. LibreOffice /
   ImageMagick / Tesseract are each a format family (Office / images) and are
   deferred. Confirmed against PyPI + run-llama/liteparse README + LlamaIndex
   blog.
3. **No sidecar.** PDF-only liteparse is `pip install liteparse`; it runs
   **in-process in `vig-worker`**. So #153 collapses from "new Docker service +
   HTTP contract + contract tests" to "add the dep + call it in the processor."
   There is **no `src/services/liteparse.py` HTTP client** and **no
   `vig-document` container** in this PR.
4. **#152: drop the arxiv host special-casing.** Route by extension only
   (`.pdf`). arxiv patterns return when someone actually sends one.
5. **#155 buttons are deferred.** `📄 Get Markdown` (#156) and `✍️ Freestyle`
   (#157) handlers don't exist yet, so the MVP delivers `.txt` + enrichment
   summary **without** those two buttons rather than ship dead UI. Add them in
   the follow-up PR alongside their handlers.

---

## Dependency order (build + commit in this order)

```
#150 GCS storage seam        ← root, no deps
 ├─ #151 Telegram file upload ingestion (PDF only)
 ├─ #152 Document URL routing (.pdf, no arxiv)
 └─ #153 liteparse inline (NOT a sidecar)
      └─ #154 parse cache + Gemini enrichment   ← the keystone
           └─ #155 Telegram delivery (.txt + summary, no buttons yet)
```

---

## Codebase facts gathered (so you don't re-derive them)

### Patterns to mirror
- **Processor template:** `src/processors/article.py` is the closest analog —
  cache lookup → fetch → Gemini → `update_job_status(..., "done", ...)` →
  fire-and-forget Sheets task → Telegram enrichment message. It already has the
  `skip_document` kwarg pattern (`async def run(job, *, skip_document=False)`).
  Mirror its `_build_*_prompt`, `_extract_json`, `_build_enrichment_message`
  helpers. Note: documents get **no `promise_gap`** (same as repos — "documents
  don't pitch").
- **Sidecar HTTP client reference (for the deferred future, NOT this PR):**
  `src/services/transcript.py`.
- **Worker dispatch:** `src/worker.py` — `_TASK_HANDLERS` dict +
  `_handle_*(task)` functions. Add `"document": _handle_document` and an
  `_handle_document` that loads the job, calls `processors.document.run(job,
  skip_document=task.get("skip_document", False))`, and on exception sets status
  `error` + `_notify_failure`.

### Sender (`src/telegram/sender.py`) — ready to use as-is
- `send_message(chat_id, text, *, parse_mode=None)`
- `send_document(chat_id, file_bytes: bytes, filename, *, caption=None)` —
  multipart; hardcodes `text/markdown` mime but Telegram ignores it for `.txt`,
  fine.
- `send_inline_keyboard(chat_id, text, buttons)`
- `download_photo(file_id) -> (bytes, mime)` — **only handles image extensions.**
  For #151 you need a generic file download: add `download_file(file_id) ->
  bytes` (copy `download_photo` minus the mime map; reuse the `getFile` →
  `/file/bot{token}/{file_path}` two-step).

### Webhook routing (`src/telegram/webhook.py`)
- Entry: `webhook()` at ~L1151. Order today: callback → photo (`message.photo`,
  L1177) → text guard (`if not chat_id or not text`, L1182) → `_route_text`.
- **#151 insertion point:** add a `message.get("document")` branch **before** the
  `if not chat_id or not text` guard (a file message has no `.text`). Mirror
  `_handle_photo_update` (L1189). `message.photo` stays on the existing photo
  pipeline — only `message.document` is the new path.
- **#152 insertion point:** `detect_pipeline` in `src/utils/validators.py`
  (L41). Add a `.pdf`-extension check that returns `"document"` **before** the
  `_match_article` allowlist call (L85). Then `_route_url` (L1131) needs a
  `pipeline == "document"` branch that downloads the URL, hashes+uploads via the
  storage seam, creates the job, enqueues `{"task":"document"}`.
  `Pipeline` Literal (L8) must gain `"document"`.

### Database (`src/database.py`) — **migration required**
- `content_type` CHECK is `IN ('short','long','article','repo')` in **three
  places**: `SCHEMA_SQL` (L82) and the two frozen migration snapshots `_V6_CREATE`
  (L342) / `_V7_CREATE` (L430). **Do not touch the frozen snapshots** — they're
  historical. Only edit `SCHEMA_SQL` (L82) to add `'document'`.
- **Add a new migration** at the end of `_MIGRATIONS` (last is the `summary`
  column, ~L602) that rebuilds the jobs table with the widened CHECK. Use the
  existing helper `_rebuild_jobs_table(conn, create_sql, tmp_name, cols)` (L361).
  Build a fresh `_V17_CREATE` = the **current full** jobs DDL (copy SCHEMA_SQL
  L32–86, it has columns the V7 snapshot lacks: `best_frame_index`, `platform`,
  `video_id`, `og_image_url`, `summary`) with CHECK including `'document'`, and a
  matching col list. Append `_migrate_*` to `_MIGRATIONS`. The runner
  (`_run_migrations` L607) and `init_db` fresh-install fast-path (L641) need no
  changes.
- `status` values: documents use `processing` / `done` / `error`, all already in
  the status CHECK — **no status migration needed.**
- `create_job(*, chat_id, url, content_type, message_id=None, template=None,
  freestyle_prompt=None)` (L786) works as-is with `content_type="document"`. The
  `url` column is NOT NULL — for uploads, store the GCS key (e.g.
  `documents/{sha256}.pdf`) or a `tg://` placeholder as the url.
- Reuse existing columns for enrichment (article already does): `title`,
  `ai_objective` (←summary), `ai_action_points` (←key_points), `ai_tools`
  (←tools), and `template_analysis` JSON blob for `author` / `publisher` /
  `document_type` / `references` (ADR-0008 pattern).

### Config (`src/config.py`)
- Add `GOOGLE_STORAGE_BUCKET: str = ""`. Reuse the existing Google auth in
  `src/services/google_auth.py` (OAuth refresh token preferred, service-account
  fallback). **Drive/Sheets must stay non-required** for the hot path — the GCS
  client must build from the same creds without forcing Drive/Sheets env vars.

### Dependencies (`requirements.txt`)
- Add `liteparse` (pin the version — ADR says v2.0.7) for #153.
- Add `google-cloud-storage` for #150 (the repo currently has
  `google-api-python-client` but **not** the GCS client lib — verify and add).

---

## Per-issue build notes

### #150 — `src/services/storage.py` (GCS content-addressed seam)
- Async helpers: `upload(key, data: bytes, content_type)`, `download(key) ->
  bytes`, `exists(key) -> bool`. `google-cloud-storage` is sync — wrap calls in
  `asyncio.to_thread`.
- Key builders: `documents/{sha256}.{ext}`, `parsed/{sha256}.txt`,
  `parsed/{sha256}.md`. One small helper `_key(kind, sha256, ext)` or three
  thin functions.
- **Tests** (mock the GCS client, no network): key construction, `exists`
  cache-hit true/false, client-failure surfaces as a raised error.

### #151 — Telegram file upload ingestion (PDF only)
- In `webhook()`: new `message.document` branch → `_handle_document_update`.
- Validate: accept PDF only at MVP (check `document.mime_type ==
  "application/pdf"` or `.pdf` filename). Reject others with a clear message.
- `document.file_size > 20MB` → reject with the ADR-0023 message: *"📄 File too
  large for Telegram (max 20MB). Upload via the web dashboard — feature coming
  soon."* No job created.
- Accepted: `download_file(file_id)` → `hashlib.sha256(bytes).hexdigest()` →
  `storage.upload("documents/{sha}.pdf", bytes, "application/pdf")` →
  `create_job(content_type="document", url=key, ...)` → `queue.enqueue({"task":
  "document","job_id":...})`.
- **Tests:** accepted PDF, unsupported type rejected, oversized rejected,
  photo-vs-file routing (a `message.photo` still hits the photo pipeline).

### #152 — Document URL routing (.pdf, no arxiv)
- `validators.detect_pipeline`: return `"document"` for a `.pdf` path before the
  article allowlist. Add `"document"` to the `Pipeline` Literal. Keep it
  synchronous + network-free (extension sniff only — no HEAD).
- `_route_url`: `pipeline == "document"` → download the URL bytes (httpx), hash,
  upload through the storage seam, `create_job`, enqueue. Undetected
  document-like URLs still fall through to article/rejected.
- **Tests:** `.pdf` → document; non-pdf article URL unaffected; webhook routes a
  `.pdf` link to a document job.

### #153 — liteparse inline (no sidecar)
- Add `liteparse==2.0.7` to `requirements.txt`. Retain the LICENSE shipped with
  that version per ADR mitigation (drop it in `licenses/liteparse-2.0.7.LICENSE`
  or similar).
- Thin wrapper for testability, e.g. `src/services/parse.py`:
  `async def parse_pdf(data: bytes) -> str` that runs
  `liteparse.LiteParse(ocr_enabled=False).parse(...)` in `asyncio.to_thread` and
  returns `ParseResult.text`. (Confirm the exact v2.0.7 call signature against
  the installed package — ADR notes `LiteParse().parse()` returns a
  `ParseResult` with `.text`.)
- **Tests:** a tiny real PDF in → non-empty text out (mark `integration` if it's
  slow/native); parse-failure path raises and is catchable.

### #154 — `src/processors/document.py` (keystone)
- `worker._dispatch` handles `task="document"`, threads `skip_document`.
- Flow: derive `sha256` from the job's GCS key → `storage.exists(parsed/{sha}.txt)`?
  hit: `storage.download` the text; miss: `storage.download(documents/{sha}.pdf)`
  → `parse_pdf` → `storage.upload(parsed/{sha}.txt, ...)`.
- Gemini enrichment with the document schema: `title, author, publisher,
  document_type, summary, key_points, references[], tools[]`. Reuse
  `src/services/gemini.py` `gemini_client.generate(...)` and an `_extract_json`
  like article's.
- Persist: `title→title`, `summary→ai_objective`, `key_points→ai_action_points`,
  `tools→ai_tools`; `author/publisher/document_type/references` →
  `template_analysis` JSON. **No `promise_gap`.** Tenant-scoped: the job row is
  `chat_id`-owned even though the parsed text is shared.
- **Tests:** cache hit, cache miss (calls parse + upload), parse failure,
  enrichment failure, tenant-scoped ownership.

### #155 — Telegram delivery
- On success: `send_document(chat_id, txt_bytes, "{title}.txt")` first (primary
  portable artifact), then the enrichment summary `send_message(..., parse_mode=
  "HTML")` rendering title / summary / key points / references / tools where
  present, with the same `job_{id[-4:]}:` tag convention.
- **Buttons deferred** (see decision #5): no `✍️ Freestyle` / `📄 Get Markdown`
  this PR.
- Send failures logged + surfaced without losing the completed enrichment state.
- **Tests:** happy path (txt + summary sent), delivery failure doesn't roll back
  `done`.

---

## Pre-flight checklist when you resume
- [ ] New branch off `main` (NOT `feat/web-date-localization`). Suggested:
      `feat/document-pipeline-mvp`.
- [ ] Confirm liteparse v2.0.7 Python API call signature against the installed
      wheel before writing #153/#154 (the ADR verified it but pin-check).
- [ ] Confirm `google-cloud-storage` import path + that platform GCS creds work
      via `google_auth` without enabling Drive/Sheets.
- [ ] Run tests via the PowerShell tool, not Bash (`python -m pytest tests -q`) —
      see `.claude/rules/rtk-tests.md`. The rtk hook only intercepts the Bash
      tool and mangles/hangs pytest; PowerShell reaches pytest unmodified.
- [ ] One commit per issue, all on the one PR.

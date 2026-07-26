# vig — Function Index

**Last Updated:** 2026-07-25
<!-- seed-index: coverage=bd806a4 drift=bd806a4 -->

Catalog of the utility/service layer in `src/` and `web/` — the functions that
already exist but don't show up anywhere else in `docs/seed/`, so they get
reinvented instead of reused. Every "Called from" was verified against the
CodeGraph index and, where the index looked wrong, double-checked with a raw
grep (see finding backend-#3 / frontend-#3 below — this codebase's
`import module; module.func()` style makes CodeGraph systematically
under-report callers).

**Scope:** `src/services/`, `src/utils/`, root cross-cutting modules
(`database.py`, `brain.py`, `queue.py`, `templates.py`, `config.py`), and
`web/lib/` (including `lib/hooks/`). Deliberately **excludes**
`src/processors/`, `src/api/`, `src/auth/`, `src/telegram/`,
`web/components/`, and `web/app/` — those are orchestration/UI entry points
already covered by `MODULE_MAP.md` and `CAPABILITY_MAP.md`; you already know
they exist because you wired them yourself. This file is for the layer
underneath.

---

## Read this first — what's actually hiding

**Backend:**

1. **`is_video_url()` in `src/utils/validators.py` is dead code.** Fully implemented and unit-tested, but nothing outside `tests/test_validators.py` calls it — `detect_pipeline()` is used directly everywhere instead. Reuse it or delete it.
2. **Two unrelated functions are both named `init_db()`** — `database.py`'s (schema+migrations) and `brain.py`'s (links table + Drive pre-flight check). Both run separately at startup. Always qualify as `database.init_db()` / `brain.init_db()`.
3. **CodeGraph systematically misses this codebase's `import module; module.func()` call style.** Several real, active functions showed "zero callers" and needed grep verification: `transcript.py`'s `fetch_transcript`/`fetch_metadata`, all of `pdf_intake.py`, `filter_vision_links`, `build_transcript_markdown`, `append_short_row`/`append_long_row`, `notify_invite`, `fetch_public_image`. Treat a "no callers" result on this repo as a lead to verify, not a verdict.
4. **`sheets.py` has five near-identical append/update-row pairs** (repo/short/long/article/document) funneled through shared `_append_row_logged`/`_update_row_logged` wrappers — not duplication, it's the template to copy for a new content-type export.
5. **`slugify()` vs `sanitize_filename_chars()`** (`utils/validators.py`) look redundant but aren't: `slugify` makes a lowercase URL slug, `sanitize_filename_chars` preserves case/spaces for a human-readable filename. Reach for the right one instead of writing a third variant.
6. **`github.py` has two different repo-metadata fetchers with different caches** — `enrich_repo()` (light, 24h TTL) vs `fetch_repo_bundle()` (full README+tree, 7-day TTL). Picking the wrong one over- or under-fetches.

**Frontend:**

7. **`useSpaceUrls.reorderUrl` and `useSpaceContext.reorderBlob` duplicate the same "swap sort_order with a neighbor" pattern** on top of `swapSortOrder()` — neither uses `useFetchList` either, both hand-roll their own fetch/loading state. A consolidated space-scoped list hook is the future cleanup.
8. **`useJobTags` and `useLinkTags` already share `useTagAttachment`** for the mutation half but still each hand-roll their own fetch boilerplate and duplicate an `asTags()` guard.
9. **CodeGraph under-reports frontend callers too** — `useSpaceList`, `useLinkTags`, `apiPost`/`apiPut`/`apiDelete`, `useFetchDetail`, `swapSortOrder`, `makeHandlers` all showed "no callers" but are genuinely, actively used (verified by grep/direct read).
10. **`fetch-utils.ts` is the real shared foundation** — `useFetchList` (list + loading + reload) and `useFetchDetail` (single resource + 401/403/404 mapping) are reused by 6+ hooks. Any new "fetch a list/resource" hook should start there, not with a fresh `useState`/`useEffect`.

---

# Backend (`src/`)

## `src/services/`

### brave.py

#### `verify_links(links: list[dict]) -> list[dict]`
**Does:** Enriches up to 5 links with a Brave Search title/description lookup (one HTTP call per link), leaving links unchanged if Brave is disabled/unconfigured or a per-link call fails. Links beyond the first 5 pass through untouched.
**Called from:** `run` in `src/processors/short_video.py`.
**Usage:** `links = await brave.verify_links(extracted_links)`

### space_export.py

#### `compose_space_export(space: dict, blobs: list[dict], jobs: list[dict], tags: list[dict]) -> str`
**Does:** Pure, I/O-free markdown composer for a "Space" export — builds context-blob sections, a tag legend (only tags actually used), and one `### <job title>` block per job with its AI-extracted fields and notes. Deterministic, so it's directly unit-testable and reusable as a future NotebookLM-push payload.
**Called from:** `get_export_markdown` and `export_space` in `src/api/spaces.py`.
**Usage:** `markdown = compose_space_export(space, blobs, jobs, tags)`

### storage.py

#### `object_key(kind: str, sha256: str, ext: str) -> str`
**Does:** Builds the content-addressed GCS object key, e.g. `documents/<sha256>.pdf`, `parsed/<sha256>.txt`. Pure string formatting, no I/O.
**Called from:** `_create_document_job` (`src/api/parsed.py`), `_cached_parse`/`run` (`src/processors/document.py`), `_enqueue_document_job` (`src/telegram/webhook.py`).
**Usage:** `key = object_key("documents", sha256_hex, "pdf")`

#### `upload(key: str, data: bytes, content_type: str) -> None`
**Does:** Uploads bytes to the GCS bucket at `key` (wraps the sync `google-cloud-storage` client in `asyncio.to_thread`, since that client has no native async API).
**Called from:** `_create_document_job`/`_generate_output` (`src/api/parsed.py`), `_cached_parse`/`run` (`src/processors/document.py`), `_enqueue_document_job` (`src/telegram/webhook.py`).
**Usage:** `await storage.upload(key, pdf_bytes, "application/pdf")`

#### `download(key: str) -> bytes`
**Does:** Downloads the object at `key` from GCS as raw bytes.
**Called from:** `telegram_delivery`/`outputs`/`output_content` (`src/api/parsed.py`), `_cached_parse` (`src/processors/document.py`).
**Usage:** `data = await storage.download(key)`

#### `exists(key: str) -> bool`
**Does:** Checks whether `key` already exists in the bucket — used to short-circuit re-uploading/re-parsing content-addressed objects.
**Called from:** `_cached_parse` (`src/processors/document.py`).
**Usage:** `if await storage.exists(key): ...`

### parse.py

#### `parse_pdf(data: bytes, *, output_format: str = "text") -> str`
**Does:** Extracts text (or Markdown, if `output_format="markdown"`) from raw PDF bytes using `liteparse`, running the CPU-bound parse in a thread. Raises `ParseError` (a local wrapper class) on any failure so callers get one exception type regardless of what liteparse or the native backend throws.
**Called from:** `_cached_parse` in `src/processors/document.py`.
**Usage:** `text = await parse_pdf(pdf_bytes, output_format="markdown")`

### google_tokens.py

Encrypted per-user Google OAuth token store (Fernet, keyed by `GOOGLE_TOKEN_ENCRYPTION_KEY`), plus a short-lived OAuth `state` nonce store used for CSRF protection during the connect flow.

#### `encrypt_token(payload: dict) -> str` / `decrypt_token(ciphertext: str) -> dict`
**Does:** JSON-serialize-then-Fernet-encrypt (and reverse) a token payload dict. Thin wrappers around `google_token_fernet()`.
**Called from:** Internally by `store_google_token`/`load_google_token`/`load_google_token_sync`.
**Usage:** `blob = encrypt_token({"refresh_token": "..."})`

#### `store_google_token(chat_id: int, token_payload: dict) -> None`
**Does:** Upserts the encrypted per-user Google token row, clearing any "revoked" notification flag.
**Called from:** `google_oauth_callback` in `src/api/google_oauth.py`.
**Usage:** `await store_google_token(chat_id, {"refresh_token": rt, "scopes": [...]})`

#### `load_google_token(chat_id: int) -> dict | None`
**Does:** Async-decrypts and returns a user's stored token, or `None` if absent or corrupted (logs a warning rather than raising on decrypt failure).
**Called from:** `google_status` (`src/api/google_oauth.py`), `disconnect_google` (`src/services/google_auth.py`).
**Usage:** `token = await load_google_token(chat_id)`

#### `delete_google_token(chat_id: int) -> bool`
**Does:** Deletes a user's stored token row; returns whether a row actually existed (used to decide whether to send a one-time "disconnected" notification).
**Called from:** `handle_google_refresh_error`, `disconnect_google` (both `src/services/google_auth.py`).
**Usage:** `was_present = await delete_google_token(chat_id)`

#### `store_google_oauth_state(state, chat_id, *, ttl_seconds=600) -> None` / `consume_google_oauth_state(state) -> int | None`
**Does:** A one-shot CSRF-state nonce store for the OAuth connect flow: `store` inserts the nonce with a TTL; `consume` atomically `DELETE ... RETURNING chat_id` so a state can only be redeemed once, and opportunistically sweeps expired rows on every call.
**Called from:** `connect_google`/`google_oauth_callback` in `src/api/google_oauth.py`.
**Usage:** `await store_google_oauth_state(state, chat_id)` then later `chat_id = await consume_google_oauth_state(state)`

#### `load_google_token_sync(chat_id: int) -> dict | None`
**Does:** Synchronous (plain `sqlite3`, not `aiosqlite`) variant of `load_google_token`, for call sites that can't await — e.g. building Google API credentials inside a sync helper.
**Called from:** `has_google_connection_sync` (same file), `build_google_credentials` (`src/services/google_auth.py`).
**Usage:** `token = load_google_token_sync(chat_id)`

#### `has_google_connection_sync(chat_id: int) -> bool`
**Does:** `True` iff a decryptable token exists for `chat_id`. Thin sync boolean wrapper over `load_google_token_sync`.
**Called from:** `user_folder_id`, `user_sheet_id` (`src/services/google_workspace.py`).
**Usage:** `if has_google_connection_sync(chat_id): ...`

### drive.py

#### `upload_file(content, filename, folder_id, mime_type="text/markdown", *, chat_id=None) -> tuple[str, str]`
**Does:** Uploads content as a new Drive file, returning `(file_id, web_view_link)`. Resolves the destination folder to the calling user's own `/Ownix` workspace folder when they're connected (falls back to the operator's shared `folder_id` otherwise), and is gated by `settings.export_blocked()` — non-operator jobs without a Google connection silently get `("", "")` instead of writing to the operator's Drive (ADR-0027). A `RefreshError` triggers `handle_google_refresh_error` and degrades to empty strings rather than crashing the job.
**Called from:** `run` in `long_video.py`/`short_video.py`, `_deliver_transcript_doc` (`short_video.py`), `init_db`/`_rewrite_existing_md`/`_upload_brain_md`/`_rebuild_one_link`/`_upload_link_markdown` (`src/brain.py`), `run_prd` (`src/processors/prd.py`).
**Usage:** `file_id, link = await upload_file(markdown_text, "notes.md", folder_id, chat_id=chat_id)`

#### `update_file(file_id, content, mime_type="text/markdown", *, chat_id=None) -> str`
**Does:** In-place overwrite of an existing Drive file's content; returns its (unchanged) `webViewLink`. Same export-gating and `RefreshError`/`HttpError` degrade-not-crash behavior as `upload_file`.
**Called from:** `run_auto_resend`, `run_prd` in `src/processors/prd.py`.
**Usage:** `link = await update_file(file_id, new_markdown, chat_id=chat_id)`

#### `export_to_gdoc(markdown, name, folder_id, *, chat_id=None) -> str`
**Does:** Creates a real, editable Google **Doc** (not a raw markdown file) by uploading `text/plain` content with `mimeType=application/vnd.google-apps.document`, which Drive auto-converts. Returns the Doc's `webViewLink`. Same gating/degrade semantics as the other two.
**Called from:** `export_space` in `src/api/spaces.py`.
**Usage:** `doc_url = await export_to_gdoc(markdown, "My Space Export", folder_id, chat_id=chat_id)`

### jina.py

#### `fetch_markdown(url: str) -> tuple[str, str]`
**Does:** Fetches a URL through the Jina Reader proxy (`r.jina.ai`) and returns `(title, body)` with Jina's preamble block stripped out. Raises `JinaFetchError` on any non-200 response.
**Called from:** `_resolve_identity` (`src/brain.py`), `run` (`src/processors/article.py`), `_cmd_download_md` (`src/telegram/webhook.py`).
**Usage:** `title, body = await fetch_markdown(article_url)`

### repo_followup.py

#### `extract_repo_candidates(items: list[dict] | None, text: str | None = None) -> list[dict]`
**Does:** Filters an arbitrary list of extracted tool/link items (plus URLs scraped from free `text` via `extract_description_links`) down to normalized, deduplicated GitHub repo URLs, capped at 5. Explicit `items` win the dedupe over text-scraped ones so their display names take priority.
**Called from:** `offer_repo_followups` (same file).
**Usage:** `candidates = extract_repo_candidates(gemini_tools, text=transcript)`

#### `offer_repo_followups(job: dict, items: list[dict] | None, text: str | None = None) -> list[dict]`
**Does:** Caches extracted repo candidates in Redis (60 min TTL) and sends a Telegram inline keyboard ("Analyze owner/repo") so the user can one-tap kick off a follow-up repo-analysis job.
**Called from:** `run` in `long_video.py`, `article.py`, `enrichment.py`.
**Usage:** `await offer_repo_followups(job, gemini_result.get("tools"), text=transcript)`

#### `enqueue_repo_pick(source_job_id: str, idx_raw: str) -> dict | None`
**Does:** Resolves a repo-followup keyboard tap back to its cached candidate list, then creates+enqueues a new `repo` job for the picked URL via `create_and_enqueue_job`.
**Called from:** `_cb_repo_pick` in `src/telegram/webhook.py`.
**Usage:** `new_job = await enqueue_repo_pick(source_job_id, "0")`

### google_workspace.py

#### `user_folder_id(chat_id: int | None) -> str | None`
**Does:** Lazily creates (once) and returns a connected user's personal `/Ownix` Drive folder ID, memoized in `user_settings`. Returns `None` if the user isn't connected. Uses a per-`(chat_id, key)` in-process lock so concurrent calls can't create two folders (ponytail note: single-worker-only guarantee).
**Called from:** `user_sheet_id` (same file); indirectly drives Drive uploads via `drive.py`.
**Usage:** `folder_id = user_folder_id(chat_id)`

#### `user_sheet_id(chat_id: int | None) -> str | None`
**Does:** Lazily creates a connected user's personal "Ownix exports" Spreadsheet and moves it into their `user_folder_id()` folder, memoized in `user_settings`. Returns `None` if not connected.
**Called from:** `_append_sync`, `_update_sync` in `src/services/sheets.py`.
**Usage:** `sheet_id = user_sheet_id(chat_id) or settings.GOOGLE_SHEETS_ID`

### invite_notifications.py

#### `notify_operator_invite(chat_id: int, email: str, *, dev: bool = False) -> bool`
**Does:** Thin, shared entry point (used by both the Telegram bot and the web dashboard's auth flow) that gates on `OPS_DEV_NOTIFICATIONS`/`OPS_BOT_TOKEN` config, then delegates to `ops_bot.notify_invite` to actually send the admin approval card.
**Called from:** `dev_login`, `set_email` (`src/api/auth.py`), `_notify_operator_invite` (`src/telegram/webhook.py`).
**Usage:** `await notify_operator_invite(chat_id, "user@example.com")`

### frames.py

#### `fetch_frames(url: str) -> dict`
**Does:** Calls the transcript sidecar's `/short_frames` endpoint to extract JPEG frames from a short-form video (interval=1.0s, up to 20 frames, 768px wide). Long timeout (200s) since the sidecar has to download + decode video first.
**Called from:** `backfill` in `scripts/backfill_short_thumbnails.py`. Not used in the live worker pipeline — `short_video.py` calls the sidecar directly rather than through this wrapper; check before assuming this is on the hot path.
**Usage:** `resp = await fetch_frames(video_url)`

### ops_bot.py

The Ops Telegram bot's command handlers and Telegram-send wrappers (mirrors `src/telegram/sender.py` but always targets `OPS_BOT_TOKEN`).

#### `can_read(chat_id) / can_admin(chat_id) / can_deliver_to(ctx: OpsCtx) -> bool`
**Does:** Authorization checks against `settings.ops_chat_ids` / `ops_admin_chat_ids`. `can_deliver_to` additionally allows a user to receive results in their own DM even if they're not a listed ops chat.
**Called from:** `handle_command` (same file), `_handle_ops_callback` (`src/telegram/webhook.py`).
**Usage:** `if not can_admin(sender_id): reject()`

#### `send_ops_message` / `send_ops_keyboard` / `send_ops_document` / `answer_ops_callback` / `edit_ops_reply_markup`
**Does:** Telegram send/edit primitives pinned to the ops bot's own token, so ops replies never leak through the main user-facing bot.
**Called from:** `deliver_rows`, `notify_invite`, `handle_command` (same file); callback handlers in `src/telegram/webhook.py`.
**Usage:** `await send_ops_message(admin_chat_id, "3 pending users")`

#### `notify_invite(chat_id: int, email: str, *, dev: bool = False) -> bool`
**Does:** Sends an Approve/Block inline-keyboard card to every admin (or dev-notification) chat for a pending invite request.
**Called from:** `notify_operator_invite` in `src/services/invite_notifications.py` (module-alias call, missed by CodeGraph — verified via grep).
**Usage:** `await notify_invite(chat_id, "user@example.com")`

#### `normalize_email_domain(value: str) -> str | None`
**Does:** Validates/lowercases a bare domain string (rejects emails, missing TLD, malformed DNS labels); returns `None` for invalid input or the literal `"all"`.
**Called from:** `approve_pending_domain`, `handle_command` (same file).
**Usage:** `domain = normalize_email_domain("Example.COM")` → `"example.com"`

#### `format_rows` / `rows_csv` / `deliver_rows(chat_id, title, rows) -> None`
**Does:** Renders a user-row list as either a short bullet-list text message or, past `MAX_CHAT_ROWS=20`, a CSV file attachment — `deliver_rows` picks automatically. `rows_csv` neutralizes formula-injection characters per cell before writing CSV, since these rows can contain user-controlled Telegram names.
**Called from:** `handle_command` (same file); `rows_csv` also directly tested.
**Usage:** `await deliver_rows(chat_id, "Pending users", rows)`

#### `create_approval_batch` / `approve_pending_batch` / `approve_pending_domain`
**Does:** Two-step bulk-approve flow for `/approve_pending`: `create_approval_batch` caches the target `tg_id` list in Redis (15 min TTL) behind a random batch id so a confirm-button tap can re-fetch the exact set without re-querying; `approve_pending_batch` redeems it. `approve_pending_domain` is the direct (non-batched) path used by tests/automation.
**Called from:** `handle_command` (batch creation); `_ops_cb_approve_pending` in `src/telegram/webhook.py` (redemption).
**Usage:** `batch_id = await create_approval_batch("example.com", pending_rows)`

#### `list_users(status=None, *, email_domain=None, limit=20) -> list[dict]`
**Does:** Filtered/paginated query over the `users` table (by status and/or a `LIKE`-escaped email-domain suffix match). `limit=None` means unbounded.
**Called from:** `approve_pending_domain`, `handle_command` (same file).
**Usage:** `pending = await list_users("pending", limit=None)`

#### `handle_command(ctx: OpsCtx) -> None`
**Does:** The Ops bot's full command router — `/start`, `/help`, `/pending`, `/users [...]`, `/approve_pending <domain>`. Single entry point every ops Telegram message flows through.
**Called from:** `ops_webhook` in `src/telegram/webhook.py`.
**Usage:** `await handle_command(OpsCtx(chat_id=..., sender_id=..., parts=text.split()))`

### transcript.py

#### `fetch_transcript(url: str) -> dict`
**Does:** Calls the transcript sidecar's `/transcript` endpoint and unwraps the first element of its array response; logs (but doesn't raise on) an `error` field in the result.
**Called from:** `run` in `src/processors/short_video.py` — via `transcript_svc.fetch_transcript(url)` (module-alias call; verified with grep after CodeGraph missed it).
**Usage:** `resp = await transcript_svc.fetch_transcript(url)`

#### `fetch_metadata(url: str) -> dict`
**Does:** Calls the sidecar's `/metadata` endpoint for video title/channel/views without pulling the full transcript.
**Called from:** `run` in `src/processors/long_video.py` (same module-alias caveat as above).
**Usage:** `meta = await transcript_svc.fetch_metadata(url)`

### gemini.py

#### `generate(prompt: str, *, model: str, schema=None) -> str`
**Does:** The base text-generation call: tries `GEMINI_FREE_API_KEY` then `GEMINI_PAID_API_KEY` via `_call_with_fallback`, raising `GeminiUnavailableError` only if both keys fail. Every other Gemini call in this file is built on top of this fallback pattern.
**Called from:** `resolve_tool_urls` (same file), `run` in `article.py`/`document.py`/`repo.py`, `enrich` in `enrichment.py`, `run_prd` in `prd.py`.
**Usage:** `text = await generate(prompt, model="gemini-2.5-flash")`

#### `call_gemini_vision(frames: list[dict]) -> dict`
**Does:** Sends inline JPEG frames (base64) to Gemini for short-video content analysis; returns `{main_frame_index, summary, links}`.
**Called from:** `run` in `src/processors/short_video.py`.
**Usage:** `vision = await call_gemini_vision(frames)`

#### `call_gemini_photo_links(images: list[dict], *, caption=None) -> dict`
**Does:** OCR-style extraction of URLs/domains that are **verbatim visible** in one or more photos (screenshots). After the model call, runs `_filter_grounded_links` to drop any URL whose domain isn't literally present in the model's own quoted "verbatim" text or the summary — a guard against Gemini hallucinating plausible-looking URLs.
**Called from:** `_handle_single_photo`, `_process_media_group` in `src/telegram/webhook.py`.
**Usage:** `result = await call_gemini_photo_links(images, caption=msg.caption)`

#### `resolve_tool_urls(tools: list[dict]) -> list[dict]`
**Does:** Given a list of tool/product names Gemini extracted, asks Gemini a second time for each item's canonical homepage URL. Falls back to `url: None` on every item if Gemini is unavailable rather than raising.
**Called from:** Not called elsewhere in the codebase yet — available to use directly (zero real callers, even after grep verification; likely built for a not-yet-wired enrichment step).
**Usage:** `resolved = await resolve_tool_urls([{"name": "Redis", "type": "tool"}])`

#### `extract_json(raw: str, *, root: str = "object") -> dict | list`
**Does:** Strips ```` ```json ```` markdown fences and parses the first balanced `{...}` (or `[...]` if `root="array"`) out of a raw LLM text response — the single shared JSON-extraction routine every Gemini caller in the codebase uses instead of hand-rolling regex.
**Called from:** `call_gemini_vision`, `call_gemini_photo_links`, `resolve_tool_urls` (same file); `run` in `article.py`/`document.py`; `_extract_json` in `enrichment.py`; `run_prd` in `prd.py`.
**Usage:** `data = extract_json(response.text, root="array")`

### github.py

#### `preprocess_readme(raw: str) -> str`
**Does:** Strips badge lines and a fixed set of inline HTML tags from a raw README, then truncates to 50,000 chars — cleans README markdown before it's fed to Gemini for repo analysis.
**Called from:** `fetch_repo_bundle` (same file).
**Usage:** `clean = preprocess_readme(raw_readme_text)`

#### `fetch_readme` / `fetch_tree` / `fetch_manifest(owner, repo, ..., token) -> ... | None`
**Does:** Never-raising async wrappers around three blocking GitHub REST calls (README content, recursive file tree, a single file's content) — all return an empty/`None` fallback and log a warning on any error instead of propagating.
**Called from:** `fetch_repo_bundle` (same file); also exercised directly by `tests/test_github.py`.
**Usage:** `readme = await fetch_readme(owner, repo, token)`

#### `fetch_repo_description(owner, repo, token) -> str | None`
**Does:** Fetches just a repo's one-line GitHub description, never raising.
**Called from:** `_resolve_identity` in `src/brain.py`.
**Usage:** `desc = await fetch_repo_description(owner, repo, token)`

#### `fetch_repo_bundle(owner, repo, token) -> dict`
**Does:** Assembles the **full** analysis payload for a repo — metadata, README (preprocessed), file tree, detected manifest files (depth ≤2), and up to 4 sub-project READMEs one level deep — with all optional fetches run concurrently and individually fault-tolerant. Cached in Redis for 7 days under `github_repo_bundle:v3:{owner}/{repo}`. Raises on 404/403/5xx (unlike the other fetchers in this file, this one is allowed to raise since the repo pipeline needs to fail loudly).
**Called from:** `_refresh_repo_metadata` (`src/brain.py`), `run` (`src/processors/repo.py`).
**Usage:** `bundle = await fetch_repo_bundle(owner, repo, github_token)`

#### `enrich_repo(owner, repo, token) -> dict | None`
**Does:** Lightweight GitHub metadata lookup (stars/forks/language only — no README/tree), Redis-cached 24h under `github_meta:{owner}/{repo}`. Returns `None` on 404/error rather than raising. **Distinct from `fetch_repo_bundle`** — see top finding backend-#6.
**Called from:** `enrich_github_links` (same file).
**Usage:** `meta = await enrich_repo(owner, repo, token)`

#### `enrich_github_links(links: list[dict]) -> list[dict]`
**Does:** Mutates a list of extracted links in place, attaching star/fork/language/age metadata (via `enrich_repo`) to every `github.com` URL found; passes non-GitHub links through untouched.
**Called from:** `_report_photo_links`, `_cmd_find` in `src/telegram/webhook.py`.
**Usage:** `enriched = await enrich_github_links(extracted_links)`

### google_auth.py

#### `handle_google_refresh_error(chat_id: int | None) -> bool`
**Does:** Central handler for a revoked/expired Google OAuth token: deletes the stored token and sends a one-time "please /connect again" DM (only if a row actually existed, so the user isn't spammed on every subsequent write attempt in the same session).
**Called from:** `_append_row_logged`, `_update_row_logged`, `append_short_row`, `append_long_row`, `append_prd_row` (`src/services/sheets.py`); also used inside `drive.py`'s upload/update/gdoc paths.
**Usage:** `await handle_google_refresh_error(chat_id)`

#### `disconnect_google(chat_id: int) -> None`
**Does:** Full disconnect flow: best-effort revokes the refresh token with Google's `/revoke` endpoint (swallows any error), then deletes the local token row regardless of whether revocation succeeded.
**Called from:** `google_disconnect` route in `src/api/google_oauth.py`.
**Usage:** `await disconnect_google(chat_id)`

#### `build_google_credentials(scopes, *, prefer_service_account=False, chat_id=None) -> Credentials`
**Does:** The single credential-resolution point for every Google API call in the app. Priority: per-user encrypted refresh token (if `chat_id` given and connected) → service-account JSON (if `prefer_service_account`) → operator's legacy env refresh token → service-account JSON fallback.
**Called from:** `build_google_service` (same file); `_bucket` in `src/services/storage.py`.
**Usage:** `creds = build_google_credentials(["https://www.googleapis.com/auth/drive.file"], chat_id=chat_id)`

#### `build_google_service(api, version, scopes, *, chat_id=None) -> Any`
**Does:** `build_google_credentials` + `googleapiclient.discovery.build` in one call — the shared way every service module gets an authenticated API client.
**Called from:** `_build_service` in `src/services/sheets.py` and `src/services/drive.py`.
**Usage:** `service = build_google_service("drive", "v3", SCOPES, chat_id=chat_id)`

### job_recovery.py

Dashboard-triggered recovery for stuck/failed jobs — the backing logic for the dashboard's Recovery panel.

#### `recovery_summary(chat_id, content_type=None) -> dict[str, int]`
**Does:** One query returning counts of stale-pending, error, and stale-in-flight jobs for a chat (optionally scoped to a content type) — powers the dashboard's recovery badge counts.
**Called from:** `get_recovery_summary` route handler in `src/api/jobs.py`.
**Usage:** `counts = await recovery_summary(chat_id, "short")`

#### `retry_pending(chat_id, content_type=None) -> dict[str, int]`
**Does:** Atomically claims stale `pending` jobs, re-enqueues each, and restores any job's original timestamp if a mid-batch enqueue fails, so a Redis outage can't silently strand jobs outside the recovery window.
**Called from:** `retry_recovery_pending` route handler in `src/api/jobs.py`.
**Usage:** `result = await retry_pending(chat_id)`

#### `clear_failed(chat_id, content_type=None) -> dict[str, int]`
**Does:** Bulk-flips every `error` job for a chat/content_type to `cancelled` — the dashboard's "dismiss all failed" action.
**Called from:** `clear_recovery_failed` route handler in `src/api/jobs.py`.
**Usage:** `result = await clear_failed(chat_id)`

#### `retry_error(chat_id, content_type=None) -> dict[str, int]`
**Does:** The most involved recovery path: first reaps any jobs stuck `processing`/`enriching` past the stale window and notifies the user, then claims every `error` row and retries each per its content type — `article`/`long-with-transcript` jobs resume in place, everything else gets a brand-new replacement job. Same failure-restores-to-`error` safety net as `retry_pending`.
**Called from:** `retry_recovery_error` route handler in `src/api/jobs.py`.
**Usage:** `result = await retry_error(chat_id, "long")`

### jobs.py

#### `task_for_content_type(content_type, *, default) -> str | None`
**Does:** Maps a job's `content_type` to the worker-queue task discriminator: `short`/`long` both collapse to `"video"`; `article`/`repo`/`document`/`link` pass through unchanged.
**Called from:** `retry_pending`, `retry_error` (`job_recovery.py`); `create_and_enqueue_job` (same file); `_cb_reprocess`, `_cmd_force` (`src/telegram/webhook.py`).
**Usage:** `task = task_for_content_type("short", default=None)` → `"video"`

#### `create_and_enqueue_job(chat_id, url, content_type, *, template=None, message_id=None, freestyle_prompt=None, skip_cache=False) -> dict`
**Does:** **The** shared job-creation entry point (ADR-0033) — owns cache/dedup and the create-row + enqueue-to-Redis write path. Deliberately does **not** notify Telegram or the HTTP caller — every ingest surface owns its own result notification on top of this.
**Called from:** `_create_link_job`, `_create_pipeline_job` (`src/api/jobs.py`); `_cmd_template`, `_cmd_addlink`, `_handle_user_template_shortcut`, `_enqueue_simple_job`, `_route_video` (`src/telegram/webhook.py`).
**Usage:** `job = await create_and_enqueue_job(chat_id, url, "article")`

### pdf_intake.py

Trust-boundary module (ADR-0029) for every byte a user-supplied PDF crosses on the way into the system — extracted specifically so it's unit-testable without a router or event loop.

#### `validate_pdf(data: bytes, name: str = "document.pdf") -> None`
**Does:** Raises `HTTPException(400)` if the file is over 20MB, doesn't end in `.pdf`, or doesn't start with the `%PDF` magic bytes.
**Called from:** `fetch_remote_pdf` (same file); directly from `src/api/parsed.py`'s upload route.
**Usage:** `validate_pdf(uploaded_bytes, filename)`

#### `assert_public_host(host: str | None) -> None`
**Does:** SSRF guard — resolves `host` and raises `HTTPException` (400 if unresolvable, 422 if any resolved address is non-public: loopback/private/link-local/cloud-metadata).
**Called from:** `fetch_remote_pdf` (same file).
**Usage:** `await assert_public_host(parsed_url.hostname)`

#### `fetch_remote_pdf(url: str) -> tuple[bytes, str]`
**Does:** The full remote-PDF intake pipeline: HTTPS+`.pdf`-extension check, SSRF check, then a streamed fetch with `follow_redirects=False` (redirects are TOCTOU/SSRF risk) and a hard 20MB early-abort, finishing with the same magic-byte check. Translates specific HTTP failure modes (401/403/404) into field-level 422s.
**Called from:** Upload-by-URL route in `src/api/parsed.py`.
**Usage:** `data, filename = await fetch_remote_pdf("https://example.com/doc.pdf")`

#### `read_capped_body(request: Request) -> bytes`
**Does:** Streams a raw request body with a hard cap (20MB+1 byte) so an oversized upload can't exhaust memory before `validate_pdf`'s size check runs.
**Called from:** Direct-upload route in `src/api/parsed.py`.
**Usage:** `data = await read_capped_body(request)`

### sheets.py

Consolidated-workbook writer (ADR-0013) — one fixed tab per content type inside a single Google Sheet.

#### `append_repo_row` / `update_repo_row`, `append_short_row`, `append_long_row`, `append_article_row` / `update_article_row`, `append_document_row` / `update_document_row`, `append_prd_row`
**Does:** One append/update pair per content type, each building its own fixed-column row and writing it via the shared `_append_row_logged`/`_update_row_logged` helpers (log success/failure, call `handle_google_refresh_error` on a revoked token instead of raising). All gated by `settings.export_blocked(chat_id)`.
**Called from:** Each processor's own sheets-write step: `_sheets_append_safe`/`_sheets_update_safe` (`repo.py`), `_sheets_task` (`article.py`, `document.py`), `_append_prd_sheet_row` (`prd.py`); `append_short_row`/`append_long_row` from `short_video.py`/`long_video.py` (module-alias calls, verified with grep).
**Usage:** `row_idx = await append_article_row(job, domain="example.com")`

## `src/utils/`

### logger.py

#### `configure_logging() -> None`
**Does:** One-time process-wide structlog setup — JSON output, ISO UTC timestamps, level from `settings.LOG_LEVEL`. Call once at process start.
**Called from:** Module-level in `src/main.py` and `src/worker.py`.
**Usage:** `configure_logging()` (call once, at startup)

#### `get_logger(name=None) -> structlog.stdlib.BoundLogger`
**Does:** Returns a structlog logger bound to `name` — the standard `log = get_logger(__name__)` pattern used at the top of nearly every module in the codebase.
**Called from:** Nearly every module in `src/`.
**Usage:** `log = get_logger(__name__)`

### google_token_crypto.py

#### `google_token_fernet(raw_key: str) -> Fernet`
**Does:** Derives a valid 32-byte Fernet key from an arbitrary-length `raw_key` string via SHA-256 + urlsafe-base64, so `GOOGLE_TOKEN_ENCRYPTION_KEY` in `.env` doesn't need to be a pre-formatted Fernet key. Raises `RuntimeError` if `raw_key` is empty.
**Called from:** `_fernet` (`src/services/google_tokens.py`), `_google_token_readable` (`src/config.py`).
**Usage:** `fernet = google_token_fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY)`

### background_tasks.py

#### `spawn_background(coro: Coroutine) -> asyncio.Task`
**Does:** `asyncio.create_task()` but keeps a strong module-level reference until the task finishes and logs any unhandled exception — works around the Python gotcha where a task with no retained reference can be silently garbage-collected mid-run. **Every** fire-and-forget call site in the codebase is expected to go through this instead of calling `asyncio.create_task` directly.
**Called from:** `run` (`short_video.py`, `repo.py`), `_deliver_prd` (`prd.py`), `_report_photo_links`, `_cmd_rebuild_graph`, `_handle_document_update`, `_handle_photo_update` (`src/telegram/webhook.py`).
**Usage:** `spawn_background(long_running_coroutine())`

### markdown.py

#### `build_transcript_markdown(title, channel, views, video_id, url, transcript) -> str`
**Does:** Formats the Phase-1 raw-transcript `.md` file body (header block + horizontal rule + transcript text) that gets uploaded to Drive before enrichment runs.
**Called from:** `run` in `src/processors/long_video.py` (verified with grep — don't confuse with the differently-scoped private `_build_transcript_markdown` in `short_video.py`).
**Usage:** `md = build_transcript_markdown(title, channel, views, video_id, url, transcript)`

#### `format_promise_gap_section(promise_gap: dict | None) -> list[str]`
**Does:** Renders the "unfulfilled promises / hidden value" analysis block as a list of message lines (returns `[]` if there's nothing to show).
**Called from:** `_build_enrichment_message` in `article.py` and `enrichment.py`.
**Usage:** `lines += format_promise_gap_section(job.get("promise_gap_parsed"))`

#### `format_tool_line(tool: dict) -> str`
**Does:** Renders one Gemini-extracted tool/product as an HTML bullet line for a Telegram message; `$`-prefixes stock/crypto symbols instead of `[type]`, and hyperlinks the name if a `url` is present.
**Called from:** `_tools_section` (`article.py`), `_build_enrichment_message` (`document.py`, `enrichment.py`).
**Usage:** `line = format_tool_line({"type": "tool", "name": "Redis", "url": "https://redis.io"})`

#### `build_enriched_links_message(links: list[dict]) -> str`
**Does:** Formats a mixed link list (some GitHub-enriched, some not) into one `🔗 Links Found:` Telegram section, sorting enriched GitHub links by stars+forks descending and rendering star/fork/language/age metadata inline for those.
**Called from:** `_report_photo_links` in `src/telegram/webhook.py`.
**Usage:** `text = build_enriched_links_message(enriched_links)`

### og_image.py

#### `extract_essential_og(markup: str, base_url=None) -> dict[str, str]`
**Does:** Single-pass HTML `<meta>` tag scan collecting a fixed "Essential OG collection" (`og:title`, `og:description`, `og:image`, etc.), resolving `og:image` to an absolute URL against `base_url` and rejecting non-http(s) schemes.
**Called from:** `extract_og_image_url` (same file).
**Usage:** `tags = extract_essential_og(html, base_url=final_url)`

#### `extract_og_image_url(markup: str, base_url=None) -> str | None`
**Does:** Convenience wrapper returning just the `og:image` value from `extract_essential_og`.
**Called from:** `get_link_preview` (`src/brain.py`), `fetch_og_image_url` (same file).
**Usage:** `image_url = extract_og_image_url(html, base_url)`

#### `fetch_og_image_url(url: str) -> str | None`
**Does:** Fetches a URL's HTML (via `fetch_public_html`, SSRF-guarded) and extracts its `og:image`, in one call.
**Called from:** `run` in `src/processors/article.py`.
**Usage:** `image_url = await fetch_og_image_url(article_url)`

### public_html.py

Hardened public-HTML/image fetching for any URL derived from user content (SSRF-safe: DNS-pinned connections, redirect revalidation, capped body size).

#### `fetch_public_html(url, *, client=None) -> PublicHtmlResult | None`
**Does:** Fetches a URL's HTML, pinning the TCP connection to a resolved public IP and re-validating every redirect hop (up to 3) against the same public-IP check — defends against DNS rebinding between the initial check and the actual request. Rejects non-HTML content types and caps the body at 128KB. Returns `None` on any failure (never raises).
**Called from:** `_fetch_meta`, `get_link_preview` (`src/brain.py`), `fetch_og_image_url` (`src/utils/og_image.py`).
**Usage:** `result = await fetch_public_html(url)` → `result.html`, `result.final_url`

#### `fetch_public_image(url, *, client=None) -> PublicImageResult | None`
**Does:** Same SSRF-hardened fetch pattern as `fetch_public_html` but for raster images (5MB cap, allowlisted MIME types only) — lets the dashboard proxy an og:image same-origin instead of hot-linking it.
**Called from:** Route handler in `src/api/brain.py` (lazy import inside the function body — missed by CodeGraph, verified with grep).
**Usage:** `img = await fetch_public_image(og_image_url)` → `img.content`, `img.content_type`

### ssrf.py

#### `resolve_public_host(host: str) -> list | None`
**Does:** `socket.getaddrinfo` off the event loop; returns `None` on DNS failure.
**Called from:** `assert_public_host` (`pdf_intake.py`), `_validate_public_https_url` (`webhook.py`), `is_public_host` (same file).
**Usage:** `infos = await resolve_public_host("example.com")`

#### `is_public_ip(ip_str: str) -> bool`
**Does:** `False` for loopback/private/link-local (including the `169.254.169.254` cloud-metadata address)/reserved/multicast/unspecified addresses.
**Called from:** `assert_public_host` (`pdf_intake.py`), `_validate_public_https_url` (`webhook.py`), `is_public_host` (same file).
**Usage:** `if not is_public_ip(addr): reject()`

#### `is_public_host(host: str) -> bool`
**Does:** Convenience combinator: `True` only if every address `host` resolves to is public. Not IP-pinned like `public_html.py`'s guard — the file's own docstring flags this as a known DNS-rebinding gap to upgrade if it ever becomes a real threat.
**Called from:** `webhook.py` (aliased as `_is_public_host` — verified with grep after CodeGraph under-reported this).
**Usage:** `if await is_public_host(hostname): proceed()`

### validators.py

#### `normalize_email(email: str) -> str | None`
**Does:** Lowercases/trims and validates against a simple `x@y.z` regex + RFC 5321 254-char length cap; returns `None` for anything invalid.
**Called from:** `set_email` (`src/api/auth.py`), `_invite_gate_allows` (`src/telegram/webhook.py`).
**Usage:** `email = normalize_email(" User@Example.COM ")`

#### `is_valid_domain_name(domain: str) -> bool`
**Does:** DNS-label-level validation, stricter than a bare regex-URL check — used for domain allowlist/ignorelist entries.
**Called from:** `_cmd_ignore`, `_cmd_allowlist` in `src/telegram/webhook.py`.
**Usage:** `if not is_valid_domain_name(user_input): reject()`

#### `detect_pipeline(url: str, extra_domains=frozenset()) -> Pipeline`
**Does:** **The** URL router for the whole ingestion system — classifies a URL into `short` / `long` / `repo` / `document` / `article` / `rejected` based on host+path pattern matching. This is the single source of truth other ad-hoc "is this a video URL" checks should call into rather than reimplementing.
**Called from:** `_create_pipeline_job`, `_github_repo_path`, `resolve_thumbnail` (`src/api/jobs.py`); numerous command handlers in `src/telegram/webhook.py`; `is_video_url` (same file).
**Usage:** `pipeline = detect_pipeline(url, extra_domains=chat_allowlist)`

#### `normalize_repo_url(url: str) -> str`
**Does:** Strips subpaths from a GitHub URL down to canonical `https://github.com/{owner}/{repo}`. Raises `ValueError` if fewer than 2 path segments.
**Called from:** `_create_pipeline_job`, `_github_repo_path` (`src/api/jobs.py`); several command handlers in `webhook.py`.
**Usage:** `canonical = normalize_repo_url("https://github.com/owner/repo/blob/main/README.md")`

#### `is_fetchable_url(url: str) -> bool`
**Does:** Minimum bar for `/addlink` (which bypasses `detect_pipeline` entirely) — just "is this an absolute http(s) URL with a hostname," keeping `javascript:`/`data:` garbage out of the jobs table.
**Called from:** `_create_link_job` (`src/api/jobs.py`), `_cmd_addlink` (`webhook.py`).
**Usage:** `if not is_fetchable_url(raw_input): reject()`

#### `is_video_url(text: str) -> bool`
**Does:** `True` if `detect_pipeline(text)` returns `short`/`long`/`article`. **Dead code — see top finding backend-#1.**
**Called from:** Nothing in `src/` — available to use directly (or a delete candidate).
**Usage:** `if is_video_url(candidate): ...`

#### `filter_vision_links(links: list[dict], extra_ignored=frozenset()) -> list[dict]`
**Does:** Drops links whose host is a "generic root" (bare `github.com`, `youtube.com` with <2 path segments, etc.) or a promo-subdomain pattern, plus anything in the caller's `extra_ignored` domain set, then deduplicates by `host + first-path-segment`.
**Called from:** `run` in `src/processors/short_video.py` (module-level import, called directly — verified with grep).
**Usage:** `links = filter_vision_links(vision_result["links"], extra_ignored=ignored_domains)`

#### `extract_description_links(description: str) -> list[dict]`
**Does:** Pulls meaningful links out of a YouTube description: finds every URL, cleans trailing punctuation/zero-width junk, filters out generic-root and promo links, and keeps only ones that are either a GitHub path or have a "meaningful" keyword in their description line.
**Called from:** `run` in `src/processors/long_video.py`; `extract_repo_candidates` in `src/services/repo_followup.py`.
**Usage:** `links = extract_description_links(video_description)`

#### `slugify(s: str, max_len=80) -> str`
**Does:** Lowercase, non-alphanumeric runs collapsed to `_`, leading/trailing `_` stripped, capped at `max_len`. Produces a URL-safe slug (**not** a readable filename — see `sanitize_filename_chars` for that; top finding backend-#5).
**Called from:** `run_auto_resend`, `run_prd` in `src/processors/prd.py`.
**Usage:** `slug = slugify("My Cool Title!")` → `"my_cool_title"`

#### `sanitize_filename_chars(text, *, extra_chars="", strip_extra="", max_len=80) -> str`
**Does:** Keeps only alnum/space/hyphen/underscore (+ caller-supplied `extra_chars`), trims, caps length — preserves case and spaces for a human-readable filename stem (unlike `slugify`). Returns `""` when nothing survives; callers must supply their own fallback.
**Called from:** `_sanitize_title` (`article.py`, `webhook.py`), `_safe_filename` (`document.py`), `_sanitize_filename` (`repo.py`).
**Usage:** `stem = sanitize_filename_chars(title) or "untitled"`

## Root (`src/`)

### database.py

Async SQLite (WAL mode) data-access layer — the whole app's persistence. ~122 symbols; only the non-trivial/public ones are called out below. Most of the rest are simple, self-explanatory single-table CRUD (`list_tags`/`get_tag`/`create_tag`, `list_spaces`/`create_space`, `create_context_blob`, …) — grep the function name directly, the SQL is short.

#### `generate_id() -> str`
**Does:** Generates the app-wide ID format `YYYYMMDD_HHMMSS_XXXXXXXX` (8 hex chars) used for both job IDs and Brain link IDs — sortable by creation time and collision-resistant.
**Called from:** `create_job`, `add_document_output`, `create_tag`, `create_user_template`, `create_space`, `create_context_blob` (all same file).
**Usage:** `new_id = generate_id()`

#### `init_db() -> None`
**Does:** Creates `data/jobs.db` if absent, applies `SCHEMA_SQL`, and runs the `_MIGRATIONS` ladder via `PRAGMA user_version` (fresh databases skip straight to schema-current). Also dedupes any pre-constraint duplicate `links.url` rows before a fresh schema install. **Not the same function as `brain.init_db()`** — see top finding backend-#2.
**Called from:** Startup path in `src/main.py`.
**Usage:** `await database.init_db()` (once, at startup)

#### `connection() -> AsyncIterator[aiosqlite.Connection]`
**Does:** The async context manager every other DB function opens a connection through — sets `row_factory=aiosqlite.Row` and `PRAGMA foreign_keys=ON`, closes on exit. Prefer this over opening `aiosqlite.connect` directly anywhere new DB code is added.
**Called from:** Nearly every write function in this file.
**Usage:** `async with database.connection() as conn: await conn.execute(...)`

#### `create_job(*, chat_id, url, content_type, message_id=None, template=None, freestyle_prompt=None) -> str`
**Does:** Inserts a new `pending` job row, returns its id. The low-level primitive `create_and_enqueue_job` (`src/services/jobs.py`) wraps for dedup+enqueue — prefer that unless you specifically need creation without enqueueing.
**Called from:** `create_and_enqueue_job` (`src/services/jobs.py`), `retry_error` (`job_recovery.py`).
**Usage:** `job_id = await database.create_job(chat_id=chat_id, url=url, content_type="short")`

#### `reset_job(job_id: str) -> None`
**Does:** Resets a job back to `pending`, nulling every result column and incrementing `attempt` — a full "run this job again from scratch" reset, distinct from the lighter-touch recovery retries in `job_recovery.py`.
**Called from:** Dashboard "force reprocess" route (`src/api/jobs.py`).
**Usage:** `await database.reset_job(job_id)`

#### `fetch_and_mark_stale_jobs(stale_minutes=10, *, chat_id=None, content_type=None) -> list[dict]`
**Does:** Finds jobs stuck in `processing`/`enriching` past the stale window, flips them to `error` (+ increments `attempt`), and returns the affected rows with their **pre-reset** status so callers can route per-state notifications. Runs once at worker startup (ADR-0010) and is reused by `job_recovery.retry_error`'s reap step.
**Called from:** `reap_stale_jobs` in `src/worker.py`; `retry_error` in `src/services/job_recovery.py`.
**Usage:** `reaped = await database.fetch_and_mark_stale_jobs(10, chat_id=chat_id)`

#### `find_recent_job_by_url(chat_id, url) -> dict | None`
**Does:** Looks up the most recent non-failed job for this chat+URL — the dedup check behind `create_and_enqueue_job`'s cache-hit path.
**Called from:** `create_and_enqueue_job` (`src/services/jobs.py`).
**Usage:** `cached = await database.find_recent_job_by_url(chat_id, url)`

#### `set_job_telegram_delivery(job_id, state) -> dict | None`
**Does:** Toggles whether a job's future output re-deliveries go to Telegram (`"off"`/`"on"` — `"retroactive"` is resolved at the API layer, not accepted here directly).
**Called from:** Document-parser delivery-toggle route in `src/api/parsed.py`.
**Usage:** `job = await database.set_job_telegram_delivery(job_id, "on")`

#### `get_brain_links_view(chat_id) -> dict` / `set_brain_links_view(chat_id, *, order, size) -> dict`
**Does:** Persists a user's preferred Brain-links table sort order/page size as a JSON blob in `user_settings`, validated against a fixed allowlist — invalid stored values silently fall back to defaults.
**Called from:** Brain-links view-preference route(s) in `src/api/brain.py`.
**Usage:** `view = await database.set_brain_links_view(chat_id, order="asc", size=50)`

### brain.py

The "Second Brain" semantic link graph: Gemini embeddings + NumPy cosine similarity, mirrored to Obsidian-style `.md` files in Drive.

*Note: `src/api/brain.py` defines route handlers with the **same names** (`get_graph`, `list_links`, `get_link_preview`, `search_links`, `rebuild_graph`) that thinly wrap these — don't confuse the two when grepping.*

#### `normalize_url(url: str) -> str`
**Does:** Canonicalizes a URL for graph-node identity by stripping query string, fragment, and trailing slash.
**Called from:** `ingest_links` (same file).
**Usage:** `canonical = normalize_url(raw_url)`

#### `init_db() -> None`
**Does:** Creates the `links` table and (if `GOOGLE_DRIVE_FOLDER_BRAIN` is set) does a Drive pre-flight check by uploading and immediately deleting a temp file — fails loudly at startup if Drive write access is broken. **Distinct from `database.init_db()`** — see top finding backend-#2.
**Called from:** Startup path in `src/main.py`.
**Usage:** `await brain.init_db()` (once, at startup)

#### `ingest_links(links: list[dict], topic: str, source_job_id: str) -> None`
**Does:** Fire-and-forget: normalizes and persists each link as a Brain graph node (new node, or bump `seen_count`/`last_seen` on an existing one), computing an embedding and rewriting its Obsidian `.md` file in Drive. Per-link failures are caught and logged individually so one bad link can't abort the batch.
**Called from:** `run` in `article.py`; `_deliver_prd` (`prd.py`); `_brain_ingest_safe` (`repo.py`); `_report_photo_links` (`webhook.py`).
**Usage:** `await brain.ingest_links(extracted_links, topic, source_job_id)`

#### `get_graph() -> dict[str, list[dict]]`
**Does:** Returns the full graph as `{nodes, edges}` for the dashboard's force-graph visualization — nodes are every non-cancelled link, edges are derived on-request from pairwise cosine similarity (no persisted edge table).
**Called from:** `GET /graph` route wrapper in `src/api/brain.py`.
**Usage:** `graph = await brain.get_graph()`

#### `list_links(limit=50, offset=0, q="", order="desc", viewer_chat_id=None) -> dict`
**Does:** Paginated/searchable Brain links listing — `q` does a case-insensitive substring match across url/title/description plus exact tag-name match.
**Called from:** `GET /links` route in `src/api/brain.py`.
**Usage:** `page = await brain.list_links(limit=25, q="redis", viewer_chat_id=chat_id)`

#### `get_link_preview(link_id: str) -> dict | None`
**Does:** Returns `{id, og_image_url}` for the Links table's hover/arrow-key preview panel, lazily resolving and caching `og_image_url` on first request.
**Called from:** Preview route in `src/api/brain.py`.
**Usage:** `preview = await brain.get_link_preview(link_id)`

#### `search_links(query: str, top_k=5) -> list[dict]`
**Does:** Embeds `query` and returns the top-k links by cosine similarity above `settings.BRAIN_MIN_SCORE`, capped at 20.
**Called from:** `_cmd_find` in `src/telegram/webhook.py`; `GET /search` route in `src/api/brain.py`.
**Usage:** `hits = await brain.search_links("redis caching patterns", top_k=5)`

#### `rebuild_graph() -> int`
**Does:** Recomputes related-links for every node and rewrites every node's Drive `.md` file from scratch. Guarded by a module-level `asyncio.Lock` — raises `RuntimeError("rebuild_in_progress")` if already running. Returns the node count processed.
**Called from:** `_do_rebuild` (`webhook.py`); `POST /rebuild` route in `src/api/brain.py`.
**Usage:** `count = await brain.rebuild_graph()`

#### `refresh_stale_links() -> None`
**Does:** The scheduled maintenance job — repairs any links with `NULL` embeddings and refreshes the oldest Drive `.md` files, batch size scaled to corpus size (capped at 500). Same rebuild-lock guard as `rebuild_graph`.
**Called from:** Registered directly with APScheduler in `src/main.py` — not called from application code, only the scheduler.
**Usage:** Not called manually; runs automatically Sun/Wed at 09:00.

### queue.py

Redis-backed task queue (`video_jobs` list) — the handoff between the API/webhook process and the worker process.

#### `enqueue(task: dict) -> None`
**Does:** Pushes a `{"task": ..., "job_id": ...}` envelope onto the Redis list; raises `ValueError` if either required key is missing.
**Called from:** Nearly every job-creation path (`create_and_enqueue_job`, `job_recovery.py`, `repo_followup.py`, `webhook.py`, `worker.py`).
**Usage:** `await queue.enqueue({"task": "article", "job_id": job_id})`

#### `dequeue() -> dict | None`
**Does:** Blocking pop with a 30s timeout; returns `None` on a normal idle timeout or a malformed envelope (logged). A real `ConnectionError` (Redis down) still propagates so the worker's retry/backoff path can react.
**Called from:** The worker's main loop in `src/worker.py`.
**Usage:** `task = await queue.dequeue()`

### templates.py

#### `PROMPT_TEMPLATES: dict[str, PromptTemplate]`
**Does:** The single source of truth for the 5 analysis templates (`summary`/`method`/`technical`/`review`/`narrative`) — each with its routing/matching keyword list and the extra JSON-schema instructions appended to the Gemini prompt for that template.
**Usage:** `tmpl = PROMPT_TEMPLATES["technical"]`

#### `score_template_match(text: str) -> dict[str, int]`
**Does:** Counts keyword hits per template against `text`, reading the same `trigger_patterns` table used for auto-routing — so routing and mismatch-validation can never silently diverge.
**Called from:** `validate_template_choice` (same file); also used by auto-detection code.
**Usage:** `scores = score_template_match(transcript_text)`

#### `validate_template_choice(template: str, transcript: str) -> str | None`
**Does:** For an explicit `/template` command, checks if the chosen template scores far below the best-matching one and returns a user-facing mismatch warning string if so, else `None`.
**Called from:** `run` in `src/processors/enrichment.py`.
**Usage:** `warning = validate_template_choice("method", transcript)`

### config.py

#### `Settings.export_blocked(chat_id: int | None) -> bool`
**Does:** The gate behind every Drive/Sheets write in the app — `True` means "must NOT write to the operator's shared workspace." A chat with its own readable Google token always passes; `None` chat_id (system/aggregate calls) always passes; otherwise blocks any chat that isn't the configured `OPERATOR_CHAT_ID`.
**Called from:** Every `append_*row`/`update_*row` in `sheets.py`; `upload_file`/`update_file`/`export_to_gdoc` in `drive.py`.
**Usage:** `if await settings.export_blocked(chat_id): return`

#### `Settings.parse_chat_ids(raw: str) -> tuple[int, ...]`
**Does:** Parses a comma-separated chat-ID string into a deduped int tuple, raising `ValueError` with the offending value on a bad entry.
**Called from:** `ops_chat_ids`, `ops_admin_chat_ids`, `ops_dev_chat_ids` properties (same class).
**Usage:** `ids = settings.parse_chat_ids("123,456,123")` → `(123, 456)`

---

# Frontend (`web/lib/`)

## `lib/hooks/`

#### `useDomainList(apiPath: string, label: string): { domains, loading, fetchError, addDomain, removeDomain }`
**Does:** Generic CRUD-list hook for a simple string-based allowlist/domain endpoint. Built on `useFetchList` for the initial GET, then does its own optimistic array update on add/remove instead of refetching.
**Called from:** `ControlsPage` in `web/app/(dashboard)/controls/page.tsx` (used 3x — one per domain-scoped list).
**Usage:** `const { domains, addDomain, removeDomain } = useDomainList('/api/controls/article-domains', 'Article domains')`

#### `useSpaceEdit(spaceId, space, onSaved): { editing, editName, setEditName, editColor, setEditColor, editError, editSaving, startEdit, cancelEdit, handleEditSave }`
**Does:** Owns the "rename/recolor a Space" inline-edit form state — open/close, field values seeded from the current space, save-to-API with a 409-name-collision-specific error message.
**Called from:** `web/app/(dashboard)/spaces/[id]/page.tsx` (3 usages).
**Usage:** `const edit = useSpaceEdit(spaceId, space, (updated) => setSpace(updated))`

#### `useSemanticSearch(): { query, setQuery, results, searchState, errorMessage, runSearch }`
**Does:** Drives the Second Brain semantic search box — holds the query string, calls `/api/brain/search`, and tracks a state machine (`idle | loading | results | empty | error`) so the UI can render each case distinctly.
**Called from:** `BrainPage` in `web/app/(dashboard)/brain/page.tsx`.
**Usage:** `const { query, setQuery, results, searchState, runSearch } = useSemanticSearch()`

#### `useSpaceContext(spaceId: string): { blobs, loading, blobError, setBlobError, addBlob, updateBlob, deleteBlob, reorderBlob, patchBlobName }`
**Does:** Manages the list of "context documents" (freeform text blobs) attached to a Space — full CRUD plus a two-item sort-order swap for reordering. Hand-rolls its own fetch/loading state rather than using `useFetchList`.
**Called from:** `ContextTab` in `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`.
**Usage:** `const { blobs, addBlob, reorderBlob } = useSpaceContext(spaceId)`
**Note:** Same "swap sort_order between two adjacent rows via `swapSortOrder`" pattern as `useSpaceUrls.reorderUrl` — near-duplicate reorder logic, different item types.

#### `useSpaceDetail(spaceId: string): { space, setSpace, fetchState }`
**Does:** Thin wrapper around `useFetchDetail` typed to the `SpaceDetail` shape — fetches one Space by id.
**Called from:** `web/app/(dashboard)/spaces/[id]/page.tsx` (3 usages).
**Usage:** `const { space, fetchState } = useSpaceDetail(spaceId)`

#### `useTemplateList(): { templates, loading, fetchError, createTemplate, deleteTemplate, updateTemplate }`
**Does:** CRUD for prompt Templates. Uses `useFetchList` + the shared `apiPost`/`apiPut`/`apiDelete` helpers from `fetch-utils.ts`; on create, keeps built-in templates pinned first and re-sorts user templates alphabetically.
**Called from:** `PromptsWorkspace` in `web/app/(dashboard)/prompts/page.tsx`.
**Usage:** `const { templates, createTemplate, deleteTemplate } = useTemplateList()`

#### `useGdocExport(spaceId: string): { trigger, status, error, errorCode, resultUrl }`
**Does:** Fires the "export this Space to a Google Doc" API call and tracks a 4-state status machine (`idle | exporting | done | error`), with a specific `drive_not_configured` error code so the UI can point the user at fallback .md/.txt/PDF export buttons instead of a generic error.
**Called from:** `ExportModal` in `web/components/ui/export-modal.tsx`.
**Usage:** `const { trigger, status, resultUrl, errorCode } = useGdocExport(spaceId)`

#### `useBackgroundFreshness(reload: () => Promise<void>): void`
**Does:** Silently refreshes feed data when the user switches back to the browser tab, plus a ~2-minute backstop poll while the tab stays visible. Calls a "silent" `reload` that never flips a `loading` flag, so there's no skeleton flash — built for the "send a link on Telegram, flip back to dashboard" flow. Pure side-effect hook, no return value.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx`.
**Usage:** `useBackgroundFreshness(reload)` — pass the `reload` (not `mountLoad`) function from `useFeedData`.

#### `useCreateSpace(onCreated: () => Promise<void>): { showForm, openForm, newName, setNewName, newColor, setNewColor, newIcon, setNewIcon, submitting, formError, handleCreate, resetForm }`
**Does:** Owns the "create a new Space" form — visibility toggle, field state, submit-to-API with a 409-specific "name exists" message, resets after success or cancel.
**Called from:** `SpacesWorkspace` in `web/app/(dashboard)/spaces/page.tsx`.
**Usage:** `const create = useCreateSpace(async () => reloadSpaces())`

#### `useRecovery(contentType: string, onRecovered): { summary, loading, acting, error, reload, retryPending, retryError, clearFailed }`
**Does:** Loads the stuck/failed-job recovery summary for the active content-type tab, and exposes three recovery actions that call `/api/jobs/recovery/*` and then re-run `onRecovered`. Uses ref-based "superseded" guards so a slow request for a tab the user has since left can't clobber the new tab's state.
**Called from:** `RecoveryPanel` in `web/components/feed/recovery-panel.tsx`.
**Usage:** `const { summary, retryPending, retryError, clearFailed } = useRecovery(contentType, reload)`

#### `useJobAnnotation(jobId, fetchState, disabled?): { annotation, loaded, handleSave }`
**Does:** Loads and auto-saves a job's freeform notes/annotation. Waits for the parent job fetch (`fetchState === 'ok'`) before loading its own data, and silently swallows save errors (best-effort auto-save, no error UI).
**Called from:** `JobDetailPage` in `web/app/(dashboard)/jobs/[id]/page.tsx`.
**Usage:** `const { annotation, handleSave } = useJobAnnotation(jobId, fetchState)`

#### `useJobDetail(jobId: string, restricted?: boolean): { job, fetchState }`
**Does:** Thin `useFetchDetail` wrapper typed to the full `JobDetail` shape. Switches between `/api/jobs/:id` and `/api/preview/jobs/:id` depending on restricted mode.
**Called from:** `web/app/(dashboard)/jobs/[id]/page.tsx` (3 usages).
**Usage:** `const { job, fetchState } = useJobDetail(jobId, restricted)`

#### `useFeedData(initialContentType?, restricted?): { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload }`
**Does:** The Feed page's core data hook — dual-mode: if the account has ≤1000 jobs it loads everything client-side and filters/derives stats in memory; past that threshold it flips into "server mode" and re-fetches filtered pages from the server on every filter change. Uses a monotonic request-id ref so a slow stale request can never overwrite a newer one. `reload()` is the "silent" refetch meant for background polling — it never touches the `loading` flag.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx` (3 usages).
**Usage:** `const { jobs, stats, ctFilter, setCtFilter, reload } = useFeedData('', restricted)`
**Note:** Most structurally complex hook in the survey (~200 lines, dual data-mode). Read it fully before touching Feed filtering/pagination rather than guessing from the name.

#### `useFuseSearch(jobs: JobSummary[]): { query, setQuery, displayedJobs }`
**Does:** Client-side fuzzy search over an already-loaded job list using Fuse.js (matches on `title`/`url`, threshold 0.4). Returns the full list unfiltered when the query is empty.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx`.
**Usage:** `const { query, setQuery, displayedJobs } = useFuseSearch(jobs)`

#### `useInFlightPolling(jobs: JobSummary[], reload: () => Promise<void>): void`
**Does:** Polls `reload` every 10s via `startPolling` as long as any job in the list is in a non-terminal status (`pending`, `processing`, `enriching`, `transcript_done`); stops automatically once everything settles.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx`.
**Usage:** `useInFlightPolling(jobs, reload)`

#### `useSpaceUrls(spaceId: string): { spaceUrls, allJobs, loading, addJob, removeUrl, reorderUrl }`
**Does:** Manages the list of jobs/URLs attached to a Space plus a separate fetch of the last 50 jobs generally (for an "add existing job to this space" picker). Includes an optimistic local swap on reorder before the API round-trip completes.
**Called from:** `UrlsTab` in `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx` (2 usages). No test coverage found.
**Usage:** `const { spaceUrls, addJob, reorderUrl } = useSpaceUrls(spaceId)`
**Note:** Duplicates the same reorder-via-`swapSortOrder` pattern as `useSpaceContext.reorderBlob`.

#### `useTagList(): { tags, loading, fetchError, createTag, deleteTag, updateTag }`
**Does:** CRUD for the global tag vocabulary (name/meaning/color/icon), used from Controls settings. Keeps the list alphabetically sorted after create/update.
**Called from:** `ControlsPage` in `web/app/(dashboard)/controls/page.tsx` (2 usages). No test coverage found.
**Usage:** `const { tags, createTag, deleteTag } = useTagList()`
**Note:** Structurally identical to `useTemplateList` and `useDomainList` — same `useFetchList` + `apiPost`/`apiPut`/`apiDelete` CRUD shape, different endpoint/shape.

#### `useLinksTable({ enabled }): { query, setQuery, view, viewLoaded, updateView, toggleOrder, data, state, message, page, setPage, jumpPage, setJumpPage, submitJump, pageCount, currentPage, start, end, hasPrevious, hasNext, selectedLinkId, selectLink, hoverLink, cancelHover, selectAdjacent, preview, previewState }`
**Does:** The big one — owns everything for the Links tab: debounced search, sort/page-size view preference (persisted server-side via GET+PUT), pagination math, and a hover/click-driven preview panel (with per-link-id caching so a re-selected row never re-fetches). `enabled` lets the parent mount it inert until the tab is actually active.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx`.
**Usage:** `const table = useLinksTable({ enabled: activeTab === 'links' })`
**Note:** Also exports `LINKS_PAGE_SIZES` (`[25, 50, 100]`) and `UseLinksTableResult`. Largest/most stateful hook in the survey (~260 lines) — read it directly before extending.

#### `useVisualViewport(active: boolean): { centerY: number | null; height: number | null }`
**Does:** Tracks the mobile *visual* viewport's center point and height (not the layout viewport), so a modal/dialog can recenter itself above an on-screen software keyboard instead of being pinned to the middle of a shrunken viewport. Returns nulls when inactive, on the server, or when `window.visualViewport` isn't available.
**Called from:** `DialogContent` in `web/components/ui/dialog.tsx`.
**Usage:** `const { centerY, height } = useVisualViewport(dialogOpen)`

#### `useJobTags(jobId, fetchState, disabled?): { jobTags, allTags, refetchTags, toggleTag, createTag }`
**Does:** Loads a job's attached tags plus the full tag vocabulary, and wraps attach/detach/create through the shared `useTagAttachment`. Waits for `fetchState === 'ok'` before fetching, like `useJobAnnotation`.
**Called from:** `JobDetailPage` in `web/app/(dashboard)/jobs/[id]/page.tsx` (2 usages). No test coverage found.
**Usage:** `const { jobTags, allTags, toggleTag, createTag } = useJobTags(jobId, fetchState)`

#### `useLinkTags(linkId: string, initialTags?: TagSummary[]): { linkTags, allTags, toggleTag, createTag }`
**Does:** Same shape as `useJobTags` but for Brain links, with one extra optimization: the tag vocabulary fetch is a module-level shared promise so the ~100 tag-cluster instances that can mount on one 50-row links table share a single in-flight request instead of each firing its own.
**Called from:** `LinkTagCluster` in `web/components/feed/links-table.tsx`. CodeGraph's index showed zero callers — confirmed stale via grep; it is genuinely used.
**Usage:** `const { linkTags, allTags, toggleTag, createTag } = useLinkTags(link.id, link.tags)`

#### `useReducedMotion(): boolean`
**Does:** Tracks `prefers-reduced-motion` via `matchMedia`, defaulting to `true` (motion off) until the media query resolves client-side — a safe-by-default choice so no animation flashes before the effect runs.
**Called from:** Widely used — `BrainGraph`, `AppSlot`/`CountUp`/`DemoVideo`/`HeroGradient` (`web/components/landing/`), `GoogleConnectedAvatar` (`web/components/shell/sidebar.tsx`), `DevPersonaSwitch`.
**Usage:** `const reduced = useReducedMotion(); if (!reduced) animate();`

#### `useTagAttachment({ path, itemLabel, refetchTags, refetchAll, disabled? }): { toggleTag, createTag }`
**Does:** Shared attach/detach/create-and-attach mutation logic for any `.../<itemId>/tags[/<tagId>]`-shaped endpoint. Callers own their own fetch/caching strategy for reading tags; this hook only wraps the POST/DELETE mutation calls both share. Includes an SSRF guard (`sameOriginPath`) that throws if the caller-supplied `path` isn't a relative same-origin path.
**Called from:** `useJobTags`, `useLinkTags` — internal hook-of-hooks, not called directly from components.
**Usage:** `const { toggleTag, createTag } = useTagAttachment({ path: (tagId) => \`/api/jobs/${id}/tags${tagId ? '/' + tagId : ''}\`, itemLabel: 'job', refetchTags, refetchAll })`

#### `useSpaceList(): { spaces, loading, error, reload }`
**Does:** Thin `useFetchList` wrapper for the Spaces index (`/api/spaces`), renaming `fetchError` to `error` for its consumer.
**Called from:** `SpacesWorkspace` in `web/app/(dashboard)/spaces/page.tsx`. CodeGraph showed zero callers — confirmed stale via grep; genuinely used.
**Usage:** `const { spaces, loading, reload } = useSpaceList()`

## `lib/` (root)

#### `startPolling(fetchFn, isIdleFn, intervalMs = 10000): () => void`
**Does:** Generic setInterval-style poller: stops entirely once `isIdleFn()` returns true, and skips (but keeps scheduling) any tick while the browser tab is hidden, so polling pauses in background tabs and resumes on the next natural tick. Returns a cancel function.
**Called from:** `useInFlightPolling` in `web/lib/hooks/useInFlightPolling.ts`.
**Usage:** `const cancel = startPolling(reload, () => allDone, 10_000); // later: cancel()`

#### `spaceIcon(name: string | undefined): IconCmp`
**Does:** Resolves a stored icon-name string (e.g. `"folder"`, `"rocket"`) to its Lucide icon component, falling back to `Folder` for an unknown/missing name. Also exports `SPACE_ICONS` (the full curated list of 20 name+Icon pairs), the single source of truth shared by the icon picker and the space card — must be kept in sync with the backend's `SpaceIcon` Literal in `src/api/spaces.py`.
**Called from:** `SpaceCard` in `web/components/spaces/space-card.tsx` (2 usages).
**Usage:** `const Icon = spaceIcon(space.icon); <Icon className="h-4 w-4" />`

#### `job-detail-utils.ts` — job-detail field rendering/copy/markdown helpers
**Does (as a group):** Defines which fields render for which job content-type (`ENRICHMENT_FIELDS` for long/article/repo, `SHORT_FIELDS` for short-pipeline jobs) and how to turn each field's raw value into copy-pasteable text or a full Markdown export of the job.
- `jobScopeQuery(scope)` — builds the `content_type`/`status` query-param object the job-card link and the detail page's "adjacent job" lookup share, so the Feed's active filter scope survives navigation into a job and back.
- `buildJobHref(id, scope)` — wraps `jobScopeQuery` into a Next.js `{ pathname, query }` href object. Called from `JobCard`/`PreviewCard`.
- `parseLinks(raw: string): JobLink[]` — parses the short-pipeline job's JSON "links found" blob into typed objects, dropping anything that isn't a valid `http(s)://` URL.
- `linksToMarkdown(raw: string): string` — renders `parseLinks` output as a Markdown bullet list.
- `splitPipes(value: string): string[]` — splits a field value that's either a JSON array (repo jobs) or a `' | '`-joined string (video jobs) into a clean string array — handles two different backend serialization conventions transparently.
- `humanizeKey(key: string): string` — snake_case → Title Case for field labels.
- `isEmpty(value: unknown): boolean` — a "falsy-for-display-purposes" check used to skip rendering empty fields.
- `objectToInline`, `arrayToMarkdown`, `objectToMarkdown` — a small recursive JSON→Markdown renderer trio for the `template_analysis` field's arbitrary nested JSON shape.
- `templateAnalysisToMarkdown(raw: string): string` — entry point that JSON-parses `template_analysis` and renders it via `objectToMarkdown`, falling back to the raw string if it isn't valid JSON.
- `fieldCopyText(value, render): string` — dispatches to the right renderer (`list`/`json`/`links`/`text`) for the "copy field" button.
- `buildMarkdown(job: JobDetail): string` — assembles the full job into one Markdown document — powers the "Export as Markdown" action.
**Called from (as a group):** `web/app/(dashboard)/jobs/[id]/page.tsx` (`FieldBody`, `FieldCard`, `JobHeader`, `JobActionsBar`, `JsonValue`, `JsonObject`), plus `JobCard`/`PreviewCard` in `web/components/feed/`.
**Usage:** `const md = buildMarkdown(job); navigator.clipboard.writeText(md)`

#### `fetchAuthStatus(cookieHeader: string): Promise<'approved' | 'unapproved' | 'unreachable'>` (`restricted/server.ts`)
**Does:** Server-side check of the current session's approval status against `/api/auth/me` on the backend, with a 3s timeout. Distinguishes a definitive "not approved" from "couldn't even reach the backend" so callers can choose a safe default for the latter.
**Called from:** `isRestrictedRequest` (same file) — internal to the restricted-mode gate.
**Usage:** `const status = await fetchAuthStatus(request.headers.get('cookie') ?? '')`

#### `isRestrictedRequest({ hasPreviewCookie, hasSession, cookieHeader }): Promise<boolean>` (`restricted/server.ts`)
**Does:** The actual gate that decides whether a dashboard request should render in Restricted (read-only preview) mode. A preview cookie alone isn't authoritative — an approved real session always outranks a stale cookie, and an unreachable backend fails closed to restricted (grants less access, not more).
**Called from:** `DashboardLayout` in `web/app/(dashboard)/layout.tsx`.
**Usage:** `const restricted = await isRestrictedRequest({ hasPreviewCookie, hasSession, cookieHeader })`

#### `design-tokens.ts` — `statusColors`
**Does:** A 4-entry hex-color map (`processing`/`pending`/`done`/`error`) mirroring the Tailwind/DESIGN.md semantic tokens, for runtime consumers that need a raw color value instead of a CSS class (e.g. canvas/SVG rendering).
**Called from:** `web/components/shell/sidebar.tsx`.
**Usage:** `<circle fill={statusColors[job.status]} />`

#### `extractSharedUrl(shareUrl: string | null, shareText: string | null): string | null` (`share-target.ts`)
**Does:** Pulls a usable URL out of a Web Share Target GET request. Prefers `share_url` if it's a valid http(s) URL; otherwise scans `share_text` for an embedded URL (common on Android, which often puts the shared link in the text field) and trims trailing sentence punctuation / unbalanced closing parens.
**Called from:** `FeedPageContent` in `web/app/(dashboard)/feed/page.tsx` (handles the PWA "Share to Ownix" entry point).
**Usage:** `const url = extractSharedUrl(searchParams.get('share_url'), searchParams.get('share_text'))`

#### `fetch-utils.ts` — shared fetch/CRUD primitives
**Does (as a group):** The foundational data-fetching layer nearly every other hook in this survey builds on.
- `useFetchList<T>(url, errorLabel)` — generic "GET a JSON array" hook with abort-on-unmount and a request-generation guard against stale responses clobbering fresher ones. Powers `useDomainList`, `useTemplateList`, `useTagList`, `useSpaceList`.
- `useFetchDetail<T>(url)` — generic "GET a single JSON resource" hook that maps HTTP status to a `FetchState` (`'loading' | 'ok' | 'not_found' | 'forbidden' | 'error'`, treating both 401 and 403 as `'forbidden'`) and resets state on URL change. Powers `useSpaceDetail`, `useJobDetail`.
- `apiPost<T>(url, body, fallback?)` / `apiPut<T>(url, body, fallback?)` / `apiDelete(url, fallback?)` — POST/PUT/DELETE helpers that parse a server `detail` error message on failure. Power the create/update/delete flows in `useTemplateList`, `useTagList`, `useDomainList`.
- `swapSortOrder(urlA, newOrderA, urlB, newOrderB)` — fires two parallel PATCH requests to swap two rows' `sort_order` values; the shared primitive behind every "move item up/down" reorder feature. Used by `useSpaceContext.reorderBlob` and `useSpaceUrls.reorderUrl`.
**Usage:** `const { data: tags, loading, reload } = useFetchList<Tag>('/api/controls/tags', 'tags')`
**Note:** Check here first before writing any new "fetch a list" or "fetch one thing" hook.

#### `restricted/context.tsx` — `useRestrictedMode()` / `RestrictedModeProvider`
**Does:** React context exposing whether the current view is in read-only Restricted mode, plus `showRestrictedToast(body?)` — a helper that shows a temporary (3.6s) "Restricted mode on — sign in to unlock actions" toast for any component nudging an unauthenticated preview visitor toward signing in.
**Called from:** Very widely used — `DocParserPage`, `PromptsPage`, `SpacesPage`, `ControlsPage`, `AppHeader`, `RestrictedIntroModal`, `FeedPageContent`, `JobHeader`, `JobDetailPage`, `SubmitJobProvider`, `GoogleStatusProvider`, `DevPersonaSwitch` (11 distinct call sites). `RestrictedModeProvider` is mounted once in `web/app/(dashboard)/layout.tsx`.
**Usage:** `const { restricted, showRestrictedToast } = useRestrictedMode(); if (restricted) { showRestrictedToast(); return; }`

## `lib/mocks/` (MSW demo-mode infrastructure)

Brief coverage — this is test/demo scaffolding, not app logic.

#### `startWorker(): Promise<unknown>` (`mocks/browser.ts`)
**Does:** Boots the MSW browser worker for `NEXT_PUBLIC_API_MOCK=1` demo mode. Idempotent (guards against React StrictMode's double-invoke or Fast Refresh calling `start()` twice). Fetches `/seed.json` at runtime rather than importing it, so the snapshot never enters the production bundle.
**Called from:** `MockProvider` in `web/components/shell/mock-provider.tsx`.
**Usage:** `useEffect(() => { startWorker(); }, [])`

#### `makeHandlers(seed: Seed): RequestHandler[]` (`mocks/handlers.ts`)
**Does:** Builds the full set of MSW request handlers that fake every dashboard API endpoint from a seeded in-memory dataset; mutations persist for the browser session only. Also hardcodes two special-cased mock document jobs with realistic sample content for the doc-parser demo.
**Called from:** `startWorker` (`mocks/browser.ts`).
**Usage:** `const worker = setupWorker(...makeHandlers(seedData))`

---

## See also

- `MODULE_MAP.md` — the orchestration layer this file deliberately skips (processors, api routes, telegram handlers).
- `CAPABILITY_MAP.md` — top-down capability → owning module lookup.
- `TECHSTACK.md` — why each external dependency was chosen.

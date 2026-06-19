# vig — Module Map

**Generated:** 2026-05-22 · **Refreshed:** 2026-06-18 (post document pipeline, GCS storage, job recovery, short-video transcript tail)  
Code-level reference: every `src/` module, what it owns, and how modules call each other.

---

## Entry Points

| Module | Role |
|---|---|
| `src/main.py` | FastAPI app — wires `webhook` router + `brain_router`, calls `database.init_db()` + `brain.init_db()` on startup, registers Telegram webhook URL, starts APScheduler for `brain.refresh_stale_links` (Sun/Wed 09:00) |
| `src/worker.py` | Background worker — dequeues task envelopes from Redis, dispatches to processors; runs `prd.reaper()` + `prd.reaper_intent()` on startup to un-stick stale `generating` jobs |

---

## Inbound Path (Telegram → System)

```
Telegram POST /webhook
  └─ telegram/webhook.py  (_handle_callback | _dispatch_slash | _handle_awaiting_intent | _handle_awaiting_freestyle | normal URL path)
       ├─ utils/validators.py   detect_pipeline(url, extra_domains)  → "short" | "long" | "article" | "rejected"
       ├─ database.py           create_job(), get_job(), set_chat_state(), get_chat_state(), list_allowed_domains()
       └─ queue.py              enqueue({task, job_id})
```

**Callback actions dispatched from webhook:**

| Callback prefix | Action |
|---|---|
| `gemini_yes:` | enqueue `enrichment` |
| `prd_auto:` / `prd_retry_auto:` | enqueue `prd_auto` or `prd_auto_resend` |
| `prd_build_spec:` | show 2-button sub-menu (🤖 auto / ✍️ intent) |
| `prd_intent_prompt:` | arm `chat_state` (mode=`awaiting_intent`) |
| `prd_retry_intent:` | enqueue `prd_intent` |
| `enrichment_retry:` | enqueue `enrichment` |
| `reprocess:` | create a fresh job from the orphaned job's URL + enqueue `video` (startup-recovery retry, ADR-0010) |
| `gemini_no:` | mark job `done` (skip enrichment) |
| `template_freestyle:` | arm `chat_state` (mode=`awaiting_freestyle`, job_id) — used by article ✍️ Freestyle button and long-video template picker |

**Dispatch tables (#25/#27):** `_handle_callback` splits on the first `:` and looks the prefix up in `_CALLBACK_TABLE`; slash commands route through `_dispatch_slash` → `_SLASH_TABLE` (template commands populated from `PROMPT_TEMPLATES` at import). Handlers receive a `CallbackCtx` / `SlashCtx` and never parse the raw string themselves.

---

## Queue Layer

```
queue.py  (Redis list "video_jobs")
  ├─ enqueue({task, job_id})   lpush
  └─ dequeue()                 brpop (30 s blocking)
```

**Task discriminators:** `video` | `article` | `repo` | `enrichment` | `prd_auto` | `prd_auto_resend` | `prd_intent` | `document`

---

## Worker → Processor Dispatch

```
worker.py._dispatch()
  ├─ "video"           → job.content_type == "short" → processors/short_video.py
  │                    → job.content_type == "long"  → processors/long_video.py
  ├─ "article"         → processors/article.py
  ├─ "enrichment"      → processors/enrichment.py
  ├─ "document"        → processors/document.py
  ├─ "prd_auto"        → processors/prd.py  run_auto()
  ├─ "prd_auto_resend" → processors/prd.py  run_auto_resend()
  └─ "prd_intent"      → processors/prd.py  run_intent()
```

---

## Processors

| Module | Inputs | Key services used |
|---|---|---|
| `processors/short_video.py` | job (short) | `frames`, `gemini` (Vision), `brave`, `drive`, `sheets`; template path also uses `transcript`, `analysis`, `enrichment`, `brain` |
| `processors/long_video.py` | job (long) | `transcript`, `drive`, `sheets`, `analysis`, `templates`, `validators`, `brain` (ingest_links). Phase 1 only — enrichment runs as a separate `enrichment` task |
| `processors/enrichment.py` | job after `transcript_done` | `gemini_client` (text gen), `templates`, `validation` |
| `processors/prd.py` | job with enrichment done | `gemini_client` (text gen), `drive`, `sheets`, `brain` (ingest_links), `telegram/sender` |
| `processors/article.py` | job (article) | `jina` (fetch_markdown), `database` (markdown_cache), `gemini_client` (text gen), `sheets` (append/update article row), `brain` (ingest_links), `telegram/sender` |
| `processors/document.py` | job (document) | `storage` (GCS download/upload), `parse` (liteparse PDF extraction), `gemini_client` (text gen), `database`, `telegram/sender` |

---

## Services (I/O Wrappers)

| Module | Wraps |
|---|---|
| `services/gemini_client.py` | **Central text-generation client** — free → paid key fallback, `generate(prompt, model, schema)`, raises `GeminiUnavailableError`. Used by enrichment, prd, brain, and `gemini.resolve_tool_urls` (#23/#26) |
| `services/gemini.py` | Gemini **Vision** for short-video frames (`call_gemini_vision`) + `resolve_tool_urls` (URL-resolution prompt, delegates text gen to `gemini_client`) |
| `services/gemini_photo.py` | Gemini Vision — verbatim-grounded photo link extraction |
| `services/github.py` | GitHub REST API client + Redis cache (`github_meta:{owner}/{repo}`, TTL 24h) for photo-pipeline repo enrichment (#21) |
| `services/frames.py` | Frame extraction for short videos (transcript sidecar) |
| `services/transcript.py` | Transcript sidecar client (`/transcript`, `/metadata`) |
| `services/drive.py` | Google Drive file upload |
| `services/sheets.py` | Google Sheets row write |
| `services/brave.py` | Brave Search — link verification for short-video Vision links |
| `services/jina.py` | Jina Reader API client — `fetch_markdown(url) → (title, body)`; optional `JINA_API_KEY` Bearer auth; raises `JinaFetchError` on HTTP errors |
| `services/google_auth.py` | Shared Google credential builder — OAuth refresh token (personal) or service-account fallback; `prefer_service_account` flag for GCS |
| `services/job_recovery.py` | Dashboard-triggered job recovery orchestration — stale job detection, re-enqueue, batch retry/cancel for the web recovery panel |
| `services/storage.py` | GCS content-addressed blob store — `upload`/`download`/`exists` keyed by SHA-256; prefixes `documents/` and `parsed/`; sync SDK wrapped in `asyncio.to_thread` |
| `services/parse.py` | liteparse PDF text extraction — `parse_pdf(bytes) → str`; raises `ParseError`; sync CPU-bound work wrapped in `asyncio.to_thread` |

---

## Second Brain

```
brain.py  (SQLite `links` table + Google Drive .md files)
  ├─ ingest_links()          ← short_video, long_video, prd processors + photo pipeline (webhook)
  ├─ search_links()          ← /find slash command + GET /links/search
  ├─ rebuild_graph()         ← /rebuild-graph slash command + POST /links/rebuild
  └─ refresh_stale_links()   ← APScheduler (Sun/Wed 09:00)

api.py  (brain_router, prefix=/links)
  ├─ GET  /links/search  → brain.search_links()
  └─ POST /links/rebuild → brain.rebuild_graph()
```

---

## Storage

| Store | Used for |
|---|---|
| SQLite `jobs` table | Job lifecycle, transcript, AI enrichment fields, PRD slots, `sheets_row_id` for article in-place row updates |
| SQLite `links` table | Second Brain semantic link graph |
| SQLite `allowed_domains` table | Per-chat article domain allowlist (`/allowlist` family) |
| SQLite `markdown_cache` table | Jina Reader response cache keyed by URL; no TTL — `/force` is the invalidation path |
| SQLite `chat_state` table | `awaiting_intent` / `awaiting_freestyle` mode per chat (10-min TTL) |
| Redis `video_jobs` list | Task envelope queue |
| Redis `photo_batch_*` keys | Photo batch session state per chat |
| Google Cloud Storage | Content-addressed document blobs: `documents/<sha>.pdf`, `parsed/<sha>.txt` |
| Google Drive | Enrichment docs, PRD docs, Brain `.md` nodes (article + document pipelines have **no** Drive upload) |
| Google Sheets | Per-job summary rows: `YouTube Transcript Index`, `Short Video Analysis`, `Article Analysis`, `Repo Analysis`, `mini PRD` |

---

## Utilities / Cross-cutting

| Module | Role |
|---|---|
| `config.py` | `Settings` (pydantic-settings, reads `.env`) — single source of all env vars |
| `database.py` | aiosqlite wrapper; schema DDL; all job + chat_state CRUD |
| `telegram/sender.py` | `send_message`, `send_inline_keyboard`, `send_force_reply`, `download_photo`, `answer_callback_query` |
| `utils/validators.py` | `detect_pipeline(url, extra_domains)` — URL routing (short / long / article / rejected); `ARTICLE_DEFAULT_DOMAINS` frozenset; `extract_description_links()`, `slugify()` |
| `utils/markdown.py` | `build_links_message()` + `build_enriched_links_message()` (GitHub repo metadata, `_humanize_age`) for photo pipeline results |
| `utils/logger.py` | structlog configuration |
| `analysis.py` | `extract_key_phrases()` — feeds the enrichment KEY CONTEXT block |
| `templates.py` | `PROMPT_TEMPLATES` registry (summary/method/technical/review/narrative); drives slash commands + enrichment `extra_instructions` |
| `validation.py` | `validate_template_choice()` — template/transcript mismatch warning |

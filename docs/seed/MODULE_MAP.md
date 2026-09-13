# vig — Module Map

**Generated:** 2026-05-22 · **Refreshed:** 2026-07-18 (post web dashboard, Ownix transition, ops bot, link identity/tags)
Code-level reference: every `src/` module, what it owns, and how modules call each other.

---

## Entry Points

| Module | Role |
|---|---|
| `src/main.py` | FastAPI app — wires the Telegram webhook router, the ops-bot webhook (`/webhook/ops`), the dashboard API routers (`src/api/`), and the session middleware (`src/auth/`); calls `database.init_db()` + `brain.preflight()` on startup, registers Telegram webhook URL, starts APScheduler for `brain.refresh_stale_links` (Sun/Wed 09:00) |
| `src/worker.py` | Background worker — dequeues task envelopes from Redis, dispatches to processors; runs `prd.reaper()` + `prd.reaper_intent()` on startup to un-stick stale `generating` jobs |

---

## Inbound Paths

### Telegram → System

```
Telegram POST /webhook
  └─ telegram/webhook.py  (_handle_callback | _dispatch_slash | _handle_awaiting_intent | _handle_awaiting_freestyle | normal URL path | inline photo pipeline)
       ├─ utils/validators.py   detect_pipeline(url, extra_domains)  → "short" | "long" | "repo" | "document" | "article" | rejected
       ├─ services/jobs.py      create_and_enqueue_job()  — shared dedup + create + enqueue core (ADR-0033)
       ├─ database.py           get_job(), set_chat_state(), get_chat_state(), list_allowed_domains()
       └─ queue.py              enqueue({task, job_id})
```

Photo messages are processed inline in the webhook — never queued (ADR-0003); multi-image sends are auto-batched via Telegram `media_group_id` (ADR-0024). Result messages carry an **Open in Dashboard** button (#388).

### Dashboard → System

```
Next.js (web/) → /api/*  (session cookie, src/auth/middleware.py)
  ├─ api/jobs.py       list / stats / detail / annotations / tags — POST /api/jobs also calls services/jobs.create_and_enqueue_job (ADR-0032/0033)
  ├─ api/brain.py      /api/brain/search (same brain.search_links as /find), /api/brain/rebuild
  ├─ api/spaces.py     Spaces CRUD + URLs tab + context blobs + export
  ├─ api/templates.py  user-defined enrichment templates (dash-sigil `-name`, ADR-0019)
  ├─ api/controls.py   allowed/ignored domains + tags CRUD
  ├─ api/parsed.py     Doc Parser page API (ADR-0029) — pdf_intake + parse + document_outputs
  ├─ api/preview.py    Restricted-mode read-only preview endpoints (ADR-0035)
  ├─ api/auth.py       Telegram Login Widget → session cookie; logout; me
  └─ api/google_oauth.py  per-user Google OAuth connect flow (ADR-0030)
```

### Ops bot → System

```
Telegram POST /webhook/ops
  └─ services/ops_bot.py   ADR-0036 — user/invite administration commands for the operator
       └─ services/invite_notifications.py  invite-gate notifications shared by Telegram + web auth flows
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
| `repo_followup:` | create a repo-analysis job for a GitHub URL extracted from another result (`services/repo_followup.py`) |

**Dispatch tables (#25/#27):** `_handle_callback` splits on the first `:` and looks the prefix up in `_CALLBACK_TABLE`; slash commands route through `_dispatch_slash` → `_SLASH_TABLE` (template commands populated from `PROMPT_TEMPLATES` at import). Handlers receive a `CallbackCtx` / `SlashCtx` and never parse the raw string themselves.

---

## Queue Layer

```
queue.py  (Redis list "video_jobs")
  ├─ enqueue({task, job_id})   lpush
  └─ dequeue()                 brpop (30 s blocking)
```

**Task discriminators:** `video` | `article` | `repo` | `document` | `enrichment` | `prd_auto` | `prd_auto_resend` | `prd_intent`

---

## Worker → Processor Dispatch

```
worker.py._dispatch()
  ├─ "video"           → job.content_type == "short" → processors/short_video.py
  │                    → job.content_type == "long"  → processors/long_video.py
  ├─ "article"         → processors/article.py
  ├─ "repo"            → processors/repo.py
  ├─ "document"        → processors/document.py
  ├─ "enrichment"      → processors/enrichment.py
  ├─ "prd_auto"        → processors/prd.py  run_auto()
  ├─ "prd_auto_resend" → processors/prd.py  run_auto_resend()
  └─ "prd_intent"      → processors/prd.py  run_intent()
```

---

## Processors

| Module | Inputs | Key services used |
|---|---|---|
| `processors/short_video.py` | job (short) | `frames`, `gemini` (Vision), `brave`, `drive`, `sheets`; guaranteed transcript tail (ADR-0020) also uses `transcript`, `analysis`, `enrichment`, `brain` |
| `processors/long_video.py` | job (long) | `transcript`, `drive`, `sheets`, `analysis`, `templates`, `validators`, `brain` (ingest_links). Phase 1 only — enrichment runs as a separate `enrichment` task |
| `processors/enrichment.py` | job after `transcript_done` | `gemini_client` (text gen), `templates`, `validation` |
| `processors/prd.py` | job with enrichment done | `gemini_client` (text gen), `drive`, `sheets`, `brain` (ingest_links), `telegram/sender` |
| `processors/article.py` | job (article) | `jina` (fetch_markdown), `database` (markdown_cache), `gemini_client` (text gen), `sheets` (append/update article row), `brain` (ingest_links), `telegram/sender` |
| `processors/repo.py` | job (repo) | `github` (REST bundle: README + file tree + manifests, ADR-0014/0021), `gemini_client` (structured analysis), `drive`, `sheets` (Repo Analysis tab), `brain`, `telegram/sender` |
| `processors/document.py` | job (document) | `storage` (GCS download/upload), `parse` (liteparse PDF extraction), `gemini_client` (text gen), `database`, `telegram/sender` |

---

## Services (I/O Wrappers)

| Module | Wraps |
|---|---|
| `services/gemini_client.py` | **Central text-generation client** — free → paid key fallback, `generate(prompt, model, schema)`, raises `GeminiUnavailableError`. Used by enrichment, prd, brain, and `gemini.resolve_tool_urls` (#23/#26) |
| `services/gemini.py` | Gemini **Vision** for short-video frames (`call_gemini_vision`) + `resolve_tool_urls` (URL-resolution prompt, delegates text gen to `gemini_client`) |
| `services/gemini_photo.py` | Gemini Vision — verbatim-grounded photo link extraction |
| `services/jobs.py` | **Shared job creation core** (ADR-0033) — `create_and_enqueue_job()` owns dedup + create + enqueue for its three callers (Telegram webhook, dashboard `POST /api/jobs`, repo follow-up) |
| `services/github.py` | GitHub REST API client + Redis cache (`github_meta:{owner}/{repo}`, TTL 24h) — repo pipeline bundle + photo-pipeline repo enrichment (#21) |
| `services/repo_followup.py` | Offers extracted GitHub repositories as follow-up repo-analysis jobs |
| `services/frames.py` | Frame extraction for short videos (transcript sidecar) |
| `services/transcript.py` | Transcript sidecar client (`/transcript`, `/metadata`) |
| `services/drive.py` | Google Drive file upload + in-place update |
| `services/sheets.py` | Google Sheets append (5 tabs, tab-qualified ranges) + article in-place row update |
| `services/brave.py` | Brave Search — link verification for short-video Vision links |
| `services/jina.py` | Jina Reader API client — `fetch_markdown(url) → (title, body)`; optional `JINA_API_KEY` Bearer auth; raises `JinaFetchError` on HTTP errors |
| `services/google_auth.py` | Shared Google credential builder — OAuth refresh token (personal) or service-account fallback; `prefer_service_account` flag for GCS |
| `services/google_tokens.py` | Encrypted per-user Google OAuth token store (ADR-0030) |
| `services/google_workspace.py` | Per-user Google Drive workspace helpers (`/vig` folder + workbook) |
| `services/ops_bot.py` | Ops Telegram bot command handlers (ADR-0036) — user/invite administration |
| `services/invite_notifications.py` | Invite-gate operator notifications shared by Telegram and web auth flows (ADR-0031) |
| `services/pdf_intake.py` | Trust-boundary PDF intake (ADR-0029) — magic-byte/size validation, SSRF guard, capped remote fetch |
| `services/space_export.py` | Pure space-export composer — I/O-free, deterministic; feeds `.md`/`.txt`/PDF/Google-Doc exports |
| `services/job_recovery.py` | Dashboard-triggered job recovery orchestration — stale job detection, re-enqueue, batch retry/cancel |
| `services/storage.py` | GCS content-addressed blob store — `upload`/`download`/`exists` keyed by SHA-256; prefixes `documents/` and `parsed/`; sync SDK wrapped in `asyncio.to_thread` |
| `services/parse.py` | liteparse PDF text extraction — `parse_pdf(bytes) → str`; raises `ParseError`; sync CPU-bound work wrapped in `asyncio.to_thread` |

---

## Auth (`src/auth/`)

| Module | Role |
|---|---|
| `auth/hmac_verify.py` | Pure Telegram Login Widget HMAC verifier — `verify_telegram_auth(payload, bot_token) → user | None` |
| `auth/session.py` | Redis opaque session store — `mint` / `resolve` / `revoke`, `session:{id}` keys, 30-day TTL (ADR-0016, no JWT) |
| `auth/middleware.py` | ASGI middleware gating `/api/*`; `/webhook`, `/webhook/ops`, `/health` exempt |
| `auth/telegram_miniapp.py` | Telegram Mini App initData verification (dashboard `/mini` route) |

---

## Second Brain

```
brain.py  (SQLite `links` table + Google Drive .md files)
  ├─ ingest_links()          ← short_video, long_video, prd, article, repo processors + photo pipeline (webhook)
  ├─ search_links()          ← /find slash command + GET /api/brain/search
  ├─ rebuild_graph()         ← /rebuild-graph slash command + POST /api/brain/rebuild
  └─ refresh_stale_links()   ← APScheduler (Sun/Wed 09:00)
```

Links have standalone identity with link-level tags (`link_tags` table, #381–#387); the `links` table is deduplicated at init. Derived graph edges + topic clusters per ADR-0028; node lifecycle dedup per ADR-0027.

---

## Storage

| Store | Used for |
|---|---|
| SQLite `jobs` table | Job lifecycle, transcript, AI enrichment fields, PRD slots, `sheets_row_id` for article in-place row updates |
| SQLite `links` + `link_tags` tables | Second Brain semantic link graph; standalone link identity + link-level tags |
| SQLite `allowed_domains` / `ignored_domains` tables | Per-chat article-domain allowlist and short-video link-extraction blocklist |
| SQLite `markdown_cache` table | Jina Reader response cache keyed by URL; no TTL — `/force` is the invalidation path |
| SQLite `chat_state` table | `awaiting_intent` / `awaiting_freestyle` mode per chat (10-min TTL) |
| SQLite `users` / `user_settings` tables | Dashboard identities (Telegram Login), per-user settings, invite gate state (ADR-0031) |
| SQLite `google_oauth_tokens` / `google_oauth_states` tables | Encrypted per-user Google OAuth credentials + CSRF states (ADR-0030) |
| SQLite `tags` / `job_tags` / `job_annotations` tables | User tag vocabulary (name + meaning + color), job classification, markdown notes |
| SQLite `templates` table | User-defined enrichment templates (dash-sigil `-name`, ADR-0019) |
| SQLite `spaces` / `space_urls` / `context_blobs` tables | Curated collections + editorial context for exports |
| SQLite `job_thumbnails` table | Server-resolved feed thumbnails (ADR-0025) |
| SQLite `document_outputs` table | Doc Parser outputs (ADR-0029) |
| Redis `video_jobs` list | Task envelope queue |
| Redis `session:{id}` keys | Dashboard sessions (30-day TTL) |
| Redis `photo_batch_*` keys | Photo batch session state per chat |
| Google Cloud Storage | Content-addressed document blobs: `documents/<sha>.pdf`, `parsed/<sha>.txt` |
| Google Drive | Enrichment docs, PRD docs, Brain `.md` nodes, space exports (article + document pipelines have **no** Drive upload) |
| Google Sheets | Per-job summary rows: `YouTube Transcript Index`, `Short Video Analysis`, `Article Analysis`, `Repo Analysis`, `mini PRD` |

---

## Web (`web/`)

Next.js 14 App Router dashboard (Ownix design system, ADR-0034). Routes under `web/app/(dashboard)/` — feed, brain, spaces, prompts, controls, jobs/[id], doc-parser — plus public landing, `login`, `privacy`, `terms`, `restricted` (read-only preview, ADR-0035), and `mini` (Telegram Mini App). Session gate in `web/middleware.ts`; components in `web/components/<area>/`; served by Vercel in production. See `WEB-PRD.md` and `DESIGN.md`.

---

## Utilities / Cross-cutting

| Module | Role |
|---|---|
| `config.py` | `Settings` (pydantic-settings, reads `.env`) — single source of all env vars |
| `database.py` | aiosqlite wrapper; schema DDL + `PRAGMA user_version` migrations; all CRUD |
| `telegram/sender.py` | `send_message`, `send_inline_keyboard`, `send_force_reply`, `download_photo`, `answer_callback_query` |
| `utils/validators.py` | `detect_pipeline(url, extra_domains)` — URL routing (short / long / repo / document / article / rejected); `ARTICLE_DEFAULT_DOMAINS` frozenset; `extract_description_links()`, `slugify()` |
| `utils/markdown.py` | `build_links_message()` + `build_enriched_links_message()` (GitHub repo metadata, `_humanize_age`) for photo pipeline results |
| `utils/logger.py` | structlog JSON config |
| `analysis.py` | `extract_key_phrases()` — feeds the enrichment KEY CONTEXT block |
| `templates.py` | `PROMPT_TEMPLATES` registry (summary/method/technical/review/narrative); drives slash commands + enrichment `extra_instructions` |
| `validation.py` | `validate_template_choice()` — template/transcript mismatch warning |

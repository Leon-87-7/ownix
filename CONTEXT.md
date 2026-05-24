# vig — Domain Context

This document is the single source of truth for domain language and architecture decisions in this repository. It grows lazily via `/grill-with-docs` sessions as new terms and decisions crystallise.

---

## Glossary

| Term | Definition |
|---|---|
| **Job** | A unit of work representing one URL submitted by a user. Lives in the `jobs` table. ID format: `YYYYMMDD_HHMMSS_XXXX`. |
| **Short video** | Instagram Reel, TikTok, or YouTube Short — processed via `processors/short_video.py`. Transcript via sidecar, then Gemini text enrichment + Brave Search. |
| **Long video** | Full-length YouTube video — processed via `processors/long_video.py`. Same pipeline as short but with frame extraction. |
| **Content type** | Enum: `short` or `long`. Detected at webhook routing time by `validators.detect_pipeline`. |
| **Status FSM** | Job status lifecycle: `pending → processing → transcript_done → enriching → done` (or `error`/`cancelled`). |
| **Enrichment** | Gemini text pass that classifies the job: category, topic, objective, action points, tools, market data. |
| **Mini-PRD** | AI-generated product requirements document derived from a long-video transcript. Two slots: `auto` (no user input) and `intent` (user-supplied direction text). |
| **PRD auto slot** | Worker-owned lock (`prd_auto_status='generating'`). Single acquirer — only the worker may set this. |
| **PRD intent slot** | User-triggered PRD with a direction text up to 1000 chars. Arms a `chat_state` row with a 10-minute `awaiting_intent` window. |
| **Task envelope** | JSON dict pushed to the Redis queue: `{"task": <discriminator>, "job_id": <id>}`. |
| **Second Brain** | Semantic link graph: every URL extracted from any pipeline is embedded (768-dim via Gemini) and stored in `links` table + uploaded as Obsidian `.md` to Google Drive. |
| **Brain ingest** | Fire-and-forget `brain.ingest_links(links, topic, source_job_id)` — does not block the user-facing response. |
| **Photo pipeline** | Inline (no DB job, no queue) path for Telegram photo messages. Gemini Vision extracts verbatim-grounded URLs; `_filter_grounded_links` drops hallucinations. |
| **Verbatim** | The exact phrase Gemini quotes from the image that proves a URL/domain is literally rendered as text (not inferred from a brand name). Required field for photo link extraction. |
| **UI chrome** | Social media interface elements (follower counts, "Followed by X", timestamps) that are not promoted resources. Photo pipeline drops links whose verbatim contains "followed by". |
| **Transcript service** | Python sidecar (`vig-transcript` container) that downloads videos via yt-dlp and returns transcript text. On caption-less videos, falls back to returning raw audio bytes (base64) for the worker to send to Gemini. Called by short/long processors via HTTP. |
| **Audio fallback** | When the transcript service finds no VTT caption files, it downloads audio-only via yt-dlp and returns `{"audio_b64": "...", "mime_type": "audio/...", "fallback": "audio"}`. The worker, not the transcript service, sends this to Gemini. |
| **Audio enrichment** | A single Gemini `generate_content` call that receives inline base64 audio + the enrichment/template prompt. Gemini transcribes and analyzes in one shot. Used only in the template path when captions are unavailable. Preserves the two-call budget (Vision + Audio-Enrichment). |
| **Repo enrichment** | Post-processing step in the photo pipeline that fetches GitHub API metadata (stars, forks, last-push date, primary language) for each `github.com` link extracted by Gemini Vision, then sorts the list by stars+forks descending before delivery. Non-GitHub links pass through unenriched. |
| **Enrichment sort** | The ordering applied after repo enrichment: primary sort key is stars descending, secondary is forks descending. Applied only when enrichment succeeds for at least one repo. |
| **Repo enrichment fallback** | If the GitHub API calls fail (network error, rate limit, all 404s), the photo pipeline falls back to the plain extracted list in original order — current behavior, no metadata. |
| **GitHub token** | Personal access token (or GitHub App token) stored as `GITHUB_TOKEN` in settings. Required for repo enrichment — if absent, enrichment is skipped and the plain list is returned. Authenticates REST/GraphQL calls; raises the rate limit from 60 to 5,000 requests/hour. |
| **Repo metadata cache** | Redis keys of the form `github_meta:{owner}/{repo}` storing GitHub API metadata as JSON. TTL: 24 hours. Checked before every API call; a cache hit skips the network round-trip entirely. |
| **Repo enrichment API strategy** | GitHub REST API v3 (`GET /repos/{owner}/{repo}`), one request per repo, all fired concurrently via `asyncio.gather`. Simpler than GraphQL; parallel execution keeps wall time acceptable even on cold cache. |
| **Enriched repo line format** | Four metadata fields per repo: ⭐ star count, 🍴 fork count, 💻 primary language, 📅 human-readable last-push age (e.g. "3 days ago", "8 months ago"). Open-issues count and activity-status labels ([INACTIVE] etc.) are excluded. |
| **Enriched repo description** | For repos that enrich successfully, the GitHub API `description` field replaces the Gemini-generated label. For repos that fail enrichment (404, timeout), the Gemini label is kept as-is. |
| **Repo enrichment scope** | Only `github.com` URLs are enriched. Non-GitHub links (GitLab, direct sites, social handles) pass through unenriched in original position. Inline filter buttons (language/activity filters via Telegram keyboard) are deferred to a future issue. |
| **Template path fork** | Caption-based Reels/YouTube follow the text transcript → enrichment path. Caption-less Reels on a template job follow the audio bytes → audio enrichment path. Both paths produce the same enrichment output shape. |
| **Frame service** | HTTP endpoint that extracts key frames from a video URL. Used by the long video pipeline. |
| **Brain refresh** | Cron job (Sun + Wed 09:00 UTC) that re-embeds `links` rows whose `updated_at` is stale. |
| **Reaper** | Boot-time cleanup coroutine that resets stuck `generating` PRD locks older than a threshold. Two reapers: `prd.reaper()` (auto slot) and `prd.reaper_intent()` (intent slot). |
| **Batch mode** | Photo pipeline feature: user opens a 5-min window with `/photoBatch-start`, sends N images, closes with `/photoBatch-end`. All images sent to Gemini in one call. |
| **Slice** | Implementation milestone from the PRD (e.g. "slice #6 = Mini-PRD auto slot"). Slice numbers appear in code comments as a navigation aid. |
| **Webhook dispatch table** | Two module-level dicts in `webhook.py` that map discriminator keys to handler functions: `_CALLBACK_TABLE` (prefix before `:` in callback data → handler) and `_SLASH_TABLE` (command string → handler). Template slash commands are populated into `_SLASH_TABLE` at import time by iterating `PROMPT_TEMPLATES`. The router parses the key, looks up the handler, builds a context object, and calls it — no inline conditionals. |
| **CallbackCtx** | Context dataclass passed to every callback handler: `chat_id`, `job_id` (payload after `:`), `cq_id`, `data` (full raw string). Callback handlers never parse `data` themselves. |
| **SlashCtx** | Context dataclass passed to every slash command handler: `chat_id`, `parts` (split command + args), `message_id`. Does not carry `cq_id` — slash commands have no callback query to acknowledge. |
| **Cancel exemption** | `/cancel` is the only slash command exempt from the router's pre-clear behavior (clear `chat_state` + delete `pending_template` key). It reads `chat_state` itself before clearing, so it must own the clear internally. All other slash handlers run after the router has already cleared state. |
| **PRD skeleton** | Single `run_prd(job, *, lock_col, model, build_prompt)` function in `prd.py` that owns the shared 7-step PRD pipeline: lock acquire → transcript sample → Gemini generate → Drive upload-or-update → Sheets append → brain ingest → Telegram delivery (+ error handling). `run_auto` and `run_intent` are thin wrappers that construct the right arguments and delegate. `PRD_JSON_SCHEMA` is a constant shared by both slots — not a parameter. |
| **GeminiClient** | Single module (`src/services/gemini_client.py`) that owns text-generation calls to Gemini: free→paid key fallback, `asyncio.to_thread` wrapping, `GenerateContentConfig` assembly, and `GeminiUnavailableError` on total failure. Interface: `await gemini_client.generate(prompt, model=..., schema=None) -> str`. Vision and embedding calls are out of scope — they keep their own loops. |
| **GeminiUnavailableError** | Exception raised by `GeminiClient` when both the free and paid Gemini keys fail. Callers translate it into their domain error (e.g. `EnrichmentUnavailableError`) or handle it directly. |

---

## Architecture Overview

```
User (Telegram)
      │
      ▼ HTTPS
┌─────────────────────────────────────────────────────────┐
│  vig-api  (FastAPI, port 8000)                          │
│                                                         │
│  POST /webhook  ──► webhook.py                          │
│    ├─ photo message   → inline photo pipeline           │
│    ├─ URL message     → create_job → queue.enqueue      │
│    └─ callback_query  → _handle_callback                │
│                                                         │
│  GET  /links/search   → brain.search_links              │
│  POST /links/rebuild  → brain.rebuild_graph             │
│  GET  /health                                           │
└────────────────────┬────────────────────────────────────┘
                     │ Redis LPUSH video_jobs
                     ▼
┌─────────────────────────────────────────────────────────┐
│  vig-worker  (asyncio loop)                             │
│                                                         │
│  BRPOP video_jobs  ──► _dispatch(task)                  │
│    ├─ "video" + content_type=short  → short_video.run   │
│    ├─ "video" + content_type=long   → long_video.run    │
│    ├─ "enrichment"                  → enrichment.run    │
│    ├─ "prd_auto"                    → prd.run_auto      │
│    ├─ "prd_auto_resend"             → prd.run_auto_resend│
│    └─ "prd_intent"                  → prd.run_intent    │
└─────────────────────────────────────────────────────────┘

External services used by both containers:
  ┌────────────────┐  ┌──────────────────┐  ┌───────────────┐
  │  SQLite (WAL)  │  │  Redis 7         │  │  vig-transcript│
  │  jobs table    │  │  video_jobs list │  │  (yt-dlp)      │
  │  chat_state    │  │  photo_batch_*   │  └───────────────┘
  │  links table   │  └──────────────────┘
  └────────────────┘

  ┌────────────────┐  ┌──────────────────┐  ┌───────────────┐
  │  Gemini API    │  │  Google Drive    │  │  Brave Search  │
  │  Flash / Pro   │  │  (Drive v3)      │  │  (optional)    │
  │  Embeddings    │  │                  │  └───────────────┘
  └────────────────┘  └──────────────────┘

  ┌──────────────────────┐
  │  Google Sheets       │
  │  Short / Long / PRD  │
  └──────────────────────┘
```

---

## Data Flow — Short Video

```
URL arrives → jobs row (pending) → Redis enqueue
→ worker dequeues → short_video.run
  → transcript service (yt-dlp) → transcript text stored in jobs.transcript
  → status = transcript_done → Telegram: ask user to enrich?
  [user confirms] → enrichment.run
    → Gemini text: category, topic, objective, action_points, tools, market_data
    → Drive upload → Sheets append → Telegram delivery
    → fire-and-forget brain.ingest_links
  → status = done
```

## Data Flow — Mini-PRD (intent path)

```
User taps 📐 Build Spec → prd_build_spec callback
→ Telegram: 2-button sub-menu (🤖 auto / ✍️ intent)
[user taps ✍️ intent] → prd_intent_prompt callback
  → set chat_state(chat_id, mode='awaiting_intent', job_id, expires=10m)
  → Telegram: ForceReply prompt
[user types direction text] → webhook text handler
  → validate length (5–1000 chars)
  → store jobs.prd_intent_text
  → clear chat_state
  → enqueue {"task": "prd_intent", "job_id": ...}
→ worker: prd.run_intent
  → atomic lock (prd_intent_status = 'generating')
  → three-window transcript sample
  → Gemini Pro: structured JSON PRD + intent bias
  → Drive upload → Sheets append → Telegram delivery
  → brain.ingest_links (from PRD links section)
  → status = done
```

---

## Key Invariants

1. **Worker is the single lock acquirer for both PRD slots.** The webhook never sets `prd_auto_status='generating'` or `prd_intent_status='generating'`. This prevents TOCTOU races between two PRD trigger paths.
2. **Photo pipeline is inline.** No DB job, no Redis queue. Results go directly to Telegram. Brain ingest is fire-and-forget.
3. **Brain ingest never blocks a user-facing response.** Always wrapped in `asyncio.create_task(...)`.
4. **Free→paid Gemini key fallback.** Both the enrichment and photo pipelines try the free key first, then the paid key on failure. Anthropic keys were never in scope.
5. **SQLite WAL mode.** The API and worker both open the same SQLite file; WAL allows concurrent readers. Only one writer at a time — the worker owns all write-heavy paths.
6. **Verbatim-grounded photo links only.** Every link returned by `gemini_photo` must include a quoted substring from the image containing the domain. Post-filter in `_filter_grounded_links` drops anything ungrounded or matching UI chrome patterns.

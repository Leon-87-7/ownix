# Video Intelligence Gateway — Tech Stack

**Last Updated:** 2026-05-17  
**Rule:** Every technology earns its place. This document records what's here, why it was chosen over the alternatives, and the concrete signal that should trigger a replacement.

---

## Summary Table

| Layer                           | Technology              | Alternative Waiting       |
| ------------------------------- | ----------------------- | ------------------------- |
| Web framework                   | FastAPI                 | —                         |
| Database                        | SQLite + aiosqlite      | PostgreSQL                |
| Queue                           | Redis                   | asyncio.Queue (downgrade) |
| HTTP client                     | httpx                   | —                         |
| Config                          | pydantic-settings       | —                         |
| Logging                         | structlog               | —                         |
| AI — Vision + Text + PRD (auto) | Gemini 2.5 Flash        | —                         |
| AI — PRD (intent slot)          | Gemini 2.5 Pro          | —                         |
| AI — Embeddings                 | text-embedding-004      | —                         |
| AI enrichment fallback          | Gemini Paid API key     | —                         |
| Link verification               | Brave Search API        | —                         |
| File storage                    | Google Drive API v3     | —                         |
| Reporting                       | Google Sheets API v4    | —                         |
| Transcript extraction           | youtube-transcript-api  | —                         |
| Video download + metadata       | yt-dlp                  | —                         |
| Video frame extraction          | ffmpeg (subprocess)     | —                         |
| Image processing                | Pillow                  | —                         |
| Sidecar server                  | Flask + Waitress        | FastAPI (if rewriting)    |
| Cron scheduling                 | APScheduler             | —                         |
| Vector math                     | NumPy                   | pgvector / Qdrant         |
| Deployment                      | Docker Compose          | —                         |
| Testing                         | pytest + pytest-asyncio | —                         |

---

## 1. Web Framework — FastAPI

**What:** Async Python web framework. Handles the `/webhook`, `/callback`, `/health`, `/links/search`, and `/links/rebuild` endpoints.

**Why here:**

- Native `async/await` — the bot is I/O-bound (Telegram, Gemini, Drive, SQLite). Blocking workers would serialize requests that should run concurrently.
- Automatic OpenAPI docs at `/docs` — useful during development to inspect webhook payloads without writing a test client.
- Dependency injection for auth (`validate_telegram_webhook`) is clean and composable.
- Pydantic models are shared between FastAPI request parsing and the config layer — no duplication.

**Why not Flask:** Flask is sync by default. The existing `transcript_server.py` sidecar uses Flask because it's a simple, stable helper — not the main service. Starting a new async service in Flask would require `asyncio`-patching hacks.

**Why not Django:** Too heavy. Django's ORM, admin, migrations, and settings system are all overhead for a bot with five endpoints.

**Switch when:** Never for this project's scope. If the bot grew into a multi-tenant SaaS with a web dashboard, session management, and server-side rendering, Django REST Framework or a full Next.js backend would be a better fit.

---

## 2. Database — SQLite + aiosqlite

**What:** Embedded relational database. Stores the `jobs` table (job state machine, AI enrichment fields, transcript cache) and the `links` table (Second Brain corpus). `aiosqlite` wraps SQLite with an async interface so it doesn't block the FastAPI event loop.

**Why here:**

- Zero infrastructure. No extra Docker container, no connection pooling config, no migration daemon — the database is a single file at `data/jobs.db`.
- The workload is one user, tens of jobs per day. SQLite in WAL mode handles concurrent reads and the occasional write without contention.
- Easy backup: `cp data/jobs.db data/backups/jobs_$(date +%Y%m%d).db`. No `pg_dump`.
- Portability: the entire state of the bot moves with one file.

**Why not PostgreSQL:** Operational overhead with no benefit at this scale. Running Postgres in Docker Compose adds a container, health checks, a connection pool, and a migration strategy — none of which buy anything when there's one user and ~50 jobs/day.

**Switch when:**

- More than one API container writes to the database simultaneously (SQLite's write lock becomes a bottleneck).
- Jobs/day consistently exceed ~5,000 (WAL mode checkpoint pressure).
- Need `JSONB` columns, full-text search (`tsvector`), or row-level security.
- The migration is two lines: swap `aiosqlite` for `asyncpg`, update the DSN in config. The SQL queries are standard and port directly.

---

## 3. Job Queue — Redis

**What:** Redis `lpush` / `brpop` used as a FIFO queue on the `video_jobs` key. Workers block on `brpop` with a 30s timeout. `asyncio.Queue` is the documented fallback for single-container deployments.

**Why here:**

- The queue survives a worker crash. If the worker process dies mid-poll, the job ID stays in Redis and the next worker restart picks it up — no lost jobs.
- Multiple worker containers can pull from the same queue without coordination. Scaling from 1 to 3 workers is `docker-compose scale worker=3`.
- Redis is already a well-understood operational dependency. Monitoring queue depth (`LLEN video_jobs`) is one command.

**Why not asyncio.Queue:** In-process queue disappears on restart. If the worker crashes between picking up a job and writing `status=processing` to SQLite, the job is silently lost. Acceptable for a dev environment, not for production.

**Why not Celery:** Celery adds a broker abstraction layer, result backend config, task serialization, and worker management (`celery -A ... worker`). That's three new concepts for what is fundamentally `lpush` + `brpop`.

**Why not RQ (Redis Queue):** RQ is a reasonable alternative. Avoided here to keep the dependency count low and the queue logic transparent — the full implementation is ~30 lines in `queue.py`.

**Switch to asyncio.Queue when:** Running as a single container with no restart risk (e.g., local dev only). Zero infra overhead.

**Switch to a managed queue (SQS, Google Pub/Sub) when:** Moving to a cloud-hosted deployment where self-managed Redis adds operational risk, or needing dead-letter queues and at-least-once delivery guarantees.

---

## 4. HTTP Client — httpx

**What:** Async HTTP client used for all outbound HTTP: Telegram Bot API, Brave Search API, Gemini REST calls, and the `transcript_server.py` sidecar endpoints.

**Why here:**

- Native async (`AsyncClient`) — no thread pool needed, no blocking event loop.
- `httpx` has the same API as `requests`, so it's immediately readable.
- Connection pooling via a long-lived `AsyncClient` instance avoids re-handshaking Telegram on every message.
- Used for direct Telegram API calls (no wrapper library) — `httpx` gives full control over the raw payload.

**Why not aiohttp:** `httpx` has a cleaner API and better error messages. `aiohttp` has a larger surface area and slightly more config to get right. No functional difference at this scale.

**Switch when:** Never likely. `httpx` covers every HTTP use case in this project.

---

## 5. Config — pydantic-settings

**What:** `BaseSettings` subclass that reads environment variables (from `.env` or shell) and validates them at startup. All env vars are typed, required fields crash the process immediately if missing.

**Why here:**

- Fail-fast on misconfiguration. A missing `GEMINI_FREE_API_KEY` raises a `ValidationError` before the first request is served — not on the first job that tries to use it.
- Single source of truth: `config.GEMINI_FREE_API_KEY` everywhere, no `os.getenv()` scattered across files.
- Pydantic is already a FastAPI dependency — no extra install.

**Switch when:** Never for this project. If the service grew to need dynamic config reloading (feature flags, per-user settings), a remote config store (LaunchDarkly, AWS Parameter Store) would layer on top of pydantic-settings, not replace it.

---

## 6. Logging — structlog

**What:** Structured JSON logging. Every log event is a machine-parseable JSON object with `timestamp`, `level`, `event`, and context fields (`job_id`, `chat_id`, `content_type`, etc.).

**Why here:**

- JSON logs are queryable with `jq`. Finding all failed jobs in the last hour is one pipeline: `cat logs/app.log | jq 'select(.event=="job_error")'`.
- Context binding (`log.bind(job_id=job_id)`) propagates fields automatically without threading them through every function call.
- Replaces the `print()` / `logging.info()` pattern that was the only observability in the n8n workflow.

**Why not Python's stdlib `logging`:** stdlib logging is line-based. Parsing `2026-05-16 14:32:01 ERROR job_error job_id=abc123 attempt=2` requires regex. Structlog produces `{"event":"job_error","job_id":"abc123","attempt":2}` — parseable without a custom format string.

**Switch when:** If the service moves to a managed logging platform (Datadog, Loki, CloudWatch) that ingests JSON natively, structlog output pipes directly in. No switch needed — add a sink.

---

## 7. AI — Gemini 2.5 Flash + Pro (Vision + Text + Mini-PRD)

**What:** Google's multimodal model family. Used in three modes across two tiers:

- **Vision (Flash):** Short video pipeline — frames sent as base64 JPEG inline data, model extracts links, tools, and a summary.
- **Text — enrichment (Flash):** Long video pipeline — transcript (capped at 12,000 chars) sent with a structured prompt, model returns `{category, topic, objective, action_points[], tools[], market_data}` as JSON.
- **Text — Mini-PRD auto slot (Flash):** Long video Phase 3, fires automatically when `ai_category == "Technical Tutorial"`. Transcript (capped at 60,000 chars, three-window sample if longer) + enrichment scaffolding → structured PRD JSON.
- **Text — Mini-PRD intent slot (Pro):** Long video Phase 3, user-triggered via 📐 button or `/spec` command with intent text. Same prompt shape as auto, biased by user-supplied project direction. Pro is selected for deeper reasoning on phase ordering and gap identification — the user is already prepared to wait the extra ~7s.

**Why here:**

- Gemini 2.5 Flash has a free tier sufficient for personal use. Both `GEMINI_FREE_API_KEY` and `GEMINI_PAID_API_KEY` are Gemini keys — no second vendor needed. Pro is exposed via the same keys at higher per-token cost.
- 1M token context window handles long transcripts without chunking — including the 60k PRD transcript cap.
- Native multimodal: the Vision mode accepts inline image bytes without a separate image hosting step. The `PRD_INCLUDE_FRAMES=false` flag exists as a v2 escape hatch to extend multimodal to long-video PRDs once a frame-selection strategy is built.
- Native structured output: `responseSchema` parameter enforces the enrichment and PRD JSON schemas at the API level, removing parse-failure cases for missing required fields.
- The existing n8n workflow was already Gemini-based. No prompt engineering migration needed.

**Enrichment fallback chain:** `GEMINI_FREE_API_KEY` → `GEMINI_PAID_API_KEY` → double-failure alert to user. The n8n workflow used Anthropic (`claude-sonnet-4-5`) as a third fallback — this is **not ported**. A second Gemini key is simpler and keeps the vendor surface to one.

**PRD fallback chain:** Per slot, same shape: free → paid. Failure handling differs by trigger — silent for auto-fire (logged only; user gets enrichment normally), user-facing message for manual button or `/spec` trigger. Parse failures don't retry on the paid key (model confusion is unlikely to resolve on the same prompt).

**Why Flash for auto PRD but Pro for intent PRD:**

- Flash auto: fires for every Technical Tutorial — keeps the default cost low (~$0.005 per generation at 15k input tokens) and latency ~3s, which fits the "user just enabled enrichment" flow.
- Pro intent: user explicitly invested by supplying a direction — wait tolerance is higher, reasoning quality matters more for ordering phases and identifying open questions. ~$0.035 per generation at 15k input. The 15s cooldown gate (`PRD_INTENT_COOLDOWN_SECONDS`) bounds spam cost.
- The split is a single config flag — `PRD_AUTO_MODEL=gemini-2.5-flash`, `PRD_INTENT_MODEL=gemini-2.5-pro`. Flipping either is one env change.

**Switch when:**

- Free tier rate limits become a daily blocker (>60 requests/min sustained). Current mitigation: paid key fallback.
- Gemini 2.5 Flash is deprecated — upgrade to the next Flash model (prompt schema is stable JSON, migration is a model ID string change).
- A competing model demonstrates meaningfully better structured JSON output for the enrichment or PRD schema. The prompts are self-contained in `processors/enrichment.py` and `processors/prd.py` — swapping models is isolated.
- Flash auto PRDs consistently lack phase-ordering quality — flip `PRD_AUTO_MODEL=gemini-2.5-pro` and re-measure. Architectural cost: zero.

---

## 8. AI — text-embedding-004 (Second Brain)

**What:** Google's text embedding model. Used exclusively by `brain.py` to embed links (document: `"{url} {title} {topic}"`) and search queries for cosine similarity ranking.

**Why here:**

- 768-dimension output. 768 × 4 bytes × 10,000 links = ~30MB in memory — trivially fits with NumPy. No vector database needed.
- Pinned to 768 dims explicitly on every call (`output_dimensionality=768`) to guard against SDK drift changing the default.
- Already on the Gemini platform — no second API key vendor for embeddings.
- `GEMINI_BRAIN_API_KEY` isolates brain quota from pipeline quota (optional — falls back to free key if unset).

**Switch when:**

- Corpus grows past ~100k links and in-memory numpy similarity becomes the latency bottleneck (currently <10ms for 10k links).
- At that point, migrate embeddings to `pgvector` (if already on PostgreSQL) or Qdrant. The `brain.py` interface doesn't change — only the storage and similarity query backend.

---

## 9. Link Verification — Brave Search API

**What:** REST API used in the short video pipeline to verify and enrich extracted links. Given a URL or domain, returns a title and snippet from Brave's index.

**Why here:**

- Free tier (100 queries/month) covers personal use.
- Gives Gemini-extracted links a human-readable label and description without scraping the target page directly.
- Opt-in via `ENABLE_BRAVE_SEARCH=true`. The pipeline degrades gracefully when disabled — links are sent without enrichment.

**Why not direct HTTP scraping:** Scraping target pages for titles requires headless browser or HTML parsing, has legal/ToS risk, and breaks on JS-rendered pages. Brave's index has already done this work.

**Switch when:** Free tier exceeded (>100 searches/month). Options: Brave paid tier ($3/1000 queries), SerpAPI, or disable and rely on Gemini Vision's link extraction quality alone.

---

## 10. File Storage — Google Drive API v3

**What:** Markdown files are uploaded to Google Drive via a service account. Four folders:

- `DRIVE_FOLDER_SHORT` — short video analysis reports
- `DRIVE_FOLDER_LONG` — long video transcript `.md` files
- `DRIVE_FOLDER_BRAIN` — Second Brain Obsidian vault `.md` nodes
- `DRIVE_FOLDER_PRD` — Mini-PRD files (`{slug}_{job_id_last4}_auto.md` and `_intent.md`); cached `drive_file_id` per slot on the `jobs` row enables in-place updates via `files.update`

Files are shared "anyone with link" (reader). The shareable URL is sent to the user via Telegram.

**Why here:**

- The n8n workflow already used Drive. Users have existing folders with historical data.
- Drive files open directly in the browser (Google Docs viewer renders markdown) — no self-hosted file server needed.
- The Obsidian vault use case requires Drive specifically: the Google Drive desktop app syncs the Brain folder locally, which Obsidian reads as a vault. No other storage backend supports this workflow.
- Service account auth means no OAuth dance — credentials are a JSON file.

**Switch when:** The Obsidian Drive vault workflow is abandoned. At that point, an S3-compatible store (Cloudflare R2, MinIO) would be cheaper and simpler. The `drive.py` service module is the only integration point — swapping it doesn't touch pipeline logic.

---

## 11. Reporting — Google Sheets API v4

**What:** Append-only logging of completed jobs. Three sheets — one per artifact type — written after Drive upload completes.

- `SHEETS_ID_SHORT` columns: `id, chat_id, url, title, platform, drive_url, processing_time_ms, created_at`
- `SHEETS_ID_LONG` columns: `id, chat_id, url, title, channel, views, ai_category, ai_topic, ai_objective, ai_action_points, ai_tools, ai_market_data, drive_url, created_at`
- `SHEETS_ID_PRD` columns: `job_id, video_url, title, slot, intent_text, drive_url, created_at` — one row per PRD generation (max 2 per job from the two-slot model). `slot` is `'auto'` or `'intent'`; `intent_text` is NULL for auto. Independent from `SHEETS_ID_LONG` because PRD generations happen at unpredictable times (e.g. weeks later via `/spec`) and append-only semantics require independent rows rather than retroactive updates.

**Why here:**

- Historical compatibility — the n8n workflow used Sheets as its database. The Python replacement demotes it to a read-only audit log while SQLite becomes the source of truth.
- Sheets is the easiest way to browse and filter job history without writing a dashboard.
- The Apps Script `fillTopics` tool (`scripts/apps-script-in-sheet.js`) runs inside Sheets and can retroactively fill missing `ai_topic` fields — this workflow only works with Sheets.

**Not the source of truth:** SQLite is. Sheets append can fail without affecting job processing — the failure is logged but does not trigger a retry.

**Switch when:** The Sheets-based workflow (manual browsing, Apps Script) is replaced by a proper admin dashboard. Sheets logging can simply be disabled (`LOG_TO_SHEETS=false`) without touching anything else.

---

## 12. Transcript Extraction — youtube-transcript-api

**What:** Python library that fetches YouTube caption data without downloading the video. Used in `transcript_server.py` at `GET /transcript`.

**Why here:**

- Fastest path to transcript text — no video download, no audio processing, no speech-to-text.
- Captions are usually more accurate than STT for technical content (proper nouns, library names, ticker symbols).
- Zero cost — captions are served by YouTube's own API.

**Limitation:** Only works if the video has captions enabled. Returns `TranscriptsDisabled` or `NoTranscriptFound` on failure — caller sees the error type in the response and can message the user accordingly.

**Switch when:** Transcript extraction failures on captionless videos become a common user complaint. At that point, add a `yt-dlp` audio download + Whisper STT path as a fallback inside `transcript_server.py`. The `/transcript` endpoint contract doesn't change.

---

## 13. Video Download + Metadata — yt-dlp

**What:** CLI/library used in `transcript_server.py` for two purposes:

- `GET /short_frames`: downloads the video file (`bestvideo[ext=mp4]+bestaudio[ext=m4a]/best`) so ffmpeg can extract frames.
- `GET /metadata`: extracts `title`, `channel`, `views`, `upload_date`, `description` without downloading the video (`skip_download=True`).

**Why here:**

- Supports YouTube Shorts, Instagram Reels, TikTok, and hundreds of other platforms via a unified interface.
- Actively maintained — cookie handling, rate-limit circumvention, and format negotiation are updated with each platform change.
- Instagram cookies (`instagram_cookies.txt`) are already configured for authenticated Instagram access.

**Switch when:** yt-dlp breaks on a specific platform and the maintainers don't fix it quickly. The most likely scenario is Instagram — Instagram actively blocks scrapers. At that point, a platform-specific API (RapidAPI TikTok scraper, Instagram Graph API) can be added as a per-platform override inside `transcript_server.py`.

---

## 14. Frame Extraction — ffmpeg (subprocess)

**What:** System binary called via `subprocess.run` inside `transcript_server.py`. Extracts JPEG frames from the downloaded video at a configurable interval (`fps=1/{interval}`) up to `max_frames`, scaled to `max_width`.

**Why here:**

- ffmpeg is the universal standard for video frame extraction. No Python-native library matches its format support, performance, or reliability.
- The `subprocess` call is straightforward: fixed command, fixed args, check returncode.
- Frames are written to a temp directory and cleaned up in a `finally` block.

**Limit:** Videos longer than 180 seconds are rejected before download. This keeps temp disk usage and ffmpeg runtime bounded.

**Switch when:** Never — ffmpeg is the right tool for this job. If the frame extraction service is rewritten in Python (as part of this project), ffmpeg stays.

---

## 15. Image Processing — Pillow

**What:** Used in `transcript_server.py` after ffmpeg extraction. Opens each JPEG frame, re-encodes it at `quality=85`, and base64-encodes the result for the JSON response.

**Why here:**

- Re-encoding at quality=85 reduces frame size ~30–40% vs ffmpeg's default output before base64 inflation.
- Pillow is a single-purpose step: open → encode → close. No complex image manipulation needed.

**Switch when:** Never. If memory becomes a concern for large frame counts, reduce `max_frames` or `max_width` via query params before touching Pillow.

---

## 16. Sidecar Server — Flask + Waitress

**What:** `transcript_server.py` runs as a Flask app served by Waitress (a production WSGI server). Exposes `/transcript`, `/metadata`, `/short_frames`, and `/health` on port 5151.

**Why here:** This server already exists and works. It is not being rewritten as part of this project. Flask + Waitress is the current stack, and replacing it is not in scope.

**If rewriting from scratch:** Use FastAPI + uvicorn for consistency with the main service. The route signatures are simple GETs and map directly to FastAPI path functions.

**Switch when:** The sidecar is folded into the main Python service (e.g., to eliminate the Docker networking complexity between `FRAME_SERVICE_URL` and `TRANSCRIPT_SERVICE_URL`). At that point, the Flask app is rewritten as FastAPI routes inside `services/frames.py` and `services/transcript.py` — the endpoint contracts stay the same.

---

## 17. Cron Scheduling — APScheduler

**What:** `AsyncIOScheduler` registered on FastAPI startup. Runs `brain.refresh_stale_links()` on cron `0 9 * * 0,3` (9 AM UTC, Sunday and Wednesday).

**Why here:**

- APScheduler integrates with asyncio natively — the scheduled coroutine runs on the same event loop as the FastAPI app. No separate process or container needed.
- Cron expression `0 9 * * 0,3` is readable and matches the design spec exactly.
- The scheduler is registered once in `main.py` and is invisible to the rest of the codebase.

**Why not a cron job (system cron / Docker cron):** A system cron entry would need to spawn a separate Python process, reconnect to SQLite, and re-initialize the Gemini client on every fire. APScheduler keeps the connection and credentials warm inside the running process.

**Switch when:** The refresh worker needs to run on a separate container (e.g., to isolate Drive API calls from the web tier). At that point, extract the scheduled function into a standalone `python -m src.brain_worker` entry point and trigger it with a Docker-level cron or a managed scheduler (Cloud Scheduler, GitHub Actions cron).

---

## 18. Vector Math — NumPy

**What:** Used in `brain.py` to:

- Store embeddings as a 2D float32 matrix (rows = links, cols = 768 dims)
- Compute cosine similarity: `dot(query, corpus.T) / (norm(query) * norm(corpus, axis=1))`
- Rank and filter results by `BRAIN_MIN_SCORE`

**Why here:**

- 768 floats × N links is a small matrix. 10,000 links = ~30MB. In-memory is faster than any database round-trip.
- NumPy cosine similarity over 10k vectors takes <5ms. No approximate nearest-neighbour index needed at this scale.
- NumPy is a transitive dependency of many packages already — no net new dependency in practice.
- `float32.tobytes()` / `frombuffer(..., dtype=float32)` is the SQLite BLOB serialization format — round-trips perfectly with no external encoding.

**Switch when:** Corpus grows past ~100k links and similarity search latency exceeds 100ms, OR per-user corpora require concurrent queries that can't share a single matrix. At that point, migrate to `pgvector` (already on PostgreSQL by then) or Qdrant. The `brain.search_links()` interface doesn't change — only the backend.

---

## 19. Deployment — Docker Compose

**What:** Three-container setup: `api` (FastAPI + APScheduler), `worker` (background job processor), `redis`. All share a `video-bot-network` bridge network and mount `./data` and `./logs` volumes.

**Why here:**

- `docker-compose up -d` is the entire deployment. No systemd units, no manual process management.
- Worker can be scaled independently of the API: `docker-compose up --scale worker=3`.
- `transcript_server.py` runs outside Docker (on the host machine), accessed via `host.docker.internal:5151` from inside containers.

**Switch when:** Moving to a cloud provider. At that point: push images to a container registry, replace Compose with ECS Task Definitions or a Kubernetes Deployment. The Docker images themselves don't change — only the orchestration layer.

---

## 20. Testing — pytest + pytest-asyncio

**What:** `pytest` as the test runner. `pytest-asyncio` enables `async def test_*` functions and marks async fixtures. `pytest.ini` or `pyproject.toml` sets `asyncio_mode = auto` so every async test is handled without manual `@pytest.mark.asyncio` decoration.

**Why here:**

- pytest is the Python testing standard. `pytest-asyncio` is its natural async extension.
- `anyio` or `trio` are alternatives, but `pytest-asyncio` integrates directly with the asyncio event loop that FastAPI and aiosqlite use — no backend switching.

**Integration test gate:** Tests that call real Gemini APIs are gated behind `RUN_INTEGRATION=1` so CI stays fast by default.

**Switch when:** Never. pytest is not a technology decision that needs revisiting.

---

## Dependency Install Surface

```txt
# Core
fastapi
uvicorn[standard]
httpx
pydantic-settings
aiosqlite
structlog

# Queue
redis[asyncio]

# Google / AI
google-generativeai
google-api-python-client
google-auth

# Second Brain
apscheduler>=3.10
numpy>=1.26

# Sidecar (transcript_server.py — separate install)
flask
waitress
youtube-transcript-api
yt-dlp
Pillow

# Testing
pytest
pytest-asyncio
```

`ffmpeg` is a system binary — installed on the host (or in a Dockerfile layer) separately from pip.

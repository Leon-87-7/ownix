# Video Intelligence Gateway

> Telegram bot that turns YouTube videos, Instagram Reels, TikToks, dev articles, GitHub repos, and PDF documents into structured intelligence — frame analysis, transcripts, Gemini enrichment, a searchable Second Brain, and AI-generated product specs — delivered in chat and browsable in a Next.js web dashboard ("The Operator's Console").

---

## Why I Built It

I was spending hours each week watching YouTube tutorials and saving random links. The workflow was broken:

- **Watch a video** → take scattered notes → forget where I put them
- **Find a tool in a screenshot** → manually Google every brand name → half the links were hallucinated
- **Save a Substack article** → never read again
- **Build a PRD** → start from scratch every time instead of extracting from the content I'd already consumed

I had a 60-node n8n workflow that half-worked. I killed it and replaced it with this.

---

## What It Does

Send a URL to the Telegram bot. Get back structured intelligence.

| Input                                      | Output                                                                                                              |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| YouTube Short / Reel / TikTok              | Frame analysis + extracted tool links, verified via Brave Search                                                    |
| Full YouTube video                         | Transcript `.md` → Gemini enrichment (topic, action points, tools) → Drive → optional Mini-PRD                      |
| Substack / Medium / dev.to / Ghost article | Clean Markdown doc + structured analysis (topic, objective, action points, tools, promise-gap)                      |
| `github.com/<owner>/<repo>`                | GitHub API bundle → structured analysis (tagline, tech stack, use-cases, curriculum hooks with file pointers)       |
| PDF (upload or `.pdf` URL)                 | liteparse text extraction → GCS content-addressed cache → Gemini enrichment (title, author, key points, references) |
| Screenshot(s)                              | Verbatim-grounded link extraction — only URLs literally visible in the image; multi-image sends auto-batched        |

Everything feeds a **Second Brain**: a semantic link graph (Gemini embeddings, cosine similarity) that surfaces related content via `/find <query>` — and everything lands in the **web dashboard** ("The Operator's Console", Ownix design system): feed with per-type tabs and server-resolved thumbnails, brain graph, curated Spaces with export, custom prompt templates, a Doc Parser page, and dashboard job submission. Telegram Login + invite gate; a second "Ops" bot handles user/invite administration.

---

## Demo

```
User:  https://www.youtube.com/watch?v=abc123

Bot:   🔊 Transcript done → Drive
       [sendDocument] tutorial.md
       [Run Gemini?] [No Thanks] [Build Spec]

User:  ✨ Run Gemini → picks "Technical" template

Bot:   job_A3F9:
       ✍️ Building a RAG Pipeline with LangChain
       🎫 RAG · LangChain · vector search

       🎯 Objective
       End-to-end guide to building a retrieval-augmented generation
       system with LangChain, FAISS, and OpenAI embeddings.

       ✅ Action Points
       • Split documents into chunks ≤ 512 tokens
       • Use FAISS for local embedding storage
       • Wrap retriever in ConversationalRetrievalChain

       🛠 Tools
       • [library] LangChain (langchain.com): orchestration
       • [library] FAISS (github.com/facebookresearch/faiss): vector index
       • [service] OpenAI Embeddings: text-embedding-ada-002

       =====PROMISE=GAP=====
       ❌ Unfulfilled: "production-ready" — no deployment or auth covered
       💎 Hidden value: FAISS index serialisation pattern is reusable across projects

       [📐 Build Spec]
```

---

## Architecture

```
Telegram User
      │ HTTPS
      ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI :8000                                          │
│                                                         │
│  POST /webhook  ──► webhook.py                          │
│    ├─ photo      → inline photo pipeline (no queue)     │
│    ├─ URL        → detect_pipeline → create_job → queue │
│    └─ callback   → _CALLBACK_TABLE dispatch             │
└────────────────────┬────────────────────────────────────┘
                     │ Redis LPUSH video_jobs
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Worker (asyncio loop)                                  │
│                                                         │
│  BRPOP video_jobs ──► dispatch                          │
│    ├─ "video" short   → frames → Gemini Vision          │
│    ├─ "video" long    → transcript → Drive → Phase 2    │
│    ├─ "article"       → Jina → paywall → Gemini Flash   │
│    ├─ "repo"          → GitHub bundle → Gemini Flash    │
│    ├─ "document"      → liteparse → GCS cache → Gemini  │
│    ├─ "enrichment"    → Gemini text enrichment          │
│    └─ "prd_*"         → Gemini PRD (Flash / Pro)        │
└─────────────────────────────────────────────────────────┘

Web:   Next.js 14 dashboard (Vercel) → /api/* (session cookie) → FastAPI src/api/
State: SQLite (WAL) — jobs, links, spaces, tags, templates, users, chat_state, caches
Queue: Redis FIFO — survives worker restarts, supports N workers
Brain: Gemini text-embedding-004 + NumPy cosine similarity + Drive Obsidian vault
```

---

## Key Technical Decisions

### Why FastAPI over Flask?

Native `async/await`. The bot is almost entirely I/O-bound — Telegram, Gemini, Drive, SQLite, yt-dlp. Blocking workers serialize requests that should run concurrently. Flask requires patching hacks to get the same result.

The transcript sidecar still uses Flask because it pre-exists and isn't worth rewriting. Starting a new async service in Flask would mean `asyncio` monkey-patching — FastAPI makes this the default.

### Why SQLite over PostgreSQL?

One user, tens of jobs per day. SQLite in WAL mode handles concurrent reads without contention. The entire state of the bot is a single file — backup is `cp`. The migration path to PostgreSQL is two lines of config.

The n8n workflow used Google Sheets as its database. Sheets has no transactional semantics, can't be queried, and breaks under concurrent writes. Demoting it to an append-only audit log and moving truth to SQLite was the most important architectural decision.

### Why a job queue (Redis) instead of inline processing?

The Gemini API call for a long video can take 15–30 seconds. If the webhook handler awaited it, Telegram would re-deliver the message (it retries on timeout). The queue decouples receipt from processing: the webhook acks in <200ms, the worker picks it up, the user gets a Telegram notification when done.

Redis also survives worker restarts — an in-process `asyncio.Queue` disappears on crash.

### Why Gemini instead of OpenAI?

The n8n workflow was already Gemini. The 1M-token context window handles long transcripts without chunking (GPT-4 caps at 128k). Native multimodal means video frames go as inline base64 — no separate image hosting step.

The free tier covers personal use. The `free → paid key` fallback is two env vars.

### Why a Second Brain instead of just saving links?

Every link I extract from a video is useless unless I can find it again. Cosine similarity over Gemini embeddings lets me ask "what did I see about vector databases?" and surface results from 6 months of processed content. The Obsidian vault integration means I can browse it in a graph view. No vector database needed at this scale — 10k links × 768 dims = ~30MB, <5ms similarity search.

---

## The Article Pipeline

Most "read later" workflows are where articles go to die. This pipeline makes articles as actionable as videos:

1. URL hits `detect_pipeline` — matches against `ARTICLE_DEFAULT_DOMAINS` (Substack, Medium, dev.to, Ghost, Hashnode, etc.) or a per-chat `/allowlist`
2. Jina Reader fetches clean Markdown (cached in SQLite — never fetches twice)
3. Paywall heuristic: body < 500 chars or keyword phrases → `⚠️ analysis may be shallow` warning, but Gemini still runs
4. Gemini 2.5 Flash extracts: topic, objective, action points, tools with URLs, promise-gap analysis
5. Delivered as a `.md` Telegram document + enrichment message
6. `✍️ Freestyle` button re-runs analysis against cached Markdown with any user-supplied instructions — no second Jina call

The promise-gap field is the part I use most: it tells me when a headline promises "production-ready" and the article delivers a 100-line toy script.

---

## Complexity I'm Proud Of

### Photo link extraction that doesn't hallucinate

Earlier version: asked Gemini to "infer the full URL from the brand name visible in the screenshot." Result: Gemini appended `.com` to every card label, generated hundreds of plausible-looking but fake URLs.

Fix: require a **verbatim OCR quote** for every link. `_filter_grounded_links` drops anything whose domain doesn't appear literally in the quoted phrase. UI chrome (follower counts, "Followed by X") is pattern-matched and dropped before delivery.

### Migration system that doesn't break test databases

SQLite doesn't support `ALTER COLUMN` — adding a CHECK constraint to an existing column requires creating a new table, copying data, and renaming. When the v5→v6 migration added `'article'` to the `content_type` CHECK, `INSERT INTO jobs_v6 SELECT * FROM jobs` would fail on test databases that only had 6 columns.

Fix: `PRAGMA table_info(jobs)` at migration time, dynamic `INSERT INTO jobs_v6 (col1, col2, ...) SELECT col1, col2, ... FROM jobs` with only the columns that actually exist. Migration tests create minimal tables — they pass.

### Two-slot PRD model

The Mini-PRD has two slots per job: `auto` (Flash, fires for Technical Tutorial videos) and `intent` (Pro, user-supplied direction text). The atomic lock is `UPDATE prd_auto_status = 'generating' WHERE prd_auto_status IS NULL OR prd_auto_status = 'error'` — the rowcount tells you whether you won the race. No separate lock table, no Redis coordination.

The intent slot has a 15-second cooldown enforced the same way — `prd_intent_completed_at` compared in the UPDATE WHERE clause.

---

## What I'd Do Differently

1. **Structured output from day one.** I retrofitted `responseSchema` Gemini parameter months after launch. Every JSON parse failure between day 1 and that migration was unnecessary.

2. **The reaper earlier.** A worker crash leaves jobs in `processing` forever unless something resets them. I added the boot-time reaper after the first production incident. Should have been in the initial worker loop.

3. **Test database fixtures that match the full schema.** Migration tests created 6-column stub tables because full-schema tests felt like overkill. Then the v5→v6 migration broke them all. Fixtures should match production schema.

---

## Tech Stack

```
Backend:      FastAPI + uvicorn
Frontend:     Next.js 14 App Router (web/, Vercel) — Tailwind, Milkdown Crepe, react-force-graph
State:        SQLite (aiosqlite, WAL mode) + Redis
AI:           Gemini 2.5 Flash (vision, text, article, repo, document), 2.5 Pro (PRD intent), text-embedding-004
Content:      yt-dlp (download), youtube-transcript-api (captions), ffmpeg (frames), Jina Reader (articles),
              GitHub REST API (repos), liteparse (PDF)
Storage:      Google Drive API v3, Google Sheets API v4, Google Cloud Storage (content-addressed PDFs)
Search:       Brave Search API (link verification), NumPy (cosine similarity)
Bots:         Telegram Bot API (raw httpx, no wrapper library) — main bot + Ops bot
Deploy:       Docker Compose (api + worker + transcript-service + redis + cloudflared); frontend on Vercel
Tests:        pytest + pytest-asyncio (backend), Vitest + RTL + MSW (web)
```

---

## Running It

```bash
git clone https://github.com/leon-87-7/ownix
cd vig
cp .env.example .env   # fill in API keys — see .env.example for all vars

docker-compose up -d

# Register Telegram webhook
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-domain.com/webhook"

# Run tests
pytest -q
```

Required keys: `TELEGRAM_BOT_TOKEN`, `GEMINI_FREE_API_KEY`, `GOOGLE_OAUTH_*` (Drive + Sheets), `REDIS_URL`.  
Optional: `GEMINI_PAID_API_KEY`, `BRAVE_API_KEY`, `GITHUB_TOKEN`, `JINA_API_KEY`.

---

## Bot Commands

| Command                   | What it does                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------ |
| `/find <query>`           | Semantic search across the Second Brain                                                          |
| `/freestyle <url>`        | Process any URL with a custom Gemini prompt                                                      |
| `/force <url>`            | Bypass dedup + invalidate markdown cache, reprocess from scratch                                 |
| `/spec <suffix> [intent]` | Generate or regenerate Mini-PRD for a job (last 4 chars of job ID)                               |
| `/allowlist <domain>`     | Add a domain to the article pipeline for this chat (`/unallowlist`, `/allowlist_list` to manage) |
| `/ignore <domain>`        | Block a domain from short-video link extraction                                                  |
| `/download_md <url>`      | Fetch any URL as clean Markdown via Jina (no job, no Brain ingest)                               |
| `/rebuild-graph`          | Recompute all Second Brain `.md` nodes                                                           |
| `/cancel`                 | Clear any armed chat state (awaiting_freestyle / awaiting_intent)                                |

---

## Project Layout

```
src/
├── main.py                  # FastAPI app + APScheduler (brain refresh Sun/Wed)
├── worker.py                # asyncio dispatch loop + boot-time reapers
├── database.py              # SQLite schema, PRAGMA migrations, all CRUD
├── brain.py                 # Second Brain: ingest, search, rebuild, refresh
├── api/                     # Dashboard JSON API — jobs, brain, spaces, templates,
│                            # controls, parsed (Doc Parser), preview, auth, google_oauth
├── auth/                    # Login-Widget HMAC verify, Redis sessions, /api/* middleware
├── processors/
│   ├── short_video.py       # Frames → Gemini Vision → Brave → Drive
│   ├── long_video.py        # Transcript → Drive → Phase 1 delivery
│   ├── enrichment.py        # Gemini text enrichment (Phase 2)
│   ├── prd.py               # Mini-PRD: run_auto + run_intent (Phase 3)
│   ├── article.py           # Jina → paywall → Gemini → Sheets → Brain
│   ├── repo.py              # GitHub bundle → Gemini structured analysis
│   └── document.py          # liteparse PDF → GCS cache → Gemini enrichment
├── services/
│   ├── gemini_client.py     # free→paid fallback loop, GeminiUnavailableError
│   ├── jobs.py              # create_and_enqueue_job() shared core (ADR-0033)
│   ├── ops_bot.py           # Ops bot: user/invite administration (ADR-0036)
│   ├── jina.py              # Jina Reader API client
│   ├── drive.py             # Drive upload + in-place update
│   ├── sheets.py            # Sheets append (5 tabs) + article row update
│   ├── github.py            # GitHub metadata + Redis cache (24h TTL)
│   ├── storage.py           # GCS content-addressed blob store
│   └── brave.py             # Brave Search link verification
├── telegram/
│   ├── webhook.py           # Dispatch tables, URL routing, chat_state FSM
│   └── sender.py            # sendMessage, sendDocument, sendPhoto, ForceReply
└── utils/
    ├── validators.py        # detect_pipeline, ARTICLE_DEFAULT_DOMAINS
    └── logger.py            # structlog JSON

web/                         # Next.js 14 dashboard — feed, brain, spaces, prompts,
                             # controls, jobs/[id], doc-parser + landing/login/restricted
tests/                       # pytest + pytest-asyncio
transcript_server.py         # Flask+Waitress sidecar :5151 (yt-dlp + ffmpeg)
```

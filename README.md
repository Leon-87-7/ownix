# Ownix - Your internet. Own it

![Ownix: you watched it, you liked it, you lost it.](docs/assets/og-image.png)

You watched it. You liked it. You lost it.

Ownix is where the things you find online stop disappearing. Share a reel, a YouTube
video, an article, a GitHub repo, a PDF, or a screenshot, from the share sheet you
already use, a Chrome right-click, or the dashboard itself. A minute later it is an
entry in your Index: full transcript, structured summary, every link it mentioned, all
in markdown. You can search it by meaning instead of keywords, and paste it straight
into Claude, Cursor, or Codex.

Everything also lands in your own Google Drive. If Ownix shut down tomorrow, your Index
would still be there. That is the first law in
[`docs/brand/CONSTITUTION.md`](docs/brand/CONSTITUTION.md), and it constrains the
architecture, the APIs, and the export formats, not only the marketing copy.

This repository holds the whole system: a Python backend (FastAPI, SQLite, Redis), two
Telegram bots, a Flask transcript sidecar, a Chrome extension, and a Next.js dashboard
under `web/`. Backend codename: `vig`, for Video Intelligence Gateway.

---

## What it does

### Capture

Three ways in, one destination.

- **Telegram.** Share sheet on your phone, or paste a URL into the bot. Photos are
  handled inline, and multi-image sends group themselves.
- **Chrome extension** (`extension/chrome/`). A shortcut or a right-click on any page,
  link, or selection.
- **Dashboard Intake.** Paste a URL, run a command, drop a file, or write a note.

### Pipelines

The URL decides which one runs.

| Content | What comes back |
| --- | --- |
| **Short video**: Shorts, Reels, TikTok | Frame extraction, Gemini Vision analysis grounded in the transcript, Brave-verified links, Drive upload |
| **Long video**: YouTube | Transcript, Drive upload, Gemini enrichment (topic, objective, action points, tools, promise-gap), optional Mini-PRD |
| **Article**: Substack, Medium, dev.to, Ghost, Hashnode, plus your own allowlist | Jina Reader fetch, markdown cache, paywall heuristic, Gemini analysis, Sheets, Brain |
| **Repo**: `github.com/<owner>/<repo>` | README, prioritized file tree, manifests, stars and forks, then Gemini structured analysis (tagline, stack, use-cases, curriculum hooks) written to `.md` |
| **Document**: PDF, Office formats, images | liteparse extraction, content-addressed GCS cache, Gemini briefing, delivery to Telegram and the Docs page |
| **Photo**: screenshots | OCR link extraction with a verbatim-grounded filter that drops anything the image does not actually say |
| **Newsletter**: subscribed aliases | Public-archive polling, candidate promotion, issue-feed digest (ADR-0060) |

### Then use it

- **Brain.** A semantic link graph built from Gemini embeddings and cosine similarity,
  stored as an Obsidian-style `.md` vault in your Drive. Search it from the dashboard or
  with `/find`.
- **Checklists.** Turn a transcript into instructions you can hand to an agent, so it
  audits your actual codebase instead of your memory of the video. Ownix automates the
  ask. You still do the judging, which is what the Second Law protects.
- **Mini-PRD.** Product specs generated from long-video transcripts. Two slots: auto
  (Flash) and intent (Pro, steered by you).
- **Collections and Recipes.** Group saves into sets you can revisit and export. Save
  the freestyle prompt you keep retyping.

---

## The dashboard (`web/`)

Next.js 14 App Router, deployed on Vercel. Routes under `web/app/(dashboard)/`:

| Route | What it is for |
| --- | --- |
| `/intake` | One surface for everything you send Ownix |
| `/feed` | Everything you have saved, with per-type tabs, a links table, and a layout toggle |
| `/jobs/[id]` | The entry itself: transcript, summary, links, notes, checklists, export |
| `/newsletter-digest` | Subscribed newsletters and promoted candidates |
| `/doc-parser` | Docs. Upload PDFs, Office files, and images, then read the parsed result |
| `/brain` | Semantic search across the Index |
| `/spaces` | Collections |
| `/prompts` | Recipes |
| `/controls` | Settings: tags, domain rules, accessibility, extension tokens |

Public routes: `/` (landing), `/login`, `/privacy`, `/terms`, `/accessibility`,
`/restricted` (a read-only preview), `/mini` (Telegram Mini App), and `/offline`. The
session gate is `web/middleware.ts`.

Design and voice are governed by `PRODUCT.md` (users, brand personality), `DESIGN.md`
(tokens and the Personal Index north star), and
[`docs/brand/CONSTITUTION.md`](docs/brand/CONSTITUTION.md) (why any of it is allowed to
exist).

---

## Requirements

- Docker and Docker Compose
- Python 3.11+ for the transcript sidecar, which runs on the host
- A Telegram bot token
- A Google Cloud project with the Drive, Sheets, and Cloud Storage APIs enabled
- A Gemini API key. The free tier covers personal use.

Optional keys, each switching on one feature: `BRAVE_API_KEY` for link verification,
`GITHUB_TOKEN` for the repo pipeline and a higher rate limit, `JINA_API_KEY` for Jina
quota, `GEMINI_PAID_API_KEY` as a rate-limit fallback, and `GOOGLE_STORAGE_BUCKET` for
the document pipeline.

---

## Setup

### 1. Clone and configure

```Shell
git clone https://github.com/Leon-87-7/ownix
cd ownix
cp .env.example .env
```

Only `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_SECRET` are enforced at startup.
Everything else is validated at use-time by the feature that needs it. In practice you
want at least:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
WEBHOOK_URL=                        # public HTTPS base, e.g. an ngrok URL
REDIS_URL=redis://redis:6379/0

GEMINI_FREE_API_KEY=

GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_OAUTH_REFRESH_TOKEN=

GOOGLE_DRIVE_FOLDER_SHORT=
GOOGLE_DRIVE_FOLDER_LONG=
GOOGLE_DRIVE_FOLDER_BRAIN=
GOOGLE_SHEETS_ID=                   # one workbook, one tab per domain
```

`.env.example` lists everything. `src/config.py` holds the authoritative defaults.

### 2. Start the transcript sidecar on the host

```Shell
pip install flask waitress yt-dlp youtube-transcript-api Pillow
python transcript_server.py          # listens on :5151
```

### 3. Start the main services

```Shell
docker-compose up -d
```

### 4. Register the Telegram webhook

```Shell
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=<WEBHOOK_URL>/webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

### 5. Verify

```Shell
curl https://your-domain.com/health    # → {"status":"ok"}
```

---

## Bot commands

Send a bare URL and the right pipeline picks it up. Everything else:

| Command | What it does |
| --- | --- |
| `/start`, `/help` | Onboarding and the command list |
| `/find <query>` | Semantic search across your Brain |
| `/spec <suffix> [intent]` | Mini-PRD for a job, addressed by the last 4 characters of its ID |
| `/checklists <suffix>` | Turn a transcript into checks you can run |
| `/screenshots <suffix>` | Capture informative frames from a saved video |
| `/freestyle <url>` | Process a URL with your own prompt |
| `/force <url>` | Skip dedup, invalidate the markdown cache, reprocess |
| `/tag`, `/taglist` | Tag a job, list your tags |
| `/addlink <url>` | File a bare link without running a pipeline |
| `/allowlist`, `/unallowlist`, `/allowlist_list` | Per-chat article domains |
| `/ignore`, `/unignore`, `/ignore_list` | Block a domain from link extraction |
| `/download_md <url>` | Fetch any URL as clean markdown, no job created |
| `/rebuild-graph` | Recompute every Brain node |
| `/cancel` | Clear armed chat state |
| `/<template>` | Run a named Recipe. One command per entry in `PROMPT_TEMPLATES` |

Most commands also work without the slash, so `find <query>` does the same thing as
`/find <query>`. Screenshots need no batch command: send several at once and they group
by Telegram's `media_group_id`.

A second Ops bot (`/webhook/ops`, `src/services/ops_bot.py`, ADR-0036) handles user and
invite administration.

---

## Architecture

```
Capture: Telegram share sheet │ Chrome extension │ Dashboard Intake
                              ▼ HTTPS POST /webhook  |  POST /api/intake
FastAPI :8000  ─── detect_pipeline ──► create_and_enqueue_job ──► Redis LPUSH
      │                                                              │
      │ (photo messages run inline, never queued, ADR-0003)          ▼
      │                                                      Worker (asyncio)
      │                                                        │ BRPOP
      │                                                        ├─ video → short | long
      │                                                        ├─ article  → Jina → Gemini
      │                                                        ├─ repo     → GitHub → Gemini
      │                                                        ├─ document → liteparse → GCS
      │                                                        ├─ enrichment / prd_* / checklists
      │                                                        └─ screenshots / newsletter / purge

State:   SQLite WAL, holding jobs, links, chat_state, markdown_cache, allowed_domains, users
Queue:   Redis FIFO, survives restarts, supports multiple workers
Brain:   gemini-embedding-001 → NumPy cosine similarity → Drive Obsidian vault
Storage: your Google Drive and Sheets, plus GCS for content-addressed blobs
```

Two long-running processes are built from the same image.

- **API**: `src/main.py`, served by uvicorn as `src.main:app`. It hosts the Telegram
  webhook, the ops-bot webhook, `/health`, and the dashboard JSON API in `src/api/`.
  Auth is session-cookie middleware in `src/auth/`.
- **Worker**: `src/worker.py`. It BRPOPs `{"task": <discriminator>, "job_id": ...}` off
  the Redis list `video_jobs` and dispatches into `src/processors/`.

### URL routing

`detect_pipeline(url, extra_domains)` in `src/utils/validators.py`:

| Pattern | Pipeline |
| --- | --- |
| `youtube.com/shorts/`, `instagram.com/reel/`, `tiktok.com/@*/video/` | short |
| `youtube.com/watch`, `youtu.be/` | long |
| `github.com/<owner>/<repo>`, with gists and enterprise hosts rejected | repo |
| any URL whose path ends in `.pdf` | document |
| a host in `ARTICLE_DEFAULT_DOMAINS` or in the chat's `allowed_domains` | article |
| anything else | rejected |

### Job status FSM

```
pending → processing → transcript_done → enriching → done
                    ↘                              ↗
                     (short, article, document: no intermediate states)
                error (retry from the dashboard or with /force) │ cancelled
```

---

## Development

```Shell
pip install -r requirements-dev.txt   # includes runtime deps
python -m pytest tests -q             # around 1,300 tests
python -m pytest tests/test_article_pipeline.py -q
RUN_INTEGRATION=1 python -m pytest tests -q   # also hits real external APIs
ruff check src/                       # line-length 100, py311
```

### Web dashboard

```Shell
cd web
npm install
npm run dev                  # Next.js dev server
npm test                     # Vitest watch, or test:run / test:coverage
npm run lint
npm run build
```

`NEXT_PUBLIC_API_MOCK=1` runs the dashboard against the MSW handlers in
`web/lib/mocks/`, with the auth gate skipped outside production.

### Database migrations

Migrations run at startup via `PRAGMA user_version`. The table lives in
`src/database.py` as `_MIGRATIONS`. Each step is either a list of idempotent SQL
statements or an async callable for steps that need introspection. Rollback discipline
is ADR-0058.

```Shell
sqlite3 data/jobs.db "PRAGMA user_version;"
```

### Adding a pipeline

1. Add the `content_type` value to the CHECK constraint in `SCHEMA_SQL`, plus a migration
2. Teach `detect_pipeline` in `src/utils/validators.py` to recognize it
3. Create `src/processors/<type>.py` with `async def run(job: dict) -> None`
4. Add a task discriminator in `src/worker.py`
5. Route it in `src/telegram/webhook.py`, in the URL handler and in `/force` and `/freestyle`

---

## Configuration reference

`src/config.py` loads every env var through pydantic-settings. Only the two Telegram
secrets are required at startup. The rest degrade gracefully: a feature is simply off
when its key is missing.

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | yes | Bot token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | yes | Random secret for webhook validation |
| `REDIS_URL` | no | Redis connection string. Default `redis://redis:6379/0` |
| `DB_PATH` | no | SQLite file. Default `/app/data/jobs.db` |
| `WEBHOOK_URL` | no | Public HTTPS base URL |
| `GEMINI_FREE_API_KEY` | no | Primary Gemini key. Enrichment is off without it |
| `GEMINI_PAID_API_KEY` | no | Fallback when the free key hits its rate limit |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN` | no | Drive and Sheets OAuth |
| `GOOGLE_TOKEN_ENCRYPTION_KEY` | no | Fernet key for stored per-user Google tokens |
| `GOOGLE_SHEETS_ID` | no | The single consolidated workbook |
| `GOOGLE_DRIVE_FOLDER_SHORT/LONG/BRAIN/PRD/EXPORTS/SCREENSHOTS` | no | Drive folder IDs. The matching feature is off when unset |
| `GOOGLE_STORAGE_BUCKET` | no | GCS bucket for the document pipeline |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | no | Service-account key path for GCS auth. Falls back to OAuth |
| `BRAVE_API_KEY` | no | Brave Search. Link verification is off without it |
| `GITHUB_TOKEN` | no | Repo pipeline and `/find` enrichment, with a higher rate limit |
| `JINA_API_KEY` | no | Jina Reader. Works without a key, with a higher quota when set |
| `BRAIN_MIN_SCORE` | no | Cosine-similarity floor for `/find`. Default `0.5` |
| `PRD_MAX_TRANSCRIPT_CHARS` | no | PRD transcript cap. Default `60000` |
| `CHECKLISTS_MAX_TRANSCRIPT_CHARS` | no | Checklist transcript cap. Default `60000` |
| `OPERATOR_CHAT_ID` | no | Per-user export isolation (ADR-0027). Unset means export for all |
| `SESSION_BACKEND` | no | `redis` in production, `memory` for local auth loops |
| `OPS_BOT_TOKEN` and the other `OPS_*` vars | no | The Ops bot (ADR-0036) |
| `SMTP_*` | no | Transactional email. Approval still succeeds when unset |

---

## Google APIs setup

### OAuth for Drive and Sheets

Ownix uses OAuth with a refresh token, so a personal account needs no service account.
Files are created in the user's own Drive, which is the whole point.

1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable Drive API v3 and Sheets API v4
3. Create OAuth 2.0 credentials of the Desktop app type
4. Run the auth flow once to get a refresh token
5. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`

### Sheets workbook

One spreadsheet, one tab per domain, named exactly:

- `YouTube Transcript Index`
- `Short Video Analysis`
- `Article Analysis`
- `Repo Analysis`
- `mini PRD`

Set `GOOGLE_SHEETS_ID` to the spreadsheet ID from the URL. Tab routing lives in
`src/services/sheets.py`.

---

## Deployment

```Shell
docker-compose up -d --scale worker=2   # 2 workers, 1 API container
```

Compose runs `api`, `worker`, `transcript-service`, `redis`, and `cloudflared`. Vercel
serves the frontend in production, so the local `web` service in `docker-compose.yml`
stays commented out. If you run the transcript sidecar on the host instead of in
Compose, point `TRANSCRIPT_SERVICE_URL` and `FRAME_SERVICE_URL` at it.

### Logs

```Shell
docker-compose logs -f worker                              # structured JSON via structlog
docker-compose logs worker | jq 'select(.level=="error")'
docker-compose logs worker | jq 'select(.job_id=="20260528_143022_A3F9")'
```

---

## Project structure

```
src/
├── main.py              # FastAPI app, APScheduler (brain refresh Sun/Wed 09:00 UTC)
├── worker.py            # Task dispatch loop, boot-time reapers
├── database.py          # SQLite schema, PRAGMA migrations, all CRUD
├── brain.py             # Second Brain: ingest / search / rebuild / refresh
├── queue.py             # Redis brpop/lpush wrapper
├── config.py            # pydantic-settings, all env vars
├── api/                 # Dashboard JSON API: jobs, brain, spaces, intake, parsed,
│                        #   controls, auth, google_oauth, extension_auth, preview,
│                        #   templates, newsletter_digest
├── auth/                # Session-cookie middleware
├── processors/          # short_video, long_video, article, repo, document,
│                        #   enrichment, prd, checklists, screenshots, link,
│                        #   bookmarks, newsletter_poll, email_digest, purge
├── services/            # One module per external service: gemini*, drive, sheets,
│                        #   storage (GCS), jina, github, brave, transcript, parse,
│                        #   frames, google_auth/tokens/workspace, pdf_intake,
│                        #   space_export, job_recovery, ops_bot
├── telegram/            # webhook.py (routing, chat_state FSM), sender.py
├── utils/               # validators (detect_pipeline), markdown, logger, crypto
└── templates.py         # PROMPT_TEMPLATES registry, the store behind Recipes

extension/chrome/        # Chrome extension: right-click and shortcut capture
transcript_server.py     # Flask and Waitress sidecar on :5151 (yt-dlp, ffmpeg, transcripts)
tests/                   # pytest, pytest-asyncio

web/                     # Next.js 14 dashboard
├── app/(dashboard)/     # intake, feed, newsletter-digest, doc-parser, brain,
│                        #   spaces, prompts, controls, jobs/[id]
├── app/                 # landing, login, privacy, terms, accessibility, mini, offline
├── components/          # shell/ ui/ feed/ brain/ spaces/ doc-parser/ landing/ svg/
├── lib/                 # hooks, fetch utilities, MSW mocks
└── *.test.tsx           # Vitest, React Testing Library, MSW, colocated
```

---

## Further reading

- [`docs/brand/CONSTITUTION.md`](docs/brand/CONSTITUTION.md), why Ownix exists and what it refuses to do
- [`PRODUCT.md`](PRODUCT.md), users, purpose, brand personality, accessibility bar
- [`DESIGN.md`](DESIGN.md), the visual system and its normative tokens
- [`CONTEXT.md`](CONTEXT.md), domain glossary and architecture decisions
- [`docs/adr/`](docs/adr/), numbered architecture decision records
- [`docs/seed/PRD.md`](docs/seed/PRD.md), the full spec. Use its table of contents rather than reading top to bottom
- [`docs/seed/ARCHITECTURE.md`](docs/seed/ARCHITECTURE.md), diagrams and component map
- [`docs/seed/TECHSTACK.md`](docs/seed/TECHSTACK.md), tech choices, rationale, switch conditions
- [`CLAUDE.md`](CLAUDE.md), agent and contributor instructions

---

## License

MIT

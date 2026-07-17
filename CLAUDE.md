# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

vig — Video Intelligence Gateway. A Python (FastAPI + SQLite + Redis) service replacing a 60+ node n8n workflow. A Telegram bot ingests URLs and files and routes them through typed pipelines — short videos (Reels / TikTok / YouTube Shorts), long YouTube videos, dev articles, GitHub repos, PDF documents, and photo OCR — enriches them with Gemini, stores results in Google Drive + Sheets + GCS, and accumulates a semantic link graph ("Second Brain"). A Next.js dashboard ("The Operator's Console") under `web/` browses the results, and a second "Ops" Telegram bot handles user/invite administration.

Full spec: `docs/seed/PRD.md`, `docs/seed/ARCHITECTURE.md`, `docs/seed/TECHSTACK.md`; dashboard spec: `docs/seed/WEB-PRD.md`. Domain glossary and decisions: `CONTEXT.md` (repo root) + `docs/adr/`.

## Commands

Backend (repo root, Python 3.11+):

```shell
pip install -r requirements-dev.txt            # includes runtime deps
python -m pytest tests -q                      # full suite (never via rtk — see .claude/rules/rtk-tests.md)
python -m pytest tests/test_article_pipeline.py -q   # single file
RUN_INTEGRATION=1 python -m pytest tests -q    # also run tests hitting real external APIs
ruff check src/                                # lint (line-length 100, py311)
```

Services (Docker Compose runs `api`, `worker`, `transcript-service`, `redis`, `cloudflared`):

```shell
docker-compose up -d
python transcript_server.py                    # transcript sidecar on host, :5151 (needs flask waitress yt-dlp youtube-transcript-api Pillow)
```

Web dashboard (`web/`, Node):

```shell
npm run dev          # Next.js dev server
npm test             # Vitest watch — or test:run / test:coverage
npm run lint
npm run build
```

`NEXT_PUBLIC_API_MOCK=1` runs the dashboard in mock/demo mode (MSW handlers in `web/lib/mocks/`, auth gate skipped outside production). In production the frontend is served by Vercel — the local `web` service in `docker-compose.yml` is commented out.

## Architecture

Two long-running processes are built from the same image:

- **API** — `src/main.py` (uvicorn `src.main:app`). Hosts the Telegram webhook (`src/telegram/webhook.py`), the ops-bot webhook (`/webhook/ops`, handlers in `src/services/ops_bot.py`), `/health`, and the dashboard JSON API (`src/api/` — jobs, brain, spaces, parsed/doc-parser, preview, controls, auth, google_oauth). Auth is session-cookie middleware in `src/auth/`.
- **Worker** — `src/worker.py`. BRPOPs JSON task envelopes `{"task": <discriminator>, "job_id": ...}` from the Redis list `video_jobs` (`src/queue.py`) and dispatches by discriminator: `video` (→ `short_video` or `long_video` by content_type), `enrichment`, `article`, `repo`, `document`, `prd_auto`, `prd_auto_resend`, `prd_intent` — all in `src/processors/`.

Photo messages are the exception: processed inline in the webhook, never queued (ADR-0003); multi-image sends are auto-batched via Telegram `media_group_id`.

Supporting pieces:

- **URL routing** — `detect_pipeline(url, extra_domains)` in `src/utils/validators.py` maps a URL to content_type `short` / `long` / `repo` / `document` (`.pdf`) / `article` (default-domain or per-chat allowlist), else rejects.
- **Job creation core** — `create_and_enqueue_job()` in `src/services/jobs.py` (ADR-0033) owns dedup + create + enqueue. Its three callers (Telegram webhook, dashboard `POST /api/jobs`, repo follow-up) each own their own result notification.
- **State** — SQLite WAL at `data/jobs.db` via `src/database.py`. Migrations run automatically at startup via `PRAGMA user_version`; the `_MIGRATIONS` table maps each version to either a list of idempotent SQL statements or an async callable. Job status FSM: `pending → processing → transcript_done → enriching → done` (or `error` / `cancelled`); short/article/document skip the intermediate states.
- **Transcript sidecar** — `transcript_server.py` (Flask + waitress, :5151) wraps yt-dlp / youtube-transcript-api / frame extraction; runs on the host or as the `transcript-service` container.
- **Second Brain** — `src/brain.py`: Gemini embeddings + NumPy cosine similarity, Obsidian-style `.md` node graph in Drive, searched via `/find`.
- **External services** — one module each in `src/services/` (gemini, drive, sheets, storage/GCS, jina, github, brave, transcript, google_auth/tokens/workspace, pdf_intake, space_export, job_recovery, …).
- **Web** — Next.js 14 App Router. Routes live in `web/app/(dashboard)/` (feed, brain, spaces, prompts, controls, jobs/[id], doc-parser) plus public `login` / `privacy` / `terms` / `restricted`; the session gate is `web/middleware.ts`. Tests are Vitest + React Testing Library + MSW, colocated `.test.tsx` beside each component.

## Task lookup

When the user mentions a "task" or "TASK" by number (e.g. "task 14"), look it up first in `docs/TASK.md` — briefs are numbered `## N. <title>` headings. If the number doesn't match a brief there (or the match looks wrong for what the user described), ask for clarification instead of guessing another source.

## Navigating the PRD

`docs/seed/PRD.md` is ~3900 lines. Never read it top-to-bottom. Use the two-step lookup:

1. **Find the section** — read lines 16–115 (the TOC table) to map a topic to a section number and line.
2. **Jump to it** — `Read(file, offset=<line>, limit=80)` or grep: `grep -n "§14.6" docs/seed/PRD.md` returns the exact line, then read from there.

Every `##` / `###` / `####` heading is preceded by a `<!-- §N.M -->` anchor comment, so grep always lands one line above the heading.

## Library source (opensrc)

Key dependency source code is cached globally at `C:\Users\leone\.opensrc\repos\`. Use these paths when debugging library internals — prefer reading the actual source over guessing from docs.

| Package                       | Cached path                                               |
| ----------------------------- | --------------------------------------------------------- |
| `fastapi`                     | `github.com/fastapi/fastapi/0.136.3`                      |
| `google-genai`                | `github.com/googleapis/python-genai/2.7.0`                |
| `aiosqlite`                   | `github.com/omnilib/aiosqlite/0.22.1`                     |
| `redis-py`                    | `github.com/redis/redis-py/8.0.0`                         |
| `httpx`                       | `github.com/encode/httpx/0.28.1`                          |
| `apscheduler`                 | `github.com/agronholm/apscheduler/master`                 |
| `pydantic-settings`           | `github.com/pydantic/pydantic-settings/2.14.1`            |
| `structlog`                   | `github.com/hynek/structlog/25.5.0`                       |
| `vitest`                      | `github.com/vitest-dev/vitest/4.1.8`                      |
| `msw`                         | `github.com/mswjs/msw/2.14.6`                             |
| `@testing-library/react`      | `github.com/testing-library/react-testing-library/16.3.2` |
| `@testing-library/jest-dom`   | `github.com/testing-library/jest-dom/6.9.1`               |
| `@testing-library/user-event` | `github.com/testing-library/user-event/14.6.1`            |
| `react-force-graph-2d`        | `github.com/vasturiano/react-force-graph-2d/1.29.1`       |

All paths are relative to the cache root. Example full path: `C:\Users\leone\.opensrc\repos\github.com\fastapi\fastapi\0.136.3\`.

## Design Context

Frontend design (the `web/` Next.js dashboard) is guided by `PRODUCT.md` at the
repo root — register (`product`), users, purpose, brand personality (**bold,
precise, crafted**), anti-references, design principles, and the WCAG AA + reduced-motion
bar. The visual system lives in `DESIGN.md` at the repo root — North Star "The
Operator's Console": dark plate ladder, one rationed signal orange (`#f6921e`)
that always means _act here_, JetBrains Mono for machine facts, flat-by-default
elevation. Read both before any UI work; DESIGN.md's frontmatter tokens are
normative. Reference inspirations are archived in `designs/`.
The `impeccable` design skill lives at `agent-knowledge/skills/impeccable/` — read its `SKILL.md` before any UI work.

### Component layout (`web/components/`)

Every component lives at `web/components/<area>/<kebab-name>.tsx` — there are no
loose files at the components root. To find one, pick the folder by what it is:

- `shell/` — app chrome imported by layouts/shells (header, sidebar, page-shell, auth/public shells, invite/restricted gates, google-status, mock-provider).
- `ui/` — shared primitives used by 2+ features (badges, platform-icon, date-time, filter-bar, spinner, tab-bar, dialog, tooltip, export-modal, tag-picker, markdown-editor, …).
- `feed/`, `doc-parser/`, `brain/`, `spaces/`, `landing/` — feature folders named after the dashboard route that consumes them.
- `svg/` — icon components.

Files are kebab-case; a component's `.test.tsx` sits beside it. No barrel
`index.ts` files (they hurt grep-ability) — import the file directly, e.g.
`@/components/feed/job-card`.

## Agent skills

### Issue tracker

Issues live on GitHub at `Leon-87-7/vig`. Use the `gh` CLI for all operations. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` at the repo root (glossary + architecture decisions, the single source of truth for domain language) plus numbered ADRs in `docs/adr/`. Both grow lazily via `/grill-with-docs` sessions. See `docs/agents/domain.md`. Ops runbook: `docs/agents/ops.md`.

## Shared agent knowledge

Project-specific skills live in `agent-knowledge/`. Rules are in `.claude/rules/`
(auto-loaded) and commands in `.claude/commands/`.

Before making changes, inspect these folders for relevant guidance.

### Skill discovery

When a task matches one of the skill folders in `agent-knowledge/`, read that skill’s `SKILL.md` first.

A skill folder should follow this shape:

```txt
agent-knowledge/
  skill-name/
    SKILL.md
    reference.md
    heuristics.md
    examples.md
```

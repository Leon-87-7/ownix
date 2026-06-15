# vig — Claude Code instructions

Video Intelligence Gateway — a Python (FastAPI + SQLite + Redis) service replacing a 60+ node n8n workflow. Telegram bot that processes short videos (Instagram Reels, YouTube Shorts, TikTok) and long videos (YouTube), runs them through Gemini Vision / Text enrichment, stores results in Google Drive + Sheets, and accumulates a semantic link graph (Second Brain). See `docs/seed/PRD.md`, `docs/seed/ARCHITECTURE.md`, `docs/seed/TECHSTACK.md` for full spec.

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
The `impeccable` design skill lives at `.claude/skills/impeccable/` (run `/impeccable`).

## Agent skills

### Issue tracker

Issues live on GitHub at `Leon-87-7/vig`. Use the `gh` CLI for all operations. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root (neither yet exists; `/grill-with-docs` creates them lazily as terms/decisions get resolved). See `docs/agents/domain.md`.

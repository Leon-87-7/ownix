# vig — Claude Code instructions

Video Intelligence Gateway — a Python (FastAPI + SQLite + Redis) service replacing a 60+ node n8n workflow. Telegram bot that processes short videos (Instagram Reels, YouTube Shorts, TikTok) and long videos (YouTube), runs them through Gemini Vision / Text enrichment, stores results in Google Drive + Sheets, and accumulates a semantic link graph (Second Brain). See `docs/seed/PRD.md`, `docs/seed/ARCHITECTURE.md`, `docs/seed/TECHSTACK.md` for full spec.

## Navigating the PRD

`docs/seed/PRD.md` is ~3900 lines. Never read it top-to-bottom. Use the two-step lookup:

1. **Find the section** — read lines 16–115 (the TOC table) to map a topic to a section number and line.
2. **Jump to it** — `Read(file, offset=<line>, limit=80)` or grep: `grep -n "§14.6" docs/seed/PRD.md` returns the exact line, then read from there.

Every `##` / `###` / `####` heading is preceded by a `<!-- §N.M -->` anchor comment, so grep always lands one line above the heading.

## Agent skills

### Issue tracker

Issues live on GitHub at `Leon-87-7/vig`. Use the `gh` CLI for all operations. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root (neither yet exists; `/grill-with-docs` creates them lazily as terms/decisions get resolved). See `docs/agents/domain.md`.

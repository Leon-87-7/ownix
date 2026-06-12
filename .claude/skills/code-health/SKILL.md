---
name: code-health
description: Use when running a periodic codebase health check, when pyscn or fallow report failing gates (complexity, duplication, dead code, architecture, CRAP), or before merging refactors that must keep static-analysis scores green. Applies to this repo's Python source and the web/ Next.js dashboard.
---

# Code Health Check (pyscn + fallow)

## Overview

Two analyzers gate this repo: **pyscn** (Python: `src/`, `transcript_server.py`) and **fallow** (TypeScript: `web/`). Green = pyscn Health ≥ 85 with no ❌ category, fallow exits 0. The skill's core discipline: **run fresh, triage noise from signal, fix only signal, verify with a re-run.**

## Running the analyzers — exact invocations

The rtk hook can mangle `npx`/`uvx`; if a bare call errors with "Missing script" or "Unknown command", wrap with `rtk proxy`. **Never fall back to a cached report in `.pyscn/reports/` — always produce a fresh run** (cached data goes stale silently).

```bash
# Python — from repo root, production paths ONLY (the config's exclude_patterns
# are NOT honored by the CLI — passing "." silently re-includes tests/ and scripts/)
rtk proxy uvx pyscn@latest analyze src transcript_server.py --json
# → writes .pyscn/reports/analyze_<timestamp>.json; parse with encoding="utf-8" (cp1252 default breaks)

# Web — MUST run from web/ (root run loses node_modules resolution)
cd web && npm run test:coverage
rtk proxy npx fallow                                              # combined gates; exit 0 = green
rtk proxy npx fallow health --coverage coverage/coverage-final.json  # exact CRAP scores
# (fallow ≥2.93: --coverage exists only on the `health` subcommand, not top-level)
```

## Triage rules — noise vs signal

| Finding | Verdict | Action |
|---|---|---|
| pyscn "unknown layer" / strict_mode warnings | Config gap, not code | Edit `.pyscn.toml` `[[architecture.layers]]` (keyword package lists — there is no "entry" layer concept; `main` belongs to `presentation`) |
| pyscn clone groups in `tests/` | Excluded by config | If they reappear, fix `exclude_patterns` in `.pyscn.toml` — never hand-dedupe tests |
| fallow CRAP ≈ 30 with low CC | Missing coverage, not complexity | Add hook/component tests, re-run with `--coverage` |
| pyscn clones in `src/` ≥ 0.85 similarity | Real | Extract shared helper |
| Production functions CC ≥ 10 | Real | Stage-split into helpers (CC < 5 drops out of the score denominator) |
| fallow unused exports | Real (verify with `tsc --noEmit` after) | Strip `export` keyword; keep symbol |
| fallow unused deps that are peer-deps (e.g. @milkdown/*) | False positive | Ignore in fallow config, do not uninstall |

## Fixing — hard constraints

- **`src/telegram/webhook.py` is never split into modules** (ADR-0015 wontfix). Complexity fixes stay in-file.
- **Log event names and user-facing message strings byte-identical** — tests and log consumers assert on them.
- Characterization tests **before** refactoring untested code; run the module's tests after every extraction.
- Branch + small conventional commits + PR. Never merge to main.
- Implementation subagents: sonnet.

## Loop

1. Confirm baselines green: `python -m pytest -q` and `cd web && npx vitest run && npx tsc --noEmit`. Red baseline → stop, report, don't refactor.
2. Fresh analyzer runs (commands above).
3. Triage every finding with the table; list signal items with file:line.
4. **Before proposing any fix, read `docs/superpowers/plans/2026-06-11-static-analysis-green.md`** — it contains tested recipes for this exact codebase (helper extractions, stage splits, the `.pyscn.toml` schema, characterization-test patterns). Reuse its patterns; do not re-derive them.
5. Fix signal in priority order (score impact ÷ effort), one commit per fix.
6. Re-run analyzers; paste before/after score table in the PR.

## Common mistakes

- Concluding pyscn "isn't installed" — it runs via `uvx`, nothing is in PATH by design.
- Editing `pyproject.toml` for pyscn — config lives in `.pyscn.toml` only.
- Chasing the duplication score by rewriting test files.
- Refactoring to silence a CRAP score that a coverage file would clear.

---
name: code-health
description: Use when running a periodic codebase health check, when pyscn or fallow report a failing gate (complexity, duplication, dead code, architecture, CRAP), or before merging a refactor that must keep static-analysis green. Covers this repo's Python source and the web/ Next.js dashboard.
---

# Code Health Check (pyscn + fallow)

Two analyzers gate this repo: **pyscn** (Python — `src/`, `transcript_server.py`) and **fallow** (TypeScript — `web/`). **Green** means pyscn Health ≥ 85 with no ❌ category, and fallow exits 0. Run fresh, triage noise from signal, fix only signal, verify green with a re-run.

## Loop

1. **Confirm baselines are green first**: `python -m pytest -q` and (`cd web && npx vitest run && npx tsc --noEmit`). A red baseline means stop and report — don't refactor on top of an already-broken build.
2. **Run both analyzers fresh.** Never reuse a cached `.pyscn/reports/` file — it goes stale silently.
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
   If a bare `npx`/`uvx` call errors with "Missing script" or "Unknown command", the rtk hook mangled it — wrap with `rtk proxy` as above.
3. **Triage every finding** against this table before touching anything; list signal items with file:line, skip noise.

   | Finding | Verdict | Action |
   |---|---|---|
   | pyscn "unknown layer" / strict_mode warnings | Config gap, not code | Edit `.pyscn.toml` `[[architecture.layers]]` (keyword package lists — there is no "entry" layer; `main` belongs to `presentation`) |
   | pyscn clone groups in `tests/` | Excluded by config | If they reappear, fix `exclude_patterns` in `.pyscn.toml` — never hand-dedupe tests |
   | fallow CRAP ≈ 30 with low CC | Missing coverage, not complexity | Add hook/component tests, re-run with `--coverage` |
   | pyscn clones in `src/` ≥ 0.85 similarity | Real | Extract shared helper |
   | Production functions CC ≥ 10 | Real | Stage-split into helpers (CC < 5 drops out of the score denominator) |
   | fallow unused exports | Real (verify with `tsc --noEmit` after) | Strip `export` keyword; keep symbol |
   | fallow unused deps that are peer-deps (e.g. `@milkdown/*`) | False positive | Ignore in fallow config, do not uninstall |

4. **Before proposing any fix, read `docs/superpowers/plans/2026-06-11-static-analysis-green.md`** — it has tested recipes for this exact codebase (helper extractions, stage splits, the `.pyscn.toml` schema, characterization-test patterns). Reuse them; don't re-derive.
5. **Fix signal in priority order** (score impact ÷ effort), one commit per fix, under the constraints below.
6. **Re-run both analyzers**; paste a before/after score table in the PR.

## Fixing constraints

- `src/telegram/webhook.py` is never split into modules (ADR-0015 wontfix) — complexity fixes stay in-file.
- Log event names and user-facing message strings stay byte-identical — tests and log consumers assert on them.
- Write characterization tests **before** refactoring untested code; run the module's tests after every extraction.
- Branch + small conventional commits + PR. Never merge to main.
- Implementation subagents: sonnet.

## Common mistakes

- Concluding pyscn "isn't installed" — it runs via `uvx`, nothing is in PATH by design.
- Editing `pyproject.toml` for pyscn — config lives in `.pyscn.toml` only.
- Chasing the duplication score by rewriting test files.
- Refactoring to silence a CRAP score that a coverage file would clear.

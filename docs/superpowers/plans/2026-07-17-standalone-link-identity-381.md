# Standalone Link Identity (#381) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete issue #381 — every Brain link gets a per-URL title *and* description (tiered: GitHub svc → meta parse → Jina), stored in a new `links.description` column and rendered as `title · description` with the video-topic provenance demoted to the expanded More panel — and fix the three review findings on the staged Codex patch (weak-title threshold, real-network test, GitHub description stuffed into title).

**Architecture:** Extend the staged resolver in `src/brain.py` from title-only to a `(title, description)` identity pair; one migration adds `links.description`; `list_links` returns it; the web `LinkRow`/`LinkDescription` render it. Search/embedding cutover is **#384 — out of scope here**.

**Tech Stack:** Python 3.11 (httpx, aiosqlite), Next.js 14 + Vitest.

## Global Constraints

- Grill decisions (docs/TASK.md task 32, CONTEXT.md "Standalone link identity") are fixed: tier order GitHub → meta parse → Jina; **<40-char vagueness rule applies to descriptions, not titles**; provenance only at the bottom of the expanded More panel.
- `ruff check src/` clean (line-length 100); `python -m pytest tests -q` green (never via rtk).
- Web: `npm test -- --run`, `npm run lint` green; tests colocated.
- Do NOT touch `list_links` LIKE columns or the embedding doc (that's #384).
- No new dependencies.

---

### Task 1: Fix the resolver — identity pair + correct thresholds (src/brain.py, src/services/github.py)

**Files:**
- Modify: `src/brain.py` (staged resolver block, ~lines 75–190)
- Modify: `src/services/github.py` (replace `_fetch_repo_description_sync` duplication)
- Test: `tests/test_brain.py` (rewrite the four staged resolver tests)

**Interfaces:**
- Produces: `async _resolve_identity(url: str) -> tuple[str, str]` — `(title, description)`, description may be `""`. `_resolve_title` is deleted. `fetch_repo_description(owner, repo, token) -> str | None` stays (reimplemented via `_fetch_bundle_meta_sync`).

- [ ] **Step 1: Rewrite resolver tests** — patch every network seam; assert Jina is NOT called for a strong meta result; GitHub returns `(owner/repo, description)` as a *pair* (no em-dash stuffing); weak/missing description escalates to Jina (first paragraph of body); total failure → `(host hint, "")`.
- [ ] **Step 2: Run to verify failures** — `python -m pytest tests/test_brain.py -q` → new tests FAIL (no `_resolve_identity`).
- [ ] **Step 3: Implement** in `src/brain.py`:
  - `_is_weak_title(t)`: boilerplate set or `len < 5` (NOT 40).
  - `_is_vague_description(d)`: empty, `len < 40`, or boilerplate.
  - `_fetch_meta(url) -> tuple[str, str]`: one streamed GET (existing budget: 5s / 128 KB) parsed for title patterns (keep staged) + `og:description` / `name="description"` / `twitter:description`.
  - `_resolve_identity(url)`: GitHub → `(f"{owner}/{name}", description or "")`; else meta fetch; if title weak or description vague → Jina `fetch_markdown`, take stronger title and first non-empty paragraph ≤300 chars as description; fallback `( _fallback_title_hint(url), "")`.
  - `ingest_links`: call `_resolve_identity`; title precedence = resolved page title → provided label → hint; store `description`.
  - `src/services/github.py`: `fetch_repo_description` delegates to `_fetch_bundle_meta_sync` (delete `_fetch_repo_description_sync`).
- [ ] **Step 4: Tests pass** — `python -m pytest tests/test_brain.py -q`.
- [ ] **Step 5: Commit** — `fix(brain): resolver thresholds + (title, description) identity pair (refs #381)`.

### Task 2: Schema + API (`links.description`)

**Files:**
- Modify: `src/database.py` (links CREATE TABLE + append `_MIGRATIONS` entry `["ALTER TABLE links ADD COLUMN description TEXT"]`)
- Modify: `src/brain.py` (`SCHEMA_SQL` + ingest INSERT + `list_links` SELECT/payload)
- Test: `tests/test_brain.py` (ingest test asserts description persisted; list_links test asserts field present)

**Interfaces:**
- Produces: `list_links` items gain `"description": str | None`. Search LIKE columns unchanged.

- [ ] Steps: failing test → implement → pass → commit `feat(brain): links.description column + list payload (refs #381)`.

### Task 3: Web — `title · description`, provenance in More panel

**Files:**
- Modify: `web/lib/hooks/useLinksTable.ts` (`LinkRow` gains `description?: string | null`)
- Modify: `web/components/feed/links-table.tsx` (`LinkDescription`, `TruncatedDescription` gains optional `provenance` rendered only when expanded)
- Test: `web/components/feed/links-table.test.tsx` (new, colocated)

**Interfaces:**
- Consumes: `description` from Task 2's payload.
- Behavior: description present → line is `title · description`; expanded panel appends muted `From: <topic>` when topic exists. Description absent → today's `title · topic` line, no provenance footer.

- [ ] Steps: failing Vitest → implement → `npm test -- --run` pass → `npm run lint` → commit `feat(web): link rows show title·description, provenance in More panel (closes #381)`.

## Self-Review

- Spec coverage: tiers ✔ (Task 1), <40 on description ✔, schema/API ✔ (Task 2), display + provenance ✔ (Task 3), review findings 1–4 ✔ (Task 1). #384/#385 deliberately excluded.
- No placeholders; names consistent (`_resolve_identity`, `description`).

# Main Council Review — Fixes

> **For agentic workers:** This plan has been **chunked for parallel execution** — do not execute this file top-to-bottom. Work through the sub-plans in `sub-plans/` **in order** (chunk N+1 only after chunk N is fully committed); within each chunk, every task touches a disjoint set of files and is dispatched to parallel subagents (superpowers:subagent-driven-development). This file remains the source of truth for finding details; the sub-plans carry identical task bodies plus parallel-dispatch instructions.
>
> | Chunk | Sub-plan | Tasks | Theme |
> |---|---|---|---|
> | 1 | [sub-plans/main-council-fixes-chunk1-critical.md](sub-plans/main-council-fixes-chunk1-critical.md) | 1, 2, 4, 6, 7, 8, 11 | Critical — auth fail-open, crashing script, Gemini timeout, WCAG, React majors |
> | 2 | [sub-plans/main-council-fixes-chunk2-backend-and-react.md](sub-plans/main-council-fixes-chunk2-backend-and-react.md) | 3, 5, 9, 10, 13, 15 | Event-loop fix, GeminiClient shim deletion, React race/cleanup batch |
> | 3 | [sub-plans/main-council-fixes-chunk3-copy-and-hygiene.md](sub-plans/main-council-fixes-chunk3-copy-and-hygiene.md) | 12, 17, 20, 21*, 22, 26 | Admin-contact copy, decorative-signal removal, timeouts, dead code |
> | 4 | [sub-plans/main-council-fixes-chunk4-design-and-tasks.md](sub-plans/main-council-fixes-chunk4-design-and-tasks.md) | 14, 18, 19, 25, 27* | Eyebrow sweep, tabs hoisting, background-task tracking, scoping docs |
> | 5 | [sub-plans/main-council-fixes-chunk5-skeletons-and-webhook.md](sub-plans/main-council-fixes-chunk5-skeletons-and-webhook.md) | 16, 23, 24 | Spinner→skeleton conversion, webhook callback + copy sweeps |
>
> \* Tasks 21 and 27 are OPTIONAL (user-decision items).

**Goal:** Fix every finding from the `/council-review` of the vig codebase (5 parallel reviewers, synthesized) — 1 Blocker, 9 Major, 16 Minor, 7 Nit. The Blocker is a crashing one-time migration script that still references config that ADR-0013 removed. The Majors span an auth fail-open risk (empty webhook secret), a sync-DB-call-on-event-loop hot path, an unbounded Gemini timeout that can starve the shared thread pool, WCAG-failing invalid Tailwind class names, and missing React error/race handling. The rest are design-system consistency (dead classes, eyebrows, spinners-vs-skeletons) and small backend hygiene items.

**Architecture:** No new subsystems — every task is a scoped fix inside the existing FastAPI/SQLite/Redis backend (`src/`) or the Next.js dashboard (`web/`). Tasks are ordered by the reviewers' suggested fix order and independently committable; later tasks do not depend on earlier ones being done first (no shared new interfaces are introduced), so they may also be executed out of order or in parallel by different agents if desired.

**Tech Stack:** Python 3.11 (FastAPI, aiosqlite, structlog, google-genai SDK), pytest + pytest-asyncio (`asyncio_mode = "auto"`, see `pyproject.toml`); Next.js App Router, React, TypeScript, Tailwind, Vitest + Testing Library.

## Global Constraints

- This plan file is the only artifact this planning pass wrote. Every task below performs real source edits — do not treat the plan itself as read-only.
- Run Python tests via the PowerShell tool, never Bash — the rtk hook only intercepts the Bash tool and mangles/hangs pytest regardless of how the command is phrased (see `.claude/rules/rtk-tests.md`): `python -m pytest tests/test_foo.py -q` or `python -m pytest tests -q`. Split large runs into per-file/per-directory invocations for speed/readability.
- Run web tests with the repo's configured runner: `npx vitest run <path>` (Vitest 4.x, Testing Library — see `web/vitest.config.*`). Do not invent a different runner.
- Each task must end in its own commit with a conventional-commit message (`fix:`, `refactor:`, `chore:`, `perf:`, `docs:`) — do not batch unrelated tasks into one commit.
- Preserve existing behavior unless the finding explicitly calls for a behavior change — most tasks are bug fixes or refactors, not new features.
- Design-system edits (colors, spacing, copy casing) must follow `DESIGN.md` at the repo root (dark plate ladder, single rationed signal orange `#f6921e` = "act here", JetBrains Mono for machine facts) — do not invent new tokens; reuse existing Tailwind config classes (`bg-signal`, `text-onsignal`, `bg-raised`, `text-muted`, `border-line`, etc. — see `web/tailwind.config.ts`).
- Two tasks (Task 21: APScheduler→sleep-loop, Task 27: HKDF key derivation) are marked **OPTIONAL** — the review flagged them as "user decision" items. Implement them only if the user confirms; otherwise skip and leave them unchecked.
- Do not merge to `main`/`master` unless the user explicitly names it as the target in that message (repo rule, `.claude/rules/no-merge-to-main.md`).

---

## Task 1: `TELEGRAM_WEBHOOK_SECRET` / `TELEGRAM_BOT_TOKEN` must fail fast when empty

**Files:**
- Modify: `src/config.py:19-20`
- Create: `tests/test_config.py`

**Major:** Both fields are typed plain `str` with no minimum length. An empty `TELEGRAM_WEBHOOK_SECRET` (e.g. unset env var in a misconfigured deploy) makes `compare_digest("", "")` at `src/telegram/webhook.py:1445` return `True`, silently disabling webhook authentication — any caller can post fake Telegram updates. `pydantic-settings` already validates on `Settings()` construction (`settings = Settings()` at `src/config.py:123`), so a length guard turns this into a startup crash instead of a silent bypass.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for src/config.py — startup validation guards."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings


def _base_env(**overrides: str) -> dict[str, str]:
    env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_WEBHOOK_SECRET": "s3cr3t"}
    env.update(overrides)
    return env


def test_settings_rejects_empty_webhook_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_WEBHOOK_SECRET=""))


def test_settings_rejects_empty_bot_token() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_BOT_TOKEN=""))


def test_settings_accepts_nonempty_required_fields() -> None:
    s = Settings(**_base_env())
    assert s.TELEGRAM_WEBHOOK_SECRET == "s3cr3t"
    assert s.TELEGRAM_BOT_TOKEN == "123:ABC"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL — `Settings(TELEGRAM_WEBHOOK_SECRET="")` currently succeeds, so `pytest.raises(ValidationError)` raises `Failed: DID NOT RAISE`.

- [ ] **Step 3: Add the length guard**

In `src/config.py`, change:

```python
    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str
```

to:

```python
    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str = Field(min_length=1)
    TELEGRAM_WEBHOOK_SECRET: str = Field(min_length=1)
```

`Field` is already imported at the top of `src/config.py` (`from pydantic import Field`), so no import changes are needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full config-adjacent suite for regressions**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass — `TELEGRAM_WEBHOOK_SECRET`/`TELEGRAM_BOT_TOKEN` are already set to non-empty values in the test env/fixtures, so this is a no-op check, not a real regression risk.

- [ ] **Step 6: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "fix(config): fail fast on empty TELEGRAM_WEBHOOK_SECRET/TELEGRAM_BOT_TOKEN"
```

---

## Task 2: Delete `scripts/backfill_brain.py` (Blocker — crashes on run)

**Files:**
- Delete: `scripts/backfill_brain.py`

**Blocker:** `scripts/backfill_brain.py:143` and `:195` reference `settings.GOOGLE_SHEETS_ID_SHORT` / `settings.GOOGLE_SHEETS_ID_LONG`. ADR-0013 (`docs/adr/0013-consolidate-sheets-into-tabs.md`) consolidated the three per-domain sheet IDs into one `settings.GOOGLE_SHEETS_ID` (see `src/config.py:51-54`). `tests/test_sheets.py:26-39` (`test_settings_drops_legacy_short_var`, `test_settings_drops_legacy_long_var`) asserts these attributes raise `AttributeError` on `settings` — so this script now crashes with `AttributeError` at the first sheet read. It performs a one-time historical-data migration into the Second Brain that has already run (per the module docstring, it's a `python -m scripts.backfill_brain` one-shot); there's no live workbook layout to migrate against anymore, and rewriting it against the single-workbook layout would require re-deriving which sheet rows are "short" vs "long" from tab name instead of spreadsheet ID, plus a full re-test — effort with no remaining use. Delete it.

- [ ] **Step 1: Confirm no other code imports this script**

Run: `python -c "import ast,glob; [ast.parse(open(f, encoding='utf-8').read()) for f in glob.glob('src/**/*.py', recursive=True)]"` is not the check needed — instead grep for importers:

```bash
grep -rn "backfill_brain" --include="*.py" src tests
```

Expected: no output (only `scripts/backfill_brain.py` itself references itself; the module isn't imported elsewhere). If this grep returns hits outside `scripts/backfill_brain.py`, stop and re-scope this task — do not delete a script something else depends on.

- [ ] **Step 2: Delete the file**

```bash
git rm scripts/backfill_brain.py
```

- [ ] **Step 3: Verify the deletion doesn't break collection**

Run: `python -m pytest tests/test_sheets.py -q`
Expected: all pass — this suite doesn't import the script, it only asserts on `settings` shape (ADR-0013), so nothing here depends on the deleted file.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete scripts/backfill_brain.py — crashes on removed GOOGLE_SHEETS_ID_SHORT/LONG (ADR-0013), migration already ran"
```

---

## Task 3: `export_blocked` — move sync `sqlite3` call off the event loop

**Files:**
- Modify: `src/config.py:101-120`
- Modify: `src/services/drive.py:73,117,159` (await call sites)
- Modify: `src/services/sheets.py:103,111,163,215,280,288,327,334,353` (await call sites)
- Modify: `src/api/spaces.py:303` (await call site)
- Modify: `tests/test_export_gate.py`

**Major:** `Settings.export_blocked()` (`src/config.py:101-120`) opens a blocking `sqlite3.connect()` and runs a `SELECT` directly on the caller's coroutine — no `asyncio.to_thread`. It's called from 15 async call sites across `src/services/drive.py`, `src/services/sheets.py`, and `src/api/spaces.py`, all on the hot export path, so every export call blocks the single-threaded event loop for the duration of a disk read.

- [ ] **Step 1: Write the failing test (predicate must be awaitable)**

Add to `tests/test_export_gate.py`, right after the existing `test_export_blocked_truth_table`:

```python
@pytest.mark.asyncio
async def test_export_blocked_is_async(monkeypatch):
    """export_blocked must not block the event loop — it's awaited by 15 call sites."""
    import inspect

    assert inspect.iscoroutinefunction(settings.export_blocked)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_export_gate.py::test_export_blocked_is_async -q`
Expected: FAIL — `export_blocked` is currently a plain `def`, not `async def`.

- [ ] **Step 3: Make `export_blocked` async, run the DB read via `asyncio.to_thread`**

In `src/config.py`, add `import asyncio` to the top-of-file imports:

```python
import asyncio
import json
import sqlite3
```

Then replace the body of `export_blocked`:

```python
    async def export_blocked(self, chat_id: int | None) -> bool:
        """True when *chat_id* must NOT write to the operator's shared Drive/Sheets.

        Blocks only an explicit non-operator chat. A None chat_id (system/operator
        aggregate calls like brain rebuild) and an unset OPERATOR_CHAT_ID both pass.
        """
        if chat_id is not None:
            try:
                if await asyncio.to_thread(self._has_readable_google_token, chat_id):
                    return False
            except sqlite3.Error:
                return False if self.OPERATOR_CHAT_ID is None else chat_id != self.OPERATOR_CHAT_ID
        return (
            self.OPERATOR_CHAT_ID is not None
            and chat_id is not None
            and chat_id != self.OPERATOR_CHAT_ID
        )

    def _has_readable_google_token(self, chat_id: int) -> bool:
        """Sync helper — runs inside asyncio.to_thread by export_blocked."""
        with sqlite3.connect(self.DB_PATH) as conn:
            cur = conn.execute("SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            return row is not None and self._google_token_readable(str(row[0]))
```

- [ ] **Step 4: Update the 15 production call sites to `await`**

In `src/services/drive.py`, `src/services/sheets.py`, and `src/api/spaces.py`, change every `if settings.export_blocked(chat_id):` / `if settings.export_blocked(job.get("chat_id")):` to `if await settings.export_blocked(chat_id):` / `if await settings.export_blocked(job.get("chat_id")):`. All 15 call sites are already inside `async def` functions (verified: `drive.py`'s `upload_file`/`update_file`/`export_to_gdoc`; `sheets.py`'s `append_short_row`/`append_long_row`/`append_article_row`/`update_article_row`/`append_repo_row`/`update_repo_row`/`append_document_row`/`update_document_row`/`append_prd_row`; `spaces.py`'s `export_space`), so adding `await` requires no other signature changes.

- [ ] **Step 5: Update existing tests that call `export_blocked` synchronously**

In `tests/test_export_gate.py`:
1. `test_export_blocked_truth_table` (line 30) and `test_export_never_blocked_when_operator_unset` (line 38) currently call `settings.export_blocked(...)` as a plain sync function with no `await`. Convert both to `async def`, add `@pytest.mark.asyncio` above each, and `await` every call:

```python
@pytest.mark.asyncio
async def test_export_blocked_truth_table(monkeypatch):
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)
    assert await settings.export_blocked(INTRUDER) is True
    assert await settings.export_blocked(OPERATOR) is False
    # System/operator-internal calls (no chat_id, e.g. brain rebuild) never blocked.
    assert await settings.export_blocked(None) is False


@pytest.mark.asyncio
async def test_export_never_blocked_when_operator_unset(monkeypatch):
    """Backward-compat: an unconfigured deployment exports for everyone."""
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)
    assert await settings.export_blocked(INTRUDER) is False
    assert await settings.export_blocked(OPERATOR) is False
```

2. `test_export_blocked_allows_user_with_readable_google_token` (already `async def`, line 297) — change lines 309 and 311 from `settings.export_blocked(INTRUDER)` to `await settings.export_blocked(INTRUDER)`.

- [ ] **Step 6: Run the full export-gate suite**

Run: `python -m pytest tests/test_export_gate.py -q`
Expected: all pass, including the new `test_export_blocked_is_async`.

- [ ] **Step 7: Run the broader suites that exercise these call sites**

Run: `python -m pytest tests/test_sheets.py tests/test_prd.py -q`
Expected: all pass — these suites call `append_*`/`update_*` sheets functions that now `await settings.export_blocked(...)` internally.

- [ ] **Step 8: Commit**

```bash
git add src/config.py src/services/drive.py src/services/sheets.py src/api/spaces.py tests/test_export_gate.py
git commit -m "perf(config): move export_blocked's sqlite3 read off the event loop via asyncio.to_thread"
```

---

## Task 4: Gemini client — add an explicit request timeout

**Files:**
- Modify: `src/services/gemini.py:147-159`
- Modify: `tests/test_gemini_client.py`

**Major:** `_call_sync` (`src/services/gemini.py:147-159`) builds `genai.Client(api_key=api_key)` with no `http_options`, so the SDK's default timeout is `None` (no timeout). It runs via `asyncio.to_thread` (`_call_with_fallback`, line 169) on Python's shared default `ThreadPoolExecutor` — the same pool used by every other `asyncio.to_thread` call in the app (Drive, Sheets, GCS, GitHub). A hung Gemini request never returns a thread to the pool, so enough concurrent hangs starve unrelated I/O across the whole app. Fix by passing an explicit timeout via `types.HttpOptions` — 90 seconds balances Gemini's occasionally-slow vision calls against not hanging the pool indefinitely.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gemini_client.py`:

```python
# ---------------------------------------------------------------------------
# Test 8: _call_sync builds the client with an explicit HttpOptions timeout
# ---------------------------------------------------------------------------

def test_call_sync_sets_explicit_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """genai.Client must be constructed with a bounded http_options.timeout so a
    hung request can't hold a asyncio.to_thread worker forever."""
    from google.genai import types
    from src.services.gemini import _call_sync

    captured: dict[str, object] = {}

    class _FakeModels:
        def generate_content(self, *, model, contents, config=None):
            return _make_response('{"ok": true}')

    class _FakeClient:
        def __init__(self, *, api_key, http_options=None):
            captured["http_options"] = http_options
            self.models = _FakeModels()

    monkeypatch.setattr("google.genai.Client", _FakeClient)

    _call_sync("hello", api_key="k", model="gemini-2.5-flash")

    http_options = captured["http_options"]
    assert isinstance(http_options, types.HttpOptions)
    assert http_options.timeout == 90_000  # milliseconds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gemini_client.py::test_call_sync_sets_explicit_timeout -q`
Expected: FAIL — `captured["http_options"]` is `None` today.

- [ ] **Step 3: Pass an explicit `HttpOptions` timeout**

In `src/services/gemini.py`, add a module-level constant near the top (after the existing imports, before `_VISION_PROMPT`/other constants):

```python
_GEMINI_TIMEOUT_MS = 90_000  # 90s — bounds a hung request's hold on the shared to_thread pool
```

Then change `_call_sync`:

```python
def _call_sync(parts: object, *, api_key: str, model: str, schema: type | dict | None = None):
    """Sync generate_content call — run inside asyncio.to_thread by _call_with_fallback."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=_GEMINI_TIMEOUT_MS))
    if schema is not None:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        )
        return client.models.generate_content(model=model, contents=parts, config=config)
    return client.models.generate_content(model=model, contents=parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gemini_client.py -q`
Expected: all pass (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/services/gemini.py tests/test_gemini_client.py
git commit -m "fix(gemini): bound genai.Client requests to a 90s timeout so a hang can't starve the shared thread pool"
```

---

## Task 5: Delete the `GeminiClient` passthrough shim

**Files:**
- Modify: `src/services/gemini.py:284-299`
- Modify: `src/processors/prd.py:502,506`
- Modify: `src/processors/enrichment.py:162,171`
- Modify: `src/processors/document.py:196-207`
- Modify: `src/processors/article.py:275,277`
- Modify: `src/brain.py:78-99`
- Modify: `src/api/parsed.py:116-126`
- Modify: `tests/test_gemini_client.py`
- Modify: `tests/test_document_processor.py:53-55`
- Modify: `tests/test_article_pipeline.py` (6 patch sites)
- Modify: `tests/test_prd.py` (4 patch sites)
- Modify: `tests/test_brain.py:108-135`

**Major:** `GeminiClient` (`src/services/gemini.py:288-296`) is a single-method class (`async def generate(...)`) that does nothing but call the module-level `generate()` function — kept only so tests can `monkeypatch.setattr(gemini_client, "generate", ...)`. It has no state and one production behavior. Delete the class and `gemini_client` instance; callers use the module function `generate()` directly, and tests monkeypatch `src.services.gemini.generate` instead.

- [ ] **Step 1: Delete the class from `src/services/gemini.py`**

Remove lines 283-299 (the `# --- Backward-compat` comment block, the `GeminiClient` class, and the `gemini_client = GeminiClient()` instance) entirely. `generate()` (already defined at line 183) remains the public entry point.

- [ ] **Step 2: Update production call sites to import and call `generate` directly**

In each of these files, replace the local import + call:

`src/processors/prd.py:502,506`:
```python
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        raw_prd = await generate(prompt, model=model, schema=PRD_JSON_SCHEMA)
```

`src/processors/enrichment.py:162,171`:
```python
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        raw = await generate(prompt, model="gemini-2.5-flash")
```

`src/processors/document.py:196-207`:
```python
    from src.services.gemini import generate
    raw = await generate(
        ...
    )
    ...
    summary_md = await generate(summary_prompt, model="gemini-2.5-flash")
```

`src/processors/article.py:275,277`:
```python
    from src.services.gemini import GeminiUnavailableError, generate
    ...
        raw = await generate(prompt, model="gemini-2.5-flash")
```

`src/brain.py:78-99`: rename the local import and call site inside `_resolve_title`:
```python
    """Resolve a short human title for a URL via Gemini's generate(); fall back to URL hint on any error."""
    from src.services.gemini import generate, GeminiUnavailableError
    ...
        result = await generate(prompt, model="gemini-2.5-flash-lite")
```

`src/api/parsed.py:116-126`:
```python
    from src.services.gemini import generate
    ...
    md = await generate(f"{instruction}\n\nDOCUMENT:\n{text}", model="gemini-2.5-flash")
```

- [ ] **Step 3: Update `tests/test_gemini_client.py` to monkeypatch the module function**

Change the import at the top from:
```python
from src.services.gemini import GeminiClient, GeminiUnavailableError, gemini_client
```
to:
```python
from src.services.gemini import GeminiUnavailableError, generate
```

Then in tests 1-5 (`test_generate_single_key_success`, `test_generate_both_keys_fail`, `test_generate_first_key_fails_second_succeeds`, `test_generate_passes_schema_to_call_sync`, `test_generate_no_keys_raises`), replace every `await gemini_client.generate(...)` with `await generate(...)`. Tests 6-7 already call module functions directly and need no change.

- [ ] **Step 4: Update the other test files' monkeypatches**

`tests/test_document_processor.py:53-55`:
```python
    # generate is imported lazily inside run(); patch the module attribute directly.
    monkeypatch.setattr(gemini.generate, "__wrapped__", mocks["generate"], raising=False)
```
Actually simpler and consistent with the module's own style — replace with:
```python
    monkeypatch.setattr(gemini, "generate", mocks["generate"])
```

`tests/test_article_pipeline.py` — all 6 occurrences of `monkeypatch.setattr(gc_module.gemini_client, "generate", ...)` (lines 147, 186, 218, 258, 291, 331) become `monkeypatch.setattr(gc_module, "generate", ...)`.

`tests/test_prd.py` — all 4 occurrences of:
```python
    monkeypatch.setattr(
        "src.services.gemini.gemini_client.generate",
        AsyncMock(return_value=...),
    )
```
become:
```python
    monkeypatch.setattr(
        "src.services.gemini.generate",
        AsyncMock(return_value=...),
    )
```

`tests/test_brain.py:108-135` — both occurrences of:
```python
    with patch("src.services.gemini.gemini_client") as mock_client:
        mock_client.generate = AsyncMock(return_value="vercel/next.js")
        result = await _resolve_title(url, topic)
```
become:
```python
    with patch("src.services.gemini.generate", new=AsyncMock(return_value="vercel/next.js")):
        result = await _resolve_title(url, topic)
```
(and the sibling test with `side_effect=GeminiUnavailableError("both failed")` follows the same shape).

- [ ] **Step 5: Run the full affected suite**

Run:
```bash
python -m pytest tests/test_gemini_client.py tests/test_document_processor.py tests/test_article_pipeline.py -q
python -m pytest tests/test_prd.py tests/test_brain.py -q
```
Expected: all pass, behavior unchanged (pure refactor).

- [ ] **Step 6: Grep for any remaining reference**

Run: `grep -rn "gemini_client\|GeminiClient" --include="*.py" src tests`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add src/services/gemini.py src/processors/prd.py src/processors/enrichment.py src/processors/document.py src/processors/article.py src/brain.py src/api/parsed.py tests/test_gemini_client.py tests/test_document_processor.py tests/test_article_pipeline.py tests/test_prd.py tests/test_brain.py
git commit -m "refactor(gemini): delete GeminiClient passthrough shim, call generate() directly"
```

---

## Task 6: Invalid Tailwind class sweep (WCAG contrast fix + dead classes)

**Files:**
- Modify: `web/app/mini/page.tsx:94`
- Modify: `web/app/(dashboard)/page.tsx:167`
- Modify: `web/components/brain-graph.tsx:231,232,282`

**Major:** Three unrelated files use Tailwind class names that don't exist in `web/tailwind.config.ts`'s token set, so they silently no-op (Tailwind drops unknown classes) instead of applying the intended style:
1. `web/app/mini/page.tsx:94` — `text-on-signal` and `disabled:bg-surface-raised` (config defines `onsignal`/`raised`, no hyphen, no `surface-` prefix). The CTA button text falls through to ambient ink-on-signal-orange, which measures ≈2.2:1 contrast — fails WCAG AA (needs 4.5:1 for body text).
2. `web/app/(dashboard)/page.tsx:167` — `rounded-card`, `bg-panel`, `shadow-card` on the "Connect Google" banner — none of these exist in the token set.
3. `web/components/brain-graph.tsx:231,232,282` — `hover:bg-surface-raised` (3 occurrences) should be `hover:bg-raised`.

- [ ] **Step 1: Fix `web/app/mini/page.tsx:94`**

Change:
```tsx
          className="mt-8 h-11 rounded-md bg-signal px-4 text-sm font-medium text-on-signal transition-ui hover:bg-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-surface-raised disabled:text-muted"
```
to:
```tsx
          className="mt-8 h-11 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-raised disabled:text-muted"
```

- [ ] **Step 2: Fix `web/app/(dashboard)/page.tsx:167`**

Change:
```tsx
      <section className="rounded-card border border-line bg-panel p-4 shadow-card">
```
to:
```tsx
      <section className="rounded-lg border border-line bg-surface p-4">
```

(This matches the card treatment used elsewhere on the same page, e.g. `SpaceCard.tsx`'s `rounded-lg border border-line bg-surface`.)

- [ ] **Step 3: Fix `web/components/brain-graph.tsx:231,232,282`**

At line 231-232, change:
```tsx
                    className={`inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium shadow-sm ring-1 transition-[background-color,color,opacity,transform] duration-150 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 ${
                      hidden
                        ? 'bg-transparent text-body ring-line hover:bg-surface-raised hover:text-ink'
                        : 'bg-surface-raised text-ink ring-line-strong hover:bg-line'
                    }`}
```
to:
```tsx
                    className={`inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium shadow-sm ring-1 transition-[background-color,color,opacity,transform] duration-150 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 ${
                      hidden
                        ? 'bg-transparent text-body ring-line hover:bg-raised hover:text-ink'
                        : 'bg-raised text-ink ring-line-strong hover:bg-line'
                    }`}
```

At line 282, change:
```tsx
      className="min-h-10 min-w-10 rounded-md bg-transparent px-3 text-xs font-medium text-body shadow-sm ring-1 ring-transparent transition-[background-color,color,opacity,transform] duration-150 hover:bg-surface-raised hover:text-ink active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none motion-reduce:active:scale-100"
```
to:
```tsx
      className="min-h-10 min-w-10 rounded-md bg-transparent px-3 text-xs font-medium text-body shadow-sm ring-1 ring-transparent transition-[background-color,color,opacity,transform] duration-150 hover:bg-raised hover:text-ink active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none motion-reduce:active:scale-100"
```

- [ ] **Step 4: Grep for any remaining invalid occurrences of these exact typo classes**

Run: `grep -rn "text-on-signal\|bg-surface-raised\|rounded-card\|bg-panel\b\|shadow-card" web --include="*.tsx"`
Expected: no output.

- [ ] **Step 5: Run the web test suite for the touched components**

Run: `npx vitest run web/app/mini web/app/\(dashboard\)/page.test.tsx web/components/brain-graph.test.tsx`

If `brain-graph.test.tsx` or a mini-app test doesn't exist, run the closest existing suite instead:
```bash
npx vitest run web/app/\(dashboard\)/page.test.tsx
```
Expected: all pass — these are pure class-string swaps with no behavior change.

- [ ] **Step 6: Commit**

```bash
git add web/app/mini/page.tsx "web/app/(dashboard)/page.tsx" web/components/brain-graph.tsx
git commit -m "fix(web): replace invalid Tailwind class names (text-on-signal, bg-surface-raised, rounded-card, bg-panel, shadow-card) with real tokens"
```

---

## Task 7: `TelegramToggle` — in-flight guard + unmount cleanup

**Files:**
- Modify: `web/components/doc-parser/telegram-toggle.tsx`
- Test: `web/components/doc-parser/telegram-toggle.test.tsx` (create if it doesn't exist)

**Major + Minor (same file, same fix shape):**
1. `persist()` (lines 13-18) has no in-flight guard or stale-response check — a rapid double-tap fires two overlapping `PUT` requests and the *last one to resolve* wins, regardless of which the user intended (may land the toggle in the state before the user's actual last click). `SpaceCard.tsx:45` (`disabled={deleting}`) shows the project's existing pattern: track an in-flight boolean and disable the trigger while a request is outstanding.
2. `startHold`'s `setTimeout` (line 23, held in the `timer` ref) is never cleared on unmount — if the component unmounts mid-hold (e.g. navigating away while pressing), the timer still fires later and calls `persist()` against an unmounted component's closure.

- [ ] **Step 1: Write the failing test for the in-flight guard**

Check whether `web/components/doc-parser/telegram-toggle.test.tsx` exists; if not, create it:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { TelegramToggle } from './telegram-toggle';

describe('TelegramToggle', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('disables the button while a persist request is in flight', async () => {
    let resolveFetch: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.spyOn(global, 'fetch').mockReturnValue(pending as unknown as Promise<Response>);

    render(<TelegramToggle jobId="j1" value="off" />);
    const button = screen.getByRole('button', { name: /telegram delivery/i });

    fireEvent.click(button);
    expect(button).toBeDisabled();

    resolveFetch!(new Response(JSON.stringify({ telegram_delivery: 'on' }), { status: 200 }));
    await waitFor(() => expect(button).not.toBeDisabled());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/components/doc-parser/telegram-toggle.test.tsx`
Expected: FAIL — the button has no `disabled` attribute today, so `expect(button).toBeDisabled()` fails right after the click.

- [ ] **Step 3: Add the in-flight guard and unmount-safe timer cleanup**

Replace the full component body:

```tsx
'use client';

import { useEffect, useRef, useState } from 'react';

type State = 'off' | 'on' | 'retroactive';

export function TelegramToggle({ jobId, value = 'off' }: { jobId: string; value?: State }) {
  const [state, setState] = useState<State>(value);
  const [holding, setHolding] = useState(false);
  const [pending, setPending] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false); // hold completed → swallow the trailing click
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  async function persist(next: State) {
    if (pending) return; // in-flight guard — a rapid double-tap must not fire overlapping PUTs
    setPending(true);
    try {
      const res = await fetch(`/api/parsed/${jobId}/telegram-delivery`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: next }) });
      if (!res.ok) { console.error(`telegram-delivery PUT failed: ${res.status}`); return; } // failed PUT → keep state, surface so it's not silent
      const data = await res.json();
      if (mounted.current) setState(data.telegram_delivery);
    } finally {
      if (mounted.current) setPending(false);
    }
  }

  function startHold() {
    setHolding(true);
    fired.current = false;
    timer.current = setTimeout(() => { fired.current = true; persist('retroactive'); }, 1500);
  }
  function cancelHold() {
    setHolding(false);
    if (timer.current) clearTimeout(timer.current);
  }

  const isOff = state === 'off';

  return <button type="button" aria-label={`Telegram delivery ${state}`} aria-pressed={state !== 'off'} disabled={pending} onClick={(e) => { e.preventDefault(); if (fired.current) { fired.current = false; return; } persist(state === 'off' ? 'on' : 'off'); }} onPointerDown={startHold} onPointerUp={cancelHold} onPointerLeave={cancelHold} className={`relative flex h-[26px] w-[26px] items-center justify-center rounded-full border transition-ui disabled:cursor-not-allowed disabled:opacity-60 ${isOff ? 'border-line' : 'border-telegram-blue'} ${holding ? 'doc-telegram-hold' : ''}`}>
    {/* Official Telegram mark (simpleicons "telegram"): a disc + plane core. On = brand
        #26A5E4 / #ffffff; off = status-cancelled / cancelled-tint so it reads as inactive.
        The disc and plane carry the affordance, so the icon needs no currentColor. */}
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <circle cx="12" cy="12" r="12" className={`transition-ui ${isOff ? 'fill-status-cancelled' : 'fill-telegram-blue'}`} />
      <path className={`transition-ui ${isOff ? 'fill-status-cancelled-tint' : 'fill-white'}`} d="M16.906 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.061 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  </button>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/components/doc-parser/telegram-toggle.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run any consuming pages' tests for regressions**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx" "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: all pass — `TelegramToggle` is used in both pages with the same props shape.

- [ ] **Step 6: Commit**

```bash
git add web/components/doc-parser/telegram-toggle.tsx web/components/doc-parser/telegram-toggle.test.tsx
git commit -m "fix(web): guard TelegramToggle against overlapping requests and unmount-after-hold timer leak"
```

---

## Task 8: `doc-parser/[id]/page.tsx` — `load()` cancellation guard

**Files:**
- Modify: `web/app/(dashboard)/doc-parser/[id]/page.tsx:126-136`
- Test: `web/app/(dashboard)/doc-parser/[id]/page.test.tsx`

**Minor:** `load()` (lines 126-133) and its `useEffect` (134-136) have no cancellation guard. If `id` changes quickly (e.g. fast client-side nav between two doc-parser detail pages) or the component unmounts mid-fetch, a stale response can land after a fresher one and clobber `job`/`outs` with outdated data.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/doc-parser/[id]/page.test.tsx`:

```tsx
it('does not apply a stale response after id changes', async () => {
  let resolveFirst: (v: unknown) => void;
  const firstJob = new Promise((resolve) => { resolveFirst = resolve; });

  const fetchMock = vi.spyOn(global, 'fetch').mockImplementation((url: string) => {
    if (String(url).includes('/api/jobs/first')) {
      return firstJob.then(() => new Response(JSON.stringify({ id: 'first', title: 'First' }))) as unknown as Promise<Response>;
    }
    if (String(url).includes('/api/jobs/second')) {
      return Promise.resolve(new Response(JSON.stringify({ id: 'second', title: 'Second' })));
    }
    return Promise.resolve(new Response(JSON.stringify([])));
  });

  const { rerender } = render(<DocDetail params={{ id: 'first' }} />);
  rerender(<DocDetail params={{ id: 'second' }} />);
  await waitFor(() => expect(screen.getByText('Second')).toBeInTheDocument());

  resolveFirst!(undefined); // first request resolves AFTER the second one already rendered
  await new Promise((r) => setTimeout(r, 0));

  expect(screen.getByText('Second')).toBeInTheDocument(); // must not be clobbered back to "First"
  fetchMock.mockRestore();
});
```

(Adjust the mocked URLs/param shape to match how `useParams` is exercised in the file's existing tests — follow whatever mocking convention `web/app/(dashboard)/doc-parser/[id]/page.test.tsx` already uses for `next/navigation`'s `useParams`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: FAIL — the stale `first` response overwrites `job` back to "First" after the second one already landed.

- [ ] **Step 3: Add the cancelled-flag guard**

In `web/app/(dashboard)/doc-parser/[id]/page.tsx`, change:

```tsx
  async function load() {
    const [j, o] = await Promise.all([
      fetch(`/api/jobs/${id}`).then((r) => r.json()),
      fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
    ]);
    setJob(j);
    setOuts(o);
  }
  useEffect(() => {
    load();
  }, [id]);
```

to:

```tsx
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [j, o] = await Promise.all([
        fetch(`/api/jobs/${id}`).then((r) => r.json()),
        fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
      ]);
      if (cancelled) return;
      setJob(j);
      setOuts(o);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);
```

Also update `runAction`'s `await load();` call (line 148) to no longer call the now-inline `load` — since `load` moved inside the effect, `runAction` needs its own re-fetch trigger. Add a small reload helper alongside the effect instead:

```tsx
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [j, o] = await Promise.all([
        fetch(`/api/jobs/${id}`).then((r) => r.json()),
        fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
      ]);
      if (cancelled) return;
      setJob(j);
      setOuts(o);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);
```

and in `runAction`, replace `await load();` with `setReloadKey((k) => k + 1);`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/doc-parser/[id]/page.tsx" "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"
git commit -m "fix(web): guard doc-parser detail load() against stale-response races"
```

---

## Task 9: `jobs/[id]/page.tsx` — `CopyButton` timer cleanup

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx:118-131`
- Test: `web/app/(dashboard)/jobs/[id]/page.test.tsx`

**Minor:** `CopyButton`'s `handleCopy` (lines 118-122) does a bare `setTimeout(() => setCopied(false), 1500)` with no cleanup — if the component unmounts within that 1.5s window (e.g. user navigates away right after copying), React warns about (and effectively leaks) a `setState` call on an unmounted component. `OutputCard` in `web/app/(dashboard)/doc-parser/[id]/page.tsx:42-46` already has the correct pattern: track the reset in a `useEffect` keyed on the action state, with a `window.setTimeout`/`window.clearTimeout` cleanup pair.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/jobs/[id]/page.test.tsx`:

```tsx
it('does not warn about setState after unmount when copy timer is pending', async () => {
  const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

  const { unmount } = render(<CopyButton value="x" ariaLabel="Copy" label="Copy" />);
  fireEvent.click(screen.getByRole('button', { name: /copy/i }));
  await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());

  unmount();
  await new Promise((r) => setTimeout(r, 1600)); // let the reset timer fire post-unmount

  expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
  errorSpy.mockRestore();
});
```

(If `CopyButton` isn't exported from the page module, add `export` to its declaration for the test, matching how `OutputCard` is scoped in the sibling file — or test through the full page render if the project's convention is to not export page-local components; follow whatever `jobs/[id]/page.test.tsx` already does for `FieldCard`/other page-local components.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: FAIL (or the console.error spy catches React's unmounted-state-update warning).

- [ ] **Step 3: Convert to the `useEffect` reset pattern**

In `web/app/(dashboard)/jobs/[id]/page.tsx`, change:

```tsx
function CopyButton({ value, ariaLabel, label }: { value: string; ariaLabel: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
```

to:

```tsx
function CopyButton({ value, ariaLabel, label }: { value: string; ariaLabel: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); } catch {}
  };
```

Add `useEffect` to the existing `import { useState, type ReactNode } from "react";` at the top of the file → `import { useEffect, useState, type ReactNode } from "react";`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "fix(web): clean up CopyButton's reset timer on unmount"
```

---

## Task 10: `spaces/[id]/page.tsx` — `handleDelete` silent failure

**Files:**
- Modify: `web/app/(dashboard)/spaces/[id]/page.tsx:16,24-28,54-58`
- Test: `web/app/(dashboard)/spaces/[id]/page.test.tsx`

**Minor:** `handleDelete` (lines 24-28) fires a `DELETE` and only handles the success path (`if (res.ok || res.status === 204) router.push("/spaces");`) — a failed delete (network error, 4xx/5xx) does nothing: no error shown, no re-enabled affordance, the user just sees the button silently do nothing. `web/components/SpaceCard.tsx:18-33` (`deleting`/`failed` state + try/catch) already has the pattern for this exact operation on the same resource; reuse it.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/spaces/[id]/page.test.tsx`:

```tsx
it('shows an error and re-enables Delete when the DELETE request fails', async () => {
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  vi.spyOn(global, 'fetch').mockImplementation((url: string, init?: RequestInit) => {
    if (init?.method === 'DELETE') return Promise.resolve(new Response(null, { status: 500 }));
    return Promise.resolve(new Response(JSON.stringify({ id: 'sp1', name: 'S', color: '#fff' })));
  });

  render(<SpaceDetailPage params={{ id: 'sp1' }} />);
  await waitFor(() => screen.getByRole('button', { name: /delete/i }));

  fireEvent.click(screen.getByRole('button', { name: /delete/i }));
  await waitFor(() => expect(screen.getByText(/couldn.t delete/i)).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /delete/i })).not.toBeDisabled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/spaces/[id]/page.test.tsx"`
Expected: FAIL — no error text is ever rendered today.

- [ ] **Step 3: Add `deleting`/`failed` state, matching `SpaceCard.tsx`**

In `web/app/(dashboard)/spaces/[id]/page.tsx`, change the import line to add `useState`:
```tsx
import { useCallback, useState } from "react";
```

Replace `handleDelete`:
```tsx
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);

  const handleDelete = useCallback(async () => {
    if (!window.confirm("Delete this space? Jobs will not be deleted.")) return;
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const res = await fetch(`/api/spaces/${params.id}`, { method: "DELETE" });
      if (res.ok || res.status === 204) {
        router.push("/spaces");
        return;
      }
      setDeleteFailed(true);
    } catch {
      setDeleteFailed(true);
    } finally {
      setDeleting(false);
    }
  }, [params.id, router]);
```

And in the JSX, next to the Delete button:
```tsx
          <div className="flex gap-2">
            <button onClick={() => setShowExport(true)} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Export</button>
            <button onClick={startEdit} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised">Edit</button>
            <button onClick={handleDelete} disabled={deleting} className="h-8 rounded-md border border-line px-3 text-[13px] font-medium text-status-error transition-ui hover:bg-raised disabled:opacity-50">{deleting ? "Deleting…" : "Delete"}</button>
          </div>
          {deleteFailed && <p className="text-xs text-status-error">Couldn&apos;t delete — try again.</p>}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/spaces/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/spaces/[id]/page.tsx" "web/app/(dashboard)/spaces/[id]/page.test.tsx"
git commit -m "fix(web): surface space-delete failures instead of silently swallowing them"
```

---

## Task 11: Add a global error boundary (`web/app/error.tsx`)

**Files:**
- Create: `web/app/error.tsx`

**Major:** No `error.tsx`/`global-error.tsx` exists anywhere under `web/app/`. `web/app/(dashboard)/page.tsx:249-252` wraps the feed in `<Suspense fallback={null}>` with no error boundary above it — any render-time throw in the tree (a bad API shape, a hook throwing) crashes to Next.js's default unstyled error screen instead of the app's dark-plate design system.

- [ ] **Step 1: Create `web/app/error.tsx`**

Next.js App Router route-level error boundaries are Client Components exporting a default function with `{ error, reset }` props (per `next/error` conventions — confirm current API shape via context7/Next.js docs for the installed Next version in `web/package.json` before finalizing prop types, since the exact reset-signature has been stable across recent major versions but is worth a live check).

```tsx
'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <section className="w-full max-w-md rounded-lg border border-line bg-surface p-6 text-center">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-status-error">
          Error
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm leading-6 text-body">
          The page hit an unexpected error. You can try again, or head back to the feed.
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised"
          >
            Back to feed
          </a>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Write a smoke test**

Create `web/app/error.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import GlobalError from './error';

describe('GlobalError', () => {
  it('renders the fallback and calls reset on click', () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error('boom')} reset={reset} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 3: Run the test**

Run: `npx vitest run web/app/error.test.tsx`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add web/app/error.tsx web/app/error.test.tsx
git commit -m "feat(web): add app-level error boundary styled to the design system"
```

---

## Task 12: Replace hardcoded "Leon" with configurable admin-contact copy

**Files:**
- Modify: `web/components/invite-gate.tsx:32,116`
- Modify: `src/telegram/webhook.py:47-48`
- Modify: `src/config.py`
- Test: `web/components/invite-gate.test.tsx`
- Test: `tests/test_webhook.py`

**Major:** The operator's first name "Leon" is hardcoded in user-facing copy in two places: `web/components/invite-gate.tsx:32` ("Pending approval — ask Leon for access."), `:116` ("Add the email Leon should approve..."), and `src/telegram/webhook.py:47-48` (`_INVITE_EMAIL_PROMPT`: "...what's your email so Leon can approve you?", `_INVITE_WAITING_MESSAGE`: "still waiting on Leon."). If this project is ever run by a different operator, this copy is wrong and there's no config knob. Add an `ADMIN_CONTACT_NAME` setting with a generic fallback, and thread it through both surfaces.

- [ ] **Step 1: Add the setting**

In `src/config.py`, add near `OPERATOR_CHAT_ID`:

```python
    # User-facing copy — the name shown in invite-gate messages ("ask X for access").
    # Falls back to generic phrasing when unset so a fresh deploy isn't stuck with "Leon".
    ADMIN_CONTACT_NAME: str = ""
```

- [ ] **Step 2: Update `src/telegram/webhook.py`'s invite copy to use it**

Change lines 47-48 from static strings to a small helper, since `settings` isn't evaluated until runtime and these are currently module-level constants:

```python
def _admin_label() -> str:
    return settings.ADMIN_CONTACT_NAME or "the operator"


_INVITE_EMAIL_PROMPT_TEMPLATE = "VIG is invite-only — what's your email so {admin} can approve you?"
_INVITE_WAITING_MESSAGE_TEMPLATE = "still waiting on {admin}."
_INVITE_APPROVED_MESSAGE = "You're in, send a link."
_INVITE_BLOCKED_MESSAGE = "Access blocked."
```

Then everywhere `_INVITE_EMAIL_PROMPT` and `_INVITE_WAITING_MESSAGE` are referenced (`_invite_gate_allows` at `src/telegram/webhook.py:1160-1208` — `await send_message(chat_id, _INVITE_EMAIL_PROMPT)` and the two `await send_message(chat_id, _INVITE_WAITING_MESSAGE)` calls), replace with:

```python
        await send_message(chat_id, _INVITE_EMAIL_PROMPT_TEMPLATE.format(admin=_admin_label()))
```
and
```python
        await send_message(chat_id, _INVITE_WAITING_MESSAGE_TEMPLATE.format(admin=_admin_label()))
```

- [ ] **Step 3: Update `web/components/invite-gate.tsx`**

The frontend has no direct access to backend settings, so surface the admin label through the existing `/api/auth/me` response (`InviteUser`) or a small dedicated field. Simplest: extend the existing pending/blocked copy to generic phrasing without a name, since threading a new backend field through the auth response is out of scope for a copy fix:

Line 32, change:
```tsx
            : "Pending approval — ask Leon for access."}
```
to:
```tsx
            : "Pending approval — ask the operator for access."}
```

Line 116, change:
```tsx
          VIG is invite-only. Add the email Leon should approve for this
          Telegram account.
```
to:
```tsx
          VIG is invite-only. Add the email the operator should approve for
          this Telegram account.
```

- [ ] **Step 4: Update tests**

In `tests/test_webhook.py`, grep for any assertion on the literal strings `"Leon"`, `"still waiting on Leon"`, or the invite prompt text, and update them to match the new generic default (`"the operator"`) — e.g. `assert "the operator" in sent_text` instead of `"Leon" in sent_text`. Also add:

```python
@pytest.mark.asyncio
async def test_invite_prompt_uses_configured_admin_name(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "Alex")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "Alex"


def test_invite_prompt_falls_back_when_unset(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "the operator"
```

In `web/components/invite-gate.test.tsx`, grep for any assertion on the literal string `"Leon"` and update to the new generic copy.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_webhook.py -q
npx vitest run web/components/invite-gate.test.tsx
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/config.py src/telegram/webhook.py web/components/invite-gate.tsx tests/test_webhook.py web/components/invite-gate.test.tsx
git commit -m "fix: replace hardcoded operator name 'Leon' with configurable ADMIN_CONTACT_NAME / generic copy"
```

---

## Task 13: "Connect Google" button — use the shared button-signal spec

**Files:**
- Modify: `web/app/(dashboard)/page.tsx:174`
- Test: `web/app/(dashboard)/page.test.tsx`

**Minor:** The "Connect Google" `<a>` at line 174 uses `rounded-full`, `text-canvas`, and `hover:brightness-110` — none of which match the project's shared signal-button spec used everywhere else (e.g. `SpacesPage`'s "New Space" button, `web/app/(dashboard)/spaces/[id]/page.tsx`'s "Save" button): `h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal hover:bg-signal-bright active:bg-signal-deep`.

- [ ] **Step 1: Update the class list**

In `web/app/(dashboard)/page.tsx`, change:
```tsx
          <a href="/api/google/connect" className="inline-flex items-center justify-center rounded-full bg-signal px-4 py-2 text-sm font-semibold text-canvas transition-ui hover:brightness-110">Connect Google</a>
```
to:
```tsx
          <a href="/api/google/connect" className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep">Connect Google</a>
```

- [ ] **Step 2: Grep for any other stray uses of this non-standard button spec**

Run: `grep -rn "rounded-full bg-signal\|text-canvas\b" web --include="*.tsx"`
If other unrelated hits show up, leave them — this task only covers the finding's cited line.

- [ ] **Step 3: Run tests**

Run: `npx vitest run "web/app/(dashboard)/page.test.tsx"`
Expected: PASS — pure class-string change.

- [ ] **Step 4: Commit**

```bash
git add "web/app/(dashboard)/page.tsx"
git commit -m "fix(web): align Connect Google button with the shared button-signal spec"
```

---

## Task 14: Eyebrow sweep — drop or fold banned tracked-uppercase labels

**Files:**
- Modify: `web/app/(dashboard)/page.tsx:170`
- Modify: `web/components/invite-gate.tsx:23-25`
- Modify: `web/app/login/page.tsx:81`
- Modify: `web/app/logout/page.tsx:47`
- Modify: `web/app/mini/page.tsx:79`

**Minor:** `DESIGN.md` bans decorative all-caps tracked-letterspacing "eyebrow" labels (`text-xs uppercase tracking-widest` / `font-mono uppercase tracking-[0.04em]` micro-labels above a heading) as noise that competes with the single rationed signal-orange accent. Five instances remain:

- [ ] **Step 1: `web/app/(dashboard)/page.tsx:170`**

Change:
```tsx
          <div>
            <p className="text-xs uppercase tracking-widest text-muted">Google export</p>
            <h2 className="mt-1 text-lg font-semibold text-ink">Connect Google</h2>
```
to (fold the eyebrow into the heading, no separate label element):
```tsx
          <div>
            <h2 className="text-lg font-semibold text-ink">Connect Google</h2>
```

- [ ] **Step 2: `web/components/invite-gate.tsx:23-25`**

Change:
```tsx
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-muted">
          {blocked ? "BLOCKED" : "PENDING"}
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">
          {blocked ? "Access blocked" : "Pending approval"}
        </h1>
```
to (drop the eyebrow — the heading already states the status in plain case):
```tsx
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {blocked ? "Access blocked" : "Pending approval"}
        </h1>
```

- [ ] **Step 3: `web/app/login/page.tsx:81`**

Change:
```tsx
        <p className="mt-10 text-xs uppercase tracking-widest text-muted">
          Sign in to your console
        </p>
```
to:
```tsx
        <p className="mt-10 text-sm text-body">
          Sign in to your console
        </p>
```

- [ ] **Step 4: `web/app/logout/page.tsx:47`**

Change:
```tsx
              <p className="text-xs uppercase tracking-widest text-muted">
                Session closed
              </p>
```
to (fold into the following heading — drop the separate label, since `"See you soon"` already communicates state; keep one line of supporting copy):
```tsx
              <p className="text-sm text-body">
                Session closed
              </p>
```

- [ ] **Step 5: `web/app/mini/page.tsx:79`**

Change:
```tsx
              <p className="font-mono text-[11px] uppercase tracking-[0.04em] text-muted">Telegram Mini App</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em] text-balance">Connect Google inside VIG</h1>
```
to:
```tsx
              <h1 className="text-2xl font-semibold tracking-[-0.02em] text-balance">Connect Google inside VIG</h1>
```

- [ ] **Step 6: Grep for any remaining eyebrow-shaped labels this sweep may have missed**

Run: `grep -rn "uppercase tracking-widest\|uppercase tracking-\[0.04em\]" web --include="*.tsx"`
Review remaining hits — some may be legitimate machine-fact labels (e.g. `FieldCard`'s field-name label in `jobs/[id]/page.tsx:172`, which is a JetBrains Mono *data* label, not a decorative eyebrow per DESIGN.md's own distinction between "machine facts" and decorative copy). Only remove hits that match the five findings above; leave data labels alone.

- [ ] **Step 7: Run tests for all five touched pages**

```bash
npx vitest run "web/app/(dashboard)/page.test.tsx" web/components/invite-gate.test.tsx web/app/logout/page.test.tsx
```
(`login/page.tsx` and `mini/page.tsx` may not have dedicated test files — if so, this step covers what exists; visually confirm the other two via `/run` if available.)
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add "web/app/(dashboard)/page.tsx" web/components/invite-gate.tsx web/app/login/page.tsx web/app/logout/page.tsx web/app/mini/page.tsx
git commit -m "fix(web): drop banned uppercase-tracked eyebrow labels per DESIGN.md"
```

---

## Task 15: Doc Parser page — loading skeleton + empty state

**Files:**
- Modify: `web/app/(dashboard)/doc-parser/page.tsx`
- Test: `web/app/(dashboard)/doc-parser/page.test.tsx`

**Minor:** `DocParserPage` has no loading skeleton (the job list just pops in empty then fills) and no empty state (an empty `filtered` array renders nothing — no "no documents yet" messaging). The feed page (`web/app/(dashboard)/page.tsx`) already solves both with `SkeletonList`/`EmptyState` from `web/components/feed/feed-states.tsx`; reuse them.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/doc-parser/page.test.tsx`:

```tsx
it('shows an empty state when there are no documents', async () => {
  vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [] })));
  render(<DocParserPage />);
  await waitFor(() => expect(screen.getByText(/no documents yet/i)).toBeInTheDocument());
});

it('shows a loading skeleton before the first response resolves', () => {
  let resolveFetch: (v: Response) => void;
  vi.spyOn(global, 'fetch').mockReturnValue(new Promise((resolve) => { resolveFetch = resolve; }) as unknown as Promise<Response>);
  render(<DocParserPage />);
  expect(screen.getAllByRole('presentation', { hidden: true }).length).toBeGreaterThan(0);
  // resolve to avoid an unresolved-promise warning after the test ends
  resolveFetch!(new Response(JSON.stringify({ items: [] })));
});
```

(Match the skeleton's actual accessible query to how `SkeletonList` renders — it wraps rows in `aria-hidden="true"` divs, so query via `container.querySelectorAll('.animate-pulse')` if `getByRole('presentation')` doesn't resolve them; follow whichever existing feed-page test in `web/app/(dashboard)/page.test.tsx` already asserts on `SkeletonList` presence, and mirror that exact query.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx"`
Expected: FAIL — no empty-state text and no skeleton exist today.

- [ ] **Step 3: Add loading + empty states**

In `web/app/(dashboard)/doc-parser/page.tsx`, add the import:
```tsx
import { SkeletonList, EmptyState } from '@/components/feed/feed-states';
```

Add a `loading` flag around `load`:
```tsx
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const r = await fetch(`/api/jobs?content_type=document&limit=100${status ? `&status=${status}` : ''}`);
    const d = await r.json();
    setJobs(d.items ?? []);
    setLoading(false);
  }, [status]);
```

In the JSX, replace the results section:
```tsx
        <section className="space-y-2">
          {filtered.map(j => (
```
with:
```tsx
        <section className="space-y-2">
          {loading && <SkeletonList />}
          {!loading && filtered.length === 0 && (
            <EmptyState hasFilters={Boolean(q || status)} onClear={() => { setQ(''); setStatus(''); }} />
          )}
          {!loading && filtered.map(j => (
```
(close the existing `.map` block's parenthesis/`))}` unchanged — only the wrapping conditionals are new). `EmptyState`'s copy ("No jobs match these filters" / "No jobs yet") is generic across job types; that's an acceptable reuse — DocParser doesn't need bespoke empty-state copy for this fix.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/doc-parser/page.tsx" "web/app/(dashboard)/doc-parser/page.test.tsx"
git commit -m "feat(web): add loading skeleton and empty state to Doc Parser page"
```

---

## Task 16: Spinner-in-content → skeleton conversion (7 files)

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx:235-241`
- Modify: `web/app/(dashboard)/spaces/page.tsx:27-34`
- Modify: `web/app/(dashboard)/spaces/[id]/page.tsx:30-37`
- Modify: `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx:31-35`
- Modify: `web/app/(dashboard)/spaces/[id]/ContextTab.tsx:35-39`
- Modify: `web/components/ExportModal.tsx:111-115`
- Modify: `web/components/invite-gate.tsx:187-194`

**Minor:** Seven places render a bare centered `<Spinner />` + text for their loading state instead of a content-shaped skeleton (which reduces layout shift and reads as "the real content is coming" rather than "please wait"). Build two small reusable skeleton blocks matching `web/components/feed/feed-states.tsx`'s `SkeletonRow` visual language (`h-4 animate-pulse rounded bg-raised` bars inside a `rounded-lg border border-line bg-surface` card) and swap each spinner for the shape-appropriate one.

- [ ] **Step 1: Add two small skeleton primitives to `web/components/feed/feed-states.tsx`**

Append (after the existing `SkeletonGrid` export, before `ErrorBanner`):

```tsx
export function SkeletonLine({ width = 'w-2/3' }: { width?: string }) {
  return <div className={`h-4 ${width} animate-pulse rounded bg-raised`} aria-hidden="true" />;
}

export function SkeletonBlock({ className = 'h-24' }: { className?: string }) {
  return <div className={`w-full animate-pulse rounded-lg border border-line bg-surface ${className}`} aria-hidden="true" />;
}
```

- [ ] **Step 2: `web/app/(dashboard)/jobs/[id]/page.tsx:235-241`**

Change:
```tsx
  if (fetchState === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-body">
        <Spinner />
        Loading…
      </div>
    );
  }
```
to:
```tsx
  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-16" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
      </PageShell>
    );
  }
```
Add `import { SkeletonBlock } from "@/components/feed/feed-states";` to the file's imports. (`Spinner` import can stay if used elsewhere in the file — check before removing it; if unused after this change, drop it from the import.)

- [ ] **Step 3: `web/app/(dashboard)/spaces/page.tsx:27-34`**

Change:
```tsx
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-body">
        <Spinner />
        Loading…
      </div>
    );
  }
```
to:
```tsx
  if (loading) {
    return (
      <PageShell>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
          <SkeletonBlock className="h-[100px]" />
        </div>
      </PageShell>
    );
  }
```
Add `import { SkeletonBlock } from '@/components/feed/feed-states';`.

- [ ] **Step 4: `web/app/(dashboard)/spaces/[id]/page.tsx:30-37`**

Same shape as jobs/[id] — change to:
```tsx
  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-8 w-32" />
          <SkeletonBlock className="h-40" />
        </div>
      </PageShell>
    );
  }
```
Add the same `SkeletonBlock` import.

- [ ] **Step 5: `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx:31-35`**

Change:
```tsx
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-body">
          <Spinner size={3} />
          Loading…
        </div>
      ) : spaceUrls.length === 0 ? (
```
to:
```tsx
      {loading ? (
        <div className="space-y-2">
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-2/3" />
        </div>
      ) : spaceUrls.length === 0 ? (
```
Replace `import { Spinner } from '@/components/ui';` with `import { SkeletonLine } from '@/components/feed/feed-states';` (unless `Spinner` is used elsewhere in the file — it isn't, per the read excerpt).

- [ ] **Step 6: `web/app/(dashboard)/spaces/[id]/ContextTab.tsx:35-39`**

Same pattern as UrlsTab:
```tsx
      {loading ? (
        <div className="space-y-2">
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-full" />
        </div>
      ) : blobs.length === 0 ? (
```
Replace the `Spinner` import the same way.

- [ ] **Step 7: `web/components/ExportModal.tsx:111-115`**

Change:
```tsx
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-body">
            <Spinner />
            Composing export…
          </div>
        ) : loadError ? (
```
to:
```tsx
        {loading ? (
          <div className="space-y-2 py-2">
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-5/6" />
            <SkeletonLine width="w-3/4" />
          </div>
        ) : loadError ? (
```
Add `import { SkeletonLine } from '@/components/feed/feed-states';` (keep the `Spinner` import if it's used elsewhere in this file's other loading state — verify before removing).

- [ ] **Step 8: `web/components/invite-gate.tsx:187-194`**

This one is the full-screen session-check gate, not in-content — a skeleton for "the whole page hasn't decided what to show yet" makes less sense than a spinner (there's no content shape to preview). Leave this one as `<Spinner />` — it's a defensible exception, not part of this task's scope. (Confirmed: reviewers' 7-file list includes this line, but the shape here is a full-page gate, not in-content loading; note this explicitly rather than silently skipping — if the user disagrees after review, convert to a centered `SkeletonBlock` matching `GateScreen`'s card shape.)

- [ ] **Step 9: Run the touched suites**

```bash
npx vitest run "web/app/(dashboard)/jobs/[id]/page.test.tsx" "web/app/(dashboard)/spaces/page.test.tsx" "web/app/(dashboard)/spaces/[id]/page.test.tsx" "web/app/(dashboard)/spaces/[id]/UrlsTab.test.tsx" "web/app/(dashboard)/spaces/[id]/ContextTab.test.tsx"
```
Expected: all pass — check each suite for any assertion that specifically queries for `<Spinner />`'s role/test-id in a loading state and update it to query the new skeleton instead (e.g. `container.querySelector('.animate-pulse')`).

- [ ] **Step 10: Commit**

```bash
git add web/components/feed/feed-states.tsx "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/spaces/page.tsx" "web/app/(dashboard)/spaces/[id]/page.tsx" "web/app/(dashboard)/spaces/[id]/UrlsTab.tsx" "web/app/(dashboard)/spaces/[id]/ContextTab.tsx" web/components/ExportModal.tsx
git commit -m "feat(web): replace in-content spinners with content-shaped skeletons in 6 views"
```

---

## Task 17: Drop decorative signal-orange accents (logout glow, doc-parser Sparkles)

**Files:**
- Modify: `web/app/logout/page.tsx:29`
- Modify: `web/app/(dashboard)/doc-parser/page.tsx:167`

**Minor:** `DESIGN.md`'s Signal Rule reserves signal orange for "act here" affordances only. Two decorative uses violate it:
1. `web/app/logout/page.tsx:29` — the card's `shadow-[...,0_18px_60px_-34px_rgba(246,146,30,0.55)]` is a purely decorative glow on a static (non-interactive) card using the signal color's exact RGB (`246,146,30` = `#f6921e`).
2. `web/app/(dashboard)/doc-parser/page.tsx:167` — `<Sparkles className="h-4 w-4 text-signal" />` renders on every row unconditionally, not tied to any action — recolor to `text-muted`.

- [ ] **Step 1: `web/app/logout/page.tsx:29`**

Change:
```tsx
          <div className="mt-10 rounded-xl bg-surface/85 p-3 shadow-[0_0_0_1px_rgba(38,42,49,0.9),0_18px_60px_-34px_rgba(246,146,30,0.55)] backdrop-blur-sm">
```
to:
```tsx
          <div className="mt-10 rounded-xl bg-surface/85 p-3 shadow-[0_0_0_1px_rgba(38,42,49,0.9)] backdrop-blur-sm">
```

- [ ] **Step 2: `web/app/(dashboard)/doc-parser/page.tsx:167`**

Change:
```tsx
                <Sparkles className="h-4 w-4 text-signal" />
```
to:
```tsx
                <Sparkles className="h-4 w-4 text-muted" />
```

- [ ] **Step 3: Run tests**

```bash
npx vitest run web/app/logout/page.test.tsx "web/app/(dashboard)/doc-parser/page.test.tsx"
```
Expected: PASS — pure visual class changes.

- [ ] **Step 4: Commit**

```bash
git add web/app/logout/page.tsx "web/app/(dashboard)/doc-parser/page.tsx"
git commit -m "fix(web): drop decorative signal-orange accents per DESIGN.md's Signal Rule"
```

---

## Task 18: Hoist `SegmentedTabs`/`FilterBar` tabs array literals to module constants

**Files:**
- Modify: `web/app/(dashboard)/brain/page.tsx:420-428`
- Modify: `web/app/(dashboard)/doc-parser/page.tsx:126-139`

**Minor:** `SegmentedTabs` (`web/components/filter-bar.tsx:37-58`) measures the active tab's DOM position in a `useIsoLayoutEffect` keyed on `[activeIndex, tabs]`. Both `brain/page.tsx:424-427` and `doc-parser/page.tsx:127-133` pass a fresh array literal as `tabs`/`FilterBar`'s `tabs` prop on every render, so the effect's dependency array sees a new reference every render and re-runs its `offsetLeft`/`offsetWidth` measurement + `resize` listener re-subscription unnecessarily on every parent re-render. The feed page (`web/app/(dashboard)/page.tsx:28-34`, `CONTENT_TYPE_FILTERS`) already hoists this to a module-level constant — follow that pattern.

- [ ] **Step 1: `web/app/(dashboard)/brain/page.tsx`**

Above the component function (near other module-level constants, or right after the imports if none exist yet), add:
```tsx
const BRAIN_TABS = [
  { label: 'Search', value: 'search' },
  { label: 'Links', value: 'links', dividerBefore: true },
] as const;
```

Then change:
```tsx
      <SegmentedTabs
        label="Brain sections"
        value={activeTab}
        onChange={(v) => setActiveTab(v as BrainTab)}
        tabs={[
          { label: 'Search', value: 'search' },
          { label: 'Links', value: 'links', dividerBefore: true },
        ]}
      />
```
to:
```tsx
      <SegmentedTabs
        label="Brain sections"
        value={activeTab}
        onChange={(v) => setActiveTab(v as BrainTab)}
        tabs={BRAIN_TABS}
      />
```

- [ ] **Step 2: `web/app/(dashboard)/doc-parser/page.tsx`**

Above `DocParserPage`, add:
```tsx
const DOC_FORMAT_TABS = [
  { label: 'PDF', value: 'pdf', count: undefined },
  { label: 'Word', value: 'word', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Spreadsheet', value: 'spreadsheet', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Presentation', value: 'presentation', disabled: true, badge: 'soon', dividerBefore: true },
  { label: 'Image', value: 'image', disabled: true, badge: 'soon', dividerBefore: true },
] as const;
```
Note the `PDF` tab's `count` depends on `jobs.length`, which isn't available at module scope — keep that one field dynamic by merging it back in at render time:
```tsx
      <FilterBar
        tabs={DOC_FORMAT_TABS.map((t) => (t.value === 'pdf' ? { ...t, count: jobs.length } : t))}
        tabValue="pdf"
        onTabChange={() => {}}
        tabsLabel="Document format"
        query={q} setQuery={setQ} searchPlaceholder="Search documents…" searchLabel="Search documents"
        statusValue={status} onStatusChange={setStatus}
      />
```
This still allocates a new array each render (the `.map`), but it no longer allocates new *tab objects* for the 4 static disabled tabs, and more importantly keeps the tab *definitions* (labels, disabled flags, dividers) as a single source of truth instead of inline JSX. If exact reference-stability for the layout effect matters more than DRY-ing the static fields, memoize instead:
```tsx
  const tabs = useMemo(
    () => DOC_FORMAT_TABS.map((t) => (t.value === 'pdf' ? { ...t, count: jobs.length } : t)),
    [jobs.length],
  );
```
and pass `tabs={tabs}` — use this `useMemo` form so the array reference is stable across renders where `jobs.length` hasn't changed (add `useMemo` to the existing `react` import).

- [ ] **Step 3: Run tests**

```bash
npx vitest run "web/app/(dashboard)/brain/page.test.tsx" "web/app/(dashboard)/doc-parser/page.test.tsx"
```
Expected: all pass — tab rendering/labels/counts are unchanged, only the object identity/allocation site moved.

- [ ] **Step 4: Commit**

```bash
git add "web/app/(dashboard)/brain/page.tsx" "web/app/(dashboard)/doc-parser/page.tsx"
git commit -m "perf(web): hoist SegmentedTabs/FilterBar tab definitions to stable references"
```

---

## Task 19: Track fire-and-forget `asyncio.create_task` references

**Files:**
- Modify: `src/telegram/webhook.py:104,576,1528,1564`
- Modify: `src/processors/short_video.py:255,273`
- Modify: `src/processors/repo.py:501,503,506`
- Modify: `src/processors/prd.py:436`
- Create: `src/utils/background_tasks.py`
- Test: `tests/test_background_tasks.py`

**Minor:** 10 call sites across `webhook.py`, `short_video.py`, `repo.py`, and `prd.py` fire `asyncio.create_task(...)` and discard the returned `Task` immediately. Per the `asyncio` docs, a task with no strong reference can be garbage-collected mid-run, silently dropping the work (this is exactly why `webhook.py:87` retains its debounce task in `_BATCH_TASKS`). Add a shared helper that keeps a strong reference until the task completes, then reuse it at all 10 sites.

- [ ] **Step 1: Write the failing test for the helper**

Create `tests/test_background_tasks.py`:

```python
"""Unit tests for src/utils/background_tasks.py."""
from __future__ import annotations

import asyncio

import pytest

from src.utils.background_tasks import spawn_background, _BACKGROUND_TASKS


@pytest.mark.asyncio
async def test_spawn_background_retains_reference_until_done() -> None:
    started = asyncio.Event()
    finished = asyncio.Event()

    async def work() -> None:
        started.set()
        await asyncio.sleep(0.01)
        finished.set()

    task = spawn_background(work())
    assert task in _BACKGROUND_TASKS

    await started.wait()
    assert task in _BACKGROUND_TASKS  # still tracked while running

    await finished.wait()
    await asyncio.sleep(0)  # let the done_callback fire
    assert task not in _BACKGROUND_TASKS  # discarded once complete


@pytest.mark.asyncio
async def test_spawn_background_runs_the_coroutine() -> None:
    result = {}

    async def work() -> None:
        result["ran"] = True

    task = spawn_background(work())
    await task

    assert result == {"ran": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_background_tasks.py -q`
Expected: FAIL — `src.utils.background_tasks` doesn't exist yet (`ModuleNotFoundError`).

- [ ] **Step 3: Create the helper**

Create `src/utils/background_tasks.py`:

```python
"""Shared fire-and-forget task tracking.

asyncio.create_task(...) with no retained reference can be garbage-collected
mid-run (see the asyncio docs' "Important" note on create_task). Every
fire-and-forget call site in the codebase should go through spawn_background
instead of calling asyncio.create_task directly.
"""
from __future__ import annotations

import asyncio
from typing import Coroutine

_BACKGROUND_TASKS: set[asyncio.Task] = set()


def spawn_background(coro: Coroutine) -> asyncio.Task:
    """asyncio.create_task, but keeps a strong reference until the task finishes."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_background_tasks.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Replace the 10 call sites**

In `src/telegram/webhook.py`, add `from src.utils.background_tasks import spawn_background` to the imports, then:
- Line 104: `asyncio.create_task(_ingest_document(chat_id, document, message.get("message_id")))` → `spawn_background(_ingest_document(chat_id, document, message.get("message_id")))`
- Line 576: `asyncio.create_task(_do_rebuild())` → `spawn_background(_do_rebuild())`
- Line 1528: same replacement as line 104 (duplicate call site — see grep below to confirm this isn't the same line double-counted; if so, treat as one edit) — `asyncio.create_task(_ingest_document(chat_id, document, message.get("message_id")))` → `spawn_background(...)`
- Line 1564: `asyncio.create_task(_handle_single_photo(chat_id, file_id, caption))` → `spawn_background(_handle_single_photo(chat_id, file_id, caption))`

(Note: `webhook.py:87`'s `_BATCH_TASKS[media_group_id] = asyncio.create_task(_debounce())` already retains a reference via the dict — leave that one alone, it's not part of this finding.)

In `src/processors/short_video.py`, add the same import, then:
- Line 255: `asyncio.create_task(brain.ingest_links(links, topic=summary, source_job_id=source_job_id))` → `spawn_background(brain.ingest_links(links, topic=summary, source_job_id=source_job_id))`
- Line 273: `asyncio.create_task(brain.ingest_links(links, topic=vision.get("summary", ""), source_job_id=job_id))` → `spawn_background(...)`

In `src/processors/repo.py`, add the same import, then:
- Line 501: `asyncio.create_task(_sheets_update_safe(int(sheets_row_id), current_job, analysis, bundle))` → `spawn_background(_sheets_update_safe(int(sheets_row_id), current_job, analysis, bundle))`
- Line 503: `asyncio.create_task(_sheets_append_safe(job_id, current_job, analysis, bundle))` → `spawn_background(_sheets_append_safe(job_id, current_job, analysis, bundle))`
- Line 506: `asyncio.create_task(_brain_ingest_safe(...))` → `spawn_background(_brain_ingest_safe(...))`

In `src/processors/prd.py`, add the same import, then:
- Line 436: `asyncio.create_task(brain.ingest_links(brain_links, topic=prd_data.get("project", ""), source_job_id=job_id))` → `spawn_background(...)`

- [ ] **Step 6: Run the affected processor/webhook suites**

```bash
python -m pytest tests/test_webhook.py tests/test_short_video.py tests/test_repo_pipeline.py tests/test_prd.py tests/test_background_tasks.py -q
```
Expected: all pass — behaviorally identical, only the task-tracking mechanism changed. (If any of these test filenames differ from what's on disk, run `python -m pytest tests -k "webhook or short_video or repo or prd" -q` instead to catch the right set.)

- [ ] **Step 7: Commit**

```bash
git add src/utils/background_tasks.py tests/test_background_tasks.py src/telegram/webhook.py src/processors/short_video.py src/processors/repo.py src/processors/prd.py
git commit -m "fix: retain strong references to fire-and-forget asyncio tasks (prevent mid-run GC)"
```

---

## Task 20: Jina Reader — explicit httpx timeout

**Files:**
- Modify: `src/services/jina.py:90`
- Test: `tests/test_jina.py` (create/extend)

**Minor:** `fetch_markdown` (`src/services/jina.py:78-99`) uses `async with httpx.AsyncClient() as client:` with no `timeout=`, so it inherits httpx's default 5-second timeout — too short for a slow page through the Jina Reader proxy. `src/services/pdf_intake.py:57` already sets an explicit generous timeout (`httpx.AsyncClient(follow_redirects=False, timeout=20)`) for a comparable external fetch; match that.

- [ ] **Step 1: Write the failing test**

Create or extend `tests/test_jina.py`:

```python
import inspect

import pytest


def test_fetch_markdown_uses_explicit_timeout(monkeypatch):
    """httpx.AsyncClient must be constructed with an explicit generous timeout,
    not the 5s httpx default, since Jina Reader can be slow on large pages."""
    import httpx
    from src.services import jina

    captured = {}
    real_init = httpx.AsyncClient.__init__

    def spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", spy_init)

    # We only need to observe the constructor call, not complete the fetch —
    # a monkeypatched .get is enough to avoid a real network call.
    async def fake_get(self, url, headers=None):
        class _Resp:
            status_code = 200
            text = "Title: T\n\nBody"
        return _Resp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    import asyncio
    asyncio.get_event_loop().run_until_complete(jina.fetch_markdown("https://example.com"))

    assert captured.get("timeout") is not None
    assert captured["timeout"] != 5  # not the bare httpx default
```

(If the project's test conventions prefer `pytest.mark.asyncio` + `async def test_...` over manual `run_until_complete`, use that form instead — check a neighboring async test in `tests/` for the house style and match it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_jina.py -q`
Expected: FAIL — `captured.get("timeout")` is `None` today (no `timeout=` kwarg passed).

- [ ] **Step 3: Add the explicit timeout**

In `src/services/jina.py`, change:
```python
    async with httpx.AsyncClient() as client:
        response = await client.get(jina_url, headers=headers)
```
to:
```python
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(jina_url, headers=headers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_jina.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/jina.py tests/test_jina.py
git commit -m "fix(jina): set an explicit 30s httpx timeout instead of the 5s default"
```

---

## Task 21 [OPTIONAL — requires user decision]: Replace APScheduler with an asyncio sleep-loop

**Files:**
- Modify: `src/main.py:49-54`
- Modify: `pyproject.toml` (drop the `apscheduler` dependency, if present)

**Minor:** `src/main.py:49-54` pulls in `apscheduler` for exactly one twice-weekly cron job (`brain.refresh_stale_links`, Sunday/Wednesday 9am). A dependency with its own scheduler thread/executor model is a lot of surface area for one job; a small `asyncio` sleep-loop task can express the same schedule with zero extra dependencies. **This is a user call, not an obvious win** — if more scheduled jobs are planned soon, keep APScheduler (adding jobs to it is trivial; hand-rolling multi-job cron logic is not). Do not implement this task until the user confirms no more jobs are planned in the near term.

- [ ] **Step 1: Confirm with the user before proceeding**

Ask: "main.py's APScheduler currently runs one twice-weekly job (brain.refresh_stale_links). Replace it with a small asyncio sleep-loop and drop the apscheduler dependency, or keep APScheduler in case more scheduled jobs are added soon?" Only continue past this step if the answer is "replace it."

- [ ] **Step 2: Write the failing test**

```python
"""Unit test for the asyncio-based scheduler loop replacing APScheduler."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.main import _next_brain_refresh_run, _seconds_until


def test_next_run_picks_nearest_sunday_or_wednesday_9am() -> None:
    # A Monday 10am — next run should be Wednesday 9am, same week.
    now = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)  # Monday
    nxt = _next_brain_refresh_run(now)
    assert nxt.weekday() == 2  # Wednesday
    assert nxt.hour == 9 and nxt > now


def test_seconds_until_is_nonnegative() -> None:
    now = datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc)
    nxt = datetime(2026, 7, 8, 9, 0, tzinfo=timezone.utc)
    assert _seconds_until(now, nxt) > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_main_scheduler.py -q` (create this test file with the content from Step 2 first)
Expected: FAIL — `_next_brain_refresh_run`/`_seconds_until` don't exist yet.

- [ ] **Step 4: Implement the sleep-loop**

In `src/main.py`, replace:
```python
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler()
        scheduler.add_job(brain.refresh_stale_links, "cron", hour=9, day_of_week="sun,wed")
        scheduler.start()
        log.info("brain_scheduler_started")
```
with:
```python
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        await brain.init_db()
        scheduler_task = asyncio.create_task(_brain_refresh_loop())
        log.info("brain_scheduler_started")
```

Add near the top of `src/main.py` (module scope, above `lifespan`):
```python
import asyncio
from datetime import datetime, timedelta, timezone

_BRAIN_REFRESH_DAYS = {6, 2}  # Sunday=6, Wednesday=2 (datetime.weekday())
_BRAIN_REFRESH_HOUR = 9


def _next_brain_refresh_run(now: datetime) -> datetime:
    candidate = now.replace(hour=_BRAIN_REFRESH_HOUR, minute=0, second=0, microsecond=0)
    if candidate <= now or candidate.weekday() not in _BRAIN_REFRESH_DAYS:
        candidate += timedelta(days=1)
    while candidate.weekday() not in _BRAIN_REFRESH_DAYS or candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _seconds_until(now: datetime, target: datetime) -> float:
    return (target - now).total_seconds()


async def _brain_refresh_loop() -> None:
    from src import brain

    while True:
        now = datetime.now(timezone.utc)
        nxt = _next_brain_refresh_run(now)
        await asyncio.sleep(_seconds_until(now, nxt))
        try:
            await brain.refresh_stale_links()
        except Exception:
            log.exception("brain_refresh_failed")
```

Also cancel `scheduler_task` in the shutdown section of `lifespan` (after `yield`), guarding for the case where `GOOGLE_DRIVE_FOLDER_BRAIN` was unset and `scheduler_task` was never created:
```python
    yield
    log.info("api_shutting_down")
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        scheduler_task.cancel()
    await sender.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_main_scheduler.py -q`
Expected: PASS.

- [ ] **Step 6: Drop the dependency**

Remove `apscheduler` from `pyproject.toml`'s dependency list if it's declared there (check — it may only be in a `requirements.txt` or lockfile instead; update whichever file actually declares it).

- [ ] **Step 7: Run the full backend suite for regressions**

Run: `python -m pytest tests -q` (split per-directory if it gets backgrounded with empty output, per the repo's rtk-tests rule)
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/main.py tests/test_main_scheduler.py pyproject.toml
git commit -m "refactor: replace APScheduler with a small asyncio sleep-loop for the twice-weekly brain refresh"
```

---

## Task 22: Delete unused `_DETAIL_FIELDS` tuple

**Files:**
- Modify: `src/api/jobs.py:355-356`

**Nit:** `_DETAIL_FIELDS = _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG` (line 356) claims in its comment to be "kept for callers that import it directly (e.g. tests)" but `grep -rn "_DETAIL_FIELDS\b" src tests` (confirmed during this plan's research) shows zero references anywhere except its own definition line. Delete it and the stale comment.

- [ ] **Step 1: Confirm it's unused**

Run: `grep -rn "_DETAIL_FIELDS\b" --include="*.py" src tests`
Expected: only `src/api/jobs.py:356` itself.

- [ ] **Step 2: Delete the tuple and its comment**

In `src/api/jobs.py`, remove:
```python
# Legacy flat tuple kept for callers that import it directly (e.g. tests)
_DETAIL_FIELDS = _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG
```

- [ ] **Step 3: Run the jobs API suite**

Run: `python -m pytest tests/test_jobs_api.py -q` (or the closest matching test filename for `src/api/jobs.py` — check `tests/` for the exact name if this doesn't exist)
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/api/jobs.py
git commit -m "chore: delete unused _DETAIL_FIELDS tuple in src/api/jobs.py"
```

---

## Task 23: Fix `_handle_callback`'s invite-gate message for button-press context

**Files:**
- Modify: `src/telegram/webhook.py:415-444,1170-1208`
- Modify: `tests/test_webhook.py`

**Minor:** `_handle_callback` (line 439) calls `_invite_gate_allows(chat_id, "", identity)` with an empty `text`. Inside `_invite_gate_allows`, when the chat's state is `awaiting_email` (`src/telegram/webhook.py:1183-1188`), it calls `normalize_email("")` → `None` → sends `"Please send a valid email address."` as a Telegram message — a text-input error message sent in response to an inline-button press, which is confusing (the user pressed a button, not typed anything). Adapt the gate for the callback path: skip the email-parsing branch entirely when the trigger wasn't a text message.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_webhook.py`:

```python
@pytest.mark.asyncio
async def test_callback_from_pending_awaiting_email_does_not_send_email_validation_error(monkeypatch):
    """A button press from a pending, awaiting_email chat must not trigger the
    'Please send a valid email address' text-input error message."""
    from src.telegram import webhook

    sent: list[str] = []

    async def fake_send_message(chat_id, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(webhook, "send_message", fake_send_message)
    monkeypatch.setattr(webhook.database, "get_user_status", AsyncMock(return_value="pending"))
    monkeypatch.setattr(webhook.database, "get_user", AsyncMock(return_value={"email": None}))
    monkeypatch.setattr(webhook.database, "get_chat_state", AsyncMock(return_value={"mode": "awaiting_email"}))
    monkeypatch.setattr(webhook, "_resolve_chat_state", lambda state: True)
    monkeypatch.setattr(webhook.database, "upsert_user", AsyncMock())

    allowed = await webhook._invite_gate_allows(123, "", {"first_name": "X", "last_name": None, "username": None}, via_callback=True)

    assert allowed is False
    assert "valid email address" not in " ".join(sent)
```

(Adjust the exact `database`/`send_message` mock targets to match how other tests in `tests/test_webhook.py` already monkeypatch these — follow the file's existing convention, e.g. it may patch `webhook.database.get_user_status` directly via `AsyncMock` as shown, or via `monkeypatch.setattr("src.telegram.webhook.database.get_user_status", ...)`; use whichever form the surrounding tests already use for consistency.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_webhook.py::test_callback_from_pending_awaiting_email_does_not_send_email_validation_error -q`
Expected: FAIL — `_invite_gate_allows` doesn't accept a `via_callback` kwarg yet (`TypeError`), and even once added as a no-op it would still send the validation message.

- [ ] **Step 3: Add the `via_callback` parameter and skip the text-parsing branch**

In `src/telegram/webhook.py`, change `_invite_gate_allows`'s signature and the `awaiting_email` branch:

```python
async def _invite_gate_allows(
    chat_id: int,
    text: str,
    identity: dict[str, str | None] | None,
    *,
    via_callback: bool = False,
) -> bool:
    status = await database.get_user_status(chat_id)
    user = await database.get_user(chat_id)
    await _remember_invite_identity(chat_id, identity, status=status, user=user)
    if status == "approved":
        return True
    if status == "blocked":
        await send_message(chat_id, _INVITE_BLOCKED_MESSAGE)
        return False

    state = await database.get_chat_state(chat_id)
    if not via_callback and state and state.get("mode") == "awaiting_email" and _resolve_chat_state(state):
        email = normalize_email(text)
        if email is None:
            await send_message(chat_id, "Please send a valid email address.")
            return False
        await database.set_user_email(chat_id, email)
        await _notify_operator_invite(chat_id, email)
        await database.clear_chat_state(chat_id)
        await send_message(chat_id, _INVITE_WAITING_MESSAGE)
        return False

    if not user or not user.get("email"):
        await database.set_chat_state(
            chat_id=chat_id,
            mode="awaiting_email",
            job_id=f"invite:{chat_id}",
            expires_minutes=60 * 24 * 30,
        )
        await send_message(chat_id, _INVITE_EMAIL_PROMPT)
        return False

    await send_message(chat_id, _INVITE_WAITING_MESSAGE)
    return False
```

Then update the call in `_handle_callback` (line 439):
```python
        if not await _invite_gate_allows(chat_id, "", identity, via_callback=True):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_webhook.py::test_callback_from_pending_awaiting_email_does_not_send_email_validation_error -q`
Expected: PASS.

- [ ] **Step 5: Run the full webhook suite for regressions**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass — text-message-driven invite flow (the common case) is unaffected since `via_callback` defaults to `False`.

- [ ] **Step 6: Commit**

```bash
git add src/telegram/webhook.py tests/test_webhook.py
git commit -m "fix(webhook): don't send the email-validation error in response to a callback button press"
```

---

## Task 24: `webhook.py` message-copy hygiene sweep

**Files:**
- Modify: `src/telegram/webhook.py:333,496,952,1271,1345,1540`
- Modify: `src/telegram/webhook.py:863-879` (`_HELP_TEXT`)
- Modify: `src/telegram/webhook.py:48` (`_INVITE_WAITING_MESSAGE`, if Task 12 hasn't already superseded this string)

**Nit:** Three small copy-hygiene issues, all in the same file, all trivial text edits:
1. Six bot messages have a trailing space before `\n`: `f"📥 Received! \njob_{...}"` at lines 333, 496, 952, 1271, 1345, 1540 (confirmed via `cat -A` during this plan's research — each line ends `Received! \n` with a literal space before the escape).
2. `_HELP_TEXT` (lines 863-879) wraps only 3 of 15 listed commands in backticks (`` `/ignore_list` ``, `` `/allowlist_list` ``, `` `/download_md` <suffix> ``) — the other 12 are plain text. Format all consistently.
3. `_INVITE_WAITING_MESSAGE = "still waiting on Leon."` (line 48) starts lowercase. **Skip this specific sub-item if Task 12 already replaced this string with the `_INVITE_WAITING_MESSAGE_TEMPLATE` — check first; if Task 12 ran first, only apply the capitalization to whatever the current template string is** (e.g. `"Still waiting on {admin}."`).

- [ ] **Step 1: Fix the 6 trailing-space messages**

In `src/telegram/webhook.py`, at each of lines 333, 496, 952, 1271, 1345, 1540, change:
```python
f"📥 Received! \njob_{...}"
```
to:
```python
f"📥 Received!\njob_{...}"
```
(the `{...}` placeholder varies per call site — `new_job_id[-4:]` or `job_id[-4:]` depending on the surrounding function; only remove the space before `\n`, don't otherwise touch the f-string).

- [ ] **Step 2: Backtick every command in `_HELP_TEXT`**

Change:
```python
_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "/start — show welcome message\n"
    "/help — this message\n"
    "/find <query> — search your processed content\n"
    "/spec <suffix> [intent] — generate a mini-PRD from a long video\n"
    "/freestyle — use a custom Gemini prompt for the next job\n"
    "/force <url> — reprocess a URL (skip cache)\n"
    "/cancel — cancel the current pending prompt\n"
    "/ignore <domain> — hide a domain from link results\n"
    "/unignore <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "/allowlist <domain> — add an article domain\n"
    "/unallowlist <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "/rebuild-graph — rebuild the Second Brain link graph"
)
```
to:
```python
_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "`/start` — show welcome message\n"
    "`/help` — this message\n"
    "`/find` <query> — search your processed content\n"
    "`/spec` <suffix> [intent] — generate a mini-PRD from a long video\n"
    "`/freestyle` — use a custom Gemini prompt for the next job\n"
    "`/force` <url> — reprocess a URL (skip cache)\n"
    "`/cancel` — cancel the current pending prompt\n"
    "`/ignore` <domain> — hide a domain from link results\n"
    "`/unignore` <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "`/allowlist` <domain> — add an article domain\n"
    "`/unallowlist` <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "`/rebuild-graph` — rebuild the Second Brain link graph"
)
```

- [ ] **Step 3: Capitalize the waiting message (if not already handled by Task 12)**

Run: `grep -n "_INVITE_WAITING_MESSAGE" src/telegram/webhook.py` — if it's still `"still waiting on Leon."`, change to `"Still waiting on Leon."` (or, if Task 12 already ran, capitalize the `_INVITE_WAITING_MESSAGE_TEMPLATE` string's leading letter instead: `"Still waiting on {admin}."`).

- [ ] **Step 4: Grep for any remaining trailing-space-before-newline instances this sweep may have missed**

Run: `grep -nP '\s\\n"' src/telegram/webhook.py`
Review any additional hits and fix the same way if they're genuine trailing-space-before-escaped-newline bugs (not, e.g., a legitimate two-space Markdown line break).

- [ ] **Step 5: Run the webhook test suite**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass. If any test asserts on the exact old string (e.g. `"Received! \n"` or the un-backticked help text), update the assertion to match the corrected copy — this is a copy fix, not a behavior change, so any breakage here is exactly the test needing its expected string updated.

- [ ] **Step 6: Commit**

```bash
git add src/telegram/webhook.py tests/test_webhook.py
git commit -m "fix(webhook): message-copy hygiene — trailing spaces, _HELP_TEXT backtick consistency, capitalize waiting message"
```

---

## Task 25: Document ownership-scoping decisions (context blobs + brain endpoints)

**Files:**
- Modify: `src/database.py:2145-2179`
- Modify: `src/api/brain.py`

**Nit:** Two related "who's allowed to touch this" gaps, both resolved by adding a clarifying comment rather than a behavior change (confirm-and-document, not a code fix):
1. `src/database.py:2145-2179` — `get_context_blob`, `update_context_blob`, `delete_context_blob`, `reorder_context_blob` all take only `blob_id`, no `chat_id`. Ownership is enforced by the caller (`src/api/spaces.py`'s route handlers verify `space_id` ownership before calling these) — but that's not visible from the database function signatures themselves, so a future caller could skip the check by accident.
2. `src/api/brain.py` — `/api/brain/search`, `/graph`, `/links`, and `/rebuild` have no per-user scoping (only `/links/view` and `PUT /links/view` scope by `request.state.user["id"]`). This may be intentional — the Second Brain is described as a single shared link graph in `docs/seed/PRD.md`, not a per-user resource — but it's worth confirming and recording that decision rather than leaving it silently inconsistent with `/links/view`'s scoping.

- [ ] **Step 1: Add the ownership-contract comment to `src/database.py`**

Above `get_context_blob` (line 2145), add:
```python
# Ownership note: none of the four functions below take chat_id — the caller
# (src/api/spaces.py's route handlers) is responsible for verifying the blob's
# parent space is owned by request.state.user["id"] BEFORE calling any of these.
# If you add a new caller, verify ownership first; these functions trust the caller.
async def get_context_blob(blob_id: str) -> dict | None:
```

- [ ] **Step 2: Confirm the brain-endpoint scoping decision with the user**

Ask: "`/api/brain/search`, `/graph`, `/links`, and `/rebuild` return the full shared link graph with no per-user filter (only `/links/view` is scoped to `request.state.user["id"]`). Is the Second Brain intentionally a single shared graph across all approved users (matching the PRD's single-operator framing), or should these four endpoints also scope by user?" Record the answer as a comment (Step 3) rather than changing behavior in this task — if the user wants per-user scoping added, that's a larger follow-up (would need a `chat_id`/owner column on brain link records, which doesn't exist today) and should be a separate plan, not folded into this nit fix.

- [ ] **Step 3: Add the decision as a code comment in `src/api/brain.py`**

At the top of the file, below the module docstring, add:
```python
# Scoping note (confirmed): /search, /graph, /links, and /rebuild intentionally
# return the single shared Second Brain link graph, not a per-user view — the
# Second Brain is one operator-wide knowledge graph (see docs/seed/PRD.md §5).
# Only /links/view (display preferences, not data) is scoped per-user.
```
(If the user's answer in Step 2 was instead "yes, scope them," skip this comment and open a new tracked issue for per-user brain scoping instead of continuing this task — that's out of scope for a Nit-level fix.)

- [ ] **Step 4: Run tests for regressions (comment-only change, should be a no-op)**

```bash
python -m pytest tests/test_brain.py tests/test_spaces.py -q
```
Expected: all pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/database.py src/api/brain.py
git commit -m "docs: document context-blob and brain-endpoint ownership-scoping decisions"
```

---

## Task 26: `normalize_repo_url` — guard against unguarded indexing

**Files:**
- Modify: `src/utils/validators.py:140-143`
- Test: `tests/test_validators.py`

**Nit:** `normalize_repo_url` (`src/utils/validators.py:140-143`) does `segments[0]`/`segments[1]` with no length check. Every current call site (`webhook.py`, `api/jobs.py`, `processors/repo.py`) only calls it after `detect_pipeline`/`_match_github` has already confirmed the URL has ≥2 path segments, so it's not reachable with bad input today — but that safety is implicit and would produce a confusing raw `IndexError` instead of a clear error if a future caller skips the pre-check. Raise an explicit `ValueError`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_validators.py`:

```python
def test_normalize_repo_url_raises_on_missing_segments() -> None:
    with pytest.raises(ValueError, match="repo URL"):
        normalize_repo_url("https://github.com/owner")


def test_normalize_repo_url_raises_on_bare_domain() -> None:
    with pytest.raises(ValueError, match="repo URL"):
        normalize_repo_url("https://github.com/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validators.py -k normalize_repo_url_raises -q`
Expected: FAIL — today these raise a bare `IndexError`, not `ValueError`, so `pytest.raises(ValueError, ...)` fails.

- [ ] **Step 3: Add the guard**

In `src/utils/validators.py`, change:
```python
def normalize_repo_url(url: str) -> str:
    """Strip subpaths from a github.com URL, returning canonical https://github.com/{owner}/{repo}."""
    segments = [s for s in urlparse(url.strip()).path.split("/") if s]
    return f"https://github.com/{segments[0]}/{segments[1]}"
```
to:
```python
def normalize_repo_url(url: str) -> str:
    """Strip subpaths from a github.com URL, returning canonical https://github.com/{owner}/{repo}."""
    segments = [s for s in urlparse(url.strip()).path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(f"Not a full owner/repo URL, cannot normalize as a repo URL: {url!r}")
    return f"https://github.com/{segments[0]}/{segments[1]}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_validators.py -q`
Expected: all pass, including the two new tests and the existing `test_normalize_repo_url_strips_subpath`/`test_normalize_repo_url_bare`.

- [ ] **Step 5: Run the webhook/jobs suites that call this function**

Run: `python -m pytest tests/test_webhook.py tests/test_jobs_api.py -q` (adjust the jobs-api filename if it differs on disk)
Expected: all pass — every existing call site already guarantees ≥2 segments before calling, so this is purely additive.

- [ ] **Step 6: Commit**

```bash
git add src/utils/validators.py tests/test_validators.py
git commit -m "fix(validators): raise explicit ValueError in normalize_repo_url instead of unguarded IndexError"
```

---

## Task 27 [OPTIONAL — hardening, not a fix]: HKDF key derivation for Google token encryption

**Files:**
- Modify: `src/utils/google_token_crypto.py`
- Test: `tests/test_google_token_crypto.py` (create if it doesn't exist)

**Nit:** `google_token_fernet` (`src/utils/google_token_crypto.py:10-14`) derives the Fernet key via unsalted `hashlib.sha256(raw_key.encode())`. This isn't an active vulnerability (the key material — `GOOGLE_TOKEN_ENCRYPTION_KEY` — is a high-entropy secret set by the operator, not a low-entropy password subject to offline dictionary attack), but HKDF is the standard-library-adjacent (via `cryptography.hazmat`) correct primitive for "derive an encryption key from other key material" and costs little to adopt. **This is optional hardening — confirm with the user before implementing**, since it changes the derived key for any already-encrypted tokens in the database (every existing `google_oauth_tokens` row would fail to decrypt after this change unless migrated).

- [ ] **Step 1: Confirm with the user before proceeding**

Ask: "google_token_crypto.py derives its Fernet key via unsalted SHA-256 of GOOGLE_TOKEN_ENCRYPTION_KEY. Switching to HKDF is more textbook-correct but will invalidate every already-stored encrypted Google OAuth token (they'd all need re-auth) unless we also write a migration that re-encrypts them. Do you want this now (with a migration), later, or not at all?" Only proceed past this step if the answer includes doing the migration — otherwise stop here and leave this task unchecked.

- [ ] **Step 2: Write the failing test**

Create `tests/test_google_token_crypto.py`:

```python
"""Unit tests for src/utils/google_token_crypto.py."""
from __future__ import annotations

import pytest

from src.utils.google_token_crypto import google_token_fernet


def test_fernet_key_is_derived_via_hkdf_not_bare_sha256() -> None:
    """A bare sha256(raw_key) digest, base64-encoded, must NOT equal the derived key
    — that would mean HKDF (with its salt/info binding) isn't actually in use."""
    import base64
    import hashlib

    raw_key = "some-secret-key-material"
    bare_sha256_key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())

    fernet = google_token_fernet(raw_key)
    # Fernet doesn't expose its key directly; instead, verify round-trip works
    # AND that reconstructing via bare sha256 would produce a token this Fernet
    # instance rejects (proving the actual derivation differs).
    token = fernet.encrypt(b"payload")

    from cryptography.fernet import Fernet, InvalidToken
    bare_fernet = Fernet(bare_sha256_key)
    with pytest.raises(InvalidToken):
        bare_fernet.decrypt(token)


def test_empty_key_still_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        google_token_fernet("")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_google_token_crypto.py -q`
Expected: `test_fernet_key_is_derived_via_hkdf_not_bare_sha256` FAILS — today's implementation IS the bare-sha256 derivation, so `bare_fernet.decrypt(token)` succeeds instead of raising.

- [ ] **Step 4: Switch to HKDF**

In `src/utils/google_token_crypto.py`, change:
```python
"""Shared Google OAuth token encryption helpers."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


def google_token_fernet(raw_key: str) -> Fernet:
    if not raw_key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for per-user Google tokens")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
    return Fernet(key)
```
to:
```python
"""Shared Google OAuth token encryption helpers."""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_HKDF_SALT = b"vig.google_token_crypto.v1"  # static, versioned salt (no per-install salt storage needed — see task notes)
_HKDF_INFO = b"google-oauth-token-fernet-key"


def google_token_fernet(raw_key: str) -> Fernet:
    if not raw_key:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for per-user Google tokens")
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    ).derive(raw_key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_google_token_crypto.py -q`
Expected: PASS.

- [ ] **Step 6: Write and run the re-encryption migration**

This step is required because Step 4 changes every derived key — every row in `google_oauth_tokens` encrypted under the old bare-SHA-256 key becomes undecryptable. Write a one-time script (e.g. `scripts/migrate_token_encryption.py`) that: for each row in `google_oauth_tokens`, decrypts with the OLD derivation (bare SHA-256, temporarily inlined in the migration script itself, not imported from the now-changed module), re-encrypts with the NEW `google_token_fernet`, and writes it back. Run it once against the production DB before deploying this change, or force full re-auth for all connected users instead if a migration is deemed not worth writing (this is a decision to make with the user in Step 1 — if they chose "not at all" or "later," stop before this step).

- [ ] **Step 7: Run the export-gate suite (exercises token decryption)**

Run: `python -m pytest tests/test_export_gate.py tests/test_google_token_crypto.py -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/utils/google_token_crypto.py tests/test_google_token_crypto.py
git commit -m "refactor(security): derive Google token Fernet key via HKDF instead of bare SHA-256"
```

(Commit the migration script from Step 6 separately once written and run, with its own commit message, e.g. `chore: one-time re-encryption migration for HKDF key derivation switch`.)

---

## Final Review

After all tasks (skipping Task 21 and Task 27 unless the user opted in): dispatch a whole-diff code reviewer against the merge-base `main` → HEAD diff, per `superpowers:subagent-driven-development`. Then run `superpowers:finishing-a-development-branch` to decide how to land the branch — per this repo's `no-merge-to-main` rule, do not merge to `main`/`master` unless the user explicitly names it as the target in that message.

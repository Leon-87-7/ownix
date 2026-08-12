# /checklists Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an on-demand `/checklists <suffix>` command that turns a short/long video's transcript into a checklist of standalone, agent-pasteable directives ("does the current project have X — if not, report and plan how to implement it"), available identically from Telegram, the `/intake` dashboard composer, and the job detail page.

**Architecture:** One inline (non-queued, non-locked) Gemini call per invocation, built in `src/processors/checklists.py` and reused by three thin entry points: a `SHARED_COMMANDS` handler (`src/intake/commands.py`, powers both Telegram and the dashboard composer for free), a Telegram-only `.md` delivery wrapper (`src/telegram/webhook.py`), and a job-scoped REST trigger (`src/api/jobs.py`) for the job detail page's button. Generation can overlap normal job progression because it has no lock, so checklist persistence updates only its two fields and never rewrites status. The generated markdown persists on two new `jobs` columns (`checklists_md`, `checklists_generated_at`) — no lock/status column, no Drive upload, no Sheets row, no Brain ingest.

**Tech Stack:** Python 3.11 / FastAPI / aiosqlite (backend), Next.js 14 / React / Vitest (frontend), Gemini via `src/services/gemini.py`.

## Global Constraints

- Telegram command word and every internal name (module, DB columns, response `kind`) is `checklists` — not `audit`, which already names an unrelated existing concept (`audit_log` table).
- No lock column, no reaper, no retry-button/keyboard machinery — a failed generation is just retried by re-running the command/button.
- No Drive upload, no Sheets row, no Brain ingest for this artifact.
- Gate: `content_type in ("short", "long")` AND `status in ("transcript_done", "done")` AND non-empty `transcript`.
- Output schema: `{"applicable": bool, "topics": [{"name": str, "directive": str}]}`. `applicable: false` (or an empty `topics`) renders as "No actionable engineering recommendations found in this transcript." — never a fabricated checklist.
- Each `topic.directive` must be self-contained (an agent reading it cold, with no video context, must be able to act on it) and phrased as: check whether the current project already has this, present a report, and if it's missing, plan how to implement it. Never reference "the video" or hardcode a project name.
- Reuse `sample_transcript()` from `src/processors/prd.py` rather than duplicating it.

---

## Task 1: Database migration — `checklists_md` / `checklists_generated_at` columns

**Files:**
- Modify: `src/database.py:1339` (immediately after `_MIGRATIONS.append(_AUDIT_LOG_MIGRATION)`)
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `jobs.checklists_md TEXT` (nullable), `jobs.checklists_generated_at TEXT` (nullable, ISO-8601 string) — consumed by Task 4 (`checklists_command`), Task 6 (API endpoint), and read via `database.get_job()`'s `SELECT *`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py` (near the existing `test_migration_creates_audit_log_and_triggers_directly` test):

```python
@pytest.mark.asyncio
async def test_checklists_columns_exist_after_init(tmp_path, monkeypatch) -> None:
    """A fresh init_db() must create the checklists_md / checklists_generated_at columns."""
    from src import database

    db_file = str(tmp_path / "checklists_columns.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)

    await database.init_db()

    async with database.connection() as conn:
        cur = await conn.execute("PRAGMA table_info(jobs)")
        columns = {row["name"] for row in await cur.fetchall()}

    assert "checklists_md" in columns
    assert "checklists_generated_at" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database.py::test_checklists_columns_exist_after_init -v`
Expected: FAIL — `assert "checklists_md" in columns` fails (column doesn't exist yet).

- [ ] **Step 3: Add the migration**

In `src/database.py`, immediately after the line `_MIGRATIONS.append(_AUDIT_LOG_MIGRATION)` (line 1339):

```python

# v39 → v40: on-demand "/checklists" command — one inline Gemini call per
# invocation, cached directly on the job row. No lock/status column: unlike
# the Mini-PRD slots, nothing else can race to generate this concurrently
# (see docs/superpowers/plans/2026-08-11-checklists-command.md).
_MIGRATIONS.append([
    "ALTER TABLE jobs ADD COLUMN checklists_md TEXT",
    "ALTER TABLE jobs ADD COLUMN checklists_generated_at TEXT",
])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database.py::test_checklists_columns_exist_after_init -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat(db): add checklists_md/checklists_generated_at columns to jobs"
```

---

## Task 2: Config settings

**Files:**
- Modify: `src/config.py` (after the `# Slices #6/#7 — Mini-PRD` block, e.g. after line 103)

**Interfaces:**
- Produces: `settings.CHECKLISTS_MODEL: str`, `settings.CHECKLISTS_MAX_TRANSCRIPT_CHARS: int` — consumed by Task 3.

- [ ] **Step 1: Add the settings**

In `src/config.py`, after the existing block:

```python
    # Slices #6/#7 — Mini-PRD
    GOOGLE_DRIVE_FOLDER_PRD: str = ""
    PRD_MAX_TRANSCRIPT_CHARS: int = 60_000
    PRD_INTENT_COOLDOWN_SECONDS: int = 15
    PRD_AUTO_MODEL: str = "gemini-2.5-flash"
    PRD_INTENT_MODEL: str = "gemini-2.5-pro"
```

add:

```python

    # /checklists — on-demand engineering-recommendation checklist (short/long)
    CHECKLISTS_MAX_TRANSCRIPT_CHARS: int = 60_000
    CHECKLISTS_MODEL: str = "gemini-2.5-flash"
```

- [ ] **Step 2: Verify the app still imports cleanly**

Run: `python -c "from src.config import settings; print(settings.CHECKLISTS_MODEL, settings.CHECKLISTS_MAX_TRANSCRIPT_CHARS)"`
Expected: prints `gemini-2.5-flash 60000`

- [ ] **Step 3: Commit**

```bash
git add src/config.py
git commit -m "feat(config): add CHECKLISTS_MODEL/CHECKLISTS_MAX_TRANSCRIPT_CHARS settings"
```

---

## Task 3: `src/processors/checklists.py` — schema, prompt, markdown renderer

**Files:**
- Create: `src/processors/checklists.py`
- Test: `tests/test_checklists.py`

**Interfaces:**
- Consumes: `sample_transcript(text: str, cap: int = 60_000) -> str` from `src/processors/prd.py`; `settings.CHECKLISTS_MAX_TRANSCRIPT_CHARS`, `settings.CHECKLISTS_MODEL` from `src/config.py`.
- Produces: `CHECKLISTS_JSON_SCHEMA: dict`, `build_checklists_prompt(job: dict) -> str`, `build_checklists_markdown(data: dict, *, title: str | None = None) -> str` — consumed by Task 4 (`run_checklists`, `checklists_command`), Task 6 (API endpoint), Task 7 (`_cmd_checklists`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_checklists.py`:

```python
"""Unit tests for src/processors/checklists.py"""
from __future__ import annotations

from src.processors.checklists import (
    CHECKLISTS_JSON_SCHEMA,
    build_checklists_markdown,
    build_checklists_prompt,
)


# ---------------------------------------------------------------------------
# build_checklists_prompt
# ---------------------------------------------------------------------------

def test_prompt_includes_transcript_and_title():
    job = {"title": "5 things your AI-built app forgot", "transcript": "rate limiting matters"}
    prompt = build_checklists_prompt(job)
    assert "rate limiting matters" in prompt
    assert "5 things your AI-built app forgot" in prompt


def test_prompt_never_hardcodes_a_project_name():
    job = {"title": "t", "transcript": "some engineering advice"}
    prompt = build_checklists_prompt(job)
    assert "Ownix" not in prompt


def test_prompt_includes_long_video_enrichment_when_present():
    job = {
        "title": "t",
        "transcript": "x",
        "ai_topic": "Rate limiting",
        "ai_objective": "Avoid runaway AWS bills",
    }
    prompt = build_checklists_prompt(job)
    assert "Rate limiting" in prompt
    assert "Avoid runaway AWS bills" in prompt


def test_prompt_omits_enrichment_fields_for_short_jobs():
    job = {"title": "t", "transcript": "x", "summary": "quick tips video"}
    prompt = build_checklists_prompt(job)
    assert "quick tips video" in prompt
    assert "Objective:" not in prompt


# ---------------------------------------------------------------------------
# build_checklists_markdown
# ---------------------------------------------------------------------------

def test_markdown_not_applicable_renders_no_actionable_message():
    data = {"applicable": False, "topics": []}
    md = build_checklists_markdown(data)
    assert "No actionable engineering recommendations" in md


def test_markdown_applicable_with_empty_topics_also_renders_no_actionable_message():
    data = {"applicable": True, "topics": []}
    md = build_checklists_markdown(data)
    assert "No actionable engineering recommendations" in md


def test_markdown_renders_each_topic_as_a_section():
    data = {
        "applicable": True,
        "topics": [
            {"name": "Rate limiting", "directive": "Check for per-user rate limits."},
            {"name": "Audit logging", "directive": "Check for an audit trail."},
        ],
    }
    md = build_checklists_markdown(data)
    assert "## Rate limiting" in md
    assert "Check for per-user rate limits." in md
    assert "## Audit logging" in md
    assert "Check for an audit trail." in md


def test_markdown_includes_title_when_given():
    data = {"applicable": True, "topics": [{"name": "X", "directive": "Y"}]}
    md = build_checklists_markdown(data, title="5 things your AI forgot")
    assert md.startswith("# Checklist: 5 things your AI forgot")


# ---------------------------------------------------------------------------
# CHECKLISTS_JSON_SCHEMA
# ---------------------------------------------------------------------------

def test_schema_requires_applicable_and_topics():
    assert CHECKLISTS_JSON_SCHEMA["required"] == ["applicable", "topics"]
    topic_schema = CHECKLISTS_JSON_SCHEMA["properties"]["topics"]["items"]
    assert topic_schema["required"] == ["name", "directive"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_checklists.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.processors.checklists'`

- [ ] **Step 3: Write the implementation**

Create `src/processors/checklists.py`:

```python
"""On-demand "/checklists" command — engineering-recommendation checklist
extracted from a short/long video transcript.

Unlike the Mini-PRD (src/processors/prd.py), this is a single inline Gemini
call with no lock, no queue task, no Drive/Sheets/Brain side effects — see
docs/superpowers/plans/2026-08-11-checklists-command.md.
"""
from __future__ import annotations

from src.config import settings
from src.processors.prd import sample_transcript

CHECKLISTS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "applicable": {"type": "boolean"},
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "directive": {"type": "string"},
                },
                "required": ["name", "directive"],
            },
        },
    },
    "required": ["applicable", "topics"],
}

_NO_ACTIONABLE_MESSAGE = "No actionable engineering recommendations found in this transcript."


def build_checklists_prompt(job: dict) -> str:
    """Build the Gemini prompt for *job*. Works for both short and long jobs —
    enrichment fields (ai_topic/ai_objective) are included only when present."""
    transcript = sample_transcript(
        job.get("transcript") or "", settings.CHECKLISTS_MAX_TRANSCRIPT_CHARS
    )
    context_lines = [f"Video: {job.get('title', '')}"]
    if job.get("ai_topic"):
        context_lines.append(f"Topic: {job['ai_topic']}")
    if job.get("ai_objective"):
        context_lines.append(f"Objective: {job['ai_objective']}")
    if job.get("summary"):
        context_lines.append(f"Summary: {job['summary']}")
    context = "\n".join(context_lines)

    return (
        "You are a senior software engineer reviewing a video transcript for "
        "concrete, actionable engineering recommendations — the kind of advice "
        "a builder would want to check against their own codebase (e.g. rate "
        "limiting, error handling, observability, compliance, security "
        "practices).\n\n"
        f"{context}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Extract each distinct actionable recommendation as a checklist topic. "
        "Ignore filler, calls to action, and anything that is not a concrete "
        "engineering/product recommendation. If the transcript has nothing "
        "actionable for a software project, set applicable to false and "
        "return an empty topics list.\n\n"
        "Each topic's directive must be a standalone instruction written for "
        "a coding agent that will act on it directly inside an arbitrary "
        "project — never reference \"the video\" or name a specific project. "
        "Phrase it as: check whether the current project already has this, "
        "present a report, and if it's missing, plan how to implement it.\n\n"
        "Return the result as JSON matching the provided schema."
    )


def build_checklists_markdown(data: dict, *, title: str | None = None) -> str:
    """Render the checklist JSON to markdown. Empty/not-applicable renders a
    short message instead of an empty file."""
    heading = f"# Checklist: {title}" if title else "# Checklist"
    topics = data.get("topics") or []
    if not data.get("applicable") or not topics:
        return f"{heading}\n\n{_NO_ACTIONABLE_MESSAGE}\n"

    lines = [heading, ""]
    for topic in topics:
        name = topic.get("name", "Untitled")
        directive = topic.get("directive", "")
        lines += [f"## {name}", "", directive, ""]
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_checklists.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add src/processors/checklists.py tests/test_checklists.py
git commit -m "feat(checklists): add schema, prompt builder, and markdown renderer"
```

---

## Task 4: `run_checklists()` — the Gemini call

**Files:**
- Modify: `src/processors/checklists.py`
- Test: `tests/test_checklists.py`

**Interfaces:**
- Consumes: `generate(prompt: str, *, model: str, schema: dict) -> str` and `extract_json(raw: str) -> dict` from `src/services/gemini.py`; `GeminiUnavailableError` from `src/services/gemini.py`.
- Produces: `async def run_checklists(job: dict) -> tuple[dict, str]` (returns `(parsed_data, markdown)`, raises `GeminiUnavailableError` or `ValueError`/`json.JSONDecodeError` on failure) — consumed by Task 5 (`checklists_command`) and Task 6 (API endpoint).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_checklists.py`:

```python
# ---------------------------------------------------------------------------
# run_checklists
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import AsyncMock

from src.processors.checklists import run_checklists


@pytest.mark.asyncio
async def test_run_checklists_returns_data_and_markdown(monkeypatch):
    fake_generate = AsyncMock(
        return_value='{"applicable": true, "topics": [{"name": "Rate limiting", "directive": "Check it."}]}'
    )
    monkeypatch.setattr("src.services.gemini.generate", fake_generate)

    job = {"title": "t", "transcript": "some transcript text"}
    data, md = await run_checklists(job)

    assert data["applicable"] is True
    assert data["topics"][0]["name"] == "Rate limiting"
    assert "## Rate limiting" in md
    fake_generate.assert_awaited_once()
    _, kwargs = fake_generate.await_args
    assert kwargs["model"] == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_run_checklists_propagates_gemini_unavailable(monkeypatch):
    from src.services.gemini import GeminiUnavailableError

    async def _fail(*args, **kwargs):
        raise GeminiUnavailableError("both keys failed")

    monkeypatch.setattr("src.services.gemini.generate", _fail)

    with pytest.raises(GeminiUnavailableError):
        await run_checklists({"title": "t", "transcript": "x"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_checklists.py -k run_checklists -v`
Expected: FAIL — `ImportError: cannot import name 'run_checklists'`

- [ ] **Step 3: Write the implementation**

Append to `src/processors/checklists.py`:

```python


async def run_checklists(job: dict) -> tuple[dict, str]:
    """Generate the checklist for *job*. Raises GeminiUnavailableError (both
    Gemini keys failed) or a JSON-decode error (malformed model output)."""
    from src.services.gemini import extract_json, generate

    prompt = build_checklists_prompt(job)
    raw = await generate(prompt, model=settings.CHECKLISTS_MODEL, schema=CHECKLISTS_JSON_SCHEMA)
    data = extract_json(raw)
    md = build_checklists_markdown(data, title=job.get("title"))
    return data, md
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_checklists.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add src/processors/checklists.py tests/test_checklists.py
git commit -m "feat(checklists): add run_checklists Gemini call"
```

---

## Task 5: `checklists_command` — shared `SHARED_COMMANDS` handler

**Files:**
- Modify: `src/intake/commands.py`
- Test: `tests/test_intake_commands_checklists.py` (new)

**Interfaces:**
- Consumes: `run_checklists(job: dict) -> tuple[dict, str]` from `src/processors/checklists.py`; `database.find_jobs_by_suffix(chat_id: int, suffix: str) -> list[dict]` and `database.update_job_status(job_id: str, status: str, **fields) -> None` from `src/database.py`; `responses.command_result`/`responses.error` from `src/intake/responses.py`; `GeminiUnavailableError` from `src/services/gemini.py`.
- Produces: `async def checklists_command(chat_id: int, parts: list[str]) -> IntakeResponse` registered as `SHARED_COMMANDS["/checklists"]` — consumed by Task 7 (`_cmd_checklists`) and by `src/intake/router.py:_dispatch_command` automatically (no change needed there).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_intake_commands_checklists.py`:

```python
"""Tests for the shared `/checklists` command.

`checklists_command` is channel-agnostic (SHARED_COMMANDS) — Telegram and the
dashboard composer reach the exact same code path. Mirrors the structure of
tests/test_intake_commands_find.py.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.intake import commands

CHAT_ID = 42


class TestChecklistsCommand:
    def test_usage_message_with_no_suffix(self) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_no_match_returns_error(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_file = tmp_path / "checklists_no_match.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", "ZZZZ"])
        )
        assert resp.kind == "error"
        assert "ZZZZ" in resp.text

    def test_short_job_without_transcript_ready_is_rejected(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_not_ready.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short")
        )

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "error"

    def test_short_job_generates_and_persists(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_short_ok.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short")
        )
        asyncio.run(
            database.update_job_status(job_id, "done", transcript="rate limiting matters a lot")
        )

        fake_generate = AsyncMock(
            return_value='{"applicable": true, "topics": [{"name": "Rate limiting", "directive": "Check it."}]}'
        )
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )

        assert resp.kind == "checklists_result"
        assert "## Rate limiting" in resp.text
        assert resp.job_id == job_id

        job = asyncio.run(database.get_job(job_id))
        assert job["checklists_md"] is not None
        assert job["checklists_generated_at"] is not None

    def test_long_job_status_transcript_done_is_accepted(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_long_ok.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(
            database.update_job_status(job_id, "transcript_done", transcript="lots of engineering advice")
        )

        fake_generate = AsyncMock(return_value='{"applicable": false, "topics": []}')
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "checklists_result"
        assert "No actionable" in resp.text

    def test_gemini_failure_returns_retryable_error(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_gemini_fail.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database
        from src.services.gemini import GeminiUnavailableError

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done", transcript="some transcript"))

        async def _fail(*args, **kwargs):
            raise GeminiUnavailableError("both keys failed")

        monkeypatch.setattr("src.services.gemini.generate", _fail)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "error"
        assert resp.retryable is True

    def test_dashboard_reaches_it_through_the_router(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_router.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

        from src import database
        from src.intake import idempotency, router
        from src.intake.models import IntakeActor, IntakeMessage

        asyncio.run(database.init_db())
        idempotency._memory.clear()
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done", transcript="advice about audit logs"))

        fake_generate = AsyncMock(
            return_value='{"applicable": true, "topics": [{"name": "Audit logs", "directive": "Check it."}]}'
        )
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(IntakeMessage(actor=actor, text=f"/checklists {job_id[-4:]}"))
        )
        assert resp.kind == "checklists_result"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_intake_commands_checklists.py -v`
Expected: FAIL — `KeyError: '/checklists'` (not registered yet)

- [ ] **Step 3: Write the implementation**

In `src/intake/commands.py`, add `from datetime import datetime, timezone` to the imports at the top (alongside the existing `from collections.abc import ...` etc.), then add the handler right before the `SHARED_COMMANDS` dict definition:

```python
_CHECKLISTS_CONTENT_TYPES = ("short", "long")
_CHECKLISTS_READY_STATUSES = ("transcript_done", "done")


async def checklists_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    """`/checklists <suffix>` — on-demand engineering-recommendation checklist.

    Channel-agnostic: reached identically from Telegram and the dashboard
    composer. One inline Gemini call, no lock, no queue (see
    docs/superpowers/plans/2026-08-11-checklists-command.md).
    """
    if len(parts) < 2:
        return responses.command_result("Usage: /checklists <suffix>")
    suffix = parts[1][-4:]

    from src import database
    from src.processors.checklists import run_checklists
    from src.services.gemini import GeminiUnavailableError

    rows = await database.find_jobs_by_suffix(chat_id, suffix)
    candidates = [
        j
        for j in rows
        if j["content_type"] in _CHECKLISTS_CONTENT_TYPES
        and j["status"] in _CHECKLISTS_READY_STATUSES
        and (j.get("transcript") or "").strip()
    ]
    if not candidates:
        return responses.error(f"No short/long job ending in {suffix} with a transcript ready.")

    job = candidates[0]
    try:
        _, md = await run_checklists(job)
    except GeminiUnavailableError:
        log.warning("checklists.gemini_failed", job_id=job["id"])
        return responses.error(
            "Checklist generation failed — Gemini is unavailable. Try again.", retryable=True
        )
    except Exception:
        log.exception("checklists.failed", job_id=job["id"])
        return responses.error("Checklist generation failed. Try again.", retryable=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job["id"], job["status"], checklists_md=md, checklists_generated_at=generated_at
    )
    log.info("checklists.generated", job_id=job["id"], chat_id=chat_id)
    return IntakeResponse(kind="checklists_result", text=md, job_id=job["id"])
```

Then add the registry entry to `SHARED_COMMANDS`:

```python
SHARED_COMMANDS: dict[str, Command] = {
    "/help": Command("/help", "this message", help_command),
    "/cancel": Command("/cancel", "cancel the current pending prompt", cancel_command),
    "/find": Command("/find", "search your processed content", find_command, args="<query>"),
    "/force": Command("/force", "reprocess a URL (skip cache)", force_command, args="<url>"),
    "/freestyle": Command(
        "/freestyle", "use a custom Gemini prompt for the next job", freestyle_command, args="<url>"
    ),
    "/checklists": Command(
        "/checklists",
        "engineering checklist from a short/long transcript",
        checklists_command,
        args="<suffix>",
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_intake_commands_checklists.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/intake/commands.py tests/test_intake_commands_checklists.py
git commit -m "feat(intake): add shared /checklists command"
```

---

## Task 6: `POST /api/jobs/{job_id}/checklists` — job-scoped trigger for the dashboard

**Files:**
- Modify: `src/api/jobs.py`
- Create: `tests/test_jobs_api_checklists.py` (the existing `tests/test_jobs_api.py` only unit-tests pure helpers like `resolve_thumbnail` — no `TestClient`/auth fixture. The real authenticated-`TestClient` pattern lives in `tests/test_api_intake.py`; mirror it exactly.)

**Interfaces:**
- Consumes: `run_checklists(job: dict) -> tuple[dict, str]` from `src/processors/checklists.py`; `get_owned_job(job_id: str, request: Request) -> dict` from `src/api/deps.py`; `GeminiUnavailableError` from `src/services/gemini.py`.
- Produces: `POST /api/jobs/{job_id}/checklists` → `{"checklists_md": str, "checklists_generated_at": str}`; adds `checklists_md`/`checklists_generated_at` to `GET /api/jobs/{job_id}`'s response — consumed by Task 10 (`useChecklists` hook).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_jobs_api_checklists.py`:

```python
"""Tests for POST /api/jobs/{job_id}/checklists.

Follows the authenticated-TestClient pattern from tests/test_api_intake.py —
tests/test_jobs_api.py itself only unit-tests pure helpers, no client fixture.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 4242


@pytest.fixture
def jobs_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "jobs_checklists_api_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.jobs import jobs_router
    from src.auth.middleware import SessionMiddleware

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(jobs_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


class TestGenerateJobChecklists:
    def test_rejects_repo_content_type(self, jobs_client: TestClient) -> None:
        from src import database

        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://github.com/a/b", content_type="repo")
        )
        asyncio.run(database.update_job_status(job_id, "done"))
        _login(jobs_client)

        res = jobs_client.post(f"/api/jobs/{job_id}/checklists")
        assert res.status_code == 422

    def test_rejects_missing_transcript(self, jobs_client: TestClient) -> None:
        from src import database

        job_id = asyncio.run(
            database.create_job(
                chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short"
            )
        )
        asyncio.run(database.update_job_status(job_id, "done"))
        _login(jobs_client)

        res = jobs_client.post(f"/api/jobs/{job_id}/checklists")
        assert res.status_code == 422

    def test_generates_and_persists(
        self, jobs_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        job_id = asyncio.run(
            database.create_job(
                chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short"
            )
        )
        asyncio.run(
            database.update_job_status(job_id, "done", transcript="rate limiting is important")
        )
        _login(jobs_client)

        fake_generate = AsyncMock(
            return_value='{"applicable": true, "topics": [{"name": "Rate limiting", "directive": "Check it."}]}'
        )
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        res = jobs_client.post(f"/api/jobs/{job_id}/checklists")
        assert res.status_code == 200
        body = res.json()
        assert "## Rate limiting" in body["checklists_md"]
        assert body["checklists_generated_at"]

        detail = jobs_client.get(f"/api/jobs/{job_id}")
        assert "## Rate limiting" in detail.json()["checklists_md"]

    def test_requires_ownership(self, jobs_client: TestClient) -> None:
        from src import database

        job_id = asyncio.run(
            database.create_job(
                chat_id=CHAT_ID + 1, url="https://tiktok.com/@a/video/1", content_type="short"
            )
        )
        asyncio.run(database.update_job_status(job_id, "done", transcript="x"))
        _login(jobs_client)

        res = jobs_client.post(f"/api/jobs/{job_id}/checklists")
        assert res.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_jobs_api_checklists.py -v`
Expected: FAIL — 404 Not Found (route doesn't exist yet)

- [ ] **Step 3: Write the implementation**

In `src/api/jobs.py`, add `checklists_md` and `checklists_generated_at` to `_DETAIL_FIELDS_COMMON` (around line 498-511):

```python
_DETAIL_FIELDS_COMMON = (
    "id",
    "url",
    "content_type",
    "status",
    "title",
    "created_at",
    "updated_at",
    "completed_at",
    "error_msg",
    "drive_url",
    "telegram_delivery",
    "sheets_row_id",
    "checklists_md",
    "checklists_generated_at",
)
```

Then add the endpoint in the "Annotations — declared before /{job_id}" section (near line 372-397), so it stays ahead of the catch-all `GET /{job_id}` route:

```python
class ChecklistsResponse(BaseModel):
    checklists_md: str
    checklists_generated_at: str


_CHECKLISTS_CONTENT_TYPES = {"short", "long"}
_CHECKLISTS_READY_STATUSES = {"transcript_done", "done"}


@jobs_router.post("/{job_id}/checklists")
async def generate_job_checklists(job_id: str, request: Request) -> ChecklistsResponse:
    """Generate (or regenerate) the engineering checklist for an owned short/long job."""
    job = await get_owned_job(job_id, request)

    if job.get("content_type") not in _CHECKLISTS_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="Checklists are only available for short/long jobs")
    if job.get("status") not in _CHECKLISTS_READY_STATUSES or not (job.get("transcript") or "").strip():
        raise HTTPException(status_code=422, detail="Transcript isn't ready yet for this job")

    from datetime import datetime, timezone
    from src.processors.checklists import run_checklists
    from src.services.gemini import GeminiUnavailableError

    try:
        _, md = await run_checklists(job)
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Checklist generation failed") from exc

    generated_at = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job_id, job["status"], checklists_md=md, checklists_generated_at=generated_at
    )
    return ChecklistsResponse(checklists_md=md, checklists_generated_at=generated_at)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_jobs_api_checklists.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `python -m pytest tests -q`
Expected: PASS (no new failures beyond the project's known pre-existing baseline)

- [ ] **Step 6: Commit**

```bash
git add src/api/jobs.py tests/test_jobs_api_checklists.py
git commit -m "feat(api): add POST /api/jobs/{id}/checklists trigger endpoint"
```

---

## Task 7: Telegram `/checklists` command

**Files:**
- Modify: `src/telegram/webhook.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `intake_commands.checklists_command(chat_id: int, parts: list[str]) -> IntakeResponse` from Task 5; `send_message`, `send_document` from `src/telegram/sender.py`.
- Produces: `/checklists <suffix>` usable from Telegram, delivered as a `.md` document.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_webhook.py`, near the existing `test_cmd_find_*` tests (~line 1600):

```python
@pytest.mark.asyncio
async def test_cmd_checklists_no_args_sends_usage(monkeypatch):
    from src.telegram.webhook import SlashCtx, _cmd_checklists

    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    ctx = SlashCtx(chat_id=42, parts=["/checklists"], message_id=None)
    await _cmd_checklists(ctx)

    sent.assert_awaited_once()
    args, _ = sent.await_args
    assert "Usage: /checklists <suffix>" in args[1]


@pytest.mark.asyncio
async def test_cmd_checklists_error_kind_sends_message(monkeypatch):
    from src.intake.models import IntakeResponse
    from src.telegram.webhook import SlashCtx, _cmd_checklists

    async def _fake(chat_id, parts):
        return IntakeResponse(kind="error", text="No short/long job ending in ABCD with a transcript ready.")

    monkeypatch.setattr("src.intake.commands.checklists_command", _fake)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    ctx = SlashCtx(chat_id=42, parts=["/checklists", "ABCD"], message_id=None)
    await _cmd_checklists(ctx)

    sent.assert_awaited_once()
    args, _ = sent.await_args
    assert "No short/long job" in args[1]


@pytest.mark.asyncio
async def test_cmd_checklists_success_sends_document(monkeypatch):
    from src.intake.models import IntakeResponse
    from src.telegram.webhook import SlashCtx, _cmd_checklists

    async def _fake(chat_id, parts):
        return IntakeResponse(
            kind="checklists_result", text="# Checklist\n\n## Rate limiting\n\nCheck it.\n", job_id="job_abcd"
        )

    monkeypatch.setattr("src.intake.commands.checklists_command", _fake)
    sent_doc = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_document", sent_doc)

    ctx = SlashCtx(chat_id=42, parts=["/checklists", "abcd"], message_id=None)
    await _cmd_checklists(ctx)

    sent_doc.assert_awaited_once()
    args, kwargs = sent_doc.await_args
    assert args[0] == 42
    assert b"Rate limiting" in args[1]
    assert args[2] == "checklist_abcd.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_webhook.py -k cmd_checklists -v`
Expected: FAIL — `ImportError: cannot import name '_cmd_checklists'`

- [ ] **Step 3: Write the implementation**

In `src/telegram/webhook.py`, add the handler right after `_cmd_spec` (line 667-668):

```python
async def _cmd_checklists(ctx: SlashCtx) -> None:
    # Shared with the dashboard's /checklists (src/intake/commands.py:
    # checklists_command) — only Telegram's .md document delivery is
    # command-specific here.
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /checklists <suffix>")
        return

    from src.intake import commands as intake_commands

    resp = await intake_commands.checklists_command(ctx.chat_id, ctx.parts)

    if resp.kind in ("error", "command_result"):
        await send_message(ctx.chat_id, resp.text)
        return

    filename = f"checklist_{resp.job_id[-4:]}.md"
    await send_document(
        ctx.chat_id, resp.text.encode("utf-8-sig"), filename, caption="✅ Checklist ready"
    )
```

Then register it in `_SLASH_TABLE` (line 1078-1084), right after `"/spec": _cmd_spec,`:

```python
    "/spec": _cmd_spec,
    "/checklists": _cmd_checklists,
```

And add a line to `_HELP_TEXT` (line 1042-1059), right after the `/spec` line:

```python
    "`/spec` <suffix> [intent] — generate a mini-PRD from a long video\n"
    "`/checklists` <suffix> — engineering checklist from a short/long video\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_webhook.py -k cmd_checklists -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full backend suite**

Run: `python -m pytest tests -q`
Expected: PASS (no new failures beyond the project's known pre-existing baseline)

- [ ] **Step 6: Commit**

```bash
git add src/telegram/webhook.py tests/test_webhook.py
git commit -m "feat(telegram): add /checklists command"
```

---

## Task 8: Extract shared `CopyButton` component

**Files:**
- Create: `web/components/ui/copy-button.tsx`
- Create: `web/components/ui/copy-button.test.tsx`
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx` (remove local `CopyButton`, import the shared one)
- Modify: `web/app/(dashboard)/jobs/[id]/page.test.tsx` (simplify the old `CopyButton` describe block)

**Interfaces:**
- Produces: `CopyButton({ value, ariaLabel, label? }: { value: string; ariaLabel: string; label?: string })` from `@/components/ui/copy-button` — consumed by Task 11 (job detail page) and Task 12 (intake response card).

- [ ] **Step 1: Write the failing test**

Create `web/components/ui/copy-button.test.tsx`:

```tsx
// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CopyButton } from './copy-button';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('CopyButton', () => {
  it('copies the given value to the clipboard and shows a confirmation', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CopyButton value="hello world" ariaLabel="Copy text" label="Copy" />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy text' }));

    await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());
    expect(writeText).toHaveBeenCalledWith('hello world');
  });

  it('does not warn about setState after unmount when the copy timer is pending', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

    const { unmount } = render(<CopyButton value="x" ariaLabel="Copy text" />);
    fireEvent.click(screen.getByRole('button', { name: 'Copy text' }));
    await waitFor(() => expect(screen.getByLabelText('Copy text')).toBeInTheDocument());

    unmount();
    await new Promise((r) => setTimeout(r, 1600));

    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
    errorSpy.mockRestore();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run web/components/ui/copy-button.test.tsx`
Expected: FAIL — cannot find module `./copy-button`

- [ ] **Step 3: Write the implementation**

Create `web/components/ui/copy-button.tsx` (moved verbatim from `web/app/(dashboard)/jobs/[id]/page.tsx`, now shared):

```tsx
'use client';

import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';

export function CopyButton({
  value,
  ariaLabel,
  label,
}: {
  value: string;
  ariaLabel: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {}
  };
  return (
    <Tooltip content={ariaLabel}>
      <button
        onClick={handleCopy}
        aria-label={ariaLabel}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        {label && <span>{copied ? 'Copied!' : label}</span>}
      </button>
    </Tooltip>
  );
}
```

In `web/app/(dashboard)/jobs/[id]/page.tsx`:
- Remove the local `CopyButton` function definition (lines 178-217).
- Add `import { CopyButton } from '@/components/ui/copy-button';` to the imports (near the `Tooltip` import, line 33).

In `web/app/(dashboard)/jobs/[id]/page.test.tsx`, replace the `describe('CopyButton', ...)` block (lines 123-139) with:

```tsx
it('copies all fields as markdown when "Copy all" is clicked', async () => {
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

  render(<JobDetailPage />);
  fireEvent.click(screen.getByRole('button', { name: /copy all/i }));

  await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());
});
```

(the unmount-timer race regression test now lives in `web/components/ui/copy-button.test.tsx`, which tests the component directly instead of reaching it through the whole page).

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run web/components/ui/copy-button.test.tsx "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/ui/copy-button.tsx web/components/ui/copy-button.test.tsx "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "refactor(web): extract shared CopyButton component"
```

---

## Task 9: `JobDetail` type + `job-detail-utils.ts` download helper

**Files:**
- Modify: `web/lib/hooks/useJobDetail.ts`
- Modify: `web/lib/job-detail-utils.ts`
- Modify: `web/lib/job-detail-utils.test.ts` (already exists — imports `describe, expect, it` from `vitest` at line 1 and the exports it tests at lines 3-15)

**Interfaces:**
- Produces: `JobDetail.checklists_md: string | null`, `JobDetail.checklists_generated_at: string | null`; `downloadMarkdownFile(filename: string, content: string): void` — consumed by Task 11.

- [ ] **Step 1: Write the failing test**

In `web/lib/job-detail-utils.test.ts`, change line 1's import to add `vi` and `afterEach`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
```

Add `downloadMarkdownFile` to the existing named-import block from `@/lib/job-detail-utils` (lines 3-15).

Then append this block at the end of the file:

```ts
describe('downloadMarkdownFile', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates an object URL, clicks a download anchor, then revokes the URL', () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:fake-url')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })

    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadMarkdownFile('checklist_abcd.md', '# Checklist\n\nsome content')

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake-url')

    clickSpy.mockRestore()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run web/lib/job-detail-utils.test.ts`
Expected: FAIL — `downloadMarkdownFile` is not exported

- [ ] **Step 3: Write the implementation**

In `web/lib/hooks/useJobDetail.ts`, add the two fields to the `JobDetail` interface, right after `links`:

```ts
  links: string | null;
  checklists_md: string | null;
  checklists_generated_at: string | null;
```

In `web/lib/job-detail-utils.ts`, add at the end of the file:

```ts
/** Client-side download of generated markdown — no server round trip needed
 * since the content is already in hand (job detail fetch or a fresh
 * generation response). */
export function downloadMarkdownFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run web/lib/job-detail-utils.test.ts`
Expected: PASS

- [ ] **Step 5: Update the `JOB` test fixture in the job detail page test**

In `web/app/(dashboard)/jobs/[id]/page.test.tsx`, add to the `JOB` object (near `links: null,`):

```tsx
  links: null,
  checklists_md: null,
  checklists_generated_at: null,
```

Run: `npm test -- --run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: PASS (still — this task doesn't render anything new yet, just keeps the fixture in sync with the type)

- [ ] **Step 6: Commit**

```bash
git add web/lib/hooks/useJobDetail.ts web/lib/job-detail-utils.ts web/lib/job-detail-utils.test.ts "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "feat(web): add checklists fields to JobDetail and a markdown download helper"
```

---

## Task 10: `useChecklists` hook

**Files:**
- Create: `web/lib/hooks/useChecklists.ts`
- Create: `web/lib/hooks/useChecklists.test.ts`

**Interfaces:**
- Consumes: `apiPost<T>(url: string, body: unknown, fallback: string) -> Promise<{ok: true, data: T} | {ok: false, detail: string, status: number}>` from `web/lib/fetch-utils.ts`.
- Produces: `useChecklists(jobId: string) -> { generating: boolean; error: string | null; run: () => Promise<{ checklists_md: string; checklists_generated_at: string } | null> }` — consumed by Task 11.

- [ ] **Step 1: Write the failing test**

Create `web/lib/hooks/useChecklists.test.ts` (MSW request mocking, matching the established pattern in `web/lib/hooks/useFolderTagForm.test.ts` rather than stubbing `fetch` directly):

```ts
// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { useChecklists } from './useChecklists';

const server = setupServer();
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('useChecklists', () => {
  it('runs a generation and returns the result', async () => {
    server.use(
      http.post('/api/jobs/job1/checklists', () =>
        HttpResponse.json({
          checklists_md: '# Checklist',
          checklists_generated_at: '2026-08-11T00:00:00Z',
        }),
      ),
    );

    const { result } = renderHook(() => useChecklists('job1'));
    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.run();
    });

    expect(outcome).toEqual({
      checklists_md: '# Checklist',
      checklists_generated_at: '2026-08-11T00:00:00Z',
    });
    expect(result.current.error).toBeNull();
    expect(result.current.generating).toBe(false);
  });

  it('sets an error and returns null on failure', async () => {
    server.use(
      http.post('/api/jobs/job1/checklists', () =>
        HttpResponse.json({ detail: "Transcript isn't ready yet for this job" }, { status: 422 }),
      ),
    );

    const { result } = renderHook(() => useChecklists('job1'));
    let outcome: unknown;
    await act(async () => {
      outcome = await result.current.run();
    });

    expect(outcome).toBeNull();
    expect(result.current.error).toBe("Transcript isn't ready yet for this job");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- --run web/lib/hooks/useChecklists.test.ts`
Expected: FAIL — cannot find module `./useChecklists`

- [ ] **Step 3: Write the implementation**

Create `web/lib/hooks/useChecklists.ts`:

```ts
'use client';

import { useCallback, useState } from 'react';
import { apiPost } from '@/lib/fetch-utils';

interface ChecklistsResult {
  checklists_md: string;
  checklists_generated_at: string;
}

/** Drives the on-demand "/checklists" trigger on the job detail page — one
 * inline Gemini call per click, persisted on the job row (no lock, no queue;
 * see docs/superpowers/plans/2026-08-11-checklists-command.md). */
export function useChecklists(jobId: string) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (): Promise<ChecklistsResult | null> => {
    setGenerating(true);
    setError(null);
    try {
      const result = await apiPost<ChecklistsResult>(
        `/api/jobs/${encodeURIComponent(jobId)}/checklists`,
        {},
        'Checklist generation failed',
      );
      if (!result.ok) {
        setError(result.detail);
        return null;
      }
      return result.data;
    } finally {
      setGenerating(false);
    }
  }, [jobId]);

  return { generating, error, run };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- --run web/lib/hooks/useChecklists.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/lib/hooks/useChecklists.ts web/lib/hooks/useChecklists.test.ts
git commit -m "feat(web): add useChecklists hook"
```

---

## Task 11: `ChecklistsSection` on the job detail page

**Files:**
- Modify: `web/app/(dashboard)/jobs/[id]/page.tsx`
- Modify: `web/app/(dashboard)/jobs/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `useChecklists(jobId: string)` from Task 10; `downloadMarkdownFile(filename: string, content: string): void` from Task 9; `CopyButton` from Task 8.

- [ ] **Step 1: Write the failing tests**

Add to `web/app/(dashboard)/jobs/[id]/page.test.tsx`. First, add the mock near the other `vi.mock` calls (line ~22-33):

```tsx
vi.mock('@/lib/hooks/useChecklists', () => ({
  useChecklists: vi.fn(),
}));
```

and import it alongside the other hook imports (line ~51):

```tsx
import { useChecklists } from '@/lib/hooks/useChecklists';
```

then add:

```tsx
const mockUseChecklists = vi.mocked(useChecklists);
```

next to the other `mockUse*` consts, and default it inside `setupMocks` (or `beforeEach`):

```ts
mockUseChecklists.mockReturnValue({ generating: false, error: null, run: vi.fn() });
```

Then add a new `describe` block:

```tsx
describe('ChecklistsSection', () => {
  it('is hidden for content types that are not short/long', () => {
    setupMocks({ job: { ...JOB, content_type: 'repo' } });
    render(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: /run checklists/i })).not.toBeInTheDocument();
  });

  it('is hidden when the transcript is not ready yet', () => {
    setupMocks({ job: { ...JOB, content_type: 'long', status: 'processing' } });
    render(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: /run checklists/i })).not.toBeInTheDocument();
  });

  it('shows a Run Checklists button when the job is ready and ungenerated', () => {
    setupMocks({ job: { ...JOB, content_type: 'long', status: 'done', checklists_md: null } });
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: /run checklists/i })).toBeInTheDocument();
  });

  it('runs generation and renders the result on click', async () => {
    const run = vi.fn().mockResolvedValue({
      checklists_md: '# Checklist\n\n## Rate limiting\n\nCheck it.',
      checklists_generated_at: '2026-08-11T00:00:00Z',
    });
    mockUseChecklists.mockReturnValue({ generating: false, error: null, run });
    setupMocks({ job: { ...JOB, content_type: 'long', status: 'done', checklists_md: null } });

    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: /run checklists/i }));

    await waitFor(() => expect(screen.getByText(/rate limiting/i)).toBeInTheDocument());
    expect(run).toHaveBeenCalledTimes(1);
  });

  it('shows a Regenerate button and the existing checklist when already generated', () => {
    setupMocks({
      job: {
        ...JOB,
        content_type: 'short',
        status: 'done',
        checklists_md: '# Checklist\n\n## Audit logs\n\nCheck it.',
        checklists_generated_at: '2026-08-11T00:00:00Z',
      },
    });
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
    expect(screen.getByText(/audit logs/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- --run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: FAIL — `useChecklists` mock import fails / "Run Checklists" button not found

- [ ] **Step 3: Write the implementation**

In `web/app/(dashboard)/jobs/[id]/page.tsx`, add imports (near the other local imports, line ~14-30):

```tsx
import { useChecklists } from '@/lib/hooks/useChecklists';
import { downloadMarkdownFile } from '@/lib/job-detail-utils';
```

Add the component definition right after `JobActionsBar` (after line 577, before `export default function JobDetailPage()`):

```tsx
const CHECKLISTS_CONTENT_TYPES = new Set(['short', 'long']);
const CHECKLISTS_READY_STATUSES = new Set(['transcript_done', 'done']);

function ChecklistsSection({ job }: { job: JobDetail }) {
  const { generating, error, run } = useChecklists(job.id);
  const [md, setMd] = useState(job.checklists_md);
  const [generatedAt, setGeneratedAt] = useState(job.checklists_generated_at);

  if (
    !CHECKLISTS_CONTENT_TYPES.has(job.content_type) ||
    !CHECKLISTS_READY_STATUSES.has(job.status)
  ) {
    return null;
  }

  async function handleRun() {
    const result = await run();
    if (result) {
      setMd(result.checklists_md);
      setGeneratedAt(result.checklists_generated_at);
    }
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          Checklists
        </span>
        <div className="flex items-center gap-2">
          {md && (
            <>
              <CopyButton value={md} ariaLabel="Copy checklist" />
              <button
                type="button"
                onClick={() => downloadMarkdownFile(`checklist_${job.id.slice(-4)}.md`, md)}
                className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
              >
                Download .md
              </button>
            </>
          )}
          <button
            type="button"
            onClick={handleRun}
            disabled={generating}
            className="h-7 rounded-md border border-line bg-raised px-2.5 text-xs font-medium text-ink transition-ui hover:border-signal hover:text-signal disabled:opacity-50"
          >
            {generating ? 'Generating…' : md ? 'Regenerate' : 'Run Checklists'}
          </button>
        </div>
      </div>
      {error && <p className="text-xs text-status-error">{error}</p>}
      {md ? (
        <p className="whitespace-pre-wrap break-words text-sm text-ink">{md}</p>
      ) : (
        <p className="text-sm text-muted">
          Extracts actionable engineering recommendations from this transcript as a
          ready-to-paste checklist for a coding agent.
        </p>
      )}
      {generatedAt && (
        <p className="mt-2 text-xs text-muted">
          Last generated {new Date(generatedAt).toLocaleString()}
        </p>
      )}
    </div>
  );
}
```

Then render it inside `JobDetailPage`'s return, right after the `presentFields` block and before the annotation/`MarkdownEditor` block (after line 721's closing `</div>`, before line 723's `{loaded &&`):

```tsx
      <ChecklistsSection job={job} />

      {loaded &&
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run "web/app/(dashboard)/jobs/[id]/page.test.tsx"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/jobs/[id]/page.tsx" "web/app/(dashboard)/jobs/[id]/page.test.tsx"
git commit -m "feat(web): add ChecklistsSection to the job detail page"
```

---

## Task 12: Copy button on the intake `checklists_result` response card

**Files:**
- Modify: `web/components/intake/intake-response-card.tsx`
- Modify: `web/components/intake/intake-response-card.test.tsx`

**Interfaces:**
- Consumes: `CopyButton` from Task 8.

- [ ] **Step 1: Write the failing test**

Add to `web/components/intake/intake-response-card.test.tsx`, inside the main `describe('IntakeResponseCard', ...)` block:

```tsx
it('shows a copy button with the checklist text for a checklists_result response', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });

  render(
    <IntakeResponseCard
      item={item({
        response: response({
          kind: 'checklists_result',
          text: '# Checklist\n\n## Rate limiting\n\nCheck it.',
          job_id: 'j1',
        }),
      })}
    />,
  );

  await userEvent.click(screen.getByRole('button', { name: /copy checklist/i }));
  expect(writeText).toHaveBeenCalledWith('# Checklist\n\n## Rate limiting\n\nCheck it.');
});

it('does not show a checklist copy button for other response kinds', () => {
  render(<IntakeResponseCard item={item({ response: response({ kind: 'command_result' }) })} />);
  expect(screen.queryByRole('button', { name: /copy checklist/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- --run web/components/intake/intake-response-card.test.tsx`
Expected: FAIL — no "Copy checklist" button rendered

- [ ] **Step 3: Write the implementation**

In `web/components/intake/intake-response-card.tsx`, add the import:

```tsx
import { CopyButton } from '@/components/ui/copy-button';
```

Add `checklists_result: 'Checklist'` to `KIND_LABEL`:

```tsx
const KIND_LABEL: Record<string, string> = {
  job_created: 'Job created',
  job_deduped: 'Already tracked',
  unsupported: 'Unsupported',
  rejected: 'Rejected',
  error: 'Error',
  command_result: 'Command',
  state_update: 'State',
  action_ack: 'Action',
  checklists_result: 'Checklist',
};
```

Add the copy button right after the response text paragraph (after the `<p className="mt-1 whitespace-pre-wrap text-sm text-body">{response.text}</p>` line):

```tsx
        <p className="mt-1 whitespace-pre-wrap text-sm text-body">{response.text}</p>

        {response.kind === 'checklists_result' && (
          <div className="mt-2">
            <CopyButton value={response.text} ariaLabel="Copy checklist" label="Copy" />
          </div>
        )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- --run web/components/intake/intake-response-card.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/components/intake/intake-response-card.tsx web/components/intake/intake-response-card.test.tsx
git commit -m "feat(web): show a copy button on checklists_result intake responses"
```

---

## Task 13: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `python -m pytest tests -q`
Expected: PASS (no new failures beyond the project's pre-existing baseline — see memory `project_pytest_suite_baseline` if in doubt about which failures predate this work)

- [ ] **Step 2: Run the full frontend suite**

Run: `npm test -- --run`
Expected: PASS

- [ ] **Step 3: Lint both**

Run: `ruff check src/` and `npm run lint`
Expected: no new warnings/errors in touched files

- [ ] **Step 4: Manually exercise the three surfaces**

Start the stack (`docker-compose up -d` + `python transcript_server.py` + `npm run dev` under `web/`), process a short or long video to `transcript_done`/`done`, then:
- Telegram: send `/checklists <suffix>` — confirm a `.md` document arrives.
- Dashboard `/intake`: type `/checklists <suffix>` in the composer — confirm the response card shows the checklist text with a working "Copy" button.
- Job detail page for that job: confirm the "Checklists" section shows a "Run Checklists" button, generates on click, and offers both a copy button and a "Download .md" button afterward; reload the page and confirm the result is still there (persisted).

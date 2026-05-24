"""Unit tests for src/processors/prd.py"""
from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from src.processors.prd import (
    build_prd_markdown,
    sample_transcript,
)


@pytest.fixture
async def temp_db_for_prd():
    """Create a temp SQLite file with the full schema applied, patched into settings."""
    import os as _os
    import tempfile as _tf
    from unittest.mock import patch as _patch
    fd, path = _tf.mkstemp(suffix=".db")
    _os.close(fd)
    with _patch("src.config.settings.DB_PATH", path):
        from src import database as _db
        await _db.init_db()
        yield path
    _os.unlink(path)


# ---------------------------------------------------------------------------
# sample_transcript
# ---------------------------------------------------------------------------

def test_sample_transcript_under_cap():
    """Text shorter than cap is returned unchanged."""
    text = "hello world"
    result = sample_transcript(text, cap=100)
    assert result == text


def test_sample_transcript_at_cap():
    """Text exactly at cap is returned unchanged."""
    text = "x" * 100
    result = sample_transcript(text, cap=100)
    assert result == text


def test_sample_transcript_over_cap():
    """Text longer than 60k gets truncation markers inserted."""
    # Use a text longer than the default 60k cap (three 20k windows)
    text = "a" * 65_000
    result = sample_transcript(text)
    assert "[...truncated...]" in result
    # Result should be much smaller than the original
    assert len(result) < len(text)


def test_sample_transcript_three_windows():
    """Very long text contains head, middle, and tail portions with truncation markers."""
    # Build a text where head/middle/tail are distinguishable
    # head: first 20k chars (HEAD repeated), middle: 20k around centre, tail: last 20k (TAIL repeated)
    head_mark = "HEAD" * 5_000       # 20k chars at position 0
    filler = "X" * 100_000           # big gap in the middle
    tail_mark = "TAIL" * 5_000       # 20k chars at the end
    text = head_mark + filler + tail_mark

    result = sample_transcript(text)

    # Should have exactly two truncation markers
    assert result.count("[...truncated...]") == 2
    # Head portion should appear
    assert "HEAD" in result
    # Tail portion should appear
    assert "TAIL" in result


# ---------------------------------------------------------------------------
# Atomic lock tests (real SQLite in-memory)
# ---------------------------------------------------------------------------

# Minimal DDL for the lock tests — mirrors the real schema columns we need
_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    chat_id INTEGER NOT NULL DEFAULT 0,
    url TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT 'long',
    status TEXT NOT NULL DEFAULT 'done',
    prd_auto_status TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def _make_db_with_job(db_path: str, job_id: str, prd_auto_status) -> None:
    """Create schema and insert one job row."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(_JOBS_DDL)
        await conn.execute(
            "INSERT INTO jobs (id, prd_auto_status) VALUES (?, ?)",
            (job_id, prd_auto_status),
        )
        await conn.commit()


async def _run_lock_update(db_path: str, job_id: str) -> int:
    """Run the atomic lock UPDATE and return rowcount."""
    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute(
            "UPDATE jobs SET prd_auto_status='generating', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND (prd_auto_status IS NULL OR prd_auto_status='error')",
            (job_id,),
        )
        await conn.commit()
        return cur.rowcount


@pytest.mark.asyncio
async def test_atomic_lock_contention():
    """Job already 'generating' → UPDATE returns rowcount==0 (lock contention)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        await _make_db_with_job(db_path, "job_001", "generating")
        rowcount = await _run_lock_update(db_path, "job_001")
        assert rowcount == 0
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_atomic_lock_null():
    """Job with prd_auto_status=NULL → UPDATE returns rowcount==1 (lock acquired)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        await _make_db_with_job(db_path, "job_002", None)
        rowcount = await _run_lock_update(db_path, "job_002")
        assert rowcount == 1
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_atomic_lock_error_state():
    """Job with prd_auto_status='error' → UPDATE returns rowcount==1 (retry allowed)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        await _make_db_with_job(db_path, "job_003", "error")
        rowcount = await _run_lock_update(db_path, "job_003")
        assert rowcount == 1
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# Reaper test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaper_resets_stale():
    """Job stuck 'generating' with old updated_at gets reset to 'error' by reaper()."""
    from src.processors.prd import reaper

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(_JOBS_DDL)
            # Insert a job stuck in generating with an old timestamp
            await conn.execute(
                "INSERT INTO jobs (id, prd_auto_status, updated_at) VALUES (?, 'generating', datetime('now','-20 minutes'))",
                ("job_stale",),
            )
            await conn.commit()

        with patch("src.processors.prd.settings") as mock_settings, \
             patch("src.database.settings") as mock_db_settings:
            mock_settings.DB_PATH = db_path
            mock_db_settings.DB_PATH = db_path

            # Patch database.connection to use our test db
            import src.database as _db
            from contextlib import asynccontextmanager

            @asynccontextmanager
            async def _test_connection():
                conn = await aiosqlite.connect(db_path)
                conn.row_factory = aiosqlite.Row
                try:
                    yield conn
                finally:
                    await conn.close()

            with patch.object(_db, "connection", _test_connection):
                await reaper()

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT prd_auto_status FROM jobs WHERE id='job_stale'"
            )
            row = await cursor.fetchone()

        assert row["prd_auto_status"] == "error"

    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# build_prd_markdown
# ---------------------------------------------------------------------------

_SAMPLE_PRD = {
    "project": "TestBot",
    "category": "Technical Tutorial",
    "overview": "A bot that does things.",
    "phases": [{"name": "P1", "deliverables": ["d1"]}],
    "open_questions": [{"question": "q", "context": "c"}],
}


def test_build_prd_markdown_contains_project():
    """Markdown output must contain the project name."""
    md = build_prd_markdown(_SAMPLE_PRD)
    assert "TestBot" in md


def test_build_prd_markdown_structure():
    """Markdown must contain overview, phase name, and open question."""
    md = build_prd_markdown(_SAMPLE_PRD)
    assert "A bot that does things." in md
    assert "P1" in md
    assert "d1" in md
    assert "q" in md


def test_build_prd_markdown_tech_stack_table():
    """Tech stack items produce a markdown table row."""
    prd = dict(_SAMPLE_PRD)
    prd["tech_stack"] = [{"name": "FastAPI", "url": "https://fastapi.tiangolo.com", "purpose": "Web framework"}]
    md = build_prd_markdown(prd)
    assert "FastAPI" in md
    assert "fastapi.tiangolo.com" in md
    assert "Web framework" in md


# ---------------------------------------------------------------------------
# Brain link filtering
# ---------------------------------------------------------------------------

def test_brain_filter_excludes_no_url():
    """Tech stack entry without url field is excluded from brain_links."""
    tech_stack = [{"name": "SomeTool", "purpose": "does stuff"}]
    brain_links = [
        {"url": t["url"], "label": t["name"], "description": t.get("purpose", "")}
        for t in tech_stack
        if t.get("url")
    ]
    assert brain_links == []


def test_brain_filter_includes_with_url():
    """Tech stack entry with url field is included in brain_links."""
    tech_stack = [{"name": "FastAPI", "url": "https://fastapi.tiangolo.com", "purpose": "Web framework"}]
    brain_links = [
        {"url": t["url"], "label": t["name"], "description": t.get("purpose", "")}
        for t in tech_stack
        if t.get("url")
    ]
    assert len(brain_links) == 1
    assert brain_links[0]["url"] == "https://fastapi.tiangolo.com"
    assert brain_links[0]["label"] == "FastAPI"


# ---------------------------------------------------------------------------
# build_prd_markdown with intent_text (slice #7)
# ---------------------------------------------------------------------------

def test_build_prd_markdown_with_intent_text():
    from src.processors.prd import build_prd_markdown
    prd = {"project": "Demo App", "overview": "Short overview.", "phases": [], "open_questions": []}
    md = build_prd_markdown(prd, intent_text="desktop app for agentic image processing")
    assert "**Your direction:** _desktop app for agentic image processing_" in md
    # Direction must appear shortly after the title line
    lines = md.splitlines()
    title_idx = next(i for i, l in enumerate(lines) if l.startswith("# PRD:"))
    assert "Your direction" in lines[title_idx + 1] or "Your direction" in lines[title_idx + 2]


def test_build_prd_markdown_without_intent_text():
    from src.processors.prd import build_prd_markdown
    prd = {"project": "Demo App", "phases": [], "open_questions": []}
    md = build_prd_markdown(prd)
    assert "Your direction" not in md


# ---------------------------------------------------------------------------
# build_summary_lines (slice #7)
# ---------------------------------------------------------------------------

def test_build_summary_lines_zero_overview_sentences():
    from src.processors.prd import build_summary_lines
    prd = {"project": "Demo App", "overview": "", "phases": [{"name": "P1", "deliverables": ["d"]}],
           "features": [{"name": "f1"}, {"name": "f2"}]}
    lines = build_summary_lines(prd)
    assert lines == ["Project: Demo App", "1 phases, 2 features"]


def test_build_summary_lines_one_overview_sentence():
    from src.processors.prd import build_summary_lines
    prd = {"project": "X", "overview": "This is a single sentence.", "phases": [], "features": []}
    lines = build_summary_lines(prd)
    assert lines == ["Project: X", "This is a single sentence.", "0 phases, 0 features"]


def test_build_summary_lines_caps_at_two_overview_sentences():
    from src.processors.prd import build_summary_lines
    prd = {"project": "X", "overview": "One. Two. Three. Four.", "phases": [], "features": []}
    lines = build_summary_lines(prd)
    assert lines == ["Project: X", "One.", "Two.", "0 phases, 0 features"]


# ---------------------------------------------------------------------------
# reaper_intent (slice #7)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaper_intent_resets_stale_generating_rows(temp_db_for_prd):
    """A 'generating' row older than 10 minutes is reset to 'error'."""
    import aiosqlite
    from src.processors import prd
    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, prd_intent_status, updated_at) "
            "VALUES ('J_STALE', 1, 'u', 'long', 'done', 'generating', datetime('now','-15 minutes'))"
        )
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, prd_intent_status, updated_at) "
            "VALUES ('J_FRESH', 1, 'u', 'long', 'done', 'generating', datetime('now','-2 minutes'))"
        )
        await conn.commit()
    await prd.reaper_intent()
    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT id, prd_intent_status FROM jobs ORDER BY id")
        rows = await cur.fetchall()
    statuses = {r["id"]: r["prd_intent_status"] for r in rows}
    assert statuses == {"J_FRESH": "generating", "J_STALE": "error"}


# ---------------------------------------------------------------------------
# run_auto_resend (slice #7, Task 8)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_auto_resend_uses_cached_json(temp_db_for_prd, monkeypatch):
    """run_auto_resend reads cached JSON and calls update_file (not upload_file)."""
    from unittest.mock import AsyncMock
    import aiosqlite
    from src.processors import prd

    cached = '{"project":"Cached","overview":"","phases":[],"open_questions":[]}'
    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, prd_auto_status, "
            "prd_auto_drive_file_id, prd_auto_drive_url, prd_auto_json) "
            "VALUES ('J_CACHE', 1, 'u', 'long', 'done', 'done', 'DRIVE_ID_1', 'http://x', ?)",
            (cached,),
        )
        await conn.commit()

    updated = AsyncMock(return_value="http://x")
    monkeypatch.setattr("src.services.drive.update_file", updated)
    monkeypatch.setattr("src.telegram.sender.send_document", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", AsyncMock())

    await prd.run_auto_resend("J_CACHE")

    updated.assert_awaited_once()
    args, _ = updated.await_args
    assert args[0] == "DRIVE_ID_1"
    assert "Cached" in args[1]  # rendered markdown contains project name


# ---------------------------------------------------------------------------
# run_intent cooldown gate (slice #7)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intent_cooldown_blocks_within_15s(temp_db_for_prd, monkeypatch):
    """Second run_intent within 15s of a successful run is blocked by the cooldown gate."""
    import aiosqlite
    from unittest.mock import AsyncMock
    from src.processors import prd

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, "
            "prd_intent_status, prd_intent_completed_at, prd_intent_text, transcript) "
            "VALUES ('J_CD', 1, 'u', 'long', 'done', 'done', "
            "datetime('now','-5 seconds'), 'first intent', 'transcript text')"
        )
        await conn.commit()

    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_message", AsyncMock())

    await prd.run_intent("J_CD")

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT prd_intent_status FROM jobs WHERE id='J_CD'"
        )).fetchone()
    assert row["prd_intent_status"] == "done"  # unchanged — lock not acquired


@pytest.mark.asyncio
async def test_intent_cooldown_allows_after_15s(temp_db_for_prd, monkeypatch):
    """Run > 15s after a previous completion acquires the lock."""
    import aiosqlite
    from unittest.mock import AsyncMock
    from src.processors import prd

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, "
            "prd_intent_status, prd_intent_completed_at, prd_intent_text, transcript) "
            "VALUES ('J_OK', 1, 'u', 'long', 'done', 'done', "
            "datetime('now','-30 seconds'), 'second intent', 'transcript text')"
        )
        await conn.commit()

    monkeypatch.setattr(
        "src.processors.prd._call_gemini_sync",
        lambda prompt, key, model: '{"project":"X","category":"Other","overview":"","phases":[],"open_questions":[]}',
    )
    monkeypatch.setattr("src.services.drive.upload_file", AsyncMock(return_value=("FID","URL")))
    monkeypatch.setattr("src.services.drive.update_file", AsyncMock(return_value="URL"))
    monkeypatch.setattr("src.services.sheets.append_prd_row", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_document", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.brain.ingest_links", AsyncMock())
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_FOLDER_BRAIN", "")
    # Ensure at least one Gemini key is set so the loop body runs
    monkeypatch.setattr(settings, "GEMINI_FREE_API_KEY", "free-key")

    await prd.run_intent("J_OK")

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT prd_intent_status, prd_intent_completed_at FROM jobs WHERE id='J_OK'"
        )).fetchone()
    assert row["prd_intent_status"] == "done"
    assert row["prd_intent_completed_at"] is not None


# ---------------------------------------------------------------------------
# run_prd skeleton tests (issue #24)
# ---------------------------------------------------------------------------

_CANNED_PRD_JSON = '{"project":"SkeletonBot","category":"Other","overview":"Test overview.","phases":[],"open_questions":[]}'


@pytest.mark.asyncio
async def test_run_prd_auto_completes_full_pipeline(temp_db_for_prd, monkeypatch):
    """run_prd with slot='auto' runs the full pipeline end-to-end."""
    import aiosqlite
    from src.processors import prd

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, transcript) "
            "VALUES ('J_AUTO', 1, 'http://example.com', 'long', 'done', 'Some transcript')"
        )
        await conn.commit()

    monkeypatch.setattr(
        "src.processors.prd._call_gemini_sync",
        lambda prompt, key, model: _CANNED_PRD_JSON,
    )
    monkeypatch.setattr("src.services.drive.upload_file", AsyncMock(return_value=("FILE_ID", "http://drive/auto")))
    monkeypatch.setattr("src.services.drive.update_file", AsyncMock(return_value="http://drive/auto"))
    monkeypatch.setattr("src.services.sheets.append_prd_row", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_document", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", AsyncMock())
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_FOLDER_BRAIN", "")
    monkeypatch.setattr(settings, "GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr(settings, "GEMINI_PAID_API_KEY", "")

    await prd.run_prd("J_AUTO", slot="auto", model="gemini-model",
                      build_prompt=lambda j: "canned prompt")

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT prd_auto_status, prd_auto_drive_file_id, prd_auto_drive_url, prd_auto_json "
            "FROM jobs WHERE id='J_AUTO'"
        )).fetchone()

    assert row["prd_auto_status"] == "done"
    assert row["prd_auto_drive_file_id"] == "FILE_ID"
    assert row["prd_auto_drive_url"] == "http://drive/auto"
    assert "SkeletonBot" in row["prd_auto_json"]


@pytest.mark.asyncio
async def test_run_prd_intent_sets_completed_at(temp_db_for_prd, monkeypatch):
    """run_prd with slot='intent' writes prd_intent_completed_at on success."""
    import aiosqlite
    from src.processors import prd

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, transcript, prd_intent_text) "
            "VALUES ('J_INT2', 1, 'http://example.com', 'long', 'done', 'transcript', 'my intent')"
        )
        await conn.commit()

    monkeypatch.setattr(
        "src.processors.prd._call_gemini_sync",
        lambda prompt, key, model: _CANNED_PRD_JSON,
    )
    monkeypatch.setattr("src.services.drive.upload_file", AsyncMock(return_value=("FID2", "http://drive/intent")))
    monkeypatch.setattr("src.services.drive.update_file", AsyncMock(return_value="http://drive/intent"))
    monkeypatch.setattr("src.services.sheets.append_prd_row", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_document", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", AsyncMock())
    from src.config import settings
    monkeypatch.setattr(settings, "GOOGLE_DRIVE_FOLDER_BRAIN", "")
    monkeypatch.setattr(settings, "GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr(settings, "GEMINI_PAID_API_KEY", "")
    monkeypatch.setattr(settings, "PRD_INTENT_COOLDOWN_SECONDS", 0)

    await prd.run_prd("J_INT2", slot="intent", model="gemini-model",
                      build_prompt=lambda j: "canned prompt")

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT prd_intent_status, prd_intent_completed_at FROM jobs WHERE id='J_INT2'"
        )).fetchone()

    assert row["prd_intent_status"] == "done"
    assert row["prd_intent_completed_at"] is not None


@pytest.mark.asyncio
async def test_run_prd_auto_gemini_fail_sends_retry_keyboard(temp_db_for_prd, monkeypatch):
    """When both Gemini keys fail for slot='auto', a single Retry button is sent."""
    import aiosqlite
    from src.processors import prd

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, transcript) "
            "VALUES ('J_FAIL', 1, 'http://example.com', 'long', 'done', 'transcript')"
        )
        await conn.commit()

    def _raise(prompt, key, model):
        raise RuntimeError("Gemini down")

    monkeypatch.setattr("src.processors.prd._call_gemini_sync", _raise)
    send_keyboard = AsyncMock()
    monkeypatch.setattr("src.telegram.sender.send_inline_keyboard", send_keyboard)
    from src.config import settings
    monkeypatch.setattr(settings, "GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr(settings, "GEMINI_PAID_API_KEY", "paid-key")

    await prd.run_prd("J_FAIL", slot="auto", model="gemini-model",
                      build_prompt=lambda j: "canned prompt")

    send_keyboard.assert_awaited_once()
    _, kwargs = send_keyboard.await_args
    buttons = kwargs.get("buttons") or send_keyboard.await_args[0][2]
    # auto slot → single Retry button
    assert len(buttons[0]) == 1
    assert buttons[0][0]["callback_data"] == "prd_retry_auto:J_FAIL"

    async with aiosqlite.connect(temp_db_for_prd) as conn:
        conn.row_factory = aiosqlite.Row
        row = await (await conn.execute(
            "SELECT prd_auto_status FROM jobs WHERE id='J_FAIL'"
        )).fetchone()
    assert row["prd_auto_status"] == "error"

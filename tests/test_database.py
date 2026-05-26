"""Unit tests for src/database.py helpers added in slice #7."""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import aiosqlite
import pytest


@pytest.fixture
async def temp_db():
    """Create a fresh SQLite file with the full schema applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Patch settings.DB_PATH for the duration of the test
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db
        await db.init_db()
        yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_set_and_get_chat_state_round_trip(temp_db):
    from src import database as db
    await db.set_chat_state(chat_id=42, mode="awaiting_intent", job_id="20260521_120000_AAAA")
    state = await db.get_chat_state(42)
    assert state is not None
    assert state["chat_id"] == 42
    assert state["mode"] == "awaiting_intent"
    assert state["job_id"] == "20260521_120000_AAAA"
    assert state["expires_at"] > datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_get_chat_state_missing_returns_none(temp_db):
    from src import database as db
    assert await db.get_chat_state(999) is None


@pytest.mark.asyncio
async def test_clear_chat_state_removes_row(temp_db):
    from src import database as db
    await db.set_chat_state(chat_id=1, mode="awaiting_intent", job_id="J1")
    await db.clear_chat_state(1)
    assert await db.get_chat_state(1) is None


@pytest.mark.asyncio
async def test_clear_chat_state_idempotent(temp_db):
    from src import database as db
    await db.clear_chat_state(999)  # no-op, must not raise


@pytest.mark.asyncio
async def test_set_chat_state_pk_replace(temp_db):
    """Second set overwrites the first (PK on chat_id)."""
    from src import database as db
    await db.set_chat_state(chat_id=7, mode="awaiting_intent", job_id="J_OLD")
    await db.set_chat_state(chat_id=7, mode="awaiting_intent", job_id="J_NEW")
    state = await db.get_chat_state(7)
    assert state["job_id"] == "J_NEW"


async def _insert_job(path: str, job_id: str, chat_id: int, content_type: str, status: str, title: str = "") -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, title) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, chat_id, f"https://x.test/{job_id}", content_type, status, title),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_find_jobs_by_suffix_returns_all_content_types(temp_db):
    from src import database as db
    await _insert_job(temp_db, "20260521_120000_AAAA", 1, "long", "done", "Long video A")
    await _insert_job(temp_db, "20260521_120100_AAAA", 1, "short", "done", "Short video A")
    await _insert_job(temp_db, "20260521_120200_BBBB", 1, "long", "done", "Long video B")
    rows = await db.find_jobs_by_suffix(1, "AAAA")
    assert len(rows) == 2
    # Ordered by created_at DESC; the short was inserted second
    assert rows[0]["content_type"] == "short"
    assert rows[1]["content_type"] == "long"


@pytest.mark.asyncio
async def test_find_jobs_by_suffix_chat_scoped(temp_db):
    from src import database as db
    await _insert_job(temp_db, "20260521_120000_AAAA", 1, "long", "done")
    await _insert_job(temp_db, "20260521_120000_BBBB", 2, "long", "done")
    rows = await db.find_jobs_by_suffix(1, "BBBB")
    assert rows == []


@pytest.mark.asyncio
async def test_get_recent_jobs_orders_desc_and_limits(temp_db):
    from src import database as db
    for i in range(7):
        await _insert_job(temp_db, f"2026052{i}_120000_J{i:03d}1", 1, "long", "done", f"job {i}")
    rows = await db.get_recent_jobs(1, limit=5)
    assert len(rows) == 5
    assert rows[0]["title"] == "job 6"  # most recent first


@pytest.mark.asyncio
async def test_create_job_with_template_writes_column(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test",
        content_type="long",
        template="method",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["template"] == "method"


@pytest.mark.asyncio
async def test_create_job_without_template_defaults_none(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test2",
        content_type="long",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["template"] is None


@pytest.mark.asyncio
async def test_update_job_status_writes_template_detection_method(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test3",
        content_type="long",
    )
    await db.update_job_status(job_id, "pending", template_detection_method="explicit_command")
    job = await db.get_job(job_id)
    assert job["template_detection_method"] == "explicit_command"


@pytest.mark.asyncio
async def test_update_job_status_writes_key_phrases(temp_db):
    import json
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test4",
        content_type="long",
    )
    await db.update_job_status(job_id, "transcript_done", key_phrases=json.dumps(["stripe", "nextjs"]))
    job = await db.get_job(job_id)
    assert json.loads(job["key_phrases"]) == ["stripe", "nextjs"]


@pytest.mark.asyncio
async def test_set_prd_slot_status_auto(temp_db):
    from src import database as db
    job_id = await db.create_job(chat_id=1, url="https://youtube.com/watch?v=prd1", content_type="long")
    await db.set_prd_slot_status(job_id, "auto", "generating")
    job = await db.get_job(job_id)
    assert job["prd_auto_status"] == "generating"
    assert job["prd_intent_status"] is None


@pytest.mark.asyncio
async def test_set_prd_slot_status_intent(temp_db):
    from src import database as db
    job_id = await db.create_job(chat_id=1, url="https://youtube.com/watch?v=prd2", content_type="long")
    await db.set_prd_slot_status(job_id, "intent", "done")
    job = await db.get_job(job_id)
    assert job["prd_intent_status"] == "done"
    assert job["prd_auto_status"] is None


@pytest.mark.asyncio
async def test_promise_gap_column_exists(tmp_path, monkeypatch) -> None:
    """promise_gap column must exist after init_db()."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cursor = await conn.execute("PRAGMA table_info(jobs)")
        cols = {row[1] async for row in cursor}
    assert "promise_gap" in cols

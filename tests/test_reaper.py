"""Tests for ADR-0010 — orphaned-job recovery at worker startup.

Covers database.fetch_and_mark_stale_jobs() and worker.reap_stale_jobs().
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def temp_db():
    """Fresh SQLite file with the full schema applied (mirrors test_database.py)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db
        await db.init_db()
        yield path
    os.unlink(path)


async def _insert_job(
    db, job_id: str, chat_id: int, status: str, *, minutes_ago: float,
    content_type: str = "long", attempt: int = 1,
) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    async with db.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, attempt, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, chat_id, "http://x", content_type, status, attempt, ts, ts),
        )
        await conn.commit()


# ---------------------------------------------------------------------------
# database.fetch_and_mark_stale_jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaps_stale_processing(temp_db):
    from src import database as db
    await _insert_job(db, "J_PROC", 100, "processing", minutes_ago=20)

    rows = await db.fetch_and_mark_stale_jobs()

    assert rows == [{"id": "J_PROC", "chat_id": 100, "status": "processing", "url": "http://x"}]
    job = await db.get_job("J_PROC")
    assert job["status"] == "error"
    assert job["attempt"] == 2  # incremented exactly once


@pytest.mark.asyncio
async def test_reaps_stale_enriching(temp_db):
    from src import database as db
    await _insert_job(db, "J_ENR", 200, "enriching", minutes_ago=15)

    rows = await db.fetch_and_mark_stale_jobs()

    assert rows == [{"id": "J_ENR", "chat_id": 200, "status": "enriching", "url": "http://x"}]
    assert (await db.get_job("J_ENR"))["status"] == "error"


@pytest.mark.asyncio
async def test_skips_recently_touched_job(temp_db):
    """A freshly-queued enriching job (set by the webhook seconds ago) is not reaped."""
    from src import database as db
    await _insert_job(db, "J_FRESH", 300, "enriching", minutes_ago=2)

    rows = await db.fetch_and_mark_stale_jobs()

    assert rows == []
    job = await db.get_job("J_FRESH")
    assert job["status"] == "enriching"  # untouched
    assert job["attempt"] == 1


@pytest.mark.asyncio
async def test_ignores_non_reapable_states(temp_db):
    """transcript_done (waiting on the user), done, pending, error are all left alone."""
    from src import database as db
    for i, status in enumerate(("transcript_done", "done", "pending", "error")):
        await _insert_job(db, f"J{i}", 400 + i, status, minutes_ago=60)

    rows = await db.fetch_and_mark_stale_jobs()

    assert rows == []
    assert (await db.get_job("J0"))["status"] == "transcript_done"


@pytest.mark.asyncio
async def test_reaps_mixed_batch(temp_db):
    from src import database as db
    await _insert_job(db, "J_P", 1, "processing", minutes_ago=30)
    await _insert_job(db, "J_E", 2, "enriching", minutes_ago=30)
    await _insert_job(db, "J_OK", 3, "transcript_done", minutes_ago=30)

    rows = await db.fetch_and_mark_stale_jobs()

    assert {r["id"] for r in rows} == {"J_P", "J_E"}
    assert (await db.get_job("J_OK"))["status"] == "transcript_done"


# ---------------------------------------------------------------------------
# worker.reap_stale_jobs — per-state notification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reap_notifies_per_state(temp_db):
    from src import database as db, worker
    await _insert_job(db, "20260524_120000_PROC", 100, "processing", minutes_ago=20)
    await _insert_job(db, "20260524_120000_ENRC", 200, "enriching", minutes_ago=20)

    with patch("src.telegram.sender.send_message", new=AsyncMock()) as send_msg, \
         patch("src.telegram.sender.send_inline_keyboard", new=AsyncMock()) as send_kb:
        await worker.reap_stale_jobs()

    # both states now offer a one-tap retry button — no plain resend message
    send_msg.assert_not_called()
    assert send_kb.call_count == 2
    by_chat = {c.args[0]: c for c in send_kb.call_args_list}

    # processing → reprocess button carrying the orphaned job_id (one-tap resend)
    proc = by_chat[100]
    assert proc.kwargs["buttons"][0][0]["callback_data"] == "reprocess:20260524_120000_PROC"

    # enriching → the existing enrichment_retry button
    enr = by_chat[200]
    assert enr.kwargs["buttons"][0][0]["callback_data"] == "enrichment_retry:20260524_120000_ENRC"


@pytest.mark.asyncio
async def test_reap_noop_when_nothing_stale(temp_db):
    from src import database as db, worker
    await _insert_job(db, "J_FRESH", 1, "processing", minutes_ago=1)

    with patch("src.telegram.sender.send_message", new=AsyncMock()) as send_msg, \
         patch("src.telegram.sender.send_inline_keyboard", new=AsyncMock()) as send_kb:
        await worker.reap_stale_jobs()

    send_msg.assert_not_called()
    send_kb.assert_not_called()

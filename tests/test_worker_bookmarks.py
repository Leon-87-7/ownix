"""#496: the worker chains 'bookmarks_enrich' after a successful bookmark
import, and that follow-up task never depends on the job row surviving."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db

        await db.init_db()
        yield path
    os.unlink(path)


async def _make_job(chat_id: int = 1) -> str:
    from src import database

    job_id = await database.create_job(
        chat_id=chat_id, url="bookmarks:deadbeefcafef00d", content_type="link"
    )
    return job_id


@pytest.mark.asyncio
async def test_handle_bookmarks_chains_enrich_task_on_success(temp_db, monkeypatch):
    from src import worker
    from src.processors import bookmarks

    job_id = await _make_job()

    monkeypatch.setattr(bookmarks, "run", AsyncMock(return_value=None))
    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    monkeypatch.setattr(worker.queue, "enqueue", fake_enqueue)

    await worker._handle_bookmarks({"task": "bookmarks", "job_id": job_id, "html_b64": ""})

    assert enqueued == [{"task": "bookmarks_enrich", "job_id": job_id}]


@pytest.mark.asyncio
async def test_handle_bookmarks_does_not_chain_enrich_on_processor_failure(
    temp_db, monkeypatch
):
    from src import database, worker
    from src.processors import bookmarks

    job_id = await _make_job()

    monkeypatch.setattr(bookmarks, "run", AsyncMock(side_effect=RuntimeError("boom")))
    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    monkeypatch.setattr(worker.queue, "enqueue", fake_enqueue)
    monkeypatch.setattr(worker, "_notify_failure", AsyncMock())

    await worker._handle_bookmarks({"task": "bookmarks", "job_id": job_id, "html_b64": ""})

    assert enqueued == []
    job = await database.get_job(job_id)
    assert job["status"] == "error"


@pytest.mark.asyncio
async def test_handle_bookmarks_enrich_calls_refresh_links_for_job(temp_db, monkeypatch):
    from src import brain, worker

    called: list[str] = []

    async def fake_refresh(job_id: str) -> int:
        called.append(job_id)
        return 0

    monkeypatch.setattr(brain, "refresh_links_for_job", fake_refresh)

    await worker._handle_bookmarks_enrich({"task": "bookmarks_enrich", "job_id": "gone-job"})

    assert called == ["gone-job"]


@pytest.mark.asyncio
async def test_handle_bookmarks_enrich_swallows_errors(temp_db, monkeypatch):
    """Best-effort: a failure here must never propagate or touch job status."""
    from src import brain, worker

    async def fake_refresh(job_id: str) -> int:
        raise RuntimeError("Drive is down")

    monkeypatch.setattr(brain, "refresh_links_for_job", fake_refresh)

    await worker._handle_bookmarks_enrich({"task": "bookmarks_enrich", "job_id": "x"})
    # No exception propagated — reaching this line is the assertion.


@pytest.mark.asyncio
async def test_bookmarks_enrich_is_exempt_from_the_job_existence_gate(temp_db, monkeypatch):
    """ADR-0046: the job may already be deleted — _dispatch must still run
    bookmarks_enrich rather than silently skipping it as job_gone_skipped."""
    from src import worker

    called: list[str] = []

    async def fake_handler(task: dict) -> None:
        called.append(task["job_id"])

    monkeypatch.setitem(worker._TASK_HANDLERS, "bookmarks_enrich", fake_handler)

    await worker._dispatch({"task": "bookmarks_enrich", "job_id": "does-not-exist"})

    assert called == ["does-not-exist"]

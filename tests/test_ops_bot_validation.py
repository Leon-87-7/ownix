from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src import database
from src.services import jobs, ops_bot
from src.services.ops_bot import _escape_like


def test_escape_like_escapes_domain_wildcards_only() -> None:
    assert "%@" + _escape_like("exa_m%ple.com") == "%@exa\\_m\\%ple.com"
    assert _escape_like("a\\b.com") == "a\\\\b.com"


@pytest.mark.asyncio
async def test_approve_pending_ids_flushes_only_each_users_held_jobs(tmp_path, monkeypatch) -> None:
    db_file = str(tmp_path / "ops.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)
    await database.init_db()
    for tg_id in (10, 11, 12):
        await database.upsert_user(tg_id=tg_id, first_name=f"User {tg_id}")
    own_job = await database.create_job(
        chat_id=10, url="https://youtu.be/own", content_type="short", status="held"
    )
    other_job = await database.create_job(
        chat_id=12, url="https://youtu.be/other", content_type="long", status="held"
    )
    enqueue = AsyncMock()
    notify = AsyncMock()
    monkeypatch.setattr("src.services.jobs.queue.enqueue", enqueue)
    monkeypatch.setattr(ops_bot.sender, "send_message", notify)

    assert await ops_bot._approve_pending_ids([10, 11]) == 2

    assert (await database.get_job(own_job))["status"] == "pending"
    assert (await database.get_job(other_job))["status"] == "held"
    enqueue.assert_awaited_once_with({"task": "video", "job_id": own_job})
    assert notify.await_count == 2


@pytest.mark.asyncio
async def test_flush_held_jobs_continues_after_one_enqueue_failure(
    tmp_path, monkeypatch
) -> None:
    db_file = str(tmp_path / "ops.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)
    await database.init_db()
    first_job = await database.create_job(
        chat_id=20, url="https://youtu.be/first", content_type="short", status="held"
    )
    failed_job = await database.create_job(
        chat_id=20, url="https://example.com/post", content_type="article", status="held"
    )
    last_job = await database.create_job(
        chat_id=20, url="https://github.com/example/repo", content_type="repo", status="held"
    )
    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)
        if task["job_id"] == failed_job:
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr("src.services.jobs.queue.enqueue", fake_enqueue)

    assert await jobs.flush_held_jobs(20) == 2

    assert (await database.get_job(first_job))["status"] == "pending"
    assert (await database.get_job(failed_job))["status"] == "held"
    assert (await database.get_job(last_job))["status"] == "pending"
    assert sorted(enqueued, key=lambda task: task["job_id"]) == sorted(
        [
            {"task": "video", "job_id": first_job},
            {"task": "article", "job_id": failed_job},
            {"task": "repo", "job_id": last_job},
        ],
        key=lambda task: task["job_id"],
    )

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src import database
from src.services import ops_bot
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

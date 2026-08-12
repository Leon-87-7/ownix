"""Tests for the shared `/force` command (issue #486).

`/force <url>` — not a pipeline override (no such argument exists). Migrated
faithfully from `src/telegram/webhook.py:_cmd_force`'s three states: reset +
reprocess an existing job, clear an orphaned markdown-cache row, or create a
job directly (bypassing `create_and_enqueue_job`'s dedup, which is the whole
point of the command).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.intake import commands

CHAT_ID = 42


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "force_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


def _enqueue_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.services.jobs.queue.enqueue", _fake_enqueue)
    monkeypatch.setattr("src.queue.enqueue", _fake_enqueue)


class TestForceCommand:
    def test_usage_message_with_no_url(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/force"].handler(CHAT_ID, ["/force"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_unsupported_url_is_rejected(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/force"].handler(CHAT_ID, ["/force", "https://example.com/nothing"])
        )
        assert resp.kind == "unsupported"

    def test_creates_a_job_when_none_exists(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/force"].handler(
                CHAT_ID, ["/force", "https://youtube.com/shorts/force1"]
            )
        )
        assert resp.kind == "job_created"
        assert resp.job_id is not None
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["content_type"] == "short"

    def test_accepts_duplicate_canonical_tag_tokens(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        asyncio.run(
            db.create_tag(
                chat_id=CHAT_ID,
                name="Read Later",
                meaning="",
                color="#8b5cf6",
            )
        )

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/force"].handler(
                CHAT_ID,
                [
                    "/force",
                    "https://youtube.com/shorts/force-tags",
                    "#read_later",
                    "#READ_LATER",
                ],
            )
        )

        assert resp.kind == "job_created"
        assert resp.job_id is not None
        tags = asyncio.run(db.list_job_tags(resp.job_id))
        assert [tag["name"] for tag in tags] == ["Read Later"]

    def test_bypasses_dedup_and_reprocesses_an_existing_job(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        url = "https://youtube.com/shorts/force2"
        job_id = asyncio.run(db.create_job(chat_id=CHAT_ID, url=url, content_type="short", status="done"))

        resp = asyncio.run(commands.SHARED_COMMANDS["/force"].handler(CHAT_ID, ["/force", url]))

        assert resp.kind == "action_ack"
        assert resp.job_id == job_id
        job = asyncio.run(db.get_job(job_id))
        # reset_job returns it to pending — no second row was created.
        assert job["status"] == "pending"
        assert asyncio.run(db.get_job(job_id)) is not None

    def test_clears_an_orphaned_cache_row_and_continues_to_a_job(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        url = "https://youtube.com/watch?v=cache1"
        asyncio.run(db.insert_markdown_cache(url, "some cached markdown"))

        resp = asyncio.run(commands.SHARED_COMMANDS["/force"].handler(CHAT_ID, ["/force", url]))

        assert resp.kind == "job_created"
        assert resp.job_id is not None
        assert asyncio.run(db.get_markdown_cache(url)) is None
        assert asyncio.run(db.find_recent_job_by_url(CHAT_ID, url)) is not None

    def test_reachable_through_the_router(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        from src.intake import router
        from src.intake.models import IntakeActor, IntakeMessage

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(
                IntakeMessage(actor=actor, text="/force https://youtube.com/shorts/force3")
            )
        )
        assert resp.kind == "job_created"

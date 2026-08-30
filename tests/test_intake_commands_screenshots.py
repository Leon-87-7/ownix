"""Tests for the shared `/screenshots` command.

Mirrors the structure of tests/test_intake_commands_checklists.py. The
background capture run itself is covered by tests/test_screenshots.py — here
we only need `trigger()`'s lock/outcome branches to surface correctly through
the command.
"""
from __future__ import annotations

import asyncio

import pytest

from src.intake import commands

CHAT_ID = 42


def _init_db(tmp_path, monkeypatch: pytest.MonkeyPatch, name: str):
    db_file = tmp_path / name
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


class TestScreenshotsCommand:
    def test_usage_message_with_no_suffix(self) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_no_match_returns_error(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        _init_db(tmp_path, monkeypatch, "screenshots_no_match.db")

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots", "ZZZZ"])
        )
        assert resp.kind == "error"

    def test_ineligible_job_is_rejected(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        database = _init_db(tmp_path, monkeypatch, "screenshots_ineligible.db")
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short")
        )
        asyncio.run(database.update_job_status(job_id, "done"))

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots", job_id[-4:]])
        )
        assert resp.kind == "error"
        assert "long-video" in resp.text.lower()

    def test_over_duration_cap_is_rejected(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        database = _init_db(tmp_path, monkeypatch, "screenshots_too_long.db")
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(
            database.update_job_status(job_id, "done", video_duration_seconds=5_401)
        )

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots", job_id[-4:]])
        )
        assert resp.kind == "error"
        assert "duration limit" in resp.text.lower()

    def test_eligible_job_claims_lock_and_starts(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        database = _init_db(tmp_path, monkeypatch, "screenshots_started.db")
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done"))

        scheduled = []

        def capture_background(coro):
            scheduled.append(coro)
            coro.close()

        monkeypatch.setattr("src.processors.screenshots.spawn_background", capture_background)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots", job_id[-4:]])
        )

        assert resp.kind == "action_ack"
        assert resp.job_id == job_id
        assert len(scheduled) == 1

        job = asyncio.run(database.get_job(job_id))
        assert job["screenshots_status"] == "generating"

    def test_already_generating_is_busy(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        database = _init_db(tmp_path, monkeypatch, "screenshots_busy.db")
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done", screenshots_status="generating"))

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/screenshots"].handler(CHAT_ID, ["/screenshots", job_id[-4:]])
        )
        assert resp.kind == "error"
        assert "already running" in resp.text.lower()

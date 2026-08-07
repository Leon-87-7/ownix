"""Tests for the shared `/freestyle <url>` command (issue #487).

Scoped to the one-shot form only — bare `/freestyle` (no URL) arms a
Telegram-only Redis continuation (`pending_template`) outside command
dispatch entirely, and stays there (see the issue's correction comment).

The migrated half closes a real gap: `IntakeStateBanner` already renders
`awaiting_freestyle`, but nothing on the dashboard could arm it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.intake import commands, state

CHAT_ID = 42


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "freestyle_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


def _enqueue_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.queue.enqueue", _fake_enqueue)


class TestFreestyleCommand:
    def test_usage_message_with_no_url(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/freestyle"].handler(CHAT_ID, ["/freestyle"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_unsupported_url_is_rejected(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/freestyle"].handler(
                CHAT_ID, ["/freestyle", "https://example.com/nothing"]
            )
        )
        assert resp.kind == "unsupported"
        assert asyncio.run(state.get_state(CHAT_ID)) is None

    def test_long_url_enqueues_immediately_and_arms_state(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/freestyle"].handler(
                CHAT_ID, ["/freestyle", "https://youtube.com/watch?v=fs1"]
            )
        )
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["template"] == "freestyle"
        assert job["content_type"] == "long"
        pending = asyncio.run(state.get_state(CHAT_ID))
        assert pending is not None
        assert pending["mode"] == "awaiting_freestyle"
        assert pending["job_id"] == resp.job_id

    def test_short_url_arms_state_without_enqueueing(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enq = []

        async def _spy_enqueue(payload: dict) -> None:
            enq.append(payload)

        monkeypatch.setattr("src.queue.enqueue", _spy_enqueue)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/freestyle"].handler(
                CHAT_ID, ["/freestyle", "https://instagram.com/reel/abc123/"]
            )
        )
        assert resp.kind == "job_created"
        assert enq == []
        pending = asyncio.run(state.get_state(CHAT_ID))
        assert pending is not None and pending["mode"] == "awaiting_freestyle"

    def test_repo_url_skips_the_template_and_state(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/freestyle"].handler(
                CHAT_ID, ["/freestyle", "https://github.com/octocat/hello-world"]
            )
        )
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["template"] is None
        assert job["content_type"] == "repo"
        assert asyncio.run(state.get_state(CHAT_ID)) is None

    def test_reachable_through_the_router(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        from src.intake import router
        from src.intake.models import IntakeActor, IntakeMessage

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(
                IntakeMessage(actor=actor, text="/freestyle https://youtube.com/watch?v=fs2")
            )
        )
        assert resp.kind == "job_created"
        assert asyncio.run(state.get_state(CHAT_ID))["mode"] == "awaiting_freestyle"

    def test_arming_from_dashboard_replaces_a_pending_telegram_flow(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """chat_state is one slot per owner, not per channel (state.py docstring)."""
        _enqueue_noop(monkeypatch)
        asyncio.run(state.set_state(CHAT_ID, "awaiting_intent", "job_from_telegram"))

        asyncio.run(
            commands.SHARED_COMMANDS["/freestyle"].handler(
                CHAT_ID, ["/freestyle", "https://youtube.com/watch?v=fs3"]
            )
        )

        pending = asyncio.run(state.get_state(CHAT_ID))
        assert pending["mode"] == "awaiting_freestyle"
        assert pending["job_id"] != "job_from_telegram"

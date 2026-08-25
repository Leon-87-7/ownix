"""Tests for the shared `-name <url>` user-template shortcut.

Previously Telegram-only (`_handle_user_template_shortcut`,
webhook.py:1550): typing `-name <url>` on the dashboard composer fell
through to plain URL detection and was rejected as unsupported, because
`src/intake/router.py` only branched on a leading `/` for commands.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.intake import commands

CHAT_ID = 42


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "user_template_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


def _enqueue_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.job_queue.enqueue", _fake_enqueue)


class TestUserTemplateShortcut:
    def test_not_a_shortcut_is_ignored(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(commands.user_template_shortcut(CHAT_ID, "- just a note"))
        assert resp.kind == "unsupported"

    def test_usage_message_with_no_url(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(commands.user_template_shortcut(CHAT_ID, "-hello-from-gemini"))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_unknown_template_is_an_error(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        resp = asyncio.run(
            commands.user_template_shortcut(CHAT_ID, "-nope https://youtube.com/watch?v=ut1")
        )
        assert resp.kind == "error"

    def test_known_template_enqueues_freestyle_job(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        asyncio.run(
            db.create_user_template(
                chat_id=CHAT_ID,
                name="hello-from-gemini",
                description="a test prompt",
                extra_instructions="say Hello and add a short poem about the video you received",
            )
        )
        resp = asyncio.run(
            commands.user_template_shortcut(
                CHAT_ID, "-hello-from-gemini https://youtube.com/watch?v=ut2"
            )
        )
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["template"] == "freestyle"
        assert job["freestyle_prompt"] == "say Hello and add a short poem about the video you received"
        assert job["template_detection_method"] == "user_template:hello-from-gemini"

    def test_repo_url_clears_template(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        asyncio.run(
            db.create_user_template(
                chat_id=CHAT_ID, name="hello-from-gemini", extra_instructions="say hello"
            )
        )
        resp = asyncio.run(
            commands.user_template_shortcut(
                CHAT_ID, "-hello-from-gemini https://github.com/octocat/hello-world"
            )
        )
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["template"] is None
        assert job["content_type"] == "repo"

    def test_reachable_through_the_router(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        asyncio.run(
            db.create_user_template(
                chat_id=CHAT_ID, name="hello-from-gemini", extra_instructions="say hello"
            )
        )
        from src.intake import router
        from src.intake.models import IntakeActor, IntakeMessage

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(
                IntakeMessage(
                    actor=actor, text="-hello-from-gemini https://youtube.com/watch?v=ut3"
                )
            )
        )
        assert resp.kind == "job_created"

    def test_plain_note_starting_with_dash_is_not_intercepted(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A leading '-' followed by a space (not alnum) must fall through to
        normal candidate handling, not the shortcut branch."""
        from src.intake import router
        from src.intake.models import IntakeActor, IntakeMessage

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(IntakeMessage(actor=actor, text="- buy milk later"))
        )
        assert resp.kind == "unsupported"

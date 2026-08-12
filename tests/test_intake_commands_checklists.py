"""Tests for the shared `/checklists` command.

`checklists_command` is channel-agnostic (SHARED_COMMANDS) — Telegram and the
dashboard composer reach the exact same code path. Mirrors the structure of
tests/test_intake_commands_find.py.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.intake import commands

CHAT_ID = 42


class TestChecklistsCommand:
    def test_usage_message_with_no_suffix(self) -> None:
        resp = asyncio.run(commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists"]))
        assert resp.kind == "command_result"
        assert "usage" in resp.text.lower()

    def test_no_match_returns_error(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        db_file = tmp_path / "checklists_no_match.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", "ZZZZ"])
        )
        assert resp.kind == "error"
        assert "ZZZZ" in resp.text

    def test_short_job_without_transcript_ready_is_rejected(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_not_ready.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short")
        )

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "error"

    def test_short_job_generates_and_persists(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_short_ok.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://tiktok.com/@a/video/1", content_type="short")
        )
        asyncio.run(
            database.update_job_status(job_id, "done", transcript="rate limiting matters a lot")
        )

        fake_generate = AsyncMock(
            return_value='{"applicable": true, "topics": [{"name": "Rate limiting", "directive": "Check it."}]}'
        )
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )

        assert resp.kind == "checklists_result"
        assert "## Rate limiting" in resp.text
        assert resp.job_id == job_id

        job = asyncio.run(database.get_job(job_id))
        assert job["checklists_md"] is not None
        assert job["checklists_generated_at"] is not None

    def test_long_job_status_transcript_done_is_accepted(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_long_ok.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(
            database.update_job_status(job_id, "transcript_done", transcript="lots of engineering advice")
        )

        fake_generate = AsyncMock(return_value='{"applicable": false, "topics": []}')
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "checklists_result"
        assert "No actionable" in resp.text

    def test_generation_does_not_restore_stale_status(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_status_race.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(
                chat_id=CHAT_ID,
                url="https://youtube.com/watch?v=abc",
                content_type="long",
            )
        )
        asyncio.run(
            database.update_job_status(
                job_id, "transcript_done", transcript="engineering advice"
            )
        )

        async def generate_then_advance(_job: dict) -> tuple[dict, str]:
            await database.update_job_status(job_id, "done")
            return {"topics": []}, "# Checklist\n"

        monkeypatch.setattr("src.processors.checklists.run_checklists", generate_then_advance)
        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(
                CHAT_ID, ["/checklists", job_id[-4:]]
            )
        )

        assert resp.kind == "checklists_result"
        job = asyncio.run(database.get_job(job_id))
        assert job["status"] == "done"
        assert job["checklists_md"] == "# Checklist\n"

    def test_gemini_failure_returns_retryable_error(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_gemini_fail.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

        from src import database
        from src.services.gemini import GeminiUnavailableError

        asyncio.run(database.init_db())
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done", transcript="some transcript"))

        async def _fail(*args, **kwargs):
            raise GeminiUnavailableError("both keys failed")

        monkeypatch.setattr("src.services.gemini.generate", _fail)

        resp = asyncio.run(
            commands.SHARED_COMMANDS["/checklists"].handler(CHAT_ID, ["/checklists", job_id[-4:]])
        )
        assert resp.kind == "error"
        assert resp.retryable is True

    def test_dashboard_reaches_it_through_the_router(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        db_file = tmp_path / "checklists_router.db"
        monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
        monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

        from src import database
        from src.intake import idempotency, router
        from src.intake.models import IntakeActor, IntakeMessage

        asyncio.run(database.init_db())
        idempotency._memory.clear()
        job_id = asyncio.run(
            database.create_job(chat_id=CHAT_ID, url="https://youtube.com/watch?v=abc", content_type="long")
        )
        asyncio.run(database.update_job_status(job_id, "done", transcript="advice about audit logs"))

        fake_generate = AsyncMock(
            return_value='{"applicable": true, "topics": [{"name": "Audit logs", "directive": "Check it."}]}'
        )
        monkeypatch.setattr("src.services.gemini.generate", fake_generate)

        actor = IntakeActor(
            user_id=CHAT_ID, channel_id="dashboard", channel_type="dashboard", legacy_chat_id=CHAT_ID
        )
        resp = asyncio.run(
            router.handle(IntakeMessage(actor=actor, text=f"/checklists {job_id[-4:]}"))
        )
        assert resp.kind == "checklists_result"

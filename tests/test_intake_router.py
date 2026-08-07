"""Tests for the channel-neutral intake router (`src/intake/router.py`).

Covers `IntakeMessage -> IntakeResponse` for URL / unsupported / command-looking
input, schema_version rejection, and idempotent replay (issue #473).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.intake import idempotency, router
from src.intake.models import IntakeActor, IntakeMessage

CHAT_ID = 42


@pytest.fixture(autouse=True)
def _memory_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    idempotency._memory.clear()


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "intake_router_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


def _msg(**kwargs) -> IntakeMessage:
    actor = IntakeActor(
        user_id=CHAT_ID,
        channel_id="dashboard",
        channel_type="dashboard",
        legacy_chat_id=CHAT_ID,
    )
    return IntakeMessage(actor=actor, **kwargs)


def _enqueue_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.services.jobs.queue.enqueue", _fake_enqueue)


class TestUrlIntake:
    def test_supported_url_creates_job(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://youtube.com/shorts/abc123")))
        assert resp.kind == "job_created"
        assert resp.job_id is not None
        assert resp.schema_version == 1

    def test_unsupported_url_is_rejected_without_creating_a_job(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/nothing")))
        assert resp.kind == "unsupported"
        assert resp.job_id is None
        assert resp.retryable is False

    def test_document_pdf_url_is_unsupported_for_plain_submit(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/file.pdf")))
        assert resp.kind == "unsupported"


class TestCommandInput:
    def test_help_command_returns_command_result(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="/help")))
        assert resp.kind == "command_result"
        assert "cancel" in resp.text.lower()

    def test_unknown_command_is_unsupported(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="/not-a-real-command")))
        assert resp.kind == "unsupported"

    def test_cancel_with_no_pending_state(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="/cancel")))
        assert resp.kind == "command_result"
        assert "nothing to cancel" in resp.text.lower()


class TestTagTokens:
    """`#tag` tokens on a submit (issue #482)."""

    @staticmethod
    def _tag(db, name: str) -> dict:
        return asyncio.run(
            db.create_tag(chat_id=CHAT_ID, name=name, meaning="", color="#8b5cf6")
        )

    @staticmethod
    def _job_tag_names(db, job_id: str) -> list[str]:
        return [t["name"] for t in asyncio.run(db.list_job_tags(job_id))]

    def test_trailing_token_attaches_existing_tag(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        self._tag(db, "GoTo")
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag1 #GoTo")))
        assert resp.kind == "job_created"
        assert self._job_tag_names(db, resp.job_id) == ["GoTo"]

    def test_leading_token_attaches_the_same_way(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        self._tag(db, "GoTo")
        resp = asyncio.run(router.handle(_msg(text="#GoTo https://youtube.com/shorts/tag2")))
        assert resp.kind == "job_created"
        assert self._job_tag_names(db, resp.job_id) == ["GoTo"]

    def test_normalized_name_matches_existing_tag(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        self._tag(db, "Read Later")
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag3 #readlater")))
        assert self._job_tag_names(db, resp.job_id) == ["Read Later"]

    def test_url_fragment_survives_and_yields_no_tag(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag4#t=30")))
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["url"] == "https://youtube.com/shorts/tag4#t=30"
        assert self._job_tag_names(db, resp.job_id) == []

    def test_unknown_tag_still_creates_the_job(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag5 #Nope")))
        assert resp.kind == "job_created"
        assert resp.job_id is not None
        assert "Nope" in resp.text
        assert self._job_tag_names(db, resp.job_id) == []

    def test_multiple_tokens_attach_all_known(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        self._tag(db, "GoTo")
        self._tag(db, "Later")
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag6 #GoTo #Later")))
        assert sorted(self._job_tag_names(db, resp.job_id)) == ["GoTo", "Later"]

    def test_bare_token_with_no_url_is_unsupported(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        self._tag(db, "GoTo")
        resp = asyncio.run(router.handle(_msg(text="#GoTo")))
        assert resp.kind == "unsupported"
        assert resp.job_id is None
        assert "GoTo" in resp.text

    def test_tokens_do_not_break_pipeline_detection(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: the whole string used to reach `detect_pipeline`."""
        _enqueue_noop(monkeypatch)
        self._tag(db, "GoTo")
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/watch?v=abc #GoTo")))
        assert resp.kind == "job_created"
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["content_type"] == "long"
        # The token must not survive into the stored URL — detection happened to
        # tolerate the trailing text before, but the job URL was wrong.
        assert job["url"] == "https://youtube.com/watch?v=abc"
        assert self._job_tag_names(db, resp.job_id) == ["GoTo"]


class TestSchemaVersion:
    def test_unknown_schema_version_is_rejected(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(
            router.handle(_msg(url="https://youtube.com/shorts/abc123", schema_version=99))
        )
        assert resp.kind == "error"
        assert resp.retryable is False


class TestIdempotentReplay:
    def test_repeat_idempotency_key_returns_same_job_no_duplicate(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        first = asyncio.run(
            router.handle(
                _msg(url="https://youtube.com/shorts/replay1", idempotency_key="idem-1")
            )
        )
        second = asyncio.run(
            router.handle(
                _msg(url="https://youtube.com/shorts/replay1", idempotency_key="idem-1")
            )
        )
        assert first.job_id == second.job_id
        assert first.kind == "job_created"
        assert second.kind == "job_created"

        async def _count_jobs() -> int:
            async with db.connection() as conn:
                cur = await conn.execute("SELECT COUNT(*) FROM jobs WHERE chat_id = ?", (CHAT_ID,))
                row = await cur.fetchone()
                return row[0]

        assert asyncio.run(_count_jobs()) == 1

    def test_different_idempotency_keys_are_independent(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        first = asyncio.run(
            router.handle(
                _msg(url="https://youtube.com/shorts/vidA", idempotency_key="idem-a")
            )
        )
        second = asyncio.run(
            router.handle(
                _msg(url="https://youtube.com/shorts/vidB", idempotency_key="idem-b")
            )
        )
        assert first.job_id != second.job_id

    def test_retryable_response_is_never_cached(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A retryable response is a signal to try again — caching it under the
        # caller's idempotency key would make every retry replay the same
        # failure forever instead of actually re-attempting the operation.
        from src.intake.models import IntakeResponse

        call_count = 0

        async def _fake_route(_msg: IntakeMessage) -> IntakeResponse:
            nonlocal call_count
            call_count += 1
            return IntakeResponse(kind="error", text="boom", retryable=True)

        monkeypatch.setattr(router, "_route", _fake_route)

        asyncio.run(router.handle(_msg(url="https://x", idempotency_key="idem-retry")))
        asyncio.run(router.handle(_msg(url="https://x", idempotency_key="idem-retry")))

        assert call_count == 2

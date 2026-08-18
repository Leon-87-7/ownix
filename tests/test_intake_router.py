"""Tests for the channel-neutral intake router (`src/intake/router.py`).

Covers `IntakeMessage -> IntakeResponse` for URL / unsupported / command-looking
input, schema_version rejection, and idempotent replay (issue #473).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

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

    def test_document_pdf_url_uses_shared_document_intake(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_create(chat_id, url, *, require_document_path=True):
            assert (chat_id, url, require_document_path) == (
                CHAT_ID, "https://example.com/file.pdf", True
            )
            return {"job_id": "document_abcd"}

        monkeypatch.setattr("src.services.document_intake.create_remote_document_job", fake_create)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/file.pdf")))
        assert resp.kind == "job_created"
        assert resp.job_id == "document_abcd"

    def test_detected_pipeline_precedes_explicit_link_intent(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(
            url="https://youtube.com/watch?v=precedence", intent="link"
        )))
        job = asyncio.run(db.get_job(resp.job_id))
        assert job["content_type"] == "long"

    @pytest.mark.parametrize("intent", ["automatic", "article", "link", "document", "capture"])
    @pytest.mark.parametrize(
        ("url", "expected_type", "allow_domain"),
        [
            ("https://youtube.com/watch?v=precedence", "long", None),
            ("https://github.com/Leon-87-7/ownix", "repo", None),
            ("https://news.example.com/story", "article", "news.example.com"),
        ],
    )
    def test_every_detected_pipeline_precedes_every_fallback_intent(
        self, db, monkeypatch, intent, url, expected_type, allow_domain
    ) -> None:
        _enqueue_noop(monkeypatch)
        if allow_domain:
            asyncio.run(db.add_allowed_domain(CHAT_ID, allow_domain))

        resp = asyncio.run(router.handle(_msg(url=url, intent=intent)))

        assert asyncio.run(db.get_job(resp.job_id))["content_type"] == expected_type

    @pytest.mark.parametrize("intent", ["automatic", "article", "link", "document", "capture"])
    def test_detected_document_precedes_every_fallback_intent(
        self, db, monkeypatch, intent
    ) -> None:
        create = AsyncMock(return_value={
            "job_id": "document_abcd",
            "content_type": "document",
            "_deduped": False,
        })
        monkeypatch.setattr(
            "src.services.document_intake.create_remote_document_job", create
        )

        resp = asyncio.run(router.handle(_msg(
            url="https://example.com/file.pdf", intent=intent
        )))

        assert resp.job_id == "document_abcd"
        create.assert_awaited_once_with(
            CHAT_ID, "https://example.com/file.pdf", require_document_path=True
        )

    def test_article_fallback_persists_exact_hostname(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(
            url="https://News.Example.com/story", intent="article"
        )))
        assert resp.kind == "job_created"
        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == {"news.example.com"}

    def test_article_permission_survives_enqueue_failure(self, db, monkeypatch) -> None:
        async def fail_enqueue(_payload: dict) -> None:
            raise RuntimeError("queue unavailable")

        monkeypatch.setattr("src.services.jobs.queue.enqueue", fail_enqueue)

        with pytest.raises(RuntimeError, match="queue unavailable"):
            asyncio.run(router.handle(_msg(
                url="https://News.Example.com/story", intent="article"
            )))

        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == {"news.example.com"}

    def test_automatic_rejection_has_no_side_effects(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)

        resp = asyncio.run(router.handle(_msg(url="https://example.com/unsupported")))

        assert resp.kind == "unsupported"
        assert asyncio.run(db.list_allowed_domains(CHAT_ID)) == set()
        assert asyncio.run(db.find_recent_job_by_url(CHAT_ID, "https://example.com/unsupported")) is None

    def test_link_fallback_creates_link_job(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/item", intent="link")))
        assert asyncio.run(db.get_job(resp.job_id))["content_type"] == "link"

    def test_link_fallback_rejects_url_without_hostname(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https:missing-host", intent="link")))
        assert resp.kind == "unsupported"
        assert resp.job_id is None

    def test_capture_fallback_creates_link_job(self, db, monkeypatch) -> None:
        """ADR-0051: the extension's Ctrl+Shift+1 trigger (intent='capture')
        gets the same link-pipeline fallback as an explicit 'link' intent, so
        an ordinary bookmarked page doesn't silently vanish."""
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/item", intent="capture")))
        assert asyncio.run(db.get_job(resp.job_id))["content_type"] == "link"

    def test_capture_fallback_rejects_url_without_hostname(self, db, monkeypatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https:missing-host", intent="capture")))
        assert resp.kind == "unsupported"
        assert resp.job_id is None

    def test_automatic_intent_does_not_get_the_capture_fallback(self, db, monkeypatch) -> None:
        """ADR-0051: 'capture' is deliberately distinct from the contract's
        default 'automatic' intent, which every plain Telegram/dashboard
        paste also carries — this pins that the fallback stays scoped to the
        extension's explicit trigger and doesn't leak into the default."""
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/item", intent="automatic")))
        assert resp.kind == "unsupported"
        assert resp.job_id is None

    def test_explicit_document_allows_extensionless_https(self, db, monkeypatch) -> None:
        async def fake_create(chat_id, url, *, require_document_path=True):
            assert require_document_path is False
            return {"job_id": "document_1234"}
        monkeypatch.setattr("src.services.document_intake.create_remote_document_job", fake_create)
        resp = asyncio.run(router.handle(_msg(url="https://example.com/download", intent="document")))
        assert resp.job_id == "document_1234"

    @pytest.mark.parametrize(
        ("first_intent", "second_intent"),
        [("document", "link"), ("link", "document")],
    )
    def test_url_deduplication_is_authoritative_across_intents(
        self, db, monkeypatch, first_intent, second_intent
    ) -> None:
        url = "https://example.com/download"
        _enqueue_noop(monkeypatch)
        monkeypatch.setattr(
            "src.services.document_intake.fetch_remote_document",
            AsyncMock(return_value=(b"%PDF-1.4 small", "document", "pdf")),
        )
        monkeypatch.setattr("src.services.document_intake.storage.upload", AsyncMock())

        first = asyncio.run(router.handle(_msg(url=url, intent=first_intent)))
        second = asyncio.run(router.handle(_msg(url=url, intent=second_intent)))

        assert second.job_id == first.job_id
        assert second.kind == "job_deduped"


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
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/tag3 #read_later")))
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


class TestUnknownTagOffer:
    """An unknown `#tag` returns a create offer, never blocks the job (#489)."""

    def test_unknown_tag_returns_a_create_tag_action(
        self, db, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/off1 #GoTo")))
        assert resp.kind == "job_created"
        assert [a.kind for a in resp.actions] == ["create_tag"]
        assert resp.actions[0].payload["tag_name"] == "GoTo"
        assert resp.actions[0].job_id == resp.job_id

    def test_known_tag_produces_no_offer(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        asyncio.run(db.create_tag(chat_id=CHAT_ID, name="GoTo", meaning="", color="#4ade80"))
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/off2 #GoTo")))
        assert resp.actions == []

    def test_two_unknown_tags_offer_one_each(self, db, monkeypatch: pytest.MonkeyPatch) -> None:
        _enqueue_noop(monkeypatch)
        resp = asyncio.run(router.handle(_msg(text="https://youtube.com/shorts/off3 #GoTo #Foo")))
        assert [a.payload["tag_name"] for a in resp.actions] == ["GoTo", "Foo"]
        # Distinct ids, so the console can track which offer is open.
        assert len({a.action_id for a in resp.actions}) == 2

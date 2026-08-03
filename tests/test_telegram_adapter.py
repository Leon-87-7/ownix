"""Tests for the Telegram <-> IntakeMessage/IntakeResponse adapter (issue #477).

Covers both conversion directions: a Telegram update into an IntakeMessage,
and an IntakeResponse rendered back out as a Telegram send.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.channels.telegram import adapter
from src.intake.models import IntakeResponse


class TestUpdateToIntakeMessage:
    def test_plain_text_message_converts(self) -> None:
        update = {
            "update_id": 123456,
            "message": {
                "message_id": 42,
                "chat": {"id": 999},
                "text": " https://youtube.com/shorts/abc123 ",
            },
        }
        msg = adapter.update_to_intake_message(update)
        assert msg is not None
        assert msg.actor.legacy_chat_id == 999
        assert msg.actor.channel_type == "telegram"
        assert msg.text == "https://youtube.com/shorts/abc123"
        assert msg.idempotency_key == "telegram:123456"
        assert msg.source_message_id == 42

    def test_missing_update_id_omits_idempotency_key(self) -> None:
        update = {"message": {"chat": {"id": 1}, "text": "/help"}}
        msg = adapter.update_to_intake_message(update)
        assert msg is not None
        assert msg.idempotency_key is None

    def test_non_message_update_returns_none(self) -> None:
        update = {"callback_query": {"id": "cb1", "data": "template_pick:summary:J1"}}
        assert adapter.update_to_intake_message(update) is None

    def test_message_without_text_returns_none(self) -> None:
        update = {"update_id": 1, "message": {"chat": {"id": 1}, "photo": []}}
        assert adapter.update_to_intake_message(update) is None

    def test_repeat_update_id_yields_same_idempotency_key(self) -> None:
        update = {"update_id": 55, "message": {"chat": {"id": 1}, "text": "/help"}}
        first = adapter.update_to_intake_message(update)
        second = adapter.update_to_intake_message(update)
        assert first is not None and second is not None
        assert first.idempotency_key == second.idempotency_key == "telegram:55"


class TestRenderResponse:
    def test_renders_text_via_send_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_send = AsyncMock()
        monkeypatch.setattr(adapter, "send_message", mock_send)

        response = IntakeResponse(kind="job_created", text="Received — job_abcd.", job_id="j1")
        asyncio.run(adapter.render_response(42, response))

        mock_send.assert_awaited_once_with(42, "Received — job_abcd.")

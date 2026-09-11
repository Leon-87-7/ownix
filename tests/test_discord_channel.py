"""Unit tests for the offline-testable Discord DM handler."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

discord = pytest.importorskip("discord")

from src.channels.discord import gateway  # noqa: E402
from src.intake.models import IntakeResponse  # noqa: E402


def message(*, content="hello", sender=42):
    return SimpleNamespace(
        id=99,
        author=SimpleNamespace(id=sender, bot=False),
        guild=None,
        content=content,
        channel=SimpleNamespace(send=AsyncMock()),
    )


def test_client_requests_dm_intents_only():
    client = gateway.build_client()
    assert client.intents.dm_messages is True
    assert client.intents.guild_messages is False
    assert client.intents.message_content is False


@pytest.mark.asyncio
async def test_unpaired_dm_only_returns_instructions(monkeypatch):
    event = message()
    monkeypatch.setattr(gateway.database, "get_identity_owner", AsyncMock(return_value=None))
    monkeypatch.setattr(gateway.session_store, "redeem_discord_pairing", AsyncMock(return_value=None))
    link = AsyncMock()
    monkeypatch.setattr(gateway.database, "link_identity", link)
    await gateway.handle_message(event)
    event.channel.send.assert_awaited_once()
    link.assert_not_awaited()


@pytest.mark.asyncio
async def test_pairing_code_links_existing_owner(monkeypatch):
    event = message(content="pair one-time-code")
    monkeypatch.setattr(gateway.database, "get_identity_owner", AsyncMock(return_value=None))
    monkeypatch.setattr(gateway.session_store, "redeem_discord_pairing", AsyncMock(return_value=7))
    link = AsyncMock(return_value=7)
    monkeypatch.setattr(gateway.database, "link_identity", link)
    await gateway.handle_message(event)
    link.assert_awaited_once_with("discord", "42", 7, verified=True)


@pytest.mark.asyncio
async def test_paired_dm_routes_through_shared_intake(monkeypatch):
    event = message(content="https://example.com")
    monkeypatch.setattr(gateway.database, "get_identity_owner", AsyncMock(return_value=-12))
    monkeypatch.setattr(gateway.session_store, "redeem_discord_pairing", AsyncMock(return_value=None))
    handle = AsyncMock(return_value=IntakeResponse(kind="accepted", text="Saved"))
    monkeypatch.setattr(gateway.router, "handle", handle)
    await gateway.handle_message(event)
    intake = handle.await_args.args[0]
    assert intake.actor.model_dump() == {
        "user_id": -12,
        "channel_id": "discord:42",
        "channel_type": "discord",
        "legacy_chat_id": -12,
    }
    assert intake.text == "https://example.com"
    event.channel.send.assert_awaited_once_with("Saved")

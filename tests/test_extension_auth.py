"""Tests for extension pairing + bearer-token auth (issue #479).

Covers `src/auth/extension_tokens.py`: pairing-code single-use/expiry,
hash-only storage (the raw token is never persisted), token resolution, and
revocation taking effect immediately.
"""

from __future__ import annotations

import asyncio
import hashlib

import pytest

CHAT_ID = 4444


@pytest.fixture(autouse=True)
def _memory_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    from src.auth import session as session_store

    session_store._memory.clear()
    yield
    session_store._memory.clear()


class TestPairingCode:
    def test_redeems_to_chat_id(self) -> None:
        from src.auth import extension_tokens

        code = asyncio.run(extension_tokens.mint_pairing_code(CHAT_ID))
        assert asyncio.run(extension_tokens.redeem_pairing_code(code)) == CHAT_ID

    def test_is_single_use(self) -> None:
        from src.auth import extension_tokens

        code = asyncio.run(extension_tokens.mint_pairing_code(CHAT_ID))
        assert asyncio.run(extension_tokens.redeem_pairing_code(code)) == CHAT_ID
        assert asyncio.run(extension_tokens.redeem_pairing_code(code)) is None

    def test_expired_code_does_not_redeem(self) -> None:
        from src.auth import extension_tokens

        code = asyncio.run(extension_tokens.mint_pairing_code(CHAT_ID, ttl=-1))
        assert asyncio.run(extension_tokens.redeem_pairing_code(code)) is None

    def test_unknown_code_returns_none(self) -> None:
        from src.auth import extension_tokens

        assert asyncio.run(extension_tokens.redeem_pairing_code("not-a-real-code")) is None


class TestExtensionToken:
    def test_only_hash_is_ever_stored(self) -> None:
        from src.auth import extension_tokens
        from src.auth import session as session_store

        raw_token = asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        stored_keys = list(session_store._memory.keys())
        stored_values = [v for v, _exp in session_store._memory.values()]
        assert any(expected_hash in key for key in stored_keys)
        assert not any(raw_token in key for key in stored_keys)
        assert not any(raw_token in value for value in stored_values)

    def test_resolve_valid_token_returns_chat_id(self) -> None:
        from src.auth import extension_tokens

        raw_token = asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        assert asyncio.run(extension_tokens.resolve_extension_token(raw_token)) == CHAT_ID

    def test_resolve_unknown_token_returns_none(self) -> None:
        from src.auth import extension_tokens

        assert asyncio.run(extension_tokens.resolve_extension_token("garbage-token")) is None

    def test_resolve_updates_last_used_at(self) -> None:
        from src.auth import extension_tokens

        raw_token = asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        before = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID))[0]
        assert before["last_used_at"] is None

        asyncio.run(extension_tokens.resolve_extension_token(raw_token))
        after = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID))[0]
        assert after["last_used_at"] is not None

    def test_list_scoped_to_chat_id(self) -> None:
        from src.auth import extension_tokens

        asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        asyncio.run(extension_tokens.issue_extension_token(CHAT_ID + 1))

        tokens_a = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID))
        tokens_b = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID + 1))
        assert len(tokens_a) == 1
        assert len(tokens_b) == 1

    def test_revoke_takes_effect_immediately(self) -> None:
        from src.auth import extension_tokens

        raw_token = asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        token_id = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID))[0]["id"]

        assert asyncio.run(extension_tokens.revoke_extension_token(CHAT_ID, token_id)) is True
        assert asyncio.run(extension_tokens.resolve_extension_token(raw_token)) is None
        assert asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID)) == []

    def test_revoke_rejects_foreign_chat_id(self) -> None:
        from src.auth import extension_tokens

        asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
        token_id = asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID))[0]["id"]

        assert asyncio.run(extension_tokens.revoke_extension_token(CHAT_ID + 999, token_id)) is False
        # Still resolvable — a foreign revoke attempt must not have deleted it.
        assert asyncio.run(extension_tokens.list_extension_tokens(CHAT_ID)) != []

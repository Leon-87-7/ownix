from __future__ import annotations

import hashlib
import time

import pytest

from src.auth import mcp_tokens
from src.auth import session as session_store

CHAT_ID = 7632


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    session_store._memory.clear()
    yield
    session_store._memory.clear()


@pytest.mark.asyncio
async def test_mint_redeem_issue_resolve_and_revoke() -> None:
    code = await mcp_tokens.mint_pairing_code(CHAT_ID)
    assert await mcp_tokens.redeem_pairing_code(code) == CHAT_ID
    assert await mcp_tokens.redeem_pairing_code(code) is None

    raw = await mcp_tokens.issue_mcp_token(CHAT_ID)
    token_id = hashlib.sha256(raw.encode()).hexdigest()
    values = [value for value, _expiry in session_store._memory.values()]
    assert raw not in "".join(session_store._memory)
    assert raw not in "".join(values)
    assert await mcp_tokens.resolve_mcp_token(raw) == CHAT_ID

    assert await mcp_tokens.revoke_mcp_token(CHAT_ID + 1, token_id) is False
    assert await mcp_tokens.revoke_mcp_token(CHAT_ID, token_id) is True
    assert await mcp_tokens.resolve_mcp_token(raw) is None


@pytest.mark.asyncio
async def test_list_is_tenant_scoped() -> None:
    await mcp_tokens.issue_mcp_token(CHAT_ID)
    await mcp_tokens.issue_mcp_token(CHAT_ID + 1)
    assert len(await mcp_tokens.list_mcp_tokens(CHAT_ID)) == 1
    foreign_id = (await mcp_tokens.list_mcp_tokens(CHAT_ID + 1))[0]["id"]
    assert await mcp_tokens.revoke_mcp_token(CHAT_ID, foreign_id) is False


@pytest.mark.asyncio
async def test_kv_set_if_exists_treats_expired_memory_key_as_absent() -> None:
    # Physically present but lazily-expired — only a _memory_get-style read
    # evicts it. A raw `key in _memory` check would wrongly resurrect it.
    session_store._memory["k"] = ("old", time.monotonic() - 1)
    await session_store.kv_set_if_exists("k", "new")
    assert await session_store.kv_get("k") is None

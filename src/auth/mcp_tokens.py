"""MCP pairing + bearer-token auth (issue #632).

Thin namespaced wrapper over `src.auth.bearer_token_store.BearerTokenStore` —
see that module for the token scheme itself, shared with `src.auth.extension_tokens`.
"""

from __future__ import annotations

from typing import Any

from src.auth.bearer_token_store import BearerTokenStore

PAIRING_TTL_SECONDS = 300

_store = BearerTokenStore("mcp", pairing_ttl=PAIRING_TTL_SECONDS)


async def mint_pairing_code(chat_id: int, ttl: int = PAIRING_TTL_SECONDS) -> str:
    return await _store.mint_pairing_code(chat_id, ttl)


async def redeem_pairing_code(code: str) -> int | None:
    return await _store.redeem_pairing_code(code)


async def issue_mcp_token(chat_id: int, *, label: str | None = None) -> str:
    return await _store.issue_token(chat_id, label=label)


async def resolve_mcp_token(raw_token: str) -> int | None:
    return await _store.resolve_token(raw_token)


async def list_mcp_tokens(chat_id: int) -> list[dict[str, Any]]:
    return await _store.list_tokens(chat_id)


async def revoke_mcp_token(chat_id: int, token_id: str) -> bool:
    return await _store.revoke_token(chat_id, token_id)

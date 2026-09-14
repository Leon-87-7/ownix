"""Namespaced pairing-code + hashed-bearer-token scheme.

Backs both `src.auth.extension_tokens` and `src.auth.mcp_tokens` — they were
independent, byte-identical copies of this logic before this module existed
(same pairing-code convention, same token/index key shapes, same touch
throttle), which meant a fix to one (e.g. `_touch_metadata`'s
concurrent-revoke guard) had to be remembered and re-applied to the other.
One `BearerTokenStore` instance per namespace now backs both.

The pairing code mirrors `src.auth.session`'s `_mint_token`/`_redeem_token`
single-use-TTL convention exactly (same helpers, a new key prefix) — do not
invent a new token scheme. The long-lived bearer token itself is
deliberately NOT single-use/TTL'd (it must keep working until revoked); only
its SHA-256 hash is ever stored, and the raw token is generated, returned
once at issue time, and never persisted or logged again.

Token metadata lives in Redis via `src.auth.session`'s existing dual
Redis/memory backend (reusing its private `_client`/`_use_memory`/`_memory`
helpers, the same way other modules in this codebase reach into
`queue._client()` directly) rather than standing up a third parallel store.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from src.auth import session as session_store

DEFAULT_PAIRING_TTL_SECONDS = 300
_TOUCH_THROTTLE_SECONDS = 60


class BearerTokenStore:
    """One namespace's pairing codes + long-lived bearer tokens.

    `namespace` becomes the Redis key prefix (`{namespace}_pairing:`,
    `{namespace}_token:`, `{namespace}_tokens_by_chat:`) — built from a
    segment rather than a bare string literal on a variable named "token":
    Codacy's "possible hardcoded password" heuristic flags that shape
    regardless of inline suppression comments; these are Redis key
    namespaces, not credentials.
    """

    def __init__(self, namespace: str, pairing_ttl: int = DEFAULT_PAIRING_TTL_SECONDS):
        self.pairing_ttl = pairing_ttl
        self._pairing_prefix = f"{namespace}_pairing:"
        self._token_prefix = f"{namespace}_token:"
        self._token_index_prefix = f"{namespace}_tokens_by_chat:"

    @staticmethod
    def _hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    async def mint_pairing_code(self, chat_id: int, ttl: int | None = None) -> str:
        """Single-use, short-TTL pairing code that redeems to chat_id."""
        return await session_store._mint_token(
            self._pairing_prefix, str(chat_id), ttl if ttl is not None else self.pairing_ttl
        )

    async def redeem_pairing_code(self, code: str) -> int | None:
        """Atomically fetch-and-delete the chat id for a pairing code (single-use)."""
        value = await session_store._redeem_token(self._pairing_prefix, code)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def _store_metadata(self, token_hash: str, metadata: dict[str, Any]) -> None:
        key = f"{self._token_prefix}{token_hash}"
        raw = json.dumps(metadata)
        if session_store._use_memory():
            session_store._memory_set(key, raw)
        else:
            await session_store._client().set(key, raw)

    async def _get_metadata(self, token_hash: str) -> dict[str, Any] | None:
        key = f"{self._token_prefix}{token_hash}"
        raw = (
            session_store._memory_get(key)
            if session_store._use_memory()
            else await session_store._client().get(key)
        )
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def _touch_metadata(self, token_hash: str, metadata: dict[str, Any]) -> None:
        """Write metadata back only if the key still exists.

        Guards against a concurrent revoke resurrecting a just-deleted token: if
        `revoke_token` runs between `resolve_token`'s read and this write, the
        key must stay gone rather than being recreated here.
        """
        key = f"{self._token_prefix}{token_hash}"
        raw = json.dumps(metadata)
        if session_store._use_memory():
            if key in session_store._memory:
                session_store._memory_set(key, raw)
        else:
            await session_store._client().set(key, raw, xx=True)

    async def _delete_metadata(self, token_hash: str) -> None:
        key = f"{self._token_prefix}{token_hash}"
        if session_store._use_memory():
            session_store._memory.pop(key, None)
        else:
            await session_store._client().delete(key)

    async def _index_add(self, chat_id: int, token_hash: str) -> None:
        key = f"{self._token_index_prefix}{chat_id}"
        if session_store._use_memory():
            raw = session_store._memory_get(key)
            hashes = json.loads(raw) if raw else []
            if token_hash not in hashes:
                hashes.append(token_hash)
            session_store._memory_set(key, json.dumps(hashes))
        else:
            await session_store._client().sadd(key, token_hash)

    async def _index_remove(self, chat_id: int, token_hash: str) -> None:
        key = f"{self._token_index_prefix}{chat_id}"
        if session_store._use_memory():
            raw = session_store._memory_get(key)
            hashes = json.loads(raw) if raw else []
            if token_hash in hashes:
                hashes.remove(token_hash)
                session_store._memory_set(key, json.dumps(hashes))
        else:
            await session_store._client().srem(key, token_hash)

    async def _index_members(self, chat_id: int) -> list[str]:
        key = f"{self._token_index_prefix}{chat_id}"
        if session_store._use_memory():
            raw = session_store._memory_get(key)
            return json.loads(raw) if raw else []
        members = await session_store._client().smembers(key)
        return list(members)

    async def issue_token(self, chat_id: int, *, label: str | None = None) -> str:
        """Mint a new bearer token for chat_id. Returns the RAW token — the only
        time it is ever available; only its hash is stored."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)
        await self._store_metadata(
            token_hash,
            {
                "chat_id": chat_id,
                "created_at": time.time(),
                "last_used_at": None,
                "label": label,
            },
        )
        await self._index_add(chat_id, token_hash)
        return raw_token

    async def resolve_token(self, raw_token: str) -> int | None:
        """Return the owning chat_id for a bearer token, or None if unknown/revoked.

        Revocation takes effect immediately: this looks up live store state on
        every call, there is no cached/TTL'd positive result.
        """
        token_hash = self._hash_token(raw_token)
        metadata = await self._get_metadata(token_hash)
        if metadata is None:
            return None
        chat_id = int(metadata["chat_id"])
        last_used = metadata.get("last_used_at")
        # Throttle the write — every authenticated request otherwise costs a
        # store round-trip just to bump a timestamp nobody reads that often.
        if last_used is None or time.time() - float(last_used) > _TOUCH_THROTTLE_SECONDS:
            metadata["last_used_at"] = time.time()
            await self._touch_metadata(token_hash, metadata)
        return chat_id

    async def list_tokens(self, chat_id: int) -> list[dict[str, Any]]:
        """List active tokens for chat_id. `id` is the token hash — safe to expose
        (irreversible) and is what `revoke_token` expects back."""
        tokens = []
        for token_hash in await self._index_members(chat_id):
            metadata = await self._get_metadata(token_hash)
            if metadata is None:
                continue
            tokens.append(
                {
                    "id": token_hash,
                    "created_at": metadata["created_at"],
                    "last_used_at": metadata["last_used_at"],
                    "label": metadata.get("label"),
                }
            )
        return tokens

    async def revoke_token(self, chat_id: int, token_id: str) -> bool:
        metadata = await self._get_metadata(token_id)
        if metadata is None or int(metadata["chat_id"]) != chat_id:
            return False
        await self._delete_metadata(token_id)
        await self._index_remove(chat_id, token_id)
        return True

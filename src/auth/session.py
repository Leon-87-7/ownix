"""Opaque session store (ADR-0016 — Redis in production, memory for local dev)."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

import redis.asyncio as redis

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SESSION_PREFIX = "session:"
_TTL_SECONDS = 30 * 24 * 3600  # 30 days

_HANDOFF_PREFIX = "connect_handoff:"
_HANDOFF_TTL_SECONDS = 60

_DASHBOARD_HANDOFF_PREFIX = "dashboard_handoff:"

# Per-account index of minted session ids, so account deletion can invalidate
# every device's session (not just the one that triggered deletion) — closes
# the window where a stale second-device session could resurrect a just-deleted
# account via a pre-approval route like PUT /api/auth/email.
_ACCOUNT_SESSIONS_PREFIX = "account_sessions:"

_redis: redis.Redis | None = None
_memory: dict[str, tuple[str, float | None]] = {}
# ponytail: memory backend is local-dev only (Redis backs prod) — no TTL on
# this index, since dev processes restart often enough that unbounded growth
# never matters in practice.
_memory_account_sessions: dict[int, set[str]] = {}


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _use_memory() -> bool:
    return settings.SESSION_BACKEND.lower() == "memory"


def _memory_set(key: str, value: str, *, ex: int | None = None) -> None:
    expires_at = time.monotonic() + ex if ex is not None else None
    _memory[key] = (value, expires_at)


def _memory_get(key: str) -> str | None:
    item = _memory.get(key)
    if item is None:
        return None
    value, expires_at = item
    if expires_at is not None and time.monotonic() >= expires_at:
        _memory.pop(key, None)
        return None
    return value


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
    _memory.clear()


async def mint(user: dict[str, Any]) -> str:
    """Create a new session for user and return the opaque session_id."""
    session_id = secrets.token_urlsafe(32)
    key = f"{_SESSION_PREFIX}{session_id}"
    tg_id = user.get("id")
    if _use_memory():
        _memory_set(key, json.dumps(user), ex=_TTL_SECONDS)
        if tg_id is not None:
            _memory_account_sessions.setdefault(int(tg_id), set()).add(session_id)
    else:
        client = _client()
        await client.set(key, json.dumps(user), ex=_TTL_SECONDS)
        if tg_id is not None:
            index_key = f"{_ACCOUNT_SESSIONS_PREFIX}{tg_id}"
            await client.sadd(index_key, session_id)
            await client.expire(index_key, _TTL_SECONDS)
    log.info("session_minted", tg_id=tg_id)
    return session_id


async def resolve(session_id: str) -> dict[str, Any] | None:
    """Return the user dict for session_id, or None if missing / corrupt."""
    key = f"{_SESSION_PREFIX}{session_id}"
    raw = _memory_get(key) if _use_memory() else await _client().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.error("session_decode_error", session_id=session_id[:8])
        return None


async def revoke(session_id: str) -> None:
    """Delete the session key immediately (one Redis DEL)."""
    key = f"{_SESSION_PREFIX}{session_id}"
    if _use_memory():
        _memory.pop(key, None)
    else:
        await _client().delete(key)
    log.info("session_revoked")


async def revoke_account(tg_id: int) -> None:
    """Revoke every session ever minted for tg_id, across all devices.

    Used by account deletion: revoking only the triggering session leaves a
    stale-but-valid session on another device able to reach pre-approval
    routes (e.g. PUT /api/auth/email) and re-create the just-deleted account.
    """
    if _use_memory():
        session_ids = _memory_account_sessions.pop(int(tg_id), set())
        for session_id in session_ids:
            _memory.pop(f"{_SESSION_PREFIX}{session_id}", None)
    else:
        client = _client()
        index_key = f"{_ACCOUNT_SESSIONS_PREFIX}{tg_id}"
        session_ids = await client.smembers(index_key)
        if session_ids:
            await client.delete(*(f"{_SESSION_PREFIX}{sid}" for sid in session_ids))
        await client.delete(index_key)
    log.info("account_sessions_revoked", tg_id=tg_id)


async def _mint_token(prefix: str, value: str, ttl: int) -> str:
    token = secrets.token_urlsafe(24)
    key = f"{prefix}{token}"
    if _use_memory():
        _memory_set(key, value, ex=ttl)
    else:
        await _client().set(key, value, ex=ttl)
    return token


async def _redeem_token(prefix: str, token: str) -> str | None:
    """Atomically fetch-and-delete the value for a token.

    Uses GETDEL (single round trip) rather than GET+DELETE so a concurrent retry
    within the TTL can't redeem the same token twice.
    """
    key = f"{prefix}{token}"
    if _use_memory():
        value = _memory_get(key)
        _memory.pop(key, None)
        return value
    return await _client().getdel(key)


async def mint_handoff(session_id: str, ttl: int = _HANDOFF_TTL_SECONDS) -> str:
    """Create a short-lived, single-use token that redeems to session_id.

    Used when a session must cross into a context with no cookie access — Mini App
    openLink hands off to the system browser, a separate cookie jar. Putting the real
    session id in that URL would leak a long-lived, reusable credential via browser
    history and server access logs; this token is single-use and expires after `ttl`
    seconds (default 60s; job dashboard links use a longer ttl since they can sit
    unread in chat history).
    """
    return await _mint_token(_HANDOFF_PREFIX, session_id, ttl)


async def redeem_handoff(token: str) -> str | None:
    """Atomically fetch-and-delete the session id for a handoff token."""
    return await _redeem_token(_HANDOFF_PREFIX, token)


async def mint_dashboard_handoff(chat_id: int, ttl: int) -> str:
    """Create a single-use dashboard handoff token for a Telegram chat id."""
    return await _mint_token(_DASHBOARD_HANDOFF_PREFIX, str(chat_id), ttl)


async def redeem_dashboard_handoff(token: str) -> int | None:
    """Atomically fetch-and-delete the chat id for a dashboard handoff token."""
    value = await _redeem_token(_DASHBOARD_HANDOFF_PREFIX, token)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        log.error("dashboard_handoff_decode_error")
        return None

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

_redis: redis.Redis | None = None
_memory: dict[str, tuple[str, float | None]] = {}


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
    if _use_memory():
        _memory_set(key, json.dumps(user), ex=_TTL_SECONDS)
    else:
        await _client().set(key, json.dumps(user), ex=_TTL_SECONDS)
    log.info("session_minted", tg_id=user.get("id"))
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


async def mint_handoff(session_id: str) -> str:
    """Create a short-lived, single-use token that redeems to session_id.

    Used when a session must cross into a context with no cookie access — Mini App
    openLink hands off to the system browser, a separate cookie jar. Putting the real
    session id in that URL would leak a long-lived, reusable credential via browser
    history and server access logs; this token is single-use and expires in 60s.
    """
    token = secrets.token_urlsafe(24)
    key = f"{_HANDOFF_PREFIX}{token}"
    if _use_memory():
        _memory_set(key, session_id, ex=_HANDOFF_TTL_SECONDS)
    else:
        await _client().set(key, session_id, ex=_HANDOFF_TTL_SECONDS)
    return token


async def redeem_handoff(token: str) -> str | None:
    """Atomically fetch-and-delete the session id for a handoff token.

    Uses GETDEL (single round trip) rather than GET+DELETE so a concurrent retry
    within the 60s TTL can't redeem the same token twice.
    """
    key = f"{_HANDOFF_PREFIX}{token}"
    if _use_memory():
        value = _memory_get(key)
        _memory.pop(key, None)
        return value
    return await _client().getdel(key)

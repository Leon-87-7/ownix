"""Redis-backed opaque session store (ADR-0016 — no JWT)."""

from __future__ import annotations

import json
import secrets
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


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


async def mint(user: dict[str, Any]) -> str:
    """Create a new session for user and return the opaque session_id."""
    session_id = secrets.token_urlsafe(32)
    key = f"{_SESSION_PREFIX}{session_id}"
    await _client().set(key, json.dumps(user), ex=_TTL_SECONDS)
    log.info("session_minted", tg_id=user.get("id"))
    return session_id


async def resolve(session_id: str) -> dict[str, Any] | None:
    """Return the user dict for session_id, or None if missing / corrupt."""
    raw = await _client().get(f"{_SESSION_PREFIX}{session_id}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.error("session_decode_error", session_id=session_id[:8])
        return None


async def revoke(session_id: str) -> None:
    """Delete the session key immediately (one Redis DEL)."""
    await _client().delete(f"{_SESSION_PREFIX}{session_id}")
    log.info("session_revoked")


async def mint_handoff(session_id: str) -> str:
    """Create a short-lived, single-use token that redeems to session_id.

    Used when a session must cross into a context with no cookie access — Mini App
    openLink hands off to the system browser, a separate cookie jar. Putting the real
    session id in that URL would leak a long-lived, reusable credential via browser
    history and server access logs; this token is single-use and expires in 60s.
    """
    token = secrets.token_urlsafe(24)
    await _client().set(f"{_HANDOFF_PREFIX}{token}", session_id, ex=_HANDOFF_TTL_SECONDS)
    return token


async def redeem_handoff(token: str) -> str | None:
    """Fetch and immediately delete the session id for a handoff token."""
    key = f"{_HANDOFF_PREFIX}{token}"
    session_id = await _client().get(key)
    if session_id is not None:
        await _client().delete(key)
    return session_id

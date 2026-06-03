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

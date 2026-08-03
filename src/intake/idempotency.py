"""Idempotency-key store for the intake contract.

A repeat submit with the same (actor, idempotency_key) inside the TTL window
must return the exact original `IntakeResponse`, never create a second job —
this is the retry contract every at-least-once channel (webhook redelivery,
extension retry, share re-fire) depends on. Deliberately not single-use (see
`src.auth.session`'s `_mint_token`/`_redeem_token`, which IS single-use) —
retries need to read the same cached value repeatedly within the window.

Mirrors `src.auth.session`'s dual Redis/memory backend rather than importing
it directly: session tokens are single-use handoffs, this is a repeatable
cache, and the two shouldn't share a key namespace or eviction semantics.
"""

from __future__ import annotations

import json
import time
from typing import Any

import redis.asyncio as redis

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_PREFIX = "intake_idem:"
_TTL_SECONDS = 24 * 3600

_redis: redis.Redis | None = None
_memory: dict[str, tuple[str, float | None]] = {}


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _use_memory() -> bool:
    return settings.SESSION_BACKEND.lower() == "memory"


def _key(actor_key: str, idempotency_key: str) -> str:
    return f"{_PREFIX}{actor_key}:{idempotency_key}"


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
    _memory.clear()


async def get_cached(actor_key: str, idempotency_key: str) -> dict[str, Any] | None:
    key = _key(actor_key, idempotency_key)
    if _use_memory():
        item = _memory.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.monotonic() >= expires_at:
            _memory.pop(key, None)
            return None
        raw: str | None = value
    else:
        try:
            raw = await _client().get(key)
        except redis.RedisError:
            # A transient Redis outage must degrade to "cache miss", not fail
            # the request — the caller's own create_and_enqueue_job dedup is
            # the fallback safety net, not this cache.
            log.warning("idempotency_get_failed", key=key)
            return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def store(actor_key: str, idempotency_key: str, response: dict[str, Any]) -> None:
    key = _key(actor_key, idempotency_key)
    raw = json.dumps(response)
    if _use_memory():
        _memory[key] = (raw, time.monotonic() + _TTL_SECONDS)
    else:
        try:
            await _client().set(key, raw, ex=_TTL_SECONDS)
        except redis.RedisError:
            # Best-effort: the job was already created by the time we get
            # here (see router.handle), so a failed cache write just means
            # the next retry within the window creates a second job instead
            # of replaying this one — worse than losing this write is
            # raising and 500ing on an otherwise-successful request.
            log.warning("idempotency_store_failed", key=key)

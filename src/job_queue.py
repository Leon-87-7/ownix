"""Redis-backed task queue.

Every item on the `video_jobs` list is a JSON-encoded dict with at minimum:
    {"task": <discriminator>, "job_id": <id>}

Discriminators currently in use:
    {"task": "video",       "job_id": "..."}                              # slice #1/#2/#3
    {"task": "enrichment",  "job_id": "..."}                              # slice #4
    {"task": "prd_auto",    "job_id": "..."}                              # slice #6
    {"task": "prd_intent",  "job_id": "...", "intent_text": "..."}        # slice #7

See PRD §2.2.4 for the protocol contract.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_QUEUE_KEY = "video_jobs"
_DEQUEUE_TIMEOUT_SECONDS = 30

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


async def enqueue(task: dict[str, Any]) -> None:
    """Push a task envelope onto the queue. Task must include 'task' and 'job_id' keys."""
    if "task" not in task or "job_id" not in task:
        raise ValueError(f"Invalid task envelope (missing 'task' or 'job_id'): {task!r}")
    payload = json.dumps(task)
    await _client().lpush(_QUEUE_KEY, payload)
    log.info("task_queued", task=task["task"], job_id=task["job_id"])


async def dequeue() -> dict[str, Any] | None:
    """Blocking pop (30s timeout). Returns the decoded task envelope or None on timeout.

    A socket read-timeout during the blocking pop means no task arrived within the
    window — a normal idle cycle, not a failure. We swallow it and return None so the
    worker loops quietly. A real ``ConnectionError`` (Redis down) still propagates to
    the worker's retry/backoff path.
    """
    try:
        result = await _client().brpop([_QUEUE_KEY], timeout=_DEQUEUE_TIMEOUT_SECONDS)
    except RedisTimeoutError:
        return None
    if not result:
        return None
    _, raw = result
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        log.error("task_decode_failed", raw=raw[:200])
        return None
    if not isinstance(envelope, dict) or "task" not in envelope or "job_id" not in envelope:
        log.error("task_envelope_invalid", envelope=envelope)
        return None
    return envelope

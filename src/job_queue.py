"""Redis-backed task queue.

Every item on the `video_jobs` list is a JSON-encoded dict with at minimum:
    {"task": <discriminator>, "job_id": <id>}

Discriminators currently in use:
    {"task": "video",       "job_id": "..."}                              # slice #1/#2/#3
    {"task": "enrichment",  "job_id": "..."}                              # slice #4
    {"task": "prd_auto",    "job_id": "..."}                              # slice #6
    {"task": "prd_intent",  "job_id": "...", "intent_text": "..."}        # slice #7

Queue lineage (handoff §2 "Queue lineage and execution bounds"): every
envelope also carries `root_task_id` (the first task in a chain — a follow-up
task the worker auto-enqueues after another, like `bookmarks_enrich` after
`bookmarks`, inherits its parent's), `depth` (hop count from the root, 0 for
the root itself), and `attempt` (redelivery count of this exact task, 1 for a
fresh enqueue). `_dispatch` in `src/worker.py` rejects envelopes past
`settings.MAX_TASK_DEPTH`/`MAX_TASK_ATTEMPTS` rather than looping forever.

See PRD §2.2.4 for the protocol contract.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from src.config import settings
from src.db.core import generate_id
from src.utils.logger import get_logger

log = get_logger(__name__)

_QUEUE_KEY = "video_jobs"
_DEQUEUE_TIMEOUT_SECONDS = 30

_redis: redis.Redis | None = None


def _client() -> redis.Redis:
    global _redis
    if _redis is None:
        # redis-py's default socket_timeout (5s) is shorter than our blocking BRPOP
        # window, so it would raise RedisTimeoutError well before the server's own
        # timeout — turning every idle cycle into a spurious "timeout" masked below.
        # Keep it above _DEQUEUE_TIMEOUT_SECONDS so only real idle/connectivity
        # issues surface as a timeout.
        _redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=_DEQUEUE_TIMEOUT_SECONDS + 5,
        )
    return _redis


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


def chained_envelope(parent: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Build a follow-up envelope that inherits *parent*'s lineage — same
    `root_task_id`, `depth` + 1, fresh `attempt` of 1 (a new hop, not a
    redelivery of the parent). Use this whenever a processor/worker chains
    one task onto another (e.g. `bookmarks` → `bookmarks_enrich`)."""
    return {
        **task,
        "root_task_id": parent.get("root_task_id") or parent.get("job_id"),
        "depth": parent.get("depth", 0) + 1,
        "attempt": 1,
    }


async def enqueue(task: dict[str, Any]) -> None:
    """Push a task envelope onto the queue. Task must include 'task' and
    'job_id' keys. A root task (no explicit lineage passed) gets a fresh
    `root_task_id`, `depth=0`, `attempt=1` — use `chained_envelope` to enqueue
    a follow-up that inherits its parent's lineage instead."""
    if "task" not in task or "job_id" not in task:
        raise ValueError(f"Invalid task envelope (missing 'task' or 'job_id'): {task!r}")
    envelope = {
        "root_task_id": task.get("root_task_id") or generate_id(),
        "depth": task.get("depth", 0),
        "attempt": task.get("attempt", 1),
        **task,
    }
    payload = json.dumps(envelope)
    await _client().lpush(_QUEUE_KEY, payload)
    log.info(
        "task_queued",
        task=envelope["task"],
        job_id=envelope["job_id"],
        root_task_id=envelope["root_task_id"],
        depth=envelope["depth"],
        attempt=envelope["attempt"],
    )


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

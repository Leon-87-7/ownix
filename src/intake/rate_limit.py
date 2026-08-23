"""Minimal per-key rate limiter, shared by `/api/intake/*` and job creation.

This module provides the shared in-process rate-limit helper. The separate
`src/api/preview.py` implementation is an in-memory sliding window scoped to
anonymous IPs for the public preview surface. This module mirrors that shape
but keys on any caller-supplied string — `src/api/intake.py` keys on the
authenticated actor, `src/services/jobs.py` keys on `job_create:{chat_id}` to
bound job creation across every ingest surface (Telegram, dashboard API,
repo follow-up).
"""

from __future__ import annotations

import time

from fastapi import HTTPException

_WINDOW_SECONDS = 60.0
_MAX_REQUESTS = 30

_hits: dict[str, list[float]] = {}


def enforce(
    key: str,
    *,
    max_requests: int = _MAX_REQUESTS,
    window_seconds: float = _WINDOW_SECONDS,
) -> None:
    """Raise HTTP 429 (with Retry-After) once `key` exceeds `max_requests` in the window."""
    now = time.monotonic()
    cutoff = now - window_seconds
    for stale_key, stale_hits in list(_hits.items()):
        while stale_hits and stale_hits[0] <= cutoff:
            stale_hits.pop(0)
        if not stale_hits:
            _hits.pop(stale_key, None)
    hits = _hits.setdefault(key, [])
    if len(hits) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(int(window_seconds))},
        )
    hits.append(now)


def reset() -> None:
    """Test-only: clear all limiter state between test cases."""
    _hits.clear()

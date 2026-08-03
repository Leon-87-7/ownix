"""Per-user daily upload quota for `POST /api/intake/upload` (issue #475).

In-memory, resets on process restart and isn't shared across worker
processes — this batch's one permitted schema change went to nothing new
(`chat_state.expires_at` already existed; see `src/intake/state.py`), so
there is no durable table for this yet. A persistent per-user quota table is
the natural follow-up if this needs to survive restarts or scale past a
single process.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException

MAX_UPLOADS_PER_DAY = 20
MAX_BYTES_PER_DAY = 100 * 1024 * 1024

_usage: dict[int, tuple[date, int, int]] = {}  # chat_id -> (day, count, bytes_used)


def enforce(chat_id: int, size: int) -> None:
    today = date.today()
    day, count, used_bytes = _usage.get(chat_id, (today, 0, 0))
    if day != today:
        day, count, used_bytes = today, 0, 0
    if count >= MAX_UPLOADS_PER_DAY or used_bytes + size > MAX_BYTES_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily upload quota exceeded")
    _usage[chat_id] = (day, count + 1, used_bytes + size)


def reset() -> None:
    """Test-only: clear all quota state between test cases."""
    _usage.clear()

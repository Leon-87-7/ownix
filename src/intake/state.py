"""Dashboard-visible wrapper around the existing `chat_state` table.

`chat_state` (src/database.py) is keyed by `chat_id` alone — not by channel —
so a pending flow armed from Telegram and one armed from the dashboard share
the same row. That is a deliberate **last-write-wins** semantic, not an
oversight: Ownix's dashboard auth identity and Telegram chat identity are the
same `chat_id` (CLAUDE.md — dashboard auth is the existing Telegram-login
session), so "one user, two channels" is actually "one owner key, two
transports" for a single pending flow. A second in-flight arm (from either
channel) intentionally replaces the first, exactly like `database.set_chat_state`
already logs (`prd.chat_state.replaced_other_job`) for the Telegram-only case.

No new column was needed for expiry: `chat_state.expires_at` already exists
(added in the v3 migration, `src/database.py:333`, cited by the plan itself).
What was actually missing is a sweeper — `expires_at` was checked lazily on
read (`_resolve_chat_state` in webhook.py) but never reaped, so expired rows
just accumulated. `reap_expired()` below is that sweeper, wired into the
scheduler the same way `_drain_purge_outbox` is (`src/main.py`).
"""

from __future__ import annotations

from datetime import datetime, timezone

from src import database
from src.utils.logger import get_logger

log = get_logger(__name__)

PENDING_MODES = ("awaiting_intent", "awaiting_freestyle")


def _is_expired(state: dict) -> bool:
    raw = state.get("expires_at")
    if not raw:
        return True
    try:
        expires_at = datetime.fromisoformat(str(raw).replace(" ", "T"))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


async def get_state(chat_id: int) -> dict | None:
    """Return the caller's pending state, or None if absent/expired."""
    state = await database.get_chat_state(chat_id)
    if state is None or _is_expired(state):
        return None
    return state


async def set_state(chat_id: int, mode: str, job_id: str, expires_minutes: int = 10) -> dict:
    if mode not in PENDING_MODES:
        raise ValueError(f"Unsupported pending mode: {mode}")
    await database.set_chat_state(chat_id, mode=mode, job_id=job_id, expires_minutes=expires_minutes)
    state = await database.get_chat_state(chat_id)
    if state is None:
        # A concurrent clear_state for the same chat_id between the write and
        # this read-back would otherwise surface as an unhandled
        # AssertionError (and `assert` vanishes under python -O).
        raise RuntimeError(f"chat_state row for {chat_id} vanished immediately after being set")
    return state


async def clear_state(chat_id: int) -> bool:
    """Clear the caller's pending state. Returns True if a row was actually cleared."""
    existing = await get_state(chat_id)
    await database.clear_chat_state(chat_id)
    return existing is not None


async def reap_expired() -> int:
    """Delete every chat_state row whose expires_at has passed. Returns rows removed."""
    # Match database.set_chat_state's storage format (datetime.isoformat()) so
    # string comparison orders correctly — a mixed separator (" " vs "T")
    # would still sort right for same-day rows but not worth the risk.
    now = datetime.now(timezone.utc).isoformat()
    removed = await database._execute_rowcount(
        "DELETE FROM chat_state WHERE expires_at <= ?",
        (now,),
    )
    if removed:
        log.info("intake_state_reaped", removed=removed)
    return removed

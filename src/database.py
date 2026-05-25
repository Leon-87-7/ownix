"""SQLite database layer.

Schema lands here as `CREATE TABLE` DDL (greenfield — no migration runner). When the
schema changes post-launch, run a one-off `ALTER TABLE` script (see PRD §14.1
greenfield note).
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id                          TEXT PRIMARY KEY,         -- YYYYMMDD_HHMMSS_XXXX
    chat_id                     INTEGER NOT NULL,
    message_id                  INTEGER,
    url                         TEXT NOT NULL,
    content_type                TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'pending',
    attempt                     INTEGER NOT NULL DEFAULT 1,
    error_msg                   TEXT,
    drive_url                   TEXT,
    title                       TEXT,
    transcript                  TEXT,
    ai_category                 TEXT,
    ai_topic                    TEXT,
    ai_objective                TEXT,
    ai_action_points            TEXT,
    ai_tools                    TEXT,
    ai_market_data              TEXT,
    -- Mini-PRD auto slot (slice #6)
    prd_auto_status             TEXT,
    prd_auto_drive_file_id      TEXT,
    prd_auto_drive_url          TEXT,
    prd_auto_json               TEXT,
    -- Mini-PRD intent slot (slice #7)
    prd_intent_status           TEXT,
    prd_intent_drive_file_id    TEXT,
    prd_intent_drive_url        TEXT,
    prd_intent_json             TEXT,
    prd_intent_text             TEXT,
    prd_intent_completed_at     TEXT,
    sheets_row_id               TEXT,
    -- Template system (issue #17/#18)
    template                    TEXT,
    template_analysis           TEXT,
    key_phrases                 TEXT,
    validation_warning_sent     INTEGER DEFAULT 0,
    template_detection_method   TEXT,
    processing_time_ms          INTEGER,
    promise_gap                 TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);

-- Per-chat conversational mode (slice #7 uses this for ✍️ Text your intent flow).
-- Schema created here in slice #1; behaviour wired in slice #7.
CREATE TABLE IF NOT EXISTS chat_state (
    chat_id      INTEGER PRIMARY KEY,
    mode         TEXT NOT NULL,
    job_id       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    CHECK(mode IN ('awaiting_intent'))
);
"""


def generate_id() -> str:
    """YYYYMMDD_HHMMSS_XXXX where XXXX is 4 hex chars (job IDs and link IDs)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2).upper()
    return f"{ts}_{suffix}"


async def init_db() -> None:
    """Create the database file (if absent), apply DDL, set WAL mode."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.DB_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA_SQL)
        # One-time column additions for existing DBs (no-op on fresh schema)
        _TEMPLATE_COLUMNS = [
            "ALTER TABLE jobs ADD COLUMN template TEXT",
            "ALTER TABLE jobs ADD COLUMN template_analysis TEXT",
            "ALTER TABLE jobs ADD COLUMN key_phrases TEXT",
            "ALTER TABLE jobs ADD COLUMN validation_warning_sent INTEGER DEFAULT 0",
            "ALTER TABLE jobs ADD COLUMN template_detection_method TEXT",
        ]
        for stmt in _TEMPLATE_COLUMNS:
            try:
                await conn.execute(stmt)
            except Exception:
                pass  # column already exists (fresh schema or re-run)
        await conn.commit()
        try:
            await conn.execute("ALTER TABLE jobs ADD COLUMN promise_gap TEXT")
            await conn.commit()
        except Exception:
            pass  # column already exists
    log.info("db_initialized", path=settings.DB_PATH)


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(settings.DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def create_job(
    *,
    chat_id: int,
    url: str,
    content_type: str,
    message_id: int | None = None,
    template: str | None = None,
) -> str:
    """Insert a new job row with status='pending' and return the job_id."""
    job_id = generate_id()
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, chat_id, message_id, url, content_type, status, template)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
            """,
            (job_id, chat_id, message_id, url, content_type, template),
        )
        await conn.commit()
    log.info("job_created", job_id=job_id, chat_id=chat_id, content_type=content_type)
    return job_id


async def get_job(job_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        cursor = await conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def update_job_status(job_id: str, status: str, **fields: Any) -> None:
    """Update status + updated_at, plus any additional columns passed as kwargs."""
    set_parts = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = [status]
    for col, val in fields.items():
        set_parts.append(f"{col} = ?")
        params.append(val)
    params.append(job_id)
    async with connection() as conn:
        await conn.execute(
            f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",
            params,
        )
        await conn.commit()
    log.info("job_status_updated", job_id=job_id, status=status)


_REAPABLE_STATUSES = ("processing", "enriching")


async def fetch_and_mark_stale_jobs(stale_minutes: int = 10) -> list[dict[str, Any]]:
    """Recover jobs orphaned by a worker crash and return the affected rows.

    Selects jobs stuck in ``processing``/``enriching`` whose ``updated_at`` is older
    than ``stale_minutes``, flips them to ``error``, and increments ``attempt`` — all
    in one transaction. Returns ``[{"id", "chat_id", "status"}, ...]`` where ``status``
    is the value BEFORE the reset, so callers can route per-state notifications.

    Run once at worker startup (see ``worker.reap_stale_jobs``). ADR-0010.
    """
    modifier = f"-{stale_minutes} minutes"
    placeholders = ",".join("?" for _ in _REAPABLE_STATUSES)
    where = f"status IN ({placeholders}) AND updated_at < datetime('now', ?)"
    params = (*_REAPABLE_STATUSES, modifier)
    async with connection() as conn:
        cursor = await conn.execute(
            f"SELECT id, chat_id, status FROM jobs WHERE {where}", params
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        if rows:
            await conn.execute(
                f"UPDATE jobs SET status='error', attempt = attempt + 1, "
                f"updated_at=CURRENT_TIMESTAMP WHERE {where}",
                params,
            )
            await conn.commit()
    if rows:
        log.info("jobs_reaped", count=len(rows))
    return rows


async def get_chat_state(chat_id: int) -> dict | None:
    """Return the chat_state row for chat_id, or None if absent."""
    async with connection() as conn:
        cursor = await conn.execute(
            "SELECT chat_id, mode, job_id, created_at, expires_at FROM chat_state WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_chat_state(
    chat_id: int, mode: str, job_id: str, expires_minutes: int = 10
) -> None:
    """Insert or replace a chat_state row (PK chat_id gives upsert semantics).

    Logs ``prd.chat_state.replaced_other_job`` when overwriting a row for a different job_id.
    """
    existing = await get_chat_state(chat_id)
    if existing and existing["job_id"] != job_id:
        log.info(
            "prd.chat_state.replaced_other_job",
            chat_id=chat_id,
            old_job_id=existing["job_id"],
            new_job_id=job_id,
        )
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=expires_minutes)
    async with connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO chat_state (chat_id, mode, job_id, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, mode, job_id, now.isoformat(), expires.isoformat()),
        )
        await conn.commit()


async def clear_chat_state(chat_id: int) -> None:
    """Remove the chat_state row for chat_id, if any. Idempotent."""
    async with connection() as conn:
        await conn.execute("DELETE FROM chat_state WHERE chat_id = ?", (chat_id,))
        await conn.commit()


async def find_jobs_by_suffix(chat_id: int, suffix: str) -> list[dict]:
    """Return all jobs in chat_id whose id ends with suffix. Ordered by created_at DESC.

    Returns all content_types and statuses. Caller filters as needed
    (see webhook /spec handler).
    """
    async with connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM jobs WHERE chat_id = ? AND id LIKE '%' || ? ORDER BY created_at DESC, id DESC",
            (chat_id, suffix),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_recent_jobs(chat_id: int, limit: int = 5) -> list[dict]:
    """Return the most-recent jobs in chat_id, capped at limit."""
    async with connection() as conn:
        cursor = await conn.execute(
            "SELECT id, title, content_type, status FROM jobs "
            "WHERE chat_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (chat_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

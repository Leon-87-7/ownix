"""SQLite database layer.

Schema DDL is in SCHEMA_SQL. Post-launch column additions are tracked via
PRAGMA user_version so every migration step either commits or raises visibly —
no silent swallowing.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

import aiosqlite

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS allowed_domains (
    chat_id     INTEGER NOT NULL,
    domain      TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, domain)
);

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
    bot_message_id              INTEGER,
    -- Freestyle Gemini prompt (issue #51 / ADR-0012)
    freestyle_prompt            TEXT,
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

-- User-managed domain ignore list for Gemini Vision link filtering (/ignore command).
CREATE TABLE IF NOT EXISTS ignored_domains (
    domain      TEXT PRIMARY KEY,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-chat conversational mode (slice #7 uses this for ✍️ Text your intent flow).
-- Schema created here in slice #1; behaviour wired in slice #7.
CREATE TABLE IF NOT EXISTS chat_state (
    chat_id      INTEGER PRIMARY KEY,
    mode         TEXT NOT NULL,
    job_id       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle'))
);

-- Jina Reader markdown cache (issue #60 / ADR-0013).
CREATE TABLE IF NOT EXISTS markdown_cache (
    url         TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Second Brain semantic link graph (src/brain.py data-access layer).
CREATE TABLE IF NOT EXISTS links (
    id            TEXT PRIMARY KEY,
    url           TEXT NOT NULL,
    title         TEXT,
    topic         TEXT,
    source_job    TEXT NOT NULL,
    embedding     BLOB,
    drive_file_id TEXT,
    seen_count    INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
CREATE INDEX IF NOT EXISTS idx_links_updated_at ON links(updated_at);
"""


def generate_id() -> str:
    """YYYYMMDD_HHMMSS_XXXX where XXXX is 4 hex chars (job IDs and link IDs)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2).upper()
    return f"{ts}_{suffix}"


# Each list entry is one migration step (v0→v1, v1→v2, …).
# Statements in a step run together; if any raises it propagates — except
# "duplicate column name", which means the column was already added by an
# older code path and is safe to skip.
_MIGRATIONS: list[list[str]] = [
    # v0 → v1: template system, promise_gap, bot_message_id (post-launch columns)
    [
        "ALTER TABLE jobs ADD COLUMN template TEXT",
        "ALTER TABLE jobs ADD COLUMN template_analysis TEXT",
        "ALTER TABLE jobs ADD COLUMN key_phrases TEXT",
        "ALTER TABLE jobs ADD COLUMN validation_warning_sent INTEGER DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN template_detection_method TEXT",
        "ALTER TABLE jobs ADD COLUMN promise_gap TEXT",
        "ALTER TABLE jobs ADD COLUMN bot_message_id INTEGER",
    ],
    # v1 → v2: freestyle Gemini prompt (issue #51 / ADR-0012)
    [
        "ALTER TABLE jobs ADD COLUMN freestyle_prompt TEXT",
    ],
    # v2 → v3: expand chat_state.mode CHECK to include 'awaiting_freestyle' (issue #53 / ADR-0012)
    [
        """CREATE TABLE IF NOT EXISTS chat_state_v3 (
            chat_id    INTEGER PRIMARY KEY,
            mode       TEXT NOT NULL,
            job_id     TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle'))
        )""",
        "INSERT OR IGNORE INTO chat_state_v3 SELECT * FROM chat_state",
        "DROP TABLE chat_state",
        "ALTER TABLE chat_state_v3 RENAME TO chat_state",
    ],
    # v3 → v4: per-chat article allowlist (issue #61)
    [
        """CREATE TABLE IF NOT EXISTS allowed_domains (
            chat_id     INTEGER NOT NULL,
            domain      TEXT NOT NULL,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, domain)
        )""",
    ],
    # v4 → v5: Jina Reader markdown cache (issue #60)
    [
        """CREATE TABLE IF NOT EXISTS markdown_cache (
            url        TEXT PRIMARY KEY,
            content    TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ],
]


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    cur = await conn.execute("PRAGMA user_version")
    row = await cur.fetchone()
    current_version: int = row[0]
    for step, statements in enumerate(_MIGRATIONS[current_version:], start=current_version):
        for stmt in statements:
            try:
                await conn.execute(stmt)
            except aiosqlite.OperationalError as exc:
                if "duplicate column name" not in str(exc):
                    raise
        new_version = step + 1
        await conn.execute(f"PRAGMA user_version = {new_version}")
        await conn.commit()
        log.info("db_migration_applied", version=new_version)


async def init_db() -> None:
    """Create the database file (if absent), apply DDL, run pending migrations."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.DB_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        is_fresh = await cur.fetchone() is None
        await conn.executescript(SCHEMA_SQL)
        if is_fresh:
            # DDL already includes all columns; skip past all migration steps.
            await conn.execute(f"PRAGMA user_version = {len(_MIGRATIONS)}")
            await conn.commit()
        else:
            await _run_migrations(conn)
    log.info("db_initialized", path=settings.DB_PATH)


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(settings.DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def get_ignored_domains() -> set[str]:
    async with connection() as conn:
        cur = await conn.execute("SELECT domain FROM ignored_domains")
        return {row[0] for row in await cur.fetchall()}


async def add_ignored_domain(domain: str) -> None:
    async with connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO ignored_domains (domain) VALUES (?)", (domain,)
        )
        await conn.commit()


async def remove_ignored_domain(domain: str) -> bool:
    async with connection() as conn:
        cur = await conn.execute(
            "DELETE FROM ignored_domains WHERE domain=?", (domain,)
        )
        await conn.commit()
        return cur.rowcount > 0


async def add_allowed_domain(chat_id: int, domain: str) -> None:
    """Insert (chat_id, domain) into allowed_domains. Idempotent on duplicate."""
    async with connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO allowed_domains (chat_id, domain) VALUES (?, ?)",
            (chat_id, domain),
        )
        await conn.commit()


async def list_allowed_domains(chat_id: int) -> set[str]:
    """Return the set of domains allowed for this chat."""
    async with connection() as conn:
        cur = await conn.execute(
            "SELECT domain FROM allowed_domains WHERE chat_id = ?", (chat_id,)
        )
        return {row[0] for row in await cur.fetchall()}


async def remove_allowed_domain(chat_id: int, domain: str) -> bool:
    """Delete (chat_id, domain). Returns True if removed, False if not found."""
    async with connection() as conn:
        cur = await conn.execute(
            "DELETE FROM allowed_domains WHERE chat_id = ? AND domain = ?",
            (chat_id, domain),
        )
        await conn.commit()
        return cur.rowcount > 0


async def create_job(
    *,
    chat_id: int,
    url: str,
    content_type: str,
    message_id: int | None = None,
    template: str | None = None,
    freestyle_prompt: str | None = None,
) -> str:
    """Insert a new job row with status='pending' and return the job_id."""
    job_id = generate_id()
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (id, chat_id, message_id, url, content_type, status, template, freestyle_prompt)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (job_id, chat_id, message_id, url, content_type, template, freestyle_prompt),
        )
        await conn.commit()
    log.info("job_created", job_id=job_id, chat_id=chat_id, content_type=content_type)
    return job_id


async def reset_job(job_id: str) -> None:
    """Reset a job back to pending, clearing all result fields. Increments attempt."""
    async with connection() as conn:
        await conn.execute(
            """
            UPDATE jobs SET
                status = 'pending',
                attempt = attempt + 1,
                error_msg = NULL,
                drive_url = NULL,
                title = NULL,
                transcript = NULL,
                bot_message_id = NULL,
                key_phrases = NULL,
                template_analysis = NULL,
                ai_category = NULL,
                ai_topic = NULL,
                ai_objective = NULL,
                ai_action_points = NULL,
                ai_tools = NULL,
                ai_market_data = NULL,
                processing_time_ms = NULL,
                promise_gap = NULL,
                completed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
        await conn.commit()
    log.info("job_reset", job_id=job_id)


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


async def set_prd_slot_status(job_id: str, slot: Literal["auto", "intent"], status: str) -> None:
    """Set prd_auto_status or prd_intent_status without leaking column names to callers."""
    col = "prd_auto_status" if slot == "auto" else "prd_intent_status"
    async with connection() as conn:
        await conn.execute(
            f"UPDATE jobs SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id),
        )
        await conn.commit()
    log.info("prd_slot_status_set", job_id=job_id, slot=slot, status=status)


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


async def find_recent_job_by_url(chat_id: int, url: str) -> dict | None:
    """Return the most recent non-failed job for this chat_id + url, or None.

    Covers pending/processing (still running) and completed (cached result).
    Failed and stale jobs are excluded so the user can retry after a failure.
    """
    async with connection() as conn:
        cursor = await conn.execute(
            "SELECT id, title, drive_url, content_type, status, bot_message_id FROM jobs "
            "WHERE chat_id = ? AND url = ? AND status NOT IN ('error', 'cancelled') "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (chat_id, url),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Markdown cache (Jina Reader — issue #60 / ADR-0013)
# ---------------------------------------------------------------------------


async def get_markdown_cache(url: str) -> dict | None:
    """Return the markdown_cache row for *url*, or None if absent."""
    async with connection() as conn:
        cursor = await conn.execute(
            "SELECT url, content, fetched_at FROM markdown_cache WHERE url = ?",
            (url,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def insert_markdown_cache(url: str, content: str) -> None:
    """Insert or replace a markdown_cache row for *url*."""
    async with connection() as conn:
        await conn.execute(
            "INSERT OR REPLACE INTO markdown_cache (url, content, fetched_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (url, content),
        )
        await conn.commit()
    log.info("markdown_cache.inserted", url=url, content_len=len(content))


async def delete_markdown_cache(url: str) -> bool:
    """Delete the markdown_cache row for *url*. Returns True if a row was deleted."""
    async with connection() as conn:
        cur = await conn.execute(
            "DELETE FROM markdown_cache WHERE url = ?", (url,)
        )
        await conn.commit()
        return cur.rowcount > 0

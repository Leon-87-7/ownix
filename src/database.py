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
    best_frame_index            INTEGER,
    platform                    TEXT,
    video_id                    TEXT,
    og_image_url                TEXT,
    summary                     TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);

CREATE TABLE IF NOT EXISTS job_thumbnails (
    job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    bytes      BLOB NOT NULL,
    mime       TEXT NOT NULL,
    width      INTEGER,
    height     INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-managed per-chat domain ignore list for Gemini Vision link filtering (/ignore command).
CREATE TABLE IF NOT EXISTS ignored_domains (
    chat_id     INTEGER NOT NULL,
    domain      TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, domain)
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

-- Web dashboard users (issue #84 / S1 auth spine).
CREATE TABLE IF NOT EXISTS users (
    tg_id       INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT NOT NULL,
    last_name   TEXT,
    photo_url   TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_settings (
    chat_id    INTEGER NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, key)
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

-- Tag vocabulary for job tagging (issue #87 / S4).
CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    meaning    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#6366f1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);

-- User-defined enrichment templates (issue #90).
CREATE TABLE IF NOT EXISTS templates (
    id                  TEXT PRIMARY KEY,
    chat_id             INTEGER NOT NULL DEFAULT 0,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    extra_instructions  TEXT NOT NULL DEFAULT '',
    trigger_patterns    TEXT NOT NULL DEFAULT '',
    brave_search        INTEGER NOT NULL DEFAULT 0,
    content_type_scope  TEXT NOT NULL DEFAULT '',
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);

-- Job notes (issue #88 / S5).
CREATE TABLE IF NOT EXISTS job_annotations (
    job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    notes      TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Job-tag links (issue #88 / S5).
CREATE TABLE IF NOT EXISTS job_tags (
    job_id  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, tag_id)
);

-- Named collections of jobs (issue #89 / S6).
CREATE TABLE IF NOT EXISTS spaces (
    id         TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    color      TEXT NOT NULL DEFAULT '#6366f1',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);
CREATE INDEX IF NOT EXISTS idx_spaces_chat_id ON spaces(chat_id);

-- Jobs pinned into a space (issue #89 / S6).
CREATE TABLE IF NOT EXISTS space_urls (
    space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (space_id, job_id)
);

-- Per-space editorial context documents (issue #93 / S7).
CREATE TABLE IF NOT EXISTS context_blobs (
    id         TEXT PRIMARY KEY,
    space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_context_blobs_space_id ON context_blobs(space_id);
"""


def generate_id() -> str:
    """YYYYMMDD_HHMMSS_XXXXXXXX where XXXXXXXX is 8 hex chars (job IDs and link IDs)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4).upper()
    return f"{ts}_{suffix}"


# Each list entry is one migration step (v0→v1, v1→v2, …).
# Entries may be a list[str] (SQL statements) or an async callable(conn).
# SQL statements swallow "duplicate column name" errors; callables are
# responsible for their own idempotency.
_MIGRATIONS: list = [
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
    # v5 → v6: expand content_type CHECK to include 'article' (issue #62)
    # Callable because SELECT * fails when old table has fewer columns than jobs_v6.
    None,  # replaced with _migrate_v5_v6 after function definition below
]

_V6_CREATE = """CREATE TABLE IF NOT EXISTS jobs_v6 (
    id                          TEXT PRIMARY KEY,
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
    prd_auto_status             TEXT,
    prd_auto_drive_file_id      TEXT,
    prd_auto_drive_url          TEXT,
    prd_auto_json               TEXT,
    prd_intent_status           TEXT,
    prd_intent_drive_file_id    TEXT,
    prd_intent_drive_url        TEXT,
    prd_intent_json             TEXT,
    prd_intent_text             TEXT,
    prd_intent_completed_at     TEXT,
    sheets_row_id               TEXT,
    template                    TEXT,
    template_analysis           TEXT,
    key_phrases                 TEXT,
    validation_warning_sent     INTEGER DEFAULT 0,
    template_detection_method   TEXT,
    processing_time_ms          INTEGER,
    promise_gap                 TEXT,
    bot_message_id              INTEGER,
    freestyle_prompt            TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
)"""

_V6_COLS = [
    "id", "chat_id", "message_id", "url", "content_type", "status", "attempt",
    "error_msg", "drive_url", "title", "transcript", "ai_category", "ai_topic",
    "ai_objective", "ai_action_points", "ai_tools", "ai_market_data",
    "prd_auto_status", "prd_auto_drive_file_id", "prd_auto_drive_url", "prd_auto_json",
    "prd_intent_status", "prd_intent_drive_file_id", "prd_intent_drive_url",
    "prd_intent_json", "prd_intent_text", "prd_intent_completed_at", "sheets_row_id",
    "template", "template_analysis", "key_phrases", "validation_warning_sent",
    "template_detection_method", "processing_time_ms", "promise_gap", "bot_message_id",
    "freestyle_prompt", "created_at", "updated_at", "completed_at",
]


async def _rebuild_jobs_table(
    conn: aiosqlite.Connection, create_sql: str, tmp_name: str, cols: list[str]
) -> None:
    """Recreate jobs under *tmp_name* (widened CHECK), copying the shared columns."""
    await conn.execute(create_sql)
    cur = await conn.execute("PRAGMA table_info(jobs)")
    rows = await cur.fetchall()
    existing = {row[1] for row in rows}
    copy_cols = [c for c in cols if c in existing]
    if copy_cols:
        col_str = ", ".join(copy_cols)
        await conn.execute(
            f"INSERT OR IGNORE INTO {tmp_name} ({col_str}) SELECT {col_str} FROM jobs"
        )
    await conn.execute("DROP TABLE jobs")
    await conn.execute(f"ALTER TABLE {tmp_name} RENAME TO jobs")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")


async def _migrate_v5_v6(conn: aiosqlite.Connection) -> None:
    """Expand content_type CHECK to include 'article' via selective column copy."""
    await _rebuild_jobs_table(conn, _V6_CREATE, "jobs_v6", _V6_COLS)


_MIGRATIONS[5] = _migrate_v5_v6

_V7_CREATE = """CREATE TABLE IF NOT EXISTS jobs_v7 (
    id                          TEXT PRIMARY KEY,
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
    prd_auto_status             TEXT,
    prd_auto_drive_file_id      TEXT,
    prd_auto_drive_url          TEXT,
    prd_auto_json               TEXT,
    prd_intent_status           TEXT,
    prd_intent_drive_file_id    TEXT,
    prd_intent_drive_url        TEXT,
    prd_intent_json             TEXT,
    prd_intent_text             TEXT,
    prd_intent_completed_at     TEXT,
    sheets_row_id               TEXT,
    template                    TEXT,
    template_analysis           TEXT,
    key_phrases                 TEXT,
    validation_warning_sent     INTEGER DEFAULT 0,
    template_detection_method   TEXT,
    processing_time_ms          INTEGER,
    promise_gap                 TEXT,
    bot_message_id              INTEGER,
    freestyle_prompt            TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
)"""

_V7_COLS = [
    "id", "chat_id", "message_id", "url", "content_type", "status", "attempt",
    "error_msg", "drive_url", "title", "transcript", "ai_category", "ai_topic",
    "ai_objective", "ai_action_points", "ai_tools", "ai_market_data",
    "prd_auto_status", "prd_auto_drive_file_id", "prd_auto_drive_url", "prd_auto_json",
    "prd_intent_status", "prd_intent_drive_file_id", "prd_intent_drive_url",
    "prd_intent_json", "prd_intent_text", "prd_intent_completed_at", "sheets_row_id",
    "template", "template_analysis", "key_phrases", "validation_warning_sent",
    "template_detection_method", "processing_time_ms", "promise_gap", "bot_message_id",
    "freestyle_prompt", "created_at", "updated_at", "completed_at",
]


async def _migrate_v6_v7(conn: aiosqlite.Connection) -> None:
    """Expand content_type CHECK to include 'repo'."""
    await _rebuild_jobs_table(conn, _V7_CREATE, "jobs_v7", _V7_COLS)


_MIGRATIONS.append(_migrate_v6_v7)


async def _migrate_v7_v8(conn: aiosqlite.Connection) -> None:
    """Add chat_id to ignored_domains, changing PK from (domain) to (chat_id, domain)."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ignored_domains_v2 (
            chat_id  INTEGER NOT NULL,
            domain   TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, domain)
        )
    """)
    # Backfill existing rows with the one chat_id present in jobs.
    # Falls back to 0 if jobs is empty (fresh installs skip migrations anyway).
    await conn.execute("""
        INSERT OR IGNORE INTO ignored_domains_v2 (chat_id, domain, added_at)
        SELECT COALESCE((SELECT chat_id FROM jobs LIMIT 1), 0), domain, added_at
        FROM ignored_domains
    """)
    await conn.execute("DROP TABLE ignored_domains")
    await conn.execute("ALTER TABLE ignored_domains_v2 RENAME TO ignored_domains")


_MIGRATIONS.append(_migrate_v7_v8)

# v8 → v9: users table for web dashboard auth (issue #84)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS users (
        tg_id       INTEGER PRIMARY KEY,
        username    TEXT,
        first_name  TEXT NOT NULL,
        last_name   TEXT,
        photo_url   TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
])

# v9 → v10: tags table (issue #87 / S4)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS tags (
        id         TEXT PRIMARY KEY,
        chat_id    INTEGER NOT NULL,
        name       TEXT NOT NULL,
        meaning    TEXT NOT NULL DEFAULT '',
        color      TEXT NOT NULL DEFAULT '#6366f1',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, name)
    )""",
])

# v10 → v11: user-defined enrichment templates (issue #90)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS templates (
        id                  TEXT PRIMARY KEY,
        chat_id             INTEGER NOT NULL DEFAULT 0,
        name                TEXT NOT NULL,
        description         TEXT NOT NULL DEFAULT '',
        extra_instructions  TEXT NOT NULL DEFAULT '',
        trigger_patterns    TEXT NOT NULL DEFAULT '',
        brave_search        INTEGER NOT NULL DEFAULT 0,
        content_type_scope  TEXT NOT NULL DEFAULT '',
        is_builtin          INTEGER NOT NULL DEFAULT 0,
        created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, name)
    )""",
])

# v11 → v12: job annotations + job-tag links (issue #88 / S5)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS job_annotations (
        job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        notes      TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS job_tags (
        job_id  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (job_id, tag_id)
    )""",
])

# v12 → v13: spaces + space_urls tables (issue #89 / S6)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS spaces (
        id         TEXT PRIMARY KEY,
        chat_id    INTEGER NOT NULL,
        name       TEXT NOT NULL,
        color      TEXT NOT NULL DEFAULT '#6366f1',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, name)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_spaces_chat_id ON spaces(chat_id)",
    """CREATE TABLE IF NOT EXISTS space_urls (
        space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
        job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (space_id, job_id)
    )""",
])

# v13 → v14: context_blobs table (issue #93 / S7)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS context_blobs (
        id         TEXT PRIMARY KEY,
        space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
        name       TEXT NOT NULL,
        content    TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_context_blobs_space_id ON context_blobs(space_id)",
])

# v14 -> v15: job media metadata and persisted thumbnails (issues #146/#147)
_MIGRATIONS.append([
    "ALTER TABLE jobs ADD COLUMN best_frame_index INTEGER",
    "ALTER TABLE jobs ADD COLUMN platform TEXT",
    "ALTER TABLE jobs ADD COLUMN video_id TEXT",
    "ALTER TABLE jobs ADD COLUMN og_image_url TEXT",
    """CREATE TABLE IF NOT EXISTS job_thumbnails (
        job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
        bytes      BLOB NOT NULL,
        mime       TEXT NOT NULL,
        width      INTEGER,
        height     INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
])

# v15 -> v16: per-chat web dashboard settings (issue #171)
_MIGRATIONS.append([
    """CREATE TABLE IF NOT EXISTS user_settings (
        chat_id    INTEGER NOT NULL,
        key        TEXT NOT NULL,
        value      TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, key)
    )""",
])


# v15 → v16: vision summary column for short jobs (issue #164)
_MIGRATIONS.append([
    "ALTER TABLE jobs ADD COLUMN summary TEXT",
])


# v16 → v17: widen content_type CHECK to include 'document' (issue #150/#151).
# SQLite can't ALTER a CHECK, so rebuild the table. _V17_CREATE is the current
# full jobs DDL (mirrors SCHEMA_SQL) with 'document' added to the CHECK.
_V17_CREATE = """CREATE TABLE IF NOT EXISTS jobs_v17 (
    id                          TEXT PRIMARY KEY,
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
    prd_auto_status             TEXT,
    prd_auto_drive_file_id      TEXT,
    prd_auto_drive_url          TEXT,
    prd_auto_json               TEXT,
    prd_intent_status           TEXT,
    prd_intent_drive_file_id    TEXT,
    prd_intent_drive_url        TEXT,
    prd_intent_json             TEXT,
    prd_intent_text             TEXT,
    prd_intent_completed_at     TEXT,
    sheets_row_id               TEXT,
    template                    TEXT,
    template_analysis           TEXT,
    key_phrases                 TEXT,
    validation_warning_sent     INTEGER DEFAULT 0,
    template_detection_method   TEXT,
    processing_time_ms          INTEGER,
    promise_gap                 TEXT,
    bot_message_id              INTEGER,
    freestyle_prompt            TEXT,
    best_frame_index            INTEGER,
    platform                    TEXT,
    video_id                    TEXT,
    og_image_url                TEXT,
    summary                     TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
)"""

_V17_COLS = [
    "id", "chat_id", "message_id", "url", "content_type", "status", "attempt",
    "error_msg", "drive_url", "title", "transcript", "ai_category", "ai_topic",
    "ai_objective", "ai_action_points", "ai_tools", "ai_market_data",
    "prd_auto_status", "prd_auto_drive_file_id", "prd_auto_drive_url", "prd_auto_json",
    "prd_intent_status", "prd_intent_drive_file_id", "prd_intent_drive_url",
    "prd_intent_json", "prd_intent_text", "prd_intent_completed_at", "sheets_row_id",
    "template", "template_analysis", "key_phrases", "validation_warning_sent",
    "template_detection_method", "processing_time_ms", "promise_gap", "bot_message_id",
    "freestyle_prompt", "best_frame_index", "platform", "video_id", "og_image_url",
    "summary", "created_at", "updated_at", "completed_at",
]


async def _migrate_v16_v17(conn: aiosqlite.Connection) -> None:
    """Widen content_type CHECK to include 'document' via selective column copy."""
    await _rebuild_jobs_table(conn, _V17_CREATE, "jobs_v17", _V17_COLS)


_MIGRATIONS.append(_migrate_v16_v17)


async def _run_migrations(conn: aiosqlite.Connection) -> None:
    cur = await conn.execute("PRAGMA user_version")
    row = await cur.fetchone()
    current_version: int = row[0]
    for step, migration_step in enumerate(_MIGRATIONS[current_version:], start=current_version):
        if callable(migration_step):
            await migration_step(conn)
        else:
            for stmt in migration_step:
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
    await conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        await conn.close()


async def _execute(sql: str, params: tuple = ()) -> None:
    async with connection() as conn:
        await conn.execute(sql, params)
        await conn.commit()


async def _execute_rowcount(sql: str, params: tuple = ()) -> int:
    async with connection() as conn:
        cur = await conn.execute(sql, params)
        await conn.commit()
        return cur.rowcount


async def _fetch_one(sql: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with connection() as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchone()


async def _fetch_all(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with connection() as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchall()


async def _fetch_dicts(sql: str, params: tuple = ()) -> list[dict]:
    """`_fetch_all` with rows converted to plain dicts."""
    rows = await _fetch_all(sql, params)
    return [dict(row) for row in rows]


async def _insert_returning(
    insert_sql: str, insert_params: tuple, select_sql: str, select_params: tuple
) -> dict:
    """Run an INSERT/UPSERT, then SELECT the resulting row back, on one connection."""
    async with connection() as conn:
        await conn.execute(insert_sql, insert_params)
        cur = await conn.execute(select_sql, select_params)
        row = await cur.fetchone()
        await conn.commit()
        return dict(row)  # type: ignore[arg-type]


async def _fetch_in(sql_template: str, ids: list[str]) -> list[dict]:
    """Run *sql_template* (containing ``{placeholders}``) with an expanded IN list."""
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    async with connection() as conn:
        cur = await conn.execute(sql_template.format(placeholders=placeholders), tuple(ids))
        return [dict(r) for r in await cur.fetchall()]


async def get_ignored_domains(chat_id: int) -> set[str]:
    rows = await _fetch_all("SELECT domain FROM ignored_domains WHERE chat_id = ?", (chat_id,))
    return {row[0] for row in rows}


async def add_ignored_domain(chat_id: int, domain: str) -> bool:
    return await _execute_rowcount(
        "INSERT OR IGNORE INTO ignored_domains (chat_id, domain) VALUES (?, ?)",
        (chat_id, domain),
    ) > 0


async def remove_ignored_domain(chat_id: int, domain: str) -> bool:
    return await _execute_rowcount(
        "DELETE FROM ignored_domains WHERE chat_id = ? AND domain = ?",
        (chat_id, domain),
    ) > 0


async def get_user_setting(chat_id: int, key: str) -> str | None:
    row = await _fetch_one(
        "SELECT value FROM user_settings WHERE chat_id = ? AND key = ?",
        (chat_id, key),
    )
    return str(row["value"]) if row else None


async def set_user_setting(chat_id: int, key: str, value: str) -> None:
    await _execute(
        """
        INSERT INTO user_settings (chat_id, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id, key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (chat_id, key, value),
    )


_RECOVERY_TELEGRAM_NOTIFICATIONS_KEY = "dashboard_recovery_telegram_notifications"


async def get_recovery_telegram_notifications_enabled(chat_id: int) -> bool:
    value = await get_user_setting(chat_id, _RECOVERY_TELEGRAM_NOTIFICATIONS_KEY)
    return value != "0"


async def set_recovery_telegram_notifications_enabled(chat_id: int, enabled: bool) -> None:
    await set_user_setting(chat_id, _RECOVERY_TELEGRAM_NOTIFICATIONS_KEY, "1" if enabled else "0")


async def add_allowed_domain(chat_id: int, domain: str) -> bool:
    """Insert (chat_id, domain) into allowed_domains. Returns True if inserted, False if already present."""
    return await _execute_rowcount(
        "INSERT OR IGNORE INTO allowed_domains (chat_id, domain) VALUES (?, ?)",
        (chat_id, domain),
    ) > 0


async def list_allowed_domains(chat_id: int) -> set[str]:
    """Return the set of domains allowed for this chat."""
    rows = await _fetch_all("SELECT domain FROM allowed_domains WHERE chat_id = ?", (chat_id,))
    return {row[0] for row in rows}


async def remove_allowed_domain(chat_id: int, domain: str) -> bool:
    """Delete (chat_id, domain). Returns True if removed, False if not found."""
    return await _execute_rowcount(
        "DELETE FROM allowed_domains WHERE chat_id = ? AND domain = ?",
        (chat_id, domain),
    ) > 0


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
                best_frame_index = NULL,
                platform = NULL,
                video_id = NULL,
                og_image_url = NULL,
                summary = NULL,
                promise_gap = NULL,
                completed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
        await conn.execute("DELETE FROM job_thumbnails WHERE job_id = ?", (job_id,))
        await conn.commit()
    log.info("job_reset", job_id=job_id)


async def get_job(job_id: str) -> dict[str, Any] | None:
    row = await _fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
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


async def backfill_og_image_url(job_id: str, og_image_url: str) -> bool:
    """Set og_image_url for a still-completed article without touching status.

    Idempotent and race-safe: only writes when the job is still ``done`` and the
    column is still empty, so a job reset to pending between scan and write is
    never forced back to ``done``. Returns True iff a row was updated.
    """
    rowcount = await _execute_rowcount(
        """
        UPDATE jobs
        SET og_image_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'done' AND og_image_url IS NULL
        """,
        (og_image_url, job_id),
    )
    return rowcount > 0


# Image MIME types we are willing to persist and later serve to browsers.
# Anything else (e.g. a stray ``text/html`` from the vision model) is coerced
# to ``image/jpeg`` so stored bytes can never be interpreted as active content.
ALLOWED_THUMBNAIL_MIMES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)


async def save_thumbnail(
    job_id: str,
    thumbnail_bytes: bytes,
    *,
    mime: str = "image/jpeg",
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Persist a job thumbnail and return its API URL."""
    safe_mime = mime if mime in ALLOWED_THUMBNAIL_MIMES else "image/jpeg"
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO job_thumbnails (job_id, bytes, mime, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_id) DO UPDATE SET
                bytes = excluded.bytes,
                mime = excluded.mime,
                width = excluded.width,
                height = excluded.height
            """,
            (job_id, thumbnail_bytes, safe_mime, width, height),
        )
        await conn.commit()
    log.info("job_thumbnail_saved", job_id=job_id, mime=safe_mime, bytes=len(thumbnail_bytes))
    return f"/api/jobs/{job_id}/thumbnail"


async def get_thumbnail(job_id: str) -> dict[str, Any] | None:
    row = await _fetch_one(
        "SELECT job_id, bytes, mime, width, height, created_at FROM job_thumbnails WHERE job_id = ?",
        (job_id,),
    )
    return dict(row) if row else None


async def has_thumbnail(job_id: str) -> bool:
    row = await _fetch_one("SELECT 1 FROM job_thumbnails WHERE job_id = ?", (job_id,))
    return row is not None


async def get_thumbnail_job_ids(job_ids: list[str]) -> set[str]:
    """Return the subset of *job_ids* that have a stored thumbnail (single query)."""
    rows = await _fetch_in(
        "SELECT job_id FROM job_thumbnails WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"] for row in rows}


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


async def fetch_and_mark_stale_jobs(
    stale_minutes: int = 10,
    *,
    chat_id: int | None = None,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """Recover jobs orphaned by a worker crash and return the affected rows.

    Selects jobs stuck in ``processing``/``enriching`` whose ``updated_at`` is older
    than ``stale_minutes``, flips them to ``error``, and increments ``attempt`` — all
    in one transaction. Returns ``[{"id", "chat_id", "status"}, ...]`` where ``status``
    is the value BEFORE the reset, so callers can route per-state notifications.

    Run once at worker startup (see ``worker.reap_stale_jobs``). ADR-0010.
    """
    modifier = f"-{stale_minutes} minutes"
    placeholders = ",".join("?" for _ in _REAPABLE_STATUSES)
    conditions = [f"status IN ({placeholders})", "updated_at < datetime('now', ?)"]
    params: list[Any] = [*_REAPABLE_STATUSES, modifier]
    if chat_id is not None:
        conditions.append("chat_id = ?")
        params.append(chat_id)
    if content_type is not None:
        conditions.append("content_type = ?")
        params.append(content_type)
    where = " AND ".join(conditions)
    async with connection() as conn:
        cursor = await conn.execute(
            f"SELECT id, chat_id, status FROM jobs WHERE {where}", tuple(params)
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        if rows:
            await conn.execute(
                f"UPDATE jobs SET status='error', attempt = attempt + 1, "
                f"updated_at=CURRENT_TIMESTAMP WHERE {where}",
                tuple(params),
            )
            await conn.commit()
    if rows:
        log.info("jobs_reaped", count=len(rows))
    return rows


async def get_chat_state(chat_id: int) -> dict | None:
    """Return the chat_state row for chat_id, or None if absent."""
    row = await _fetch_one(
        "SELECT chat_id, mode, job_id, created_at, expires_at FROM chat_state WHERE chat_id = ?",
        (chat_id,),
    )
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
    await _execute("DELETE FROM chat_state WHERE chat_id = ?", (chat_id,))


async def find_jobs_by_suffix(chat_id: int, suffix: str) -> list[dict]:
    """Return all jobs in chat_id whose id ends with suffix. Ordered by created_at DESC.

    Returns all content_types and statuses. Caller filters as needed
    (see webhook /spec handler).
    """
    return await _fetch_dicts(
        "SELECT * FROM jobs WHERE chat_id = ? AND id LIKE '%' || ? ORDER BY created_at DESC, id DESC",
        (chat_id, suffix),
    )


async def get_recent_jobs(chat_id: int, limit: int = 5) -> list[dict]:
    """Return the most-recent jobs in chat_id, capped at limit."""
    return await _fetch_dicts(
        "SELECT id, title, content_type, status FROM jobs "
        "WHERE chat_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (chat_id, limit),
    )


async def find_recent_job_by_url(chat_id: int, url: str) -> dict | None:
    """Return the most recent non-failed job for this chat_id + url, or None.

    Covers pending/processing (still running) and completed (cached result).
    Failed and stale jobs are excluded so the user can retry after a failure.
    """
    row = await _fetch_one(
        "SELECT id, title, drive_url, content_type, status, bot_message_id FROM jobs "
        "WHERE chat_id = ? AND url = ? AND status NOT IN ('error', 'cancelled') "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (chat_id, url),
    )
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
    await _execute(
        "INSERT OR REPLACE INTO markdown_cache (url, content, fetched_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP)",
        (url, content),
    )
    log.info("markdown_cache.inserted", url=url, content_len=len(content))


async def delete_markdown_cache(url: str) -> bool:
    """Delete the markdown_cache row for *url*. Returns True if a row was deleted."""
    return await _execute_rowcount("DELETE FROM markdown_cache WHERE url = ?", (url,)) > 0


# ---------------------------------------------------------------------------
# Users (web dashboard auth — issue #84)
# ---------------------------------------------------------------------------


async def upsert_user(
    *,
    tg_id: int,
    first_name: str,
    username: str | None = None,
    last_name: str | None = None,
    photo_url: str | None = None,
) -> None:
    """Insert or update a Telegram user row (keyed by tg_id)."""
    async with connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name, last_name, photo_url, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(tg_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                photo_url  = excluded.photo_url,
                updated_at = excluded.updated_at
            """,
            (tg_id, username, first_name, last_name, photo_url),
        )
        await conn.commit()
    log.info("user_upserted", tg_id=tg_id)


# ---------------------------------------------------------------------------
# Tags (web dashboard — issue #87 / S4)
# ---------------------------------------------------------------------------


async def list_tags(chat_id: int) -> list[dict]:
    return await _fetch_dicts(
        "SELECT id, name, meaning, color, created_at FROM tags WHERE chat_id = ? ORDER BY name",
        (chat_id,),
    )


async def create_tag(*, chat_id: int, name: str, meaning: str, color: str) -> dict:
    tag_id = generate_id()
    async with connection() as conn:
        await conn.execute(
            "INSERT INTO tags (id, chat_id, name, meaning, color) VALUES (?, ?, ?, ?, ?)",
            (tag_id, chat_id, name, meaning, color),
        )
        await conn.commit()
    return {"id": tag_id, "name": name, "meaning": meaning, "color": color}


async def update_tag(*, chat_id: int, tag_id: str, name: str, meaning: str, color: str) -> bool:
    return await _execute_rowcount(
        "UPDATE tags SET name = ?, meaning = ?, color = ? WHERE id = ? AND chat_id = ?",
        (name, meaning, color, tag_id, chat_id),
    ) > 0


async def delete_tag(*, chat_id: int, tag_id: str) -> bool:
    return await _execute_rowcount(
        "DELETE FROM tags WHERE id = ? AND chat_id = ?", (tag_id, chat_id)
    ) > 0


# ---------------------------------------------------------------------------
# User-defined templates (issue #90)
# ---------------------------------------------------------------------------


async def list_user_templates(chat_id: int) -> list[dict]:
    """Return user-defined templates for this chat, ordered by name."""
    return await _fetch_dicts(
        "SELECT id, name, description, extra_instructions, trigger_patterns, "
        "brave_search, content_type_scope, created_at, updated_at "
        "FROM templates WHERE chat_id = ? AND is_builtin = 0 ORDER BY name",
        (chat_id,),
    )


async def get_user_template_by_name(chat_id: int, name: str) -> dict | None:
    """Return a user-defined template owned by this chat, or None."""
    row = await _fetch_one(
        "SELECT id, name, description, extra_instructions, trigger_patterns, "
        "brave_search, content_type_scope, created_at, updated_at "
        "FROM templates WHERE chat_id = ? AND name = ? AND is_builtin = 0",
        (chat_id, name),
    )
    return dict(row) if row else None


async def create_user_template(
    *,
    chat_id: int,
    name: str,
    description: str = "",
    extra_instructions: str = "",
) -> dict:
    """Insert a user-defined template scoped to chat_id and return the new row."""
    tmpl_id = generate_id()
    async with connection() as conn:
        await conn.execute(
            """INSERT INTO templates
               (id, chat_id, name, description, extra_instructions, is_builtin)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (tmpl_id, chat_id, name, description, extra_instructions),
        )
        await conn.commit()
    log.info("template_created", id=tmpl_id, chat_id=chat_id, name=name)
    return {
        "id": tmpl_id,
        "name": name,
        "description": description,
        "extra_instructions": extra_instructions,
        "trigger_patterns": "",
        "brave_search": 0,
        "content_type_scope": "",
        "is_builtin": False,
    }


async def update_user_template(
    *,
    chat_id: int,
    name: str,
    description: str = "",
    extra_instructions: str = "",
) -> bool:
    """Update a user template owned by this chat. Returns True if updated."""
    return await _execute_rowcount(
        """UPDATE templates
           SET description = ?, extra_instructions = ?, updated_at = CURRENT_TIMESTAMP
           WHERE chat_id = ? AND name = ? AND is_builtin = 0""",
        (description, extra_instructions, chat_id, name),
    ) > 0


async def delete_user_template(chat_id: int, name: str) -> bool:
    """Delete a user template owned by this chat. Returns True if deleted."""
    return await _execute_rowcount(
        "DELETE FROM templates WHERE chat_id = ? AND name = ? AND is_builtin = 0",
        (chat_id, name),
    ) > 0


# ---------------------------------------------------------------------------
# Job annotations + job-tag links (issue #88 / S5)
# ---------------------------------------------------------------------------


async def get_job_annotation(job_id: str) -> dict | None:
    """Return the job_annotations row for *job_id*, or None if absent."""
    row = await _fetch_one(
        "SELECT job_id, notes, updated_at FROM job_annotations WHERE job_id = ?",
        (job_id,),
    )
    return dict(row) if row else None


async def upsert_job_annotation(job_id: str, notes: str) -> dict:
    """Insert or replace the annotation for *job_id*. Returns the saved row."""
    return await _insert_returning(
        """INSERT INTO job_annotations (job_id, notes, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(job_id) DO UPDATE SET
               notes      = excluded.notes,
               updated_at = excluded.updated_at""",
        (job_id, notes),
        "SELECT job_id, notes, updated_at FROM job_annotations WHERE job_id = ?",
        (job_id,),
    )


async def list_job_tags(job_id: str) -> list[dict]:
    """Return tags attached to *job_id* ordered by name."""
    return await _fetch_dicts(
        """SELECT t.id, t.name, t.color, t.meaning
           FROM job_tags jt
           JOIN tags t ON t.id = jt.tag_id
           WHERE jt.job_id = ?
           ORDER BY t.name""",
        (job_id,),
    )


async def batch_get_jobs(job_ids: list[str]) -> dict[str, dict]:
    """Return {job_id: job_dict} for the given IDs. Missing IDs are omitted."""
    rows = await _fetch_in("SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids)
    return {row["id"]: row for row in rows}


async def batch_get_job_annotations(job_ids: list[str]) -> dict[str, str]:
    """Return {job_id: notes} for jobs that have saved annotations."""
    rows = await _fetch_in(
        "SELECT job_id, notes FROM job_annotations WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"]: row["notes"] for row in rows}


async def batch_list_job_tags(job_ids: list[str]) -> dict[str, list[dict]]:
    """Return {job_id: [tag_dicts]} for all given job IDs (absent job = empty list)."""
    if not job_ids:
        return {}
    rows = await _fetch_in(
        """SELECT jt.job_id, t.id, t.name, t.color, t.meaning
           FROM job_tags jt
           JOIN tags t ON t.id = jt.tag_id
           WHERE jt.job_id IN ({placeholders})
           ORDER BY t.name""",
        job_ids,
    )
    result: dict[str, list[dict]] = {jid: [] for jid in job_ids}
    for row in rows:
        jid = row.pop("job_id")
        result[jid].append(row)
    return result


async def attach_job_tag(job_id: str, tag_id: str) -> bool:
    """Attach *tag_id* to *job_id*. Idempotent. Returns True."""
    await _execute("INSERT OR IGNORE INTO job_tags (job_id, tag_id) VALUES (?, ?)", (job_id, tag_id))
    return True


async def detach_job_tag(job_id: str, tag_id: str) -> bool:
    """Remove *tag_id* from *job_id*. Returns True if a row was deleted."""
    return await _execute_rowcount(
        "DELETE FROM job_tags WHERE job_id = ? AND tag_id = ?",
        (job_id, tag_id),
    ) > 0


# ---------------------------------------------------------------------------
# Spaces (issue #89 / S6)
# ---------------------------------------------------------------------------


async def create_space(*, chat_id: int, name: str, color: str) -> dict:
    """INSERT a new space row and return it as a dict."""
    space_id = generate_id()
    return await _insert_returning(
        "INSERT INTO spaces (id, chat_id, name, color) VALUES (?, ?, ?, ?)",
        (space_id, chat_id, name, color),
        "SELECT id, chat_id, name, color, created_at, updated_at FROM spaces WHERE id = ?",
        (space_id,),
    )


async def list_spaces(chat_id: int) -> list[dict]:
    """Return all spaces for chat_id ordered newest-first."""
    return await _fetch_dicts(
        "SELECT id, chat_id, name, color, created_at, updated_at "
        "FROM spaces WHERE chat_id = ? ORDER BY created_at DESC",
        (chat_id,),
    )


async def get_space(space_id: str) -> dict | None:
    """Return a single space by PK, or None."""
    row = await _fetch_one(
        "SELECT id, chat_id, name, color, created_at, updated_at FROM spaces WHERE id = ?",
        (space_id,),
    )
    return dict(row) if row else None


async def update_space(*, chat_id: int, space_id: str, name: str, color: str) -> bool:
    """UPDATE name/color for a space owned by chat_id. Returns True if updated."""
    return await _execute_rowcount(
        "UPDATE spaces SET name = ?, color = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ? AND chat_id = ?",
        (name, color, space_id, chat_id),
    ) > 0


async def delete_space(*, chat_id: int, space_id: str) -> bool:
    """DELETE a space owned by chat_id. Returns True if deleted."""
    return await _execute_rowcount(
        "DELETE FROM spaces WHERE id = ? AND chat_id = ?",
        (space_id, chat_id),
    ) > 0


async def add_space_url(*, space_id: str, job_id: str) -> bool:
    """Pin a job into a space. sort_order = max+1. Idempotent (INSERT OR IGNORE)."""
    await _execute(
        """INSERT OR IGNORE INTO space_urls (space_id, job_id, sort_order)
           VALUES (?, ?, COALESCE(
               (SELECT MAX(sort_order) FROM space_urls WHERE space_id = ?), 0
           ) + 1)""",
        (space_id, job_id, space_id),
    )
    return True


async def remove_space_url(*, space_id: str, job_id: str) -> bool:
    """Unpin a job from a space. Returns True if the row existed."""
    return await _execute_rowcount(
        "DELETE FROM space_urls WHERE space_id = ? AND job_id = ?",
        (space_id, job_id),
    ) > 0


async def reorder_space_url(*, space_id: str, job_id: str, new_sort_order: int) -> bool:
    """Update sort_order for a pinned job. Returns True if the row existed."""
    return await _execute_rowcount(
        "UPDATE space_urls SET sort_order = ? WHERE space_id = ? AND job_id = ?",
        (new_sort_order, space_id, job_id),
    ) > 0


async def list_space_urls(space_id: str, chat_id: int) -> list[dict]:
    """Return jobs pinned to a space, joined with key job fields, ordered by sort_order."""
    return await _fetch_dicts(
        """SELECT j.id, j.title, j.url, j.content_type, j.status,
                  su.sort_order, su.added_at
           FROM space_urls su
           JOIN jobs j ON j.id = su.job_id AND j.chat_id = ?
           WHERE su.space_id = ?
           ORDER BY su.sort_order ASC""",
        (chat_id, space_id),
    )


# ---------------------------------------------------------------------------
# Context blobs (issue #93 / S7)
# ---------------------------------------------------------------------------


async def create_context_blob(*, space_id: str, name: str, content: str = "") -> dict:
    """INSERT a context blob; auto-assigns sort_order = max+1. Returns the row."""
    blob_id = generate_id()
    return await _insert_returning(
        """INSERT INTO context_blobs (id, space_id, name, content, sort_order)
           VALUES (?, ?, ?, ?, COALESCE(
               (SELECT MAX(sort_order) FROM context_blobs WHERE space_id = ?), 0
           ) + 1)""",
        (blob_id, space_id, name, content, space_id),
        "SELECT id, space_id, name, content, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE id = ?",
        (blob_id,),
    )


async def list_context_blobs(space_id: str) -> list[dict]:
    """Return all context blobs for a space ordered by sort_order."""
    return await _fetch_dicts(
        "SELECT id, space_id, name, content, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE space_id = ? ORDER BY sort_order ASC",
        (space_id,),
    )


async def get_context_blob(blob_id: str) -> dict | None:
    """Return a single context blob by PK, or None."""
    row = await _fetch_one(
        "SELECT id, space_id, name, content, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE id = ?",
        (blob_id,),
    )
    return dict(row) if row else None


async def update_context_blob(*, blob_id: str, name: str, content: str) -> bool:
    """UPDATE name and content; sets updated_at. Returns True if the row existed."""
    return await _execute_rowcount(
        "UPDATE context_blobs SET name = ?, content = ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (name, content, blob_id),
    ) > 0


async def delete_context_blob(blob_id: str) -> bool:
    """DELETE a context blob. Returns True if the row existed."""
    return await _execute_rowcount("DELETE FROM context_blobs WHERE id = ?", (blob_id,)) > 0


async def reorder_context_blob(*, blob_id: str, new_sort_order: int) -> bool:
    """UPDATE sort_order for a blob. Returns True if the row existed."""
    return await _execute_rowcount(
        "UPDATE context_blobs SET sort_order = ? WHERE id = ?",
        (new_sort_order, blob_id),
    ) > 0

"""Frozen historical table shapes used by the jobs-table rebuild migrations.

SQLite cannot widen a CHECK constraint in place, so several early migrations
recreate `jobs` under a temporary name and copy the shared columns across. Each
`_VnnCREATE` / `_VnnCOLS` pair is the literal shape `jobs` had at that version —
history, not current schema. Never edit one to match a later change; that would
rewrite what an old database is migrated *through*. The live shape is
`src/db/schema.py`.
"""

from __future__ import annotations

import aiosqlite


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
    "id",
    "chat_id",
    "message_id",
    "url",
    "content_type",
    "status",
    "attempt",
    "error_msg",
    "drive_url",
    "title",
    "transcript",
    "ai_category",
    "ai_topic",
    "ai_objective",
    "ai_action_points",
    "ai_tools",
    "ai_market_data",
    "prd_auto_status",
    "prd_auto_drive_file_id",
    "prd_auto_drive_url",
    "prd_auto_json",
    "prd_intent_status",
    "prd_intent_drive_file_id",
    "prd_intent_drive_url",
    "prd_intent_json",
    "prd_intent_text",
    "prd_intent_completed_at",
    "sheets_row_id",
    "template",
    "template_analysis",
    "key_phrases",
    "validation_warning_sent",
    "template_detection_method",
    "processing_time_ms",
    "promise_gap",
    "bot_message_id",
    "freestyle_prompt",
    "created_at",
    "updated_at",
    "completed_at",
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
        # `tmp_name` is a literal from the calling migration step and `col_str`
        # comes from PRAGMA table_info; neither can carry caller input.
        await conn.execute(  # nosemgrep
            f"INSERT OR IGNORE INTO {tmp_name} ({col_str}) SELECT {col_str} FROM jobs"  # nosec B608
        )
    await conn.execute("DROP TABLE jobs")
    await conn.execute(f"ALTER TABLE {tmp_name} RENAME TO jobs")  # nosemgrep
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)"
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id)")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_chat_created ON jobs(chat_id, created_at, id)"
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url)")


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
    "id",
    "chat_id",
    "message_id",
    "url",
    "content_type",
    "status",
    "attempt",
    "error_msg",
    "drive_url",
    "title",
    "transcript",
    "ai_category",
    "ai_topic",
    "ai_objective",
    "ai_action_points",
    "ai_tools",
    "ai_market_data",
    "prd_auto_status",
    "prd_auto_drive_file_id",
    "prd_auto_drive_url",
    "prd_auto_json",
    "prd_intent_status",
    "prd_intent_drive_file_id",
    "prd_intent_drive_url",
    "prd_intent_json",
    "prd_intent_text",
    "prd_intent_completed_at",
    "sheets_row_id",
    "template",
    "template_analysis",
    "key_phrases",
    "validation_warning_sent",
    "template_detection_method",
    "processing_time_ms",
    "promise_gap",
    "bot_message_id",
    "freestyle_prompt",
    "created_at",
    "updated_at",
    "completed_at",
]


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
    links                       TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error'))
)"""


_V17_COLS = [
    "id",
    "chat_id",
    "message_id",
    "url",
    "content_type",
    "status",
    "attempt",
    "error_msg",
    "drive_url",
    "title",
    "transcript",
    "ai_category",
    "ai_topic",
    "ai_objective",
    "ai_action_points",
    "ai_tools",
    "ai_market_data",
    "prd_auto_status",
    "prd_auto_drive_file_id",
    "prd_auto_drive_url",
    "prd_auto_json",
    "prd_intent_status",
    "prd_intent_drive_file_id",
    "prd_intent_drive_url",
    "prd_intent_json",
    "prd_intent_text",
    "prd_intent_completed_at",
    "sheets_row_id",
    "template",
    "template_analysis",
    "key_phrases",
    "validation_warning_sent",
    "template_detection_method",
    "processing_time_ms",
    "promise_gap",
    "bot_message_id",
    "freestyle_prompt",
    "best_frame_index",
    "platform",
    "video_id",
    "og_image_url",
    "summary",
    "links",
    "created_at",
    "updated_at",
    "completed_at",
]


# v22 → v23: tighten telegram_delivery to a stored domain of {'off','on'} (#231).
# 'retroactive' is a request-only action resolved at the API boundary (it sends
# existing outputs, then persists 'on'); it must never be a stored state. The
# column was added by ALTER (v20→v21) with no CHECK, so migrated DBs have no
# constraint at all — this rebuild adds CHECK(telegram_delivery IN ('off','on')).
# SQLite can't ALTER a CHECK, so the table is rebuilt; foreign_keys is disabled
# across the DROP/RENAME so the ON DELETE CASCADE children of jobs aren't wiped.
_V23_CREATE = """CREATE TABLE IF NOT EXISTS jobs_v23 (
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
    links                       TEXT,
    telegram_delivery           TEXT NOT NULL DEFAULT 'on',
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document')),
    CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error')),
    CHECK(telegram_delivery IN ('off','on'))
)"""


_V23_COLS = _V17_COLS + ["telegram_delivery"]


async def _chat_state_allows(conn: aiosqlite.Connection, mode: str) -> bool:
    cur = await conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='chat_state'"
    )
    row = await cur.fetchone()
    return bool(row and row[0] and mode in row[0])


# v32 → v33: widen content_type CHECK to include 'link' for the Link pipeline.
# SQLite can't ALTER a CHECK, so rebuild the table via selective column copy.
# Reusing the v23 schema is safe: none of v24–v32 touch the jobs table (they
# alter users/links/tags and add OAuth tables), so _V23_CREATE is still current.
_V33_CREATE = _V23_CREATE.replace("jobs_v23", "jobs_v33").replace(
    "CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document')),",
    "CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document', 'link')),")

_V33_COLS = _V23_COLS


# v34 → v35: park pre-approval submissions as held jobs (#449).
_V35_CREATE = _V33_CREATE.replace("jobs_v33", "jobs_v35").replace(
    "CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),",
    "CHECK(status IN ('held','pending','processing','transcript_done','enriching','done','error','cancelled')),")

_V35_COLS = _V33_COLS


# v36 → v37: transient unsized video rows (#467) before worker duration resolution.
_V37_CREATE = (
    _V35_CREATE.replace("jobs_v35", "jobs_v37")
    .replace(
        "telegram_delivery           TEXT NOT NULL DEFAULT 'on',\n"
        "    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
        "telegram_delivery           TEXT NOT NULL DEFAULT 'on',\n"
        "    code                        TEXT,\n"
        "    code_lang                   TEXT,\n"
        "    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,",
    )
    .replace(
        "CHECK(content_type IN ('short', 'long', 'article', 'repo', 'document', 'link')),",
        "CHECK(content_type IN ('short', 'long', 'unsized', 'article', 'repo', 'document', 'link')),",
    )
)

_V37_COLS = _V35_COLS + ["code", "code_lang"]



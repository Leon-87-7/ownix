"""The migration steps themselves, oldest first.

Each step declares its own target version via `@migration(N)` / `sql(N, ...)`,
so file position carries no meaning — add a new one at the bottom with the next
number, or anywhere else; the registry checks it either way. See
`src/db/migrations/_registry.py` for why this is declared rather than inferred.
"""

from __future__ import annotations

import aiosqlite

from src.config import settings
from src.db.migrations._registry import migration, sql
from src.db.core import _table_columns
from src.db.migrations._snapshots import (
    _chat_state_allows,
    _rebuild_jobs_table,
    _V6_COLS,
    _V6_CREATE,
    _V7_COLS,
    _V7_CREATE,
    _V17_COLS,
    _V17_CREATE,
    _V23_COLS,
    _V23_CREATE,
    _V33_COLS,
    _V33_CREATE,
    _V35_COLS,
    _V35_CREATE,
    _V37_COLS,
    _V37_CREATE,
)
from src.db.schema import (
    _EMAIL_DIGEST_PAYLOADS_SLUG_INDEX_SQL,
    _EMAIL_DIGEST_PAYLOADS_TABLE_SQL,
    _EMAIL_DIGEST_PAYLOADS_WATCH_INDEX_SQL,
    _NEWSLETTER_WATCHES_INDEX_SQL,
    _NEWSLETTER_WATCHES_TABLE_SQL,
    _PUBLICATION_ISSUES_TABLE_SQL,
    _PUBLICATIONS_TABLE_SQL,
)

    # v0 → v1: template system, promise_gap, bot_message_id (post-launch columns)
sql(1, [
        "ALTER TABLE jobs ADD COLUMN template TEXT",
        "ALTER TABLE jobs ADD COLUMN template_analysis TEXT",
        "ALTER TABLE jobs ADD COLUMN key_phrases TEXT",
        "ALTER TABLE jobs ADD COLUMN validation_warning_sent INTEGER DEFAULT 0",
        "ALTER TABLE jobs ADD COLUMN template_detection_method TEXT",
        "ALTER TABLE jobs ADD COLUMN promise_gap TEXT",
        "ALTER TABLE jobs ADD COLUMN bot_message_id INTEGER",
    ])

    # v1 → v2: freestyle Gemini prompt (issue #51 / ADR-0012)
sql(2, [
        "ALTER TABLE jobs ADD COLUMN freestyle_prompt TEXT",
    ])

    # v2 → v3: expand chat_state.mode CHECK to include 'awaiting_freestyle' (issue #53 / ADR-0012)
sql(3, [
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
    ])

    # v3 → v4: per-chat article allowlist (issue #61)
sql(4, [
        """CREATE TABLE IF NOT EXISTS allowed_domains (
            chat_id     INTEGER NOT NULL,
            domain      TEXT NOT NULL,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, domain)
        )""",
    ])

    # v4 → v5: Jina Reader markdown cache (issue #60)
sql(5, [
        """CREATE TABLE IF NOT EXISTS markdown_cache (
            url        TEXT PRIMARY KEY,
            content    TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
    ])



@migration(6)
async def _migrate_v5_v6(conn: aiosqlite.Connection) -> None:
    """Expand content_type CHECK to include 'article' via selective column copy."""
    await _rebuild_jobs_table(conn, _V6_CREATE, "jobs_v6", _V6_COLS)



@migration(7)
async def _migrate_v6_v7(conn: aiosqlite.Connection) -> None:
    """Expand content_type CHECK to include 'repo'."""
    await _rebuild_jobs_table(conn, _V7_CREATE, "jobs_v7", _V7_COLS)



@migration(8)
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


# v8 → v9: users table for web dashboard auth (issue #84)
sql(9, 
    [
        """CREATE TABLE IF NOT EXISTS users (
        tg_id       INTEGER PRIMARY KEY,
        username    TEXT,
        first_name  TEXT NOT NULL,
        last_name   TEXT,
        photo_url   TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    ]
)


# v9 → v10: tags table (issue #87 / S4)
sql(10, 
    [
        """CREATE TABLE IF NOT EXISTS tags (
        id         TEXT PRIMARY KEY,
        chat_id    INTEGER NOT NULL,
        name       TEXT NOT NULL,
        meaning    TEXT NOT NULL DEFAULT '',
        color      TEXT NOT NULL DEFAULT '#6366f1',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(chat_id, name)
    )""",
    ]
)


# v10 → v11: user-defined enrichment templates (issue #90)
sql(11, 
    [
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
    ]
)


# v11 → v12: job annotations + job-tag links (issue #88 / S5)
sql(12, 
    [
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
    ]
)


# v12 → v13: spaces + space_urls tables (issue #89 / S6)
sql(13, 
    [
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
    ]
)


# v13 → v14: context_blobs table (issue #93 / S7)
sql(14, 
    [
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
    ]
)


# v14 -> v15: job media metadata and persisted thumbnails (issues #146/#147)
sql(15, 
    [
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
    ]
)


# v15 -> v16: per-chat web dashboard settings (issue #171)
sql(16, 
    [
        """CREATE TABLE IF NOT EXISTS user_settings (
        chat_id    INTEGER NOT NULL,
        key        TEXT NOT NULL,
        value      TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (chat_id, key)
    )""",
    ]
)



# v15 → v16: vision summary column for short jobs (issue #164)
sql(17, 
    [
        "ALTER TABLE jobs ADD COLUMN summary TEXT",
    ]
)



@migration(18)
async def _migrate_v16_v17(conn: aiosqlite.Connection) -> None:
    """Widen content_type CHECK to include 'document' via selective column copy."""
    await _rebuild_jobs_table(conn, _V17_CREATE, "jobs_v17", _V17_COLS)


# v17 → v18: per-space curated icon (issue #189)
sql(19, ["ALTER TABLE spaces ADD COLUMN icon TEXT NOT NULL DEFAULT 'folder'"])


# v18 → v19: repo-node metadata refresh (issue #198)
sql(20, 
    [
        "ALTER TABLE links ADD COLUMN stars INTEGER",
        "ALTER TABLE links ADD COLUMN pushed_at TEXT",
        "ALTER TABLE links ADD COLUMN archived INTEGER NOT NULL DEFAULT 0",
    ]
)


# v19 → v20: persist enriched short-video links on jobs (issue #213)
sql(21, 
    [
        "ALTER TABLE jobs ADD COLUMN links TEXT",
    ]
)


# v20 → v21: Doc Parser dashboard delivery state and output index (ADR-0029).
sql(22, 
    [
        "ALTER TABLE jobs ADD COLUMN telegram_delivery TEXT NOT NULL DEFAULT 'on'",
        """CREATE TABLE IF NOT EXISTS document_outputs (
        id          TEXT PRIMARY KEY,
        job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        kind        TEXT NOT NULL,
        gcs_key     TEXT NOT NULL,
        title       TEXT NOT NULL DEFAULT '',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK(kind IN ('raw_txt','raw_md','summary','clean','freestyle'))
    )""",
        "CREATE INDEX IF NOT EXISTS idx_document_outputs_job_id ON document_outputs(job_id, created_at)",
    ]
)


# v21 → v22: dedup singular document outputs and enforce one-per-(job,kind)
# (ADR-0029). Freestyle stays multi-row; raw/summary/clean upsert in place.
sql(23, 
    [
        # Drop pre-existing duplicate singular rows (keep the earliest id) so the
        # unique index can be created without violating it.
        "DELETE FROM document_outputs WHERE kind <> 'freestyle' AND id NOT IN "
        "(SELECT MIN(id) FROM document_outputs WHERE kind <> 'freestyle' GROUP BY job_id, kind)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_document_outputs_singular ON document_outputs(job_id, kind) WHERE kind <> 'freestyle'",
    ]
)



@migration(24)
async def _migrate_v22_v23(conn: aiosqlite.Connection) -> None:
    """Tighten telegram_delivery CHECK to {'off','on'}; preserve FK children (#231)."""
    # A real v22 DB always has telegram_delivery (added v20→v21); guard the check
    # on its presence so the rebuild is robust on odd/replayed DBs that lack it.
    cur = await conn.execute("PRAGMA table_info(jobs)")
    has_col = any(row[1] == "telegram_delivery" for row in await cur.fetchall())
    if has_col:
        # Fail loudly rather than silently dropping/coercing a stored 'retroactive'.
        cur = await conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE telegram_delivery = 'retroactive'"
        )
        row = await cur.fetchone()
        stranded = row[0] if row else 0
        if stranded:
            raise RuntimeError(
                f"Cannot tighten telegram_delivery CHECK: {stranded} job(s) hold "
                "'retroactive', which has no stored meaning. Resolve them to 'off'/'on' "
                "before migrating."
            )
    # PRAGMA foreign_keys is a no-op inside a transaction, so commit out of any
    # open one before toggling. With FK enforcement off, DROP TABLE jobs no longer
    # cascade-deletes its ON DELETE CASCADE children (document_outputs, etc.).
    await conn.commit()
    await conn.execute("PRAGMA foreign_keys=OFF")
    try:
        await _rebuild_jobs_table(conn, _V23_CREATE, "jobs_v23", _V23_COLS)
        await conn.commit()
    finally:
        # Re-enable FK even if the rebuild raised, so a partially-failed upgrade
        # can't leave enforcement off for the rest of the connection. Roll back any
        # open transaction first — PRAGMA foreign_keys is a no-op inside one.
        await conn.rollback()
        await conn.execute("PRAGMA foreign_keys=ON")



@migration(25)
async def _migrate_v23_v24(conn: aiosqlite.Connection) -> None:
    """Add invite-gate user fields and awaiting_email chat state (#254)."""
    cur = await conn.execute("PRAGMA table_info(users)")
    existing_user_cols = {row[1] for row in await cur.fetchall()}

    if "email" not in existing_user_cols:
        await conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "status" not in existing_user_cols:
        await conn.execute(
            "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'pending' "
            "CHECK(status IN ('pending','approved','blocked'))"
        )
    await conn.execute("UPDATE users SET status = 'approved'")

    if not await _chat_state_allows(conn, "awaiting_email"):
        await conn.execute("DROP TABLE IF EXISTS chat_state_v24")
        await conn.execute("""
            CREATE TABLE chat_state_v24 (
                chat_id    INTEGER PRIMARY KEY,
                mode       TEXT NOT NULL,
                job_id     TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle', 'awaiting_email'))
            )
        """)
        await conn.execute(
            """
            INSERT INTO chat_state_v24 (chat_id, mode, job_id, created_at, expires_at)
            SELECT chat_id, mode, job_id, created_at, expires_at FROM chat_state
            """
        )
        await conn.execute("DROP TABLE chat_state")
        await conn.execute("ALTER TABLE chat_state_v24 RENAME TO chat_state")


# v24 → v25: encrypted per-user Google OAuth refresh tokens (#204).
sql(26, [
    """CREATE TABLE IF NOT EXISTS google_oauth_tokens (
        chat_id             INTEGER PRIMARY KEY,
        encrypted_token     TEXT NOT NULL,
        scopes              TEXT NOT NULL DEFAULT '',
        revoked_notified_at TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
])


# v25 → v26: DB-backed Google OAuth state tokens for multi-worker callbacks.
sql(27, [
    """CREATE TABLE IF NOT EXISTS google_oauth_states (
        state      TEXT PRIMARY KEY,
        chat_id    INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
])


# v26 → v27: standalone link identity — per-URL description (#381 / docs/TASK.md task 32).
sql(28, [
    "ALTER TABLE links ADD COLUMN description TEXT",
])


# v27 → v28: link tags join table (#382).
sql(29, [
    """CREATE TABLE IF NOT EXISTS link_tags (
        link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
        tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (link_id, tag_id)
    )""",
])


# v28 → v29: remap removed orange/yellow-band tag colors to the nearest allowed
# hue (#383). The whole band sits closest to the palette's red at ~22° — mapping
# to violet would jump ~200° of hue.
sql(30, [
    "UPDATE tags SET color = '#f87171' WHERE lower(color) IN ('#eab308', '#f97316', '#fcd34d', '#fef3c7', '#a16207')",
])


# v29 → v30: optional Lucide tag icon names (#386).
sql(31, [
    "ALTER TABLE tags ADD COLUMN icon TEXT",
])


# v30 → v31: unique URL constraint so concurrent ingests can upsert atomically
# (PR #390 review). Dedup first — keep the earliest row per URL.
sql(32, [
    "DELETE FROM links WHERE rowid NOT IN (SELECT MIN(rowid) FROM links GROUP BY url)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_links_url_unique ON links(url)",
])


# v31 → v32: cached og:image for the Links preview panel. NULL = not yet
# checked, '' = checked with no og:image found, non-empty = the resolved URL.
sql(33, [
    "ALTER TABLE links ADD COLUMN og_image_url TEXT",
])



@migration(34)
async def _migrate_v32_v33(conn: aiosqlite.Connection) -> None:
    """Widen content_type CHECK to include 'link' via selective column copy."""
    # Same FK dance as _migrate_v22_v23 (#231): with foreign_keys ON, DROP TABLE
    # jobs implicit-DELETEs every row first, cascade-wiping the ON DELETE CASCADE
    # children (document_outputs, job_thumbnails). PRAGMA foreign_keys is a no-op
    # inside a transaction, so commit out of any open one before toggling.
    await conn.commit()
    await conn.execute("PRAGMA foreign_keys=OFF")
    try:
        await _rebuild_jobs_table(conn, _V33_CREATE, "jobs_v33", _V33_COLS)
        await conn.commit()
    finally:
        await conn.rollback()
        await conn.execute("PRAGMA foreign_keys=ON")


# v33 → v34: purge_tasks outbox for durable Job purge enqueuing (issue #2)
sql(35, 
    [
        """CREATE TABLE IF NOT EXISTS purge_tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id          TEXT NOT NULL,
            chat_id         INTEGER NOT NULL,
            task_payload    TEXT NOT NULL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            enqueued_at     TIMESTAMP
        )""",
        "CREATE INDEX IF NOT EXISTS idx_purge_tasks_enqueued ON purge_tasks(enqueued_at)",
    ]
)



@migration(36)
async def _migrate_v34_v35(conn: aiosqlite.Connection) -> None:
    """Widen the job status CHECK to include held via selective column copy."""
    # Same FK dance as _migrate_v22_v23 (#231): with foreign_keys ON, DROP TABLE
    # jobs implicit-DELETEs every row first, cascade-wiping the ON DELETE CASCADE
    # children (document_outputs, job_thumbnails). PRAGMA foreign_keys is a no-op
    # inside a transaction, so commit out of any open one before toggling.
    await conn.commit()
    await conn.execute("PRAGMA foreign_keys=OFF")
    try:
        await _rebuild_jobs_table(conn, _V35_CREATE, "jobs_v35", _V35_COLS)
        await conn.commit()
    finally:
        await conn.rollback()
        await conn.execute("PRAGMA foreign_keys=ON")


# v35 → v36: persist short-pipeline code snippets (#462 follow-up) so the
# dashboard detail page can show them — previously only sent to Telegram/Drive.
sql(37, 
    [
        "ALTER TABLE jobs ADD COLUMN code TEXT",
        "ALTER TABLE jobs ADD COLUMN code_lang TEXT",
    ]
)



@migration(38)
async def _migrate_v36_v37(conn: aiosqlite.Connection) -> None:
    """Widen content_type CHECK to include transient unsized rows."""
    await conn.commit()
    await conn.execute("PRAGMA foreign_keys=OFF")
    try:
        await _rebuild_jobs_table(conn, _V37_CREATE, "jobs_v37", _V37_COLS)
        await conn.commit()
    finally:
        await conn.rollback()
        await conn.execute("PRAGMA foreign_keys=ON")



# v37 → v38: persist link ownership on links and dedupe per tenant (#499).
@migration(39)
async def _migrate_v37_v38(conn: aiosqlite.Connection) -> None:
    cols = await _table_columns(conn, "links")
    if "chat_id" not in cols:
        await conn.execute("ALTER TABLE links ADD COLUMN chat_id INTEGER")
    await conn.execute(
        """
        UPDATE links
           SET chat_id = COALESCE(
               (SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job),
               ?
           )
         WHERE chat_id IS NULL
        """,
        (settings.OPERATOR_CHAT_ID,),
    )
    await conn.execute("DROP INDEX IF EXISTS idx_links_url_unique")
    await conn.execute(
        "DELETE FROM links WHERE rowid NOT IN "
        "(SELECT MIN(rowid) FROM links GROUP BY chat_id, url)"
    )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_links_chat_url_unique ON links(chat_id, url)"
    )


# v38 → v39: append-only audit log of admin / security-relevant actions.
# Named so tests can locate this step by identity (its index shifts as later
# migrations are appended). Triggers make the append-only contract enforced.
_AUDIT_LOG_MIGRATION = [
    """CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id     INTEGER,
        action      TEXT NOT NULL,
        target_type TEXT,
        target_id   TEXT,
        metadata    TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_chat ON audit_log(chat_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_target ON audit_log(target_type, target_id)",
    """CREATE TRIGGER IF NOT EXISTS audit_log_no_update
       BEFORE UPDATE ON audit_log
       BEGIN
           SELECT RAISE(ABORT, 'audit_log is append-only');
       END""",
    """CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
       BEFORE DELETE ON audit_log
       BEGIN
           SELECT RAISE(ABORT, 'audit_log is append-only');
       END""",
]

sql(40, _AUDIT_LOG_MIGRATION)


# v39 → v40: on-demand "/checklists" command — one inline Gemini call per
# invocation, cached directly on the job row. Checklist persistence is a
# fields-only update because normal job progression can overlap generation
# (see docs/superpowers/plans/2026-08-11-checklists-command.md).
sql(41, [
    "ALTER TABLE jobs ADD COLUMN checklists_md TEXT",
    "ALTER TABLE jobs ADD COLUMN checklists_generated_at TEXT",
])


# v40 → v41: retain a remote Document's submitted URL as its URL-only dedup
# identity while `jobs.url` continues to hold the content-addressed storage key.
sql(42, [
    "ALTER TABLE jobs ADD COLUMN source_url TEXT",
    "CREATE INDEX IF NOT EXISTS idx_jobs_source_url ON jobs(source_url)",
])


# v41 → v42: the dashboard lets a user rename a job's title. `original_title`
# snapshots the pipeline-derived title on first rename so clearing the field
# later restores it (rather than clearing to NULL/the URL fallback).
sql(43, [
    "ALTER TABLE jobs ADD COLUMN original_title TEXT",
])


# v42 → v43: "GoTo" quick-jump — any number of a user's own tags can be pinned
# (command launcher's GT shortcut lists links carrying a pinned tag). Nothing
# is seeded; every tag starts unpinned.
sql(44, [
    "ALTER TABLE tags ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0",
])



# v43 → v44: widen users.status CHECK to add 'deleting' — the exclusivity lock
# self-serve account deletion holds while it runs, so every other account-write
# route (gated on status == 'approved') rejects concurrent writes during
# cleanup. SQLite can't ALTER a CHECK, so rebuild via selective column copy.
#
# The five DDL/DML statements below are wrapped in one explicit transaction:
# without BEGIN, each DDL statement auto-commits as it runs (PRAGMA
# user_version only advances after _run_migrations fully returns), so a
# crash between DROP TABLE users and the RENAME, followed by a restart,
# would rerun this migration from `DROP TABLE IF EXISTS users_v44` with the
# original `users` table already gone — destroying every user row. SQLite
# supports transactional DDL, so BEGIN/COMMIT/ROLLBACK make the whole
# rebuild all-or-nothing.
@migration(45)
async def _migrate_v43_v44(conn: aiosqlite.Connection) -> None:
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute("DROP TABLE IF EXISTS users_v44")
        await conn.execute(
            """
            CREATE TABLE users_v44 (
                tg_id       INTEGER PRIMARY KEY,
                username    TEXT,
                first_name  TEXT NOT NULL,
                last_name   TEXT,
                photo_url   TEXT,
                email       TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(status IN ('pending','approved','blocked','deleting'))
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO users_v44 (tg_id, username, first_name, last_name, photo_url,
                                    email, status, created_at, updated_at)
            SELECT tg_id, username, first_name, last_name, photo_url,
                   email, status, created_at, updated_at
              FROM users
            """
        )
        await conn.execute("DROP TABLE users")
        await conn.execute("ALTER TABLE users_v44 RENAME TO users")
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


# v44 → v45: newsletter email digest subscriptions, candidates, and payloads.
# rollback: DROP TABLE email_digest_payloads; DROP TABLE digest_candidates; DROP TABLE newsletter_subscriptions.
#
# A callable (not a plain SQL list) since the `email_digest_payloads` step
# must be guarded: a database that was fresh-installed by *today's* SCHEMA_SQL
# (issue #609 on) already has this table in the newer watch-based shape
# before this old migration step ever runs — e.g. a test that fresh-installs
# then rewinds PRAGMA user_version to replay from here. `CREATE TABLE IF NOT
# EXISTS` would silently no-op against that newer table, and the historical
# `subscription_id` index right after it would then fail with "no such
# column". Checked-then-skip keeps this step exactly as it always behaved for
# a real, sequential upgrade (table genuinely absent -> create old shape),
# while doing nothing on top of an already-newer table, which is correct:
# `_migrate_newsletter_archive_polling` further down the chain is what
# reshapes it either way.
@migration(46)
async def _migrate_email_digest_subscriptions_candidates_payloads(
    conn: aiosqlite.Connection,
) -> None:
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS newsletter_subscriptions (
        id               TEXT PRIMARY KEY,
        chat_id          INTEGER NOT NULL,
        name             TEXT NOT NULL,
        sender_email     TEXT NOT NULL,
        alias_local_part TEXT NOT NULL UNIQUE,
        space_id         TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_newsletter_subscriptions_chat_id "
        "ON newsletter_subscriptions(chat_id)"
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS digest_candidates (
        id            TEXT PRIMARY KEY,
        space_id      TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
        url           TEXT NOT NULL,
        canonical_url TEXT NOT NULL,
        title         TEXT,
        thumbnail_url TEXT,
        status        TEXT NOT NULL DEFAULT 'pending',
        job_id        TEXT REFERENCES jobs(id) ON DELETE SET NULL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CHECK(status IN ('pending','promoting','promoted','dismissed')),
        UNIQUE(space_id, canonical_url)
    )"""
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_digest_candidates_space_status "
        "ON digest_candidates(space_id, status, created_at)"
    )
    table_cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='email_digest_payloads'"
    )
    if await table_cur.fetchone() is None:
        await conn.execute(
            """CREATE TABLE email_digest_payloads (
            job_id          TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
            receipt_key     TEXT NOT NULL,
            subscription_id TEXT REFERENCES newsletter_subscriptions(id) ON DELETE SET NULL,
            subject         TEXT,
            html            TEXT,
            text            TEXT,
            UNIQUE(subscription_id, receipt_key)
        )"""
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_email_digest_payloads_subscription_id "
            "ON email_digest_payloads(subscription_id)"
        )

# v44 → v45: long-video screenshot capture and cached duration (#580/#583).
sql(47, [
    "ALTER TABLE jobs ADD COLUMN screenshots_status TEXT",
    "ALTER TABLE jobs ADD COLUMN screenshots_drive_url TEXT",
    "ALTER TABLE jobs ADD COLUMN screenshots_drive_folder_id TEXT",
    "ALTER TABLE jobs ADD COLUMN screenshots_generated_at TIMESTAMP",
    "ALTER TABLE jobs ADD COLUMN video_duration_seconds REAL",
])


# v45 → v46: transcript_drive_url for symmetric transcript/enrichment Drive
# tracking (ADR-0057) — drive_url is always the enrichment doc.
sql(48, [
    "ALTER TABLE jobs ADD COLUMN transcript_drive_url TEXT",
])


# Newsletter digest moves from inbound email to public-archive polling
# (ADR-0060, PLAN.md §1 / issue #609). newsletter_subscriptions never
# successfully ingested an issue, so its rows are dropped, not migrated.
# Teardown order matters: legacy email_digest:% jobs and their payload rows
# first (jobs.id -> email_digest_payloads.job_id cascades), then each
# subscription's backing Space (spaces -> digest_candidates/space_urls/
# context_blobs/newsletter_subscriptions all cascade on space_id), then the
# now-empty newsletter_subscriptions table itself. Dropping the table first
# would orphan every space and candidate, because the cascade runs
# spaces -> subscription, not the reverse. email_digest_payloads is then
# rebuilt: subject/html/text drop (the issue body now lives once in
# publication_issues.body_html); watch_id/publication_id/slug/context_md are
# added, with the composite FK the missing-delivery join and body-cleanup
# predicate both key on.
#
# 2026-09-08 production incident: this migration originally lived right
# after _migrate_email_digest_subscriptions_candidates_payloads (near the
# top of the migrations section), which put it at list-index 46 — BEHIND
# the two migrations above (screenshot capture / transcript_drive_url),
# which sit lower in this file despite predating it. Since _MIGRATIONS'
# runtime order is file position, not the version numbers named in each
# migration's own comment, that placement put this migration at a version
# slot production had already passed (current_version=48 at the time),
# so `_run_migrations`' `_MIGRATIONS[current_version:]` slice skipped it
# forever — email_digest_payloads never got rebuilt with watch_id, and
# every startup crashed downstream when other code assumed it had run.
# Appending a new migration ANYWHERE other than after the last existing
# `_MIGRATIONS.append(...)` call in file order silently reassigns every
# migration physically after it to a different version number than
# production already recorded. Always append here, at the true end.
# rollback: restore backup
@migration(49)
async def _migrate_newsletter_archive_polling(conn: aiosqlite.Connection) -> None:
    await conn.execute("BEGIN IMMEDIATE")
    try:
        table_cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = {row[0] for row in await table_cur.fetchall()}

        # Guarded rather than unconditional: some existing migration tests
        # build a minimal ad-hoc `jobs`/`spaces` shape (just enough columns
        # for the one migration under test) and replay the *entire* chain
        # from an old user_version, so a bare `DELETE FROM jobs WHERE
        # url LIKE ...` would 500 on "no such column: url" against a fixture
        # that never had a url column to begin with. A real database has
        # always had both, so this only ever short-circuits synthetic tests.
        if "jobs" in table_names and "url" in await _table_columns(conn, "jobs"):
            await conn.execute("DELETE FROM jobs WHERE url LIKE 'email_digest:%'")
        if "newsletter_subscriptions" in table_names and "spaces" in table_names:
            await conn.execute(
                "DELETE FROM spaces WHERE id IN (SELECT space_id FROM newsletter_subscriptions)"
            )
        await conn.execute("DROP TABLE IF EXISTS newsletter_subscriptions")
        await conn.execute("DROP TABLE IF EXISTS email_digest_payloads")

        # Same string objects SCHEMA_SQL splices in for a fresh install — kept
        # identical on purpose so a migrated database's sqlite_master output
        # matches a fresh one exactly (issue #609 acceptance criteria).
        await conn.execute(_PUBLICATIONS_TABLE_SQL)
        await conn.execute(_PUBLICATION_ISSUES_TABLE_SQL)
        await conn.execute(_NEWSLETTER_WATCHES_TABLE_SQL)
        await conn.execute(_NEWSLETTER_WATCHES_INDEX_SQL)
        await conn.execute(_EMAIL_DIGEST_PAYLOADS_TABLE_SQL)
        await conn.execute(_EMAIL_DIGEST_PAYLOADS_WATCH_INDEX_SQL)
        await conn.execute(_EMAIL_DIGEST_PAYLOADS_SLUG_INDEX_SQL)
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


# Context blobs gain source_url so the dashboard can link a Gemini-authored
# context note back to the newsletter issue it was generated from (#614
# follow-up). Always append new migrations here, at the true end of this
# file — see the 2026-09-08 incident note above _migrate_newsletter_archive_polling.
# Guarded like that migration: some tests replay the full chain from a
# synthetic old-version fixture that never created context_blobs at all
# (it's built at v13->v14, long after the versions those fixtures start from).
@migration(50)
async def _migrate_context_blobs_source_url(conn: aiosqlite.Connection) -> None:
    table_cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='context_blobs'"
    )
    if await table_cur.fetchone() is None:
        return
    # A fresh install runs SCHEMA_SQL (which already has source_url) before
    # replaying every migration from version 0, so this guard is required,
    # not defensive extra.
    col_cur = await conn.execute("PRAGMA table_info(context_blobs)")
    columns = {row[1] for row in await col_cur.fetchall()}
    if "source_url" in columns:
        return
    await conn.execute("ALTER TABLE context_blobs ADD COLUMN source_url TEXT")
    await conn.commit()



# Non-Telegram identity is additive: existing ownership remains keyed by the
# historical users.tg_id/chat_id columns (ADR-0061).
@migration(51)
async def _migrate_identity_links(conn: aiosqlite.Connection) -> None:
    table_cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    if await table_cur.fetchone() is None:
        return
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS identity_links (
            provider TEXT NOT NULL,
            subject TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(provider, subject),
            FOREIGN KEY(owner_id) REFERENCES users(tg_id) ON DELETE CASCADE
        )"""
    )
    # A case-insensitive duplicate here makes SQLite raise a bare
    # IntegrityError on the CREATE UNIQUE INDEX below, aborting startup with
    # no indication of which rows to fix. Name them up front instead.
    dupe_cur = await conn.execute(
        "SELECT LOWER(email) AS e, COUNT(*) AS n FROM users "
        "WHERE email IS NOT NULL GROUP BY LOWER(email) HAVING COUNT(*) > 1"
    )
    duplicates = [row[0] for row in await dupe_cur.fetchall()]
    if duplicates:
        raise RuntimeError(
            "Cannot add the identity_links migration: users.email already has "
            f"case-insensitive duplicates ({', '.join(duplicates)}) — resolve "
            "them manually before this migration can run."
        )
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_nocase "
        "ON users(email COLLATE NOCASE) WHERE email IS NOT NULL"
    )
    await conn.commit()



# Persists the job→link key that `_add_link_ids` already resolves on every jobs
# request and then discards. Tags live on links (link_tags), so without a stored
# key there is nothing for SQL to JOIN on — which is why tag filtering could only
# ever run in-memory, i.e. below the client-mode job cap.
@migration(52)
async def _migrate_jobs_link_id(conn: aiosqlite.Connection) -> None:
    table_cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('jobs', 'links')"
    )
    tables = {row[0] for row in await table_cur.fetchall()}
    if "jobs" not in tables:
        return
    cur = await conn.execute("PRAGMA table_info(jobs)")
    columns = {row[1] for row in await cur.fetchall()}
    if "link_id" not in columns:
        await conn.execute("ALTER TABLE jobs ADD COLUMN link_id TEXT")
    if "links" not in tables:
        # Databases old enough to predate the links table have nothing to
        # backfill from. Harmless: the column exists, and the read path fills
        # it in as jobs are listed.
        await conn.commit()
        return
    # The backfill has to be exhaustive, not best-effort. Tag-filtered SQL
    # matches ON link_id, so a job left NULL can never appear in the very query
    # that would heal it — it would just be silently missing from tag results
    # forever. Read-path healing only ever covers the newest page.
    from src.brain import normalize_url

    link_backed = ("link", "article", "repo")
    cur_jobs = await conn.execute(
        # Only `?` marks are interpolated; the values bind from `link_backed`.
        "SELECT id, chat_id, url FROM jobs "  # nosec B608
        f"WHERE link_id IS NULL AND content_type IN ({','.join('?' * len(link_backed))})",
        link_backed,
    )
    pending = await cur_jobs.fetchall()
    if not pending:
        await conn.commit()
        return
    cur_links = await conn.execute("SELECT id, chat_id, url FROM links")
    link_by_key = {(row[1], row[2]): row[0] for row in await cur_links.fetchall()}
    updates = []
    for job_id, chat_id, url in pending:
        link_id = link_by_key.get((chat_id, normalize_url(url)))
        if link_id:
            updates.append((link_id, job_id))
    # Chunked so a large backlog doesn't build one enormous statement batch.
    for start in range(0, len(updates), 500):
        await conn.executemany(
            "UPDATE jobs SET link_id = ? WHERE id = ?", updates[start : start + 500]
        )
    await conn.commit()


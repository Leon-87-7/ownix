"""Database lifecycle: create, migrate, back up, restore, and wait for ready.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from src.config import settings
from src.db.core import log, _table_columns
from src.db.migrations import MIGRATIONS, run_migrations
from src.db.schema import (
    SCHEMA_SQL,
    _EMAIL_DIGEST_PAYLOADS_SLUG_INDEX_SQL,
    _EMAIL_DIGEST_PAYLOADS_WATCH_INDEX_SQL,
)
from src.db.users import _upsert_minimal_user

#: How many pre-migration snapshots to keep on disk.
MIGRATION_BACKUP_RETENTION = 10

async def _snapshot_database(
    conn: aiosqlite.Connection, db_path: Path, from_version: int
) -> Path:
    """Create one WAL-consistent, pre-migration backup and enforce retention."""
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / (
        f"{db_path.stem}_v{from_version}_to_v{len(MIGRATIONS)}_{timestamp}.db"
    )
    with closing(sqlite3.connect(backup_path)) as destination:
        await conn.backup(destination)

    backups = sorted(
        backup_dir.glob(f"{db_path.stem}_v*_to_v*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for stale in backups[MIGRATION_BACKUP_RETENTION:]:
        stale.unlink()
    log.info("db_migration_snapshot_created", path=str(backup_path))
    return backup_path


def _restore_database_file(backup_path: Path, db_path: Path) -> int:
    """Validate *backup_path*, then atomically install it without stale WAL state."""
    try:
        with closing(sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)) as backup:
            integrity = backup.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise RuntimeError(f"backup integrity_check failed: {integrity!r}")
            version = int(backup.execute("PRAGMA user_version").fetchone()[0])
        restore_tmp = db_path.with_name(f".{db_path.name}.restore")
        with (
            closing(sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)) as source,
            closing(sqlite3.connect(restore_tmp)) as destination,
        ):
            source.backup(destination)
        # Remove db_path's own pre-restore sidecars *before* the swap, not after: if the
        # process dies between the two steps, a stale -wal from the OLD file sitting next to
        # the NEW (restored) file is exactly the mismatch SQLite's WAL recovery can't tell
        # apart from a legitimate in-progress write, risking corruption on next open.
        for suffix in ("-wal", "-shm"):
            db_path.with_name(db_path.name + suffix).unlink(missing_ok=True)
        os.replace(restore_tmp, db_path)
        return version
    except Exception:
        restore_tmp = db_path.with_name(f".{db_path.name}.restore")
        restore_tmp.unlink(missing_ok=True)
        raise


async def _approve_operator_user(conn: aiosqlite.Connection) -> None:
    operator_chat_id = settings.OPERATOR_CHAT_ID
    if operator_chat_id is None:
        return
    await _upsert_minimal_user(conn, tg_id=operator_chat_id, status="approved")
    log.info("operator_user_approved", tg_id=operator_chat_id)


async def wait_for_schema_ready(
    timeout_seconds: float = 60.0, poll_interval_seconds: float = 1.0
) -> None:
    """Block until another process's ``init_db()`` has finished migrating.

    Never runs a migration itself — unlike calling ``init_db()`` from two
    processes sharing one SQLite file, this cannot race a peer's migration or
    its backup/restore-on-failure guard, regardless of container restart
    timing. Intended for a process (e.g. the worker) that must never be the
    one to apply schema changes; the sole migration owner (the api container)
    still calls ``init_db()`` directly.
    """
    db_path = Path(settings.DB_PATH)
    deadline = time.monotonic() + timeout_seconds
    while True:
        if db_path.is_file():
            async with aiosqlite.connect(settings.DB_PATH) as conn:
                cur = await conn.execute("PRAGMA user_version")
                current_version = (await cur.fetchone())[0]
            if current_version >= len(MIGRATIONS):
                return
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"schema not ready after {timeout_seconds}s "
                f"(is the api container running and healthy?)"
            )
        await asyncio.sleep(poll_interval_seconds)


async def init_db() -> None:
    """Create the database file (if absent), apply DDL, run pending migrations."""
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    migration_started = False
    try:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            cur = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
            )
            is_fresh = await cur.fetchone() is None
            if not is_fresh:
                version_cur = await conn.execute("PRAGMA user_version")
                current_version = int((await version_cur.fetchone())[0])
                if current_version < len(MIGRATIONS):
                    backup_path = await _snapshot_database(conn, db_path, current_version)
                    migration_started = True
            if not is_fresh:
                links_cur = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='links'"
                )
                if await links_cur.fetchone() is not None:
                    # SCHEMA_SQL creates a per-owner UNIQUE index on links(chat_id, url);
                    # dedup first so old duplicate rows don't crash DDL before the
                    # ownership migration gets a chance to run.
                    link_cols = await _table_columns(conn, "links")
                    if "chat_id" not in link_cols:
                        await conn.execute("ALTER TABLE links ADD COLUMN chat_id INTEGER")
                        link_cols.add("chat_id")
                    await conn.execute(
                        """
                        DELETE FROM links
                         WHERE rowid NOT IN (
                             SELECT MIN(rowid)
                               FROM links
                              GROUP BY COALESCE(
                                  chat_id,
                                  (SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job),
                                  ?
                              ), url
                         )
                        """,
                        (settings.OPERATOR_CHAT_ID,),
                    )
            await conn.executescript(SCHEMA_SQL)
            if is_fresh:
                # DDL already includes all columns; skip past all migration steps.
                # PRAGMA takes no bind parameters; the value is a list length.
                await conn.execute(f"PRAGMA user_version = {len(MIGRATIONS)}")  # nosemgrep
                await conn.commit()
            else:
                await run_migrations(conn)
        # Kept out of SCHEMA_SQL because CREATE TABLE IF NOT EXISTS does not add
        # `source_url` to an older jobs table; creating the index before the
        # migration would fail startup with "no such column".
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_source_url ON jobs(source_url)"
            )
            # Same reasoning, for jobs.link_id (added by _migrate_jobs_link_id).
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_link_id ON jobs(link_id)"
            )
            # Same reasoning as above, for email_digest_payloads' watch_id/slug
            # columns (see the comment next to its CREATE TABLE in SCHEMA_SQL).
            await conn.execute(_EMAIL_DIGEST_PAYLOADS_WATCH_INDEX_SQL)
            await conn.execute(_EMAIL_DIGEST_PAYLOADS_SLUG_INDEX_SQL)
            # Same reasoning again: users.email exists unconditionally by
            # this point (fresh SCHEMA_SQL always had it; a migrated old DB
            # just ran the migration that adds it), but not any earlier.
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_nocase "
                "ON users(email COLLATE NOCASE) WHERE email IS NOT NULL"
            )
            await _approve_operator_user(conn)
            await conn.commit()
    except Exception:
        if migration_started and backup_path is not None:
            try:
                restored_version = _restore_database_file(backup_path, db_path)
            except Exception:
                log.exception("db_migration_backup_restore_failed", path=str(backup_path))
            else:
                log.error(
                    "db_migration_backup_restored",
                    path=str(backup_path),
                    restored_version=restored_version,
                )
        raise
    log.info("db_initialized", path=settings.DB_PATH)

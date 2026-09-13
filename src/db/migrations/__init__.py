"""Schema migrations: the registry, the steps, and the runner.

`MIGRATIONS` is the ordered step list — index N holds the vN → v(N+1) step, so
`len(MIGRATIONS)` is the version a fully migrated database sits at. It is built
from explicit per-step version declarations (see `_registry`), not from the
order the steps happen to appear in.
"""

from __future__ import annotations

import aiosqlite

from src.db.migrations import steps as _steps  # noqa: F401  -- import registers every step
from src.db.migrations._registry import Step, migration, ordered, sql
from src.db.core import log

__all__ = ["MIGRATIONS", "Step", "migration", "run_migrations", "sql"]

#: Mutable on purpose: tests substitute a single step to exercise failure paths.
MIGRATIONS: list[Step] = ordered()


async def run_migrations(conn: aiosqlite.Connection) -> None:
    """Apply every step past the database's current `user_version`, one commit each."""
    cur = await conn.execute("PRAGMA user_version")
    row = await cur.fetchone()
    current_version: int = row[0]
    for step, migration_step in enumerate(MIGRATIONS[current_version:], start=current_version):
        new_version = step + 1
        try:
            if callable(migration_step):
                await migration_step(conn)
            else:
                for stmt in migration_step:
                    try:
                        await conn.execute(stmt)
                    except aiosqlite.OperationalError as exc:
                        if "duplicate column name" not in str(exc):
                            raise
        except Exception:
            log.exception("db_migration_failed", target_version=new_version)
            raise
        # PRAGMA takes no bind parameters; `new_version` is the step's declared int.
        await conn.execute(f"PRAGMA user_version = {new_version}")  # nosemgrep
        await conn.commit()
        log.info("db_migration_applied", version=new_version)

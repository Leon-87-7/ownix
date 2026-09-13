"""Connection handling and the thin query helpers every other db module uses.

`connection()` is the only place a connection to the jobs database is opened.
It is not a bare `aiosqlite.connect()`: it installs the Row factory and turns
foreign keys ON, which SQLite otherwise leaves OFF per-connection, so every
`ON DELETE CASCADE` in the schema depends on going through here.
"""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Literal

import aiosqlite

from src.config import settings
from src.utils.logger import get_logger

#: One logger for the whole database layer, so `database.log` is the real
#: object every db module writes through.
log = get_logger("src.database")

UserStatus = Literal["pending", "approved", "blocked", "deleting"]

def generate_id() -> str:
    """YYYYMMDD_HHMMSS_XXXXXXXX where XXXXXXXX is 8 hex chars (job IDs and link IDs)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(4).upper()
    return f"{ts}_{suffix}"
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


async def _fetch_in(sql_template: str, ids: list[str], *extra_params) -> list[dict]:
    """Run *sql_template* (containing ``{placeholders}``) with an expanded IN list.

    *extra_params* bind before the IN list, for a template like
    ``"... WHERE chat_id = ? AND url IN ({placeholders})"``.
    """
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    async with connection() as conn:
        # `placeholders` is only `?` marks; every id binds through the params tuple.
        cur = await conn.execute(  # nosemgrep
            sql_template.format(placeholders=placeholders), (*extra_params, *ids)
        )
        return [dict(r) for r in await cur.fetchall()]


_TABLE_INFO_SQL = {
    "links": "PRAGMA table_info(links)",
    "jobs": "PRAGMA table_info(jobs)",
}
async def _table_columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    cur = await conn.execute(_TABLE_INFO_SQL[table])
    return {row[1] for row in await cur.fetchall()}

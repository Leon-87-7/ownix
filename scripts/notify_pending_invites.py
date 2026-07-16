"""Resend operator approval keyboards for pending users with saved emails.

Usage:
    python -m scripts.notify_pending_invites
    python -m scripts.notify_pending_invites --tg-id 526036052
"""

from __future__ import annotations

import argparse
import asyncio

import aiosqlite

from src.config import settings
from src.services.invite_notifications import notify_operator_invite


async def _pending_invites(tg_id: int | None) -> list[aiosqlite.Row]:
    query = """
        SELECT tg_id, email
        FROM users
        WHERE email IS NOT NULL
          AND status = 'pending'
    """
    params: tuple[object, ...] = ()
    if tg_id is not None:
        query += " AND tg_id = ?"
        params = (tg_id,)
    query += " ORDER BY updated_at DESC"

    async with aiosqlite.connect(settings.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(query, params)
        return await cursor.fetchall()


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tg-id", type=int, help="Only notify for one Telegram user id.")
    args = parser.parse_args()

    rows = await _pending_invites(args.tg_id)
    sent = 0
    for row in rows:
        if await notify_operator_invite(int(row["tg_id"]), str(row["email"])):
            sent += 1
            print(f"sent invite approval keyboard for {row['tg_id']} <{row['email']}>")

    print(f"done: {sent}/{len(rows)} notification(s) sent")


if __name__ == "__main__":
    asyncio.run(_main())

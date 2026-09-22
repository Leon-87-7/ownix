"""Per-user spending ledger (handoff §2) — a durable, transactional
reservation ledger over SQLite so "may this user spend another $X today"
survives a process restart and stays correct across multiple API/worker
processes. SQLite is the authoritative financial ledger here the same way it
already is for jobs; Redis (elsewhere) is for burst/concurrency limits, not
accounting.

Money is always integer micros of `currency` — never `REAL`.
"""

from __future__ import annotations

from typing import Any

from src.db import core
from src.db.core import generate_id

#: Product-chosen defaults (2026-09-22): $0.50/day, $3/month. These are the
#: caps a user would have *if* paid Gemini were enabled for them — they don't
#: by themselves grant paid access. `allow_paid_gemini` staying False below is
#: the actual access gate; an Operator still opts an account in explicitly
#: (handoff §6 rollout: paid fallback starts disabled, enabled per-account).
DEFAULT_DAILY_LIMIT_MICROS = 500_000
DEFAULT_MONTHLY_LIMIT_MICROS = 3_000_000

#: Missing `user_spend_limits` row means no paid access, not unlimited —
#: never interpret an absent row as an unlimited-spend bypass.
DEFAULT_LIMITS: dict[str, Any] = {
    "currency": "USD",
    "daily_limit_micros": DEFAULT_DAILY_LIMIT_MICROS,
    "monthly_limit_micros": DEFAULT_MONTHLY_LIMIT_MICROS,
    "allow_paid_gemini": False,
    "enabled": True,
}


class SpendLimitExceeded(Exception):
    """Raised by `reserve` when the new reservation would exceed a hard limit."""


def _row_to_limits(row) -> dict[str, Any]:
    return {
        "currency": row["currency"],
        "daily_limit_micros": row["daily_limit_micros"],
        "monthly_limit_micros": row["monthly_limit_micros"],
        "allow_paid_gemini": bool(row["allow_paid_gemini"]),
        "enabled": bool(row["enabled"]),
    }


async def get_spend_limits(chat_id: int) -> dict[str, Any]:
    """Return *chat_id*'s spend limits, or `DEFAULT_LIMITS` if no row exists."""
    async with core.connection() as conn:
        cursor = await conn.execute(
            """SELECT currency, daily_limit_micros, monthly_limit_micros,
                      allow_paid_gemini, enabled
               FROM user_spend_limits WHERE chat_id = ?""",
            (chat_id,),
        )
        row = await cursor.fetchone()
    return _row_to_limits(row) if row is not None else dict(DEFAULT_LIMITS)


async def set_spend_limits(
    chat_id: int,
    *,
    daily_limit_micros: int | None,
    monthly_limit_micros: int | None,
    allow_paid_gemini: bool,
    enabled: bool = True,
    currency: str = "USD",
) -> dict[str, Any]:
    """Operator-only write (enforced by the API route, not here)."""
    async with core.connection() as conn:
        await conn.execute(
            """INSERT INTO user_spend_limits
               (chat_id, currency, daily_limit_micros, monthly_limit_micros,
                allow_paid_gemini, enabled, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(chat_id) DO UPDATE SET
                   currency              = excluded.currency,
                   daily_limit_micros    = excluded.daily_limit_micros,
                   monthly_limit_micros  = excluded.monthly_limit_micros,
                   allow_paid_gemini     = excluded.allow_paid_gemini,
                   enabled               = excluded.enabled,
                   updated_at            = CURRENT_TIMESTAMP""",
            (
                chat_id,
                currency,
                daily_limit_micros,
                monthly_limit_micros,
                int(allow_paid_gemini),
                int(enabled),
            ),
        )
        await conn.commit()
    return await get_spend_limits(chat_id)


_RESERVATION_COLUMNS = (
    "id, chat_id, job_id, root_task_id, provider, operation, model, currency, "
    "status, estimated_micros, actual_micros, input_units, output_units, "
    "idempotency_key, created_at, settled_at"
)

# Sums both settled actuals and still-open reservations within a UTC window —
# a hard limit must include in-flight money, not just money already spent,
# or two concurrent calls can each see "room" and jointly blow the limit.
_WINDOW_SPEND_SQL = """
    SELECT COALESCE(SUM(
        CASE WHEN status = 'settled' THEN actual_micros
             WHEN status = 'reserved' THEN estimated_micros
             ELSE 0 END
    ), 0) AS spent
    FROM usage_ledger
    WHERE chat_id = ? AND status != 'released' AND created_at >= datetime('now', ?)
"""


async def reserve(
    *,
    chat_id: int,
    job_id: str | None,
    root_task_id: str | None,
    provider: str,
    operation: str,
    model: str | None,
    estimated_micros: int,
    idempotency_key: str,
) -> dict[str, Any]:
    """Atomically reserve *estimated_micros* against chat_id's daily/monthly
    limits (handoff §2 "Atomic reservation algorithm") — one `BEGIN IMMEDIATE`
    transaction, so a separate check-then-insert can never race across two
    connections/processes. Raises `SpendLimitExceeded` if either non-null hard
    limit would be exceeded. A repeated `idempotency_key` returns the existing
    reservation without re-checking limits or double-counting.
    """
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")

        existing = await (
            await conn.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM usage_ledger WHERE idempotency_key = ?",
                (idempotency_key,),
            )
        ).fetchone()
        if existing is not None:
            await conn.rollback()
            return dict(existing)

        limits_row = await (
            await conn.execute(
                """SELECT currency, daily_limit_micros, monthly_limit_micros,
                          allow_paid_gemini, enabled
                   FROM user_spend_limits WHERE chat_id = ?""",
                (chat_id,),
            )
        ).fetchone()
        limits = _row_to_limits(limits_row) if limits_row is not None else dict(DEFAULT_LIMITS)

        for window, limit_key in (("start of day", "daily_limit_micros"), ("start of month", "monthly_limit_micros")):
            limit = limits[limit_key]
            if limit is None:
                continue
            spent_row = await (
                await conn.execute(_WINDOW_SPEND_SQL, (chat_id, window))
            ).fetchone()
            spent = spent_row["spent"] if spent_row else 0
            if spent + estimated_micros > limit:
                await conn.rollback()
                raise SpendLimitExceeded(
                    f"chat_id={chat_id} {limit_key}={limit} spent={spent} "
                    f"estimate={estimated_micros}"
                )

        reservation_id = generate_id()
        await conn.execute(
            """INSERT INTO usage_ledger
               (id, chat_id, job_id, root_task_id, provider, operation, model,
                currency, status, estimated_micros, idempotency_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)""",
            (
                reservation_id,
                chat_id,
                job_id,
                root_task_id,
                provider,
                operation,
                model,
                limits["currency"],
                estimated_micros,
                idempotency_key,
            ),
        )
        await conn.commit()

        row = await (
            await conn.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM usage_ledger WHERE id = ?",
                (reservation_id,),
            )
        ).fetchone()
        return dict(row)


async def settle(
    reservation_id: str,
    *,
    actual_micros: int,
    input_units: int | None = None,
    output_units: int | None = None,
) -> dict[str, Any] | None:
    """Settle a reservation to its actual cost. Idempotent: settling an
    already-settled or released row is a no-op that returns the row unchanged
    (never double-counts or overwrites a prior settlement). None if the
    reservation doesn't exist."""
    async with core.connection() as conn:
        await conn.execute(
            """UPDATE usage_ledger
               SET status = 'settled', actual_micros = ?, input_units = ?,
                   output_units = ?, settled_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status = 'reserved'""",
            (actual_micros, input_units, output_units, reservation_id),
        )
        await conn.commit()
        row = await (
            await conn.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM usage_ledger WHERE id = ?",
                (reservation_id,),
            )
        ).fetchone()
    return dict(row) if row else None


async def release(reservation_id: str) -> dict[str, Any] | None:
    """Release a reservation that never turned into real spend. Idempotent and
    never downgrades an already-settled row. None if the reservation doesn't
    exist."""
    async with core.connection() as conn:
        await conn.execute(
            "UPDATE usage_ledger SET status = 'released' WHERE id = ? AND status = 'reserved'",
            (reservation_id,),
        )
        await conn.commit()
        row = await (
            await conn.execute(
                f"SELECT {_RESERVATION_COLUMNS} FROM usage_ledger WHERE id = ?",
                (reservation_id,),
            )
        ).fetchone()
    return dict(row) if row else None


async def spend_summary(chat_id: int) -> dict[str, Any]:
    """Settled + reserved totals for the current UTC day and month, plus
    limits and remaining headroom (None = no hard limit)."""
    limits = await get_spend_limits(chat_id)
    async with core.connection() as conn:
        daily_row = await (await conn.execute(_WINDOW_SPEND_SQL, (chat_id, "start of day"))).fetchone()
        monthly_row = await (
            await conn.execute(_WINDOW_SPEND_SQL, (chat_id, "start of month"))
        ).fetchone()
    daily_spent = daily_row["spent"] if daily_row else 0
    monthly_spent = monthly_row["spent"] if monthly_row else 0
    return {
        **limits,
        "daily_spent_micros": daily_spent,
        "monthly_spent_micros": monthly_spent,
        "daily_remaining_micros": (
            None if limits["daily_limit_micros"] is None else max(0, limits["daily_limit_micros"] - daily_spent)
        ),
        "monthly_remaining_micros": (
            None
            if limits["monthly_limit_micros"] is None
            else max(0, limits["monthly_limit_micros"] - monthly_spent)
        ),
    }


async def release_stale_reservations(older_than_seconds: int) -> int:
    """Recovery sweep (handoff §2 "reservation lifecycle"): release
    reservations still `reserved` after *older_than_seconds* — calls that
    crashed or hung before settling/releasing. Returns the count released.
    ponytail: blanket age-based release, not per-provider timeout tracking;
    tighten if a provider's real max latency ever exceeds this window.
    """
    async with core.connection() as conn:
        cursor = await conn.execute(
            """UPDATE usage_ledger SET status = 'released'
               WHERE status = 'reserved'
                 AND created_at < datetime('now', ? || ' seconds')""",
            (f"-{older_than_seconds}",),
        )
        await conn.commit()
        return cursor.rowcount

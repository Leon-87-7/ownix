"""Per-user spending guardrail service (handoff §2, ADR-0006 addendum).

The public seam every paid-provider call site goes through: build a
`CostContext`, ask this module to `reserve` before the call, `settle` after a
successful one, `release` after one that never happened. The durable ledger
itself lives in `src/db/spending.py` (exported through `src.database`); this
module adds the typed exceptions, the free/paid gating policy, and
idempotency-key construction.

Decisions (handoff §2 "Decisions for this implementation"):
- Paid Gemini is opt-in per user — a missing `user_spend_limits` row or
  `allow_paid_gemini=0` means no paid access, never an unlimited bypass.
- A hard-stop beats graceful degradation: budget-exhausted or paid-disabled
  raises a typed exception instead of silently reaching for the paid key.
- `PAID_AI_ENABLED=0` is a global kill switch checked in addition to (not
  instead of) each user's own policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from src import database
from src.config import settings
from src.db.core import generate_id
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class CostContext:
    chat_id: int
    operation: str
    job_id: str | None = None
    root_task_id: str | None = None
    attempt: int = 1


@dataclass(frozen=True)
class Reservation:
    id: str
    estimated_micros: int
    idempotency_key: str


class SpendingLimitExceeded(Exception):
    """A reservation would exceed the caller's daily or monthly hard limit."""


class PaidProviderDisabled(Exception):
    """Paid Gemini isn't authorized for this call — disabled globally
    (`PAID_AI_ENABLED=0`), disabled for this chat_id, or the chat has no
    spend-limits row at all (missing means no paid access, not unlimited)."""


def _idempotency_key(cost: CostContext, *, provider: str) -> str:
    """One key per real provider attempt (handoff §2).

    `cost.attempt` is meant to make a crash-and-automatic-redelivery of the
    *same* queue attempt collapse onto one reservation instead of double
    charging. That collapsing only actually protects anything once the queue
    envelope carries a real `attempt` counter the worker increments on
    redelivery — the envelope today is bare `{task, job_id}` with no such
    field (handoff §2, "Queue lineage" — not yet implemented), and this
    worker has no automatic crash-redelivery at all, so every call today is
    either a fresh user action or a fresh scheduled tick. Collapsing on a
    caller-supplied `attempt` that never actually changes would silently
    under-count every explicit retry (the second real provider call would
    settle onto the first reservation and record no new spend) — worse than
    the double-charge risk this key format prevents, which cannot currently
    happen. So: always mint a fresh key. Revisit once the queue-lineage PR
    lands and `attempt` is wired from real redelivery, not a hardcoded 1.
    """
    return f"{provider}:{cost.operation}:{cost.chat_id}:{generate_id()}"


async def reserve_paid_gemini(
    cost: CostContext,
    *,
    model: str | None,
    estimated_micros: int,
) -> Reservation:
    """Reserve budget for one paid Gemini call. Raises `PaidProviderDisabled`
    before ever touching the ledger if paid use isn't authorized, or
    `SpendingLimitExceeded` if the reservation itself would exceed a hard
    limit — the caller (gemini.py's `_call_with_fallback`) must let both
    propagate rather than falling back to the paid key anyway.
    """
    if not settings.PAID_AI_ENABLED:
        raise PaidProviderDisabled("PAID_AI_ENABLED=0 (global kill switch)")

    limits = await database.get_spend_limits(cost.chat_id)
    if not limits["enabled"] or not limits["allow_paid_gemini"]:
        raise PaidProviderDisabled(f"chat_id={cost.chat_id} paid Gemini not authorized")

    idempotency_key = _idempotency_key(cost, provider="gemini")
    try:
        row = await database.reserve(
            chat_id=cost.chat_id,
            job_id=cost.job_id,
            root_task_id=cost.root_task_id,
            provider="gemini",
            operation=cost.operation,
            model=model,
            estimated_micros=estimated_micros,
            idempotency_key=idempotency_key,
        )
    except database.SpendLimitExceeded as exc:
        raise SpendingLimitExceeded(str(exc)) from exc

    return Reservation(
        id=row["id"], estimated_micros=row["estimated_micros"], idempotency_key=row["idempotency_key"]
    )


async def settle(reservation: Reservation, *, actual_micros: int) -> None:
    await database.settle(reservation.id, actual_micros=actual_micros)


async def release(reservation: Reservation) -> None:
    await database.release(reservation.id)


async def summary(chat_id: int) -> dict:
    return await database.spend_summary(chat_id)


async def release_stale_reservations(older_than_seconds: int = 30 * 60) -> int:
    """Recovery sweep for reservations a crashed/hung call never settled or
    released. Registered with APScheduler in `src/main.py`."""
    released = await database.release_stale_reservations(older_than_seconds)
    if released:
        log.warning("spending.stale_reservations_released", count=released)
    return released

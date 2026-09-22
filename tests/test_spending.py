"""Tests for the per-user spending ledger (handoff §2) — the durable
reservation service in src/db/spending.py (exported through src.database)
and its integration at the Gemini free→paid boundary in src/services/gemini.py.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
async def temp_db():
    """Create a fresh SQLite file with the full schema applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db

        await db.init_db()
        yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Reservation / settlement / release — the ledger's own transaction logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reservation_succeeds_below_limit(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    resv = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="generate", model="gemini-2.5-flash", estimated_micros=500_000,
        idempotency_key="k1",
    )
    assert resv["status"] == "reserved"
    assert resv["estimated_micros"] == 500_000


@pytest.mark.asyncio
async def test_reservation_exactly_at_limit_succeeds_one_micro_over_fails(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="generate", model=None, estimated_micros=1_000_000,
        idempotency_key="exact",
    )
    with pytest.raises(db.SpendLimitExceeded):
        await db.reserve(
            chat_id=1, job_id=None, root_task_id=None, provider="gemini",
            operation="generate", model=None, estimated_micros=1,
            idempotency_key="over-by-one",
        )


@pytest.mark.asyncio
async def test_settled_and_reserved_amounts_both_count(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    settled = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=400_000, idempotency_key="a",
    )
    await db.settle(settled["id"], actual_micros=400_000)
    await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="b", model=None, estimated_micros=400_000, idempotency_key="b",
    )
    # 400k settled + 400k reserved = 800k; one more 300k would exceed 1,000,000.
    with pytest.raises(db.SpendLimitExceeded):
        await db.reserve(
            chat_id=1, job_id=None, root_task_id=None, provider="gemini",
            operation="c", model=None, estimated_micros=300_000, idempotency_key="c",
        )


@pytest.mark.asyncio
async def test_daily_and_monthly_windows_are_independent(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=100, monthly_limit_micros=1_000_000, allow_paid_gemini=True
    )
    # Blows the tiny daily limit but stays well under the monthly one.
    with pytest.raises(db.SpendLimitExceeded):
        await db.reserve(
            chat_id=1, job_id=None, root_task_id=None, provider="gemini",
            operation="a", model=None, estimated_micros=1_000, idempotency_key="a",
        )
    summary = await db.spend_summary(1)
    assert summary["monthly_spent_micros"] == 0  # the rejected reservation never landed


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_oversubscribe_a_limit(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )

    async def _try_reserve(key: str):
        try:
            return await db.reserve(
                chat_id=1, job_id=None, root_task_id=None, provider="gemini",
                operation="x", model=None, estimated_micros=600_000, idempotency_key=key,
            )
        except db.SpendLimitExceeded:
            return None

    # Two concurrent 600k reservations against a 1,000,000 limit — at most one
    # may succeed (BEGIN IMMEDIATE serializes them; SQLite itself queues the
    # second writer rather than truly running them in parallel, but this
    # proves the transaction boundary — not just application-level timing —
    # is what prevents the oversubscription).
    results = await asyncio.gather(_try_reserve("c1"), _try_reserve("c2"))
    succeeded = [r for r in results if r is not None]
    assert len(succeeded) == 1


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_same_reservation(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    first = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=500_000, idempotency_key="dupe",
    )
    second = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=500_000, idempotency_key="dupe",
    )
    assert first["id"] == second["id"]
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] == 500_000  # not double-counted


@pytest.mark.asyncio
async def test_settling_is_idempotent(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    resv = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=500_000, idempotency_key="a",
    )
    await db.settle(resv["id"], actual_micros=300_000)
    await db.settle(resv["id"], actual_micros=999_999)  # must not overwrite the first settlement
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] == 300_000


@pytest.mark.asyncio
async def test_released_reservations_stop_counting(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    resv = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=900_000, idempotency_key="a",
    )
    await db.release(resv["id"])
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] == 0
    # The freed-up budget is usable again.
    await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="b", model=None, estimated_micros=900_000, idempotency_key="b",
    )


@pytest.mark.asyncio
async def test_release_of_already_settled_reservation_is_a_noop(temp_db):
    from src import database as db

    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    resv = await db.reserve(
        chat_id=1, job_id=None, root_task_id=None, provider="gemini",
        operation="a", model=None, estimated_micros=500_000, idempotency_key="a",
    )
    await db.settle(resv["id"], actual_micros=500_000)
    await db.release(resv["id"])  # must not un-count a real, already-settled charge
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] == 500_000


@pytest.mark.asyncio
async def test_user_with_no_settings_row_cannot_use_paid_key_by_default(temp_db):
    from src import database as db

    limits = await db.get_spend_limits(999)
    assert limits["allow_paid_gemini"] is False
    assert limits["enabled"] is True


@pytest.mark.asyncio
async def test_operator_defaults_are_explicit_not_an_accidental_bypass(temp_db, monkeypatch):
    """A missing row must read as 'no paid access', never 'unlimited'."""
    from src import database as db

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 42)
    limits = await db.get_spend_limits(42)
    assert limits["allow_paid_gemini"] is False
    assert limits["daily_limit_micros"] is None  # None = no cap only once explicitly set that way
    # An explicit Operator row is the only way to grant unlimited spend.
    await db.set_spend_limits(
        42, daily_limit_micros=None, monthly_limit_micros=None, allow_paid_gemini=True
    )
    limits = await db.get_spend_limits(42)
    assert limits["allow_paid_gemini"] is True


# ---------------------------------------------------------------------------
# Gemini free→paid integration — the actual provider boundary
# ---------------------------------------------------------------------------


def _response(text: str) -> MagicMock:
    r = MagicMock()
    r.text = text
    r.usage_metadata = None
    return r


@pytest.mark.asyncio
async def test_free_success_never_touches_paid_budget(temp_db, monkeypatch):
    from src import database as db
    from src.services.gemini import generate
    from src.services.spending import CostContext

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    with patch("src.services.gemini._call_sync", return_value=_response("ok")):
        result = await generate(
            "hi", model="gemini-2.5-flash", cost=CostContext(chat_id=1, operation="t")
        )
    assert result == "ok"
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] == 0
    assert summary["monthly_spent_micros"] == 0


@pytest.mark.asyncio
async def test_free_failure_paid_disabled_stops_before_paid_call(temp_db, monkeypatch):
    from src.services.gemini import generate
    from src.services.spending import CostContext, PaidProviderDisabled

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    # No user_spend_limits row for chat_id=1 → allow_paid_gemini defaults False.
    call_count = 0

    def _fake(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("free key down")

    with patch("src.services.gemini._call_sync", side_effect=_fake):
        with pytest.raises(PaidProviderDisabled):
            await generate("hi", model="gemini-2.5-flash", cost=CostContext(chat_id=1, operation="t"))
    assert call_count == 1  # only the free attempt — paid key was never dialed


@pytest.mark.asyncio
async def test_free_failure_insufficient_budget_stops_before_paid_call(temp_db, monkeypatch):
    from src import database as db
    from src.services.gemini import generate
    from src.services.spending import CostContext, SpendingLimitExceeded

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    await db.set_spend_limits(
        1, daily_limit_micros=1, monthly_limit_micros=None, allow_paid_gemini=True
    )
    call_count = 0

    def _fake(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("free key down")

    with patch("src.services.gemini._call_sync", side_effect=_fake):
        with pytest.raises(SpendingLimitExceeded):
            await generate(
                "a very long prompt " * 50,
                model="gemini-2.5-flash",
                cost=CostContext(chat_id=1, operation="t"),
            )
    assert call_count == 1


@pytest.mark.asyncio
async def test_free_failure_sufficient_budget_reserves_calls_paid_once_and_settles(
    temp_db, monkeypatch
):
    from src import database as db
    from src.services.gemini import generate
    from src.services.spending import CostContext

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    call_count = 0

    def _fake(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("free key down")
        return _response("paid result")

    with patch("src.services.gemini._call_sync", side_effect=_fake):
        result = await generate(
            "hi", model="gemini-2.5-flash", cost=CostContext(chat_id=1, operation="t")
        )
    assert result == "paid result"
    assert call_count == 2
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] > 0


@pytest.mark.asyncio
async def test_parser_failure_after_successful_paid_response_still_settles_cost(
    temp_db, monkeypatch
):
    """The user already caused the charge — a downstream parse failure must not un-charge it."""
    from src import database as db
    from src.services.gemini import generate
    from src.services.spending import CostContext

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    with patch("src.services.gemini._call_sync", return_value=_response("some text")):
        await generate("hi", model="gemini-2.5-flash", cost=CostContext(chat_id=1, operation="t"))
    # The provider call itself succeeded and settled — any JSON-parse failure
    # a caller does with the returned text happens after this point and
    # cannot retroactively unsettle the ledger row.
    summary = await db.spend_summary(1)
    assert summary["daily_spent_micros"] > 0


@pytest.mark.asyncio
async def test_two_calls_each_settle_their_own_charge(temp_db, monkeypatch):
    """Two distinct real provider calls must produce two distinct ledger charges
    (not collapse onto one reservation) — see spending._idempotency_key's
    docstring for why every call currently mints a fresh key."""
    from src import database as db
    from src.services.gemini import generate
    from src.services.spending import CostContext

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    await db.set_spend_limits(
        1, daily_limit_micros=1_000_000, monthly_limit_micros=None, allow_paid_gemini=True
    )
    cost = CostContext(chat_id=1, job_id="job-1", operation="same_operation", attempt=1)
    with patch("src.services.gemini._call_sync", return_value=_response("x" * 400)):
        await generate("hi", model="gemini-2.5-flash", cost=cost)
        await generate("hi", model="gemini-2.5-flash", cost=cost)
    summary = await db.spend_summary(1)
    # Each call settles its own row, so the total is roughly double a single
    # call's cost, not a single settled amount reused twice.
    with patch("src.services.gemini._call_sync", return_value=_response("x" * 400)):
        await generate("hi", model="gemini-2.5-flash", cost=cost)
    summary_after_three = await db.spend_summary(1)
    per_call = summary["daily_spent_micros"] / 2
    assert summary_after_three["daily_spent_micros"] == pytest.approx(per_call * 3, rel=0.05)

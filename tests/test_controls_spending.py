"""Tests for GET/PUT /api/controls/spending (handoff §2, ADR-0064)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

OPERATOR_ID = 999
OTHER_USER_ID = 42
TARGET_ID = 7


@pytest.fixture
def spending_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Yields (client_as_operator, client_as_other_user) sharing one temp DB."""
    db_file = tmp_path / "controls_spending.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR_ID)

    from src import database
    from src.api.controls import controls_router

    asyncio.run(database.init_db())

    def _make_client(chat_id: int) -> TestClient:
        app = FastAPI()

        @app.middleware("http")
        async def inject_user(request: Request, call_next, chat_id=chat_id):
            request.state.user = {"id": chat_id, "real_id": chat_id}
            return await call_next(request)

        app.include_router(controls_router)
        return TestClient(app, raise_server_exceptions=True)

    return _make_client(OPERATOR_ID), _make_client(OTHER_USER_ID)


def test_get_spending_reflects_default_caps_even_with_paid_disabled(spending_client) -> None:
    """A chat with no user_spend_limits row still gets DEFAULT_LIMITS' numeric
    caps back — allow_paid_gemini stays the real access gate, not the numbers."""
    _, other_client = spending_client
    resp = other_client.get("/api/controls/spending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["allow_paid_gemini"] is False
    assert body["daily_limit_micros"] == 500_000  # $0.50
    assert body["monthly_limit_micros"] == 3_000_000  # $3


def test_put_spending_requires_operator(spending_client) -> None:
    _, other_client = spending_client
    resp = other_client.put(
        f"/api/controls/spending/{TARGET_ID}",
        json={"allow_paid_gemini": True},
    )
    assert resp.status_code == 403


def test_operator_put_omitting_limits_gets_the_default_caps_not_unlimited(spending_client) -> None:
    """A PUT that only flips allow_paid_gemini must not silently grant
    unlimited spend — it inherits the same $0.50/$3 defaults as a missing row."""
    operator_client, _ = spending_client
    resp = operator_client.put(
        f"/api/controls/spending/{TARGET_ID}",
        json={"allow_paid_gemini": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allow_paid_gemini"] is True
    assert body["daily_limit_micros"] == 500_000
    assert body["monthly_limit_micros"] == 3_000_000


def test_operator_put_can_explicitly_remove_a_cap(spending_client) -> None:
    """Passing null explicitly is the only way to get an uncapped account."""
    operator_client, _ = spending_client
    resp = operator_client.put(
        f"/api/controls/spending/{TARGET_ID}",
        json={
            "allow_paid_gemini": True,
            "daily_limit_micros": None,
            "monthly_limit_micros": None,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["daily_limit_micros"] is None
    assert body["monthly_limit_micros"] is None


def test_get_spending_reports_operator_flag(spending_client) -> None:
    operator_client, other_client = spending_client
    assert operator_client.get("/api/controls/spending").json()["is_operator"] is True
    assert other_client.get("/api/controls/spending").json()["is_operator"] is False


def test_own_spending_put_is_operator_only_and_saves(spending_client) -> None:
    operator_client, other_client = spending_client
    assert other_client.put("/api/controls/spending", json={"allow_paid_gemini": True}).status_code == 403

    resp = operator_client.put(
        "/api/controls/spending",
        json={"allow_paid_gemini": True, "daily_limit_micros": 1_000_000, "monthly_limit_micros": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["allow_paid_gemini"] is True
    assert body["daily_limit_micros"] == 1_000_000
    assert body["monthly_limit_micros"] is None
    assert body["is_operator"] is True
    assert operator_client.get("/api/controls/spending").json()["allow_paid_gemini"] is True

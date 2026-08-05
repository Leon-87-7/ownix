"""Tests for dashboard-visible pending intake state (issue #474).

Covers `src/intake/state.py` (create/resume/cancel/reap) and the
`GET`/`DELETE /api/intake/state` endpoints, including scoping to the
signed-in user.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_A = 111
CHAT_B = 222


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "intake_state_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    asyncio.run(database.init_db())
    return database


class TestStateModule:
    def test_set_get_clear_roundtrip(self, db) -> None:
        from src.intake import state

        assert asyncio.run(state.get_state(CHAT_A)) is None
        asyncio.run(state.set_state(CHAT_A, "awaiting_intent", "job_1"))
        pending = asyncio.run(state.get_state(CHAT_A))
        assert pending is not None
        assert pending["mode"] == "awaiting_intent"
        assert pending["job_id"] == "job_1"

        cleared = asyncio.run(state.clear_state(CHAT_A))
        assert cleared is True
        assert asyncio.run(state.get_state(CHAT_A)) is None

    def test_clear_with_nothing_pending_returns_false(self, db) -> None:
        from src.intake import state

        assert asyncio.run(state.clear_state(CHAT_A)) is False

    def test_expired_state_reads_as_absent(self, db) -> None:
        from src import database
        from src.intake import state

        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        asyncio.run(
            database._execute(
                "INSERT INTO chat_state (chat_id, mode, job_id, created_at, expires_at) "
                "VALUES (?, 'awaiting_freestyle', 'job_2', ?, ?)",
                (CHAT_A, past, past),
            )
        )
        assert asyncio.run(state.get_state(CHAT_A)) is None

    def test_reap_expired_removes_only_expired_rows(self, db) -> None:
        from src import database
        from src.intake import state

        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        asyncio.run(
            database._execute(
                "INSERT INTO chat_state (chat_id, mode, job_id, created_at, expires_at) "
                "VALUES (?, 'awaiting_intent', 'job_expired', ?, ?)",
                (CHAT_A, past, past),
            )
        )
        asyncio.run(state.set_state(CHAT_B, "awaiting_intent", "job_fresh"))

        removed = asyncio.run(state.reap_expired())
        assert removed == 1
        assert asyncio.run(database.get_chat_state(CHAT_A)) is None
        assert asyncio.run(database.get_chat_state(CHAT_B)) is not None


@pytest.fixture
def intake_state_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "intake_state_api_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.intake import intake_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_A, "approved"))
    asyncio.run(database.set_user_status(CHAT_B, "approved"))
    rate_limit.reset()

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(intake_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login_as(client: TestClient, chat_id: int) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": chat_id, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


class TestStateEndpoints:
    def test_get_state_returns_null_when_nothing_pending(
        self, intake_state_client: TestClient
    ) -> None:
        _login_as(intake_state_client, CHAT_A)
        resp = intake_state_client.get("/api/intake/state")
        assert resp.status_code == 200
        assert resp.json() == {"pending": None}

    def test_state_scoped_to_signed_in_user(self, intake_state_client: TestClient) -> None:
        from src.intake import state

        asyncio.run(state.set_state(CHAT_A, "awaiting_intent", "job_a"))

        _login_as(intake_state_client, CHAT_B)
        resp = intake_state_client.get("/api/intake/state")
        assert resp.status_code == 200
        assert resp.json() == {"pending": None}

        _login_as(intake_state_client, CHAT_A)
        resp = intake_state_client.get("/api/intake/state")
        assert resp.json()["pending"]["mode"] == "awaiting_intent"

    def test_delete_state_clears_pending(self, intake_state_client: TestClient) -> None:
        from src.intake import state

        asyncio.run(state.set_state(CHAT_A, "awaiting_freestyle", "job_a"))
        _login_as(intake_state_client, CHAT_A)

        resp = intake_state_client.delete("/api/intake/state")
        assert resp.status_code == 200
        assert resp.json() == {"cleared": True}

        resp = intake_state_client.get("/api/intake/state")
        assert resp.json() == {"pending": None}

    def test_auth_required(self, intake_state_client: TestClient) -> None:
        resp = intake_state_client.get("/api/intake/state")
        assert resp.status_code == 401

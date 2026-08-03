"""Tests for POST /api/intake/action (issue #475): generic dashboard actions,
idempotent per (actor, action_id) so a double-fired action never double-applies."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 888
OTHER_CHAT_ID = 999


@pytest.fixture
def action_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "intake_action_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.intake import intake_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import idempotency, rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    rate_limit.reset()
    idempotency._memory.clear()

    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.services.jobs.queue.enqueue", _fake_enqueue)

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(intake_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


async def _insert_error_job(job_id: str, chat_id: int = CHAT_ID) -> None:
    from src import database

    async with database.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status) VALUES (?, ?, ?, 'short', 'error')",
            (job_id, chat_id, "https://youtube.com/shorts/abc123"),
        )
        await conn.commit()


async def _count_jobs_for_url(url: str) -> int:
    from src import database

    async with database.connection() as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM jobs WHERE url = ?", (url,))
        row = await cur.fetchone()
        return row[0]


class TestActionIdempotency:
    def test_double_fired_retry_job_does_not_double_apply(self, action_client: TestClient) -> None:
        asyncio.run(_insert_error_job("job_retry_1"))
        _login(action_client)

        body = {"action_id": "retry-job_retry_1", "kind": "retry_job", "job_id": "job_retry_1"}
        first = action_client.post("/api/intake/action", json=body)
        second = action_client.post("/api/intake/action", json=body)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["job_id"] == second.json()["job_id"]
        # Original error job + exactly one retry replacement — never two.
        assert asyncio.run(_count_jobs_for_url("https://youtube.com/shorts/abc123")) == 2

    def test_retry_job_rejects_foreign_job(self, action_client: TestClient) -> None:
        asyncio.run(_insert_error_job("job_foreign", chat_id=OTHER_CHAT_ID))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a1", "kind": "retry_job", "job_id": "job_foreign"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "error"

    def test_cancel_pending_action(self, action_client: TestClient) -> None:
        from src.intake import state

        asyncio.run(state.set_state(CHAT_ID, "awaiting_intent", "job_x"))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "cancel-1", "kind": "cancel_pending"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "command_result"
        assert asyncio.run(state.get_state(CHAT_ID)) is None

    def test_unknown_action_kind_is_unsupported(self, action_client: TestClient) -> None:
        _login(action_client)
        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a2", "kind": "not_a_real_action"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "unsupported"

    def test_auth_required(self, action_client: TestClient) -> None:
        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a3", "kind": "cancel_pending"},
        )
        assert resp.status_code == 401

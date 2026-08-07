"""Tests for POST /api/intake/message (issue #472).

Covers successful URL submit, unsupported URL, auth error, rate-limit
rejection, and idempotent re-submit — through the real SessionMiddleware, on
a temp DB, with the intake idempotency/rate-limit stores reset per test.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 4242


@pytest.fixture
def intake_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "intake_api_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.intake import intake_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import idempotency, rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))

    idempotency._memory.clear()
    rate_limit.reset()

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


class TestPostIntakeMessage:
    def test_auth_required(self, intake_client: TestClient) -> None:
        resp = intake_client.post("/api/intake/message", json={"url": "https://youtube.com/shorts/abc"})
        assert resp.status_code == 401

    def test_successful_url_submit_creates_job(self, intake_client: TestClient) -> None:
        _login(intake_client)
        resp = intake_client.post(
            "/api/intake/message", json={"url": "https://youtube.com/shorts/abc123"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "job_created"
        assert body["job_id"]
        assert body["job_url"] == f"/jobs/{body['job_id']}"

    def test_unsupported_url_returns_clear_response(self, intake_client: TestClient) -> None:
        _login(intake_client)
        resp = intake_client.post(
            "/api/intake/message", json={"url": "https://example.com/nothing"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "unsupported"
        assert body["job_id"] is None

    def test_missing_text_and_url_is_422(self, intake_client: TestClient) -> None:
        _login(intake_client)
        resp = intake_client.post("/api/intake/message", json={})
        assert resp.status_code == 422

    def test_idempotent_resubmit_returns_original_job(self, intake_client: TestClient) -> None:
        _login(intake_client)
        headers = {"Idempotency-Key": "resubmit-1"}
        first = intake_client.post(
            "/api/intake/message",
            json={"url": "https://youtube.com/shorts/replayxyz"},
            headers=headers,
        )
        second = intake_client.post(
            "/api/intake/message",
            json={"url": "https://youtube.com/shorts/replayxyz"},
            headers=headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["job_id"] == second.json()["job_id"]

    def test_rate_limit_rejection(self, intake_client: TestClient) -> None:
        _login(intake_client)
        from src.intake import rate_limit

        for _ in range(rate_limit._MAX_REQUESTS):
            resp = intake_client.post(
                "/api/intake/message", json={"text": "/help"}
            )
            assert resp.status_code == 200
        resp = intake_client.post("/api/intake/message", json={"text": "/help"})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


class TestCommandPalette:
    """`GET /api/intake/commands` — the palette's source of truth (issue #484)."""

    def test_lists_the_shared_commands_with_hints(self, intake_client) -> None:
        _login(intake_client)
        resp = intake_client.get("/api/intake/commands")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["commands"]]
        assert "/help" in names
        assert "/cancel" in names

    def test_is_derived_from_the_registry_not_hardcoded(self, intake_client) -> None:
        """A newly registered command must appear without touching the endpoint."""
        from src.intake import commands as intake_commands

        async def _noop(chat_id: int, parts: list[str]):
            from src.intake import responses

            del chat_id, parts
            return responses.command_result("ok")

        intake_commands.SHARED_COMMANDS["/probe"] = intake_commands.Command(
            "/probe", "temporary probe", _noop, args="<query>"
        )
        try:
            _login(intake_client)
            entry = next(
                c for c in intake_client.get("/api/intake/commands").json()["commands"]
                if c["name"] == "/probe"
            )
            assert entry["args"] == "<query>"
            assert entry["usage"] == "/probe <query>"
            # /help renders from the same registry.
            assert "/probe <query>" in intake_commands.help_text()
        finally:
            del intake_commands.SHARED_COMMANDS["/probe"]

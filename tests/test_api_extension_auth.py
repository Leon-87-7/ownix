"""Tests for the /api/extension/* endpoints and bearer-token auth through
SessionMiddleware (issue #479)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

CHAT_ID = 5555


@pytest.fixture(autouse=True)
def _memory_backend_reset() -> None:
    # session_store._memory is a module-level global (shared with
    # extension_tokens.py's Redis/memory dual backend) — clear it per test so
    # a token minted in one test can't leak into another's chat_id-scoped list.
    from src.auth import session as session_store

    session_store._memory.clear()
    yield
    session_store._memory.clear()


@pytest.fixture
def ext_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "extension_auth_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.extension_auth import extension_auth_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    rate_limit.reset()

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(extension_auth_router)

    @test_app.get("/api/probe")
    async def probe(request: Request) -> dict:
        return {"user": request.state.user}

    # A bearer token must only ever authenticate paths under /api/intake/* —
    # this stub stands in for that scope without needing the real intake router.
    @test_app.get("/api/intake/probe")
    async def intake_probe(request: Request) -> dict:
        return {"user": request.state.user}

    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


class TestPairAndRedeem:
    def test_pair_requires_session(self, ext_client: TestClient) -> None:
        resp = ext_client.post("/api/extension/pair")
        assert resp.status_code == 401

    def test_full_pairing_flow(self, ext_client: TestClient) -> None:
        _login(ext_client)
        pair_resp = ext_client.post("/api/extension/pair")
        assert pair_resp.status_code == 200
        code = pair_resp.json()["code"]

        ext_client.cookies.clear()  # the extension redeeming has no dashboard session
        redeem_resp = ext_client.post("/api/extension/token", json={"code": code})
        assert redeem_resp.status_code == 200
        body = redeem_resp.json()
        assert body["chat_id"] == CHAT_ID
        assert body["token"]

    def test_pairing_code_is_single_use_at_the_api_layer(self, ext_client: TestClient) -> None:
        _login(ext_client)
        code = ext_client.post("/api/extension/pair").json()["code"]
        ext_client.cookies.clear()

        first = ext_client.post("/api/extension/token", json={"code": code})
        second = ext_client.post("/api/extension/token", json={"code": code})
        assert first.status_code == 200
        assert second.status_code == 401

    def test_invalid_code_is_401(self, ext_client: TestClient) -> None:
        resp = ext_client.post("/api/extension/token", json={"code": "bogus"})
        assert resp.status_code == 401


def _pair_and_redeem(client: TestClient) -> str:
    _login(client)
    code = client.post("/api/extension/pair").json()["code"]
    client.cookies.clear()
    return client.post("/api/extension/token", json={"code": code}).json()["token"]


class TestBearerAuth:
    def test_bearer_token_authenticates_intake_requests(self, ext_client: TestClient) -> None:
        token = _pair_and_redeem(ext_client)

        resp = ext_client.get("/api/intake/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user"]["id"] == CHAT_ID
        assert resp.json()["user"]["auth"] == "extension_token"

    def test_bearer_token_does_not_authenticate_non_intake_paths(self, ext_client: TestClient) -> None:
        # Least-privilege (issue #479): a leaked extension token must not
        # double as a full-account session on unrelated routes.
        token = _pair_and_redeem(ext_client)

        resp = ext_client.get("/api/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_invalid_bearer_token_is_401(self, ext_client: TestClient) -> None:
        resp = ext_client.get(
            "/api/intake/probe", headers={"Authorization": "Bearer garbage"}
        )
        assert resp.status_code == 401

    def test_revoked_token_stops_authenticating_immediately(self, ext_client: TestClient) -> None:
        token = _pair_and_redeem(ext_client)

        assert (
            ext_client.get(
                "/api/intake/probe", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 200
        )

        _login(ext_client)
        token_id = ext_client.get("/api/extension/tokens").json()[0]["id"]
        revoke_resp = ext_client.delete(f"/api/extension/tokens/{token_id}")
        assert revoke_resp.status_code == 204
        ext_client.cookies.clear()

        resp = ext_client.get("/api/intake/probe", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401


class TestTokenListAndRevoke:
    def test_list_tokens_requires_session(self, ext_client: TestClient) -> None:
        assert ext_client.get("/api/extension/tokens").status_code == 401

    def test_revoke_unknown_token_is_404(self, ext_client: TestClient) -> None:
        _login(ext_client)
        resp = ext_client.delete("/api/extension/tokens/not-a-real-hash")
        assert resp.status_code == 404

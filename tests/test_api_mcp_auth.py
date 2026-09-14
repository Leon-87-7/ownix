from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

CHAT_ID = 8632


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "mcp-auth.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    from src import database
    from src.api.mcp_auth import mcp_auth_router
    from src.auth import session as session_store
    from src.auth.middleware import SessionMiddleware
    from src.intake import rate_limit

    session_store._memory.clear()
    rate_limit.reset()
    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(mcp_auth_router)

    @app.get("/api/intake/probe")
    async def intake_probe(request: Request) -> dict:
        return request.state.user

    return TestClient(app)


def login(client: TestClient, chat_id: int = CHAT_ID) -> None:
    from src.auth import session as session_store

    client.cookies.set("vig_session", asyncio.run(session_store.mint({"id": chat_id})))


def issue(client: TestClient) -> str:
    login(client)
    code = client.post("/api/mcp/pair").json()["code"]
    client.cookies.clear()
    return client.post("/api/mcp/token", json={"code": code}).json()["token"]


def test_pair_redeem_ping_and_cross_prefix_isolation(client: TestClient) -> None:
    assert client.post("/api/mcp/pair").status_code == 401
    login(client)
    assert client.get("/api/mcp/ping").status_code == 401
    client.cookies.clear()
    token = issue(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/mcp/ping", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"chat_id": CHAT_ID}
    assert client.get("/api/intake/probe", headers=headers).status_code == 401


def test_extension_token_cannot_authenticate_mcp(client: TestClient) -> None:
    from src.auth import extension_tokens

    token = asyncio.run(extension_tokens.issue_extension_token(CHAT_ID))
    response = client.get("/api/mcp/ping", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_revocation_and_tenant_checked_management(client: TestClient) -> None:
    token = issue(client)
    login(client)
    token_id = client.get("/api/mcp/tokens").json()[0]["id"]
    assert client.delete(f"/api/mcp/tokens/{token_id}").status_code == 204
    client.cookies.clear()
    assert (
        client.get("/api/mcp/ping", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    )


def test_pair_and_redeem_are_rate_limited(client: TestClient) -> None:
    login(client)
    for _ in range(10):
        assert client.post("/api/mcp/pair").status_code == 200
    assert client.post("/api/mcp/pair").status_code == 429
    client.cookies.clear()
    for _ in range(20):
        client.post("/api/mcp/token", json={"code": "invalid"})
    assert client.post("/api/mcp/token", json={"code": "invalid"}).status_code == 429

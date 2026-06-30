"""Tests for HMAC verifier, Redis session store, and session middleware.

Covers the two PRD seams for S1 (issue #84):
  1. HMAC verifier golden vectors
  2. Session store mint/resolve/revoke + middleware 401/pass behavior
"""

from __future__ import annotations

import hashlib
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import hmac
import json
import time
from pathlib import Path

import pytest
from src.auth.hmac_verify import verify_telegram_auth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_payload(data: dict[str, str], bot_token: str) -> str:
    """Return the HMAC-SHA256 hex for a given data dict and bot token."""
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def _make_payload(bot_token: str, age_seconds: int = 0, **extra: str) -> dict[str, str]:
    """Build a correctly-signed Telegram auth payload."""
    data: dict[str, str] = {
        "id": "99999",
        "first_name": "Test",
        "auth_date": str(int(time.time()) - age_seconds),
        **extra,
    }
    data["hash"] = _sign_payload(data, bot_token)
    return data


# ---------------------------------------------------------------------------
# HMAC golden vectors
# ---------------------------------------------------------------------------

TOKEN = "test-bot-token"


class TestVerifyTelegramAuth:
    def test_valid_payload_returns_user(self):
        payload = _make_payload(TOKEN)
        result = verify_telegram_auth(payload, TOKEN)
        assert result is not None
        assert result["id"] == "99999"
        assert "hash" not in result

    def test_tampered_hash_returns_none(self):
        payload = _make_payload(TOKEN)
        payload["hash"] = "deadbeef" * 8
        assert verify_telegram_auth(payload, TOKEN) is None

    def test_wrong_token_returns_none(self):
        payload = _make_payload(TOKEN)
        assert verify_telegram_auth(payload, "wrong-token") is None

    def test_stale_auth_date_returns_none(self):
        # auth_date older than 24 h + 1 s
        payload = _make_payload(TOKEN, age_seconds=86_401)
        assert verify_telegram_auth(payload, TOKEN) is None

    def test_missing_hash_returns_none(self):
        payload = _make_payload(TOKEN)
        del payload["hash"]
        assert verify_telegram_auth(payload, TOKEN) is None

    def test_missing_auth_date_returns_none(self):
        # Build a payload without auth_date (hash is over remaining fields)
        data = {"id": "99999", "first_name": "Test"}
        data["hash"] = _sign_payload(data, TOKEN)
        assert verify_telegram_auth(data, TOKEN) is None

    def test_extra_fields_included_in_check(self):
        payload = _make_payload(TOKEN, username="tester")
        result = verify_telegram_auth(payload, TOKEN)
        assert result is not None
        assert result["username"] == "tester"


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, *keys: str) -> int:
        return sum(1 for k in keys if self._store.pop(k, None) is not None)

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    import src.auth.session as session_module

    fr = FakeRedis()
    monkeypatch.setattr(session_module, "_redis", fr)
    return fr


class TestSessionStore:
    async def test_mint_resolve_roundtrip(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        user = {"id": 42, "username": "leon"}
        sid = await session.mint(user)
        assert await session.resolve(sid) == user

    async def test_revoke_then_resolve_returns_none(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        sid = await session.mint({"id": 1})
        await session.revoke(sid)
        assert await session.resolve(sid) is None

    async def test_resolve_unknown_id_returns_none(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        assert await session.resolve("no-such-session") is None


# ---------------------------------------------------------------------------
# Session middleware + auth router (integration via TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Minimal FastAPI app with SessionMiddleware + auth_router + a guarded probe endpoint."""
    db_file = tmp_path / "auth_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

    # Fake the session store so tests don't need Redis
    import src.auth.session as session_module

    fr = FakeRedis()
    monkeypatch.setattr(session_module, "_redis", fr)

    # Build app fresh (avoid touching the global app in src.main)
    from src.auth.middleware import SessionMiddleware
    from src.api.auth import auth_router

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(auth_router)

    @test_app.get("/api/probe")
    async def probe(request: Request) -> dict:
        return {"user": request.state.user}

    @test_app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @test_app.post("/webhook")
    async def webhook_stub() -> dict:
        return {"ok": True}

    return TestClient(test_app, raise_server_exceptions=True)


class TestSessionMiddleware:
    def test_api_endpoint_401_without_cookie(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/probe")
        assert resp.status_code == 401

    def test_api_endpoint_401_with_invalid_cookie(self, auth_client: TestClient) -> None:
        auth_client.cookies.set("vig_session", "invalid-garbage")
        resp = auth_client.get("/api/probe")
        assert resp.status_code == 401

    def test_api_endpoint_passes_with_valid_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module

        # Inject a known session directly into the fake store
        user = {"id": 7, "username": "leon"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = json.dumps(user)

        resp = auth_client.get("/api/probe", cookies={"vig_session": "fixed-session-id"})
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json()["user"]["id"] == 7

    def test_health_passes_without_cookie(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/health")
        assert resp.status_code == 200

    def test_webhook_passes_without_cookie(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/webhook")
        assert resp.status_code == 200

    def test_login_endpoint_reachable_without_cookie(self, auth_client: TestClient) -> None:
        # /api/auth/telegram is the login endpoint — must not 401 before payload validation
        # We send a deliberately invalid payload; the response should be 422 (validation)
        # or 401 (bad HMAC), NOT the middleware's 401 "Not authenticated".
        resp = auth_client.post("/api/auth/telegram", json={"bad": "data"})
        # 422 = FastAPI schema validation (missing fields) — middleware did not block it
        assert resp.status_code == 422


class TestAuthRouter:
    def test_logout_clears_cookie(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module

        user = {"id": 5}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:logout-sid"] = json.dumps(user)

        auth_client.cookies.set("vig_session", "logout-sid")
        resp = auth_client.post("/api/auth/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/logout"
        # Session key should be gone
        assert "session:logout-sid" not in fr._store
        # Cookie must be actively cleared, not just present in the header
        set_cookie = resp.headers["set-cookie"]
        assert "vig_session=" in set_cookie
        assert 'vig_session=""' in set_cookie or "vig_session=;" in set_cookie
        assert "Max-Age=0" in set_cookie or "expires=Thu, 01 Jan 1970" in set_cookie

    def test_me_returns_current_user(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module

        user = {"id": 99, "username": "me_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:me-sid"] = json.dumps(user)

        auth_client.cookies.set("vig_session", "me-sid")
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "me_user"

"""Tests for HMAC verifier, Redis session store, and session middleware.

Covers the two PRD seams for S1 (issue #84):
  1. HMAC verifier golden vectors
  2. Session store mint/resolve/revoke + middleware 401/pass behavior
"""

from __future__ import annotations

import asyncio
import hashlib
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
import hmac
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock

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

    async def getdel(self, key: str) -> str | None:
        return self._store.pop(key, None)

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    import src.auth.session as session_module

    fr = FakeRedis()
    monkeypatch.setattr(session_module.settings, "SESSION_BACKEND", "redis")
    monkeypatch.setattr(session_module, "_redis", fr)
    return fr


class TestSessionStore:
    async def test_mint_resolve_roundtrip(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        user = {"id": 42, "username": "leon"}
        sid = await session.mint(user)
        assert await session.resolve(sid) == user

    async def test_memory_backend_mint_resolve_roundtrip(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.auth import session

        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        await session.close()

        user = {"id": 43, "username": "local"}
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

    async def test_handoff_redeems_once_then_returns_none(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        token = await session.mint_handoff("real-session-id")
        assert await session.redeem_handoff(token) == "real-session-id"
        assert await session.redeem_handoff(token) is None

    async def test_memory_backend_handoff_redeems_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.auth import session

        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        await session.close()

        token = await session.mint_handoff("real-session-id")

        assert await session.redeem_handoff(token) == "real-session-id"
        assert await session.redeem_handoff(token) is None

    async def test_redeem_unknown_handoff_returns_none(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        assert await session.redeem_handoff("no-such-token") is None


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
    monkeypatch.setattr(session_module.settings, "SESSION_BACKEND", "redis")
    monkeypatch.setattr(session_module, "_redis", fr)

    # Build app fresh (avoid touching the global app in src.main)
    from src import database
    from src.auth.middleware import SessionMiddleware
    from src.api.auth import auth_router

    asyncio.run(database.init_db())

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(auth_router)

    @test_app.get("/api/probe")
    async def probe(request: Request) -> dict:
        return {"user": request.state.user}

    @test_app.get("/api/google/connect")
    async def google_connect_probe(request: Request) -> dict:
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
        from src import database

        # Inject a known session directly into the fake store
        user = {"id": 7, "username": "leon"}
        asyncio.run(database.set_user_status(7, "approved"))
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = json.dumps(user)

        resp = auth_client.get("/api/probe", cookies={"vig_session": "fixed-session-id"})
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json()["user"]["id"] == 7

    def test_google_connect_reachable_via_handoff_token(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """openLink hands off to the system browser, which has no cookie — the Mini App
        appends a single-use handoff token (not the session id) and this path must
        redeem it as a fallback."""
        import src.auth.session as session_module
        from src import database

        user = {"id": 9, "username": "mini_user"}
        asyncio.run(database.set_user_status(9, "approved"))
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:mini-connect-sid"] = json.dumps(user)
        fr._store["connect_handoff:handoff-tok"] = "mini-connect-sid"

        resp = auth_client.get("/api/google/connect", params={"token": "handoff-tok"})
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json()["user"]["id"] == 9
        # Single-use: the token must be gone after redemption.
        assert "connect_handoff:handoff-tok" not in fr._store

    def test_google_connect_falls_back_to_token_with_stale_cookie(
        self, auth_client: TestClient
    ) -> None:
        """A stale/expired same-origin cookie in the system browser must not shadow a
        valid handoff token — the fallback must still run when cookie resolution fails."""
        import src.auth.session as session_module
        from src import database

        user = {"id": 11, "username": "mini_user_2"}
        asyncio.run(database.set_user_status(11, "approved"))
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:mini-connect-sid-2"] = json.dumps(user)
        fr._store["connect_handoff:handoff-tok-2"] = "mini-connect-sid-2"

        resp = auth_client.get(
            "/api/google/connect",
            params={"token": "handoff-tok-2"},
            cookies={"vig_session": "stale-or-expired-cookie"},
        )
        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json()["user"]["id"] == 11

    def test_probe_endpoint_ignores_handoff_token(self, auth_client: TestClient) -> None:
        """The handoff-token fallback is scoped to /api/google/connect only, not every route."""
        import src.auth.session as session_module

        user = {"id": 10, "username": "should_not_pass"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:leaked-sid"] = json.dumps(user)
        fr._store["connect_handoff:leaked-tok"] = "leaked-sid"

        resp = auth_client.get("/api/probe", params={"token": "leaked-tok"})
        assert resp.status_code == 401

    def test_api_endpoint_403_with_pending_session(self, auth_client: TestClient) -> None:
        import src.auth.session as session_module

        user = {"id": 8, "username": "pending_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:pending-session-id"] = json.dumps(user)

        resp = auth_client.get("/api/probe", cookies={"vig_session": "pending-session-id"})
        assert resp.status_code == 403

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

    def test_new_user_telegram_login_creates_pending_user(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First-ever sign-in for a tg id: valid HMAC → session cookie set,
        user upserted with default 'pending' status (not yet approved)."""
        from src import database

        monkeypatch.setattr("src.api.auth.settings.TELEGRAM_BOT_TOKEN", TOKEN)
        payload = _make_payload(TOKEN, username="new_guy")

        resp = auth_client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert "vig_session=" in resp.headers["set-cookie"]
        status = asyncio.run(database.get_user_status(99999))
        assert status == "pending"

    def test_dev_login_is_disabled_by_default(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", False)

        resp = auth_client.post("/api/auth/dev-login")

        assert resp.status_code == 404
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_dev_login_creates_pending_user_when_enabled(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        monkeypatch.setattr("src.api.auth.random.randint", lambda _start, _end: 123456789)

        resp = auth_client.post("/api/auth/dev-login")

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert "vig_session=" in resp.headers["set-cookie"]
        status = asyncio.run(database.get_user_status(123456789))
        assert status == "pending"

    def test_dev_login_quiet_by_default(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notify = AsyncMock()
        monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)
        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.OPS_DEV_NOTIFICATIONS", False)
        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        monkeypatch.setattr("src.api.auth.random.randint", lambda _start, _end: 123456790)

        resp = auth_client.post("/api/auth/dev-login")

        assert resp.status_code == 200
        notify.assert_not_awaited()

    def test_dev_approve_fallback_approves_current_dev_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database

        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        user = {"id": 123456792, "username": "dev_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:dev-approve-sid"] = json.dumps(user)

        resp = auth_client.post("/api/auth/dev-approve", cookies={"vig_session": "dev-approve-sid"})

        assert resp.status_code == 200
        assert asyncio.run(database.get_user_status(123456792)) == "approved"

    def test_dev_login_sends_marked_ops_card_when_enabled(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notify = AsyncMock()
        monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)
        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.OPS_DEV_NOTIFICATIONS", True)
        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        monkeypatch.setattr("src.api.auth.random.randint", lambda _start, _end: 123456791)

        resp = auth_client.post("/api/auth/dev-login")

        assert resp.status_code == 200
        notify.assert_awaited_once_with(123456791, "dev-123456791@local.test", dev=True)


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
        assert resp.json()["status"] == "pending"

    def test_set_email_persists_for_current_user(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database

        notify = AsyncMock()
        monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)
        user = {"id": 101, "username": "email_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:email-sid"] = json.dumps(user)

        resp = auth_client.put(
            "/api/auth/email",
            cookies={"vig_session": "email-sid"},
            json={"email": "User@Example.COM"},
        )

        assert resp.status_code == 200
        assert resp.json()["email"] == "user@example.com"
        db_user = asyncio.run(database.get_user(101))
        assert db_user is not None
        assert db_user["email"] == "user@example.com"
        notify.assert_awaited_once_with(101, "user@example.com")

    def test_set_email_does_not_notify_for_approved_user(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database

        notify = AsyncMock()
        monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)
        user = {"id": 102, "username": "approved_user"}
        asyncio.run(database.set_user_status(102, "approved"))
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:approved-email-sid"] = json.dumps(user)

        resp = auth_client.put(
            "/api/auth/email",
            cookies={"vig_session": "approved-email-sid"},
            json={"email": "Approved@Example.COM"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# Telegram Mini App initData
# ---------------------------------------------------------------------------


def _sign_miniapp(data: dict[str, str], bot_token: str) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def _make_init_data(
    bot_token: str,
    *,
    auth_date: int = 1_700_000_000,
    user_id: int = 4242,
    chat_id: int | None = None,
) -> str:
    from urllib.parse import urlencode

    data = {
        "auth_date": str(auth_date),
        "query_id": "AAH-test",
        "user": json.dumps(
            {"id": user_id, "first_name": "Mini", "username": "mini_user"}, separators=(",", ":")
        ),
    }
    if chat_id is not None:
        data["chat"] = json.dumps({"id": chat_id, "type": "private"}, separators=(",", ":"))
    data["hash"] = _sign_miniapp(data, bot_token)
    return urlencode(data)


def test_verify_miniapp_init_data_accepts_fresh_signed_payload() -> None:
    from src.auth.telegram_miniapp import trusted_chat_id, verify_init_data

    init_data = _make_init_data(TOKEN, auth_date=1_700_000_000, chat_id=7777)
    verified = verify_init_data(init_data, TOKEN, now=1_700_000_030)

    assert verified is not None
    assert verified["user"]["id"] == 4242
    assert trusted_chat_id(verified) == 4242


def test_verify_miniapp_init_data_rejects_tampering_and_stale_payloads() -> None:
    from src.auth.telegram_miniapp import verify_init_data

    init_data = _make_init_data(TOKEN, auth_date=1_700_000_000)
    assert (
        verify_init_data(init_data.replace("mini_user", "attacker"), TOKEN, now=1_700_000_030)
        is None
    )
    assert verify_init_data(init_data, TOKEN, now=1_700_004_000) is None


def test_miniapp_session_mints_same_shape_as_web_login(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api import auth as auth_api

    stored_user: dict[str, object] = {}
    upserted: dict[str, object] = {}

    async def fake_mint(user: dict) -> str:
        stored_user.update(user)
        return "mini-session"

    async def fake_mint_handoff(session_id: str) -> str:
        assert session_id == "mini-session"
        return "mini-handoff-token"

    async def fake_upsert_user(**kwargs: object) -> None:
        upserted.update(kwargs)

    monkeypatch.setattr(auth_api.session_store, "mint", fake_mint)
    monkeypatch.setattr(auth_api.session_store, "mint_handoff", fake_mint_handoff)
    monkeypatch.setattr(auth_api.database, "upsert_user", fake_upsert_user)
    monkeypatch.setattr(auth_api.settings, "TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setattr(auth_api.settings, "SESSION_COOKIE_SECURE", False)

    response = Response()
    payload = auth_api.MiniAppSessionPayload(
        init_data=_make_init_data(TOKEN, auth_date=int(time.time()), chat_id=-7777)
    )
    import asyncio

    result = asyncio.run(auth_api.miniapp_session(payload, response))

    assert result["ok"] is True
    assert result["google_connect_url"] == "/api/google/connect?token=mini-handoff-token"
    assert upserted["tg_id"] == 4242
    assert stored_user == {
        "id": 4242,
        "first_name": "Mini",
        "username": "mini_user",
        "photo_url": None,
        "source": "telegram_mini_app",
    }
    assert "vig_session=mini-session" in response.headers["set-cookie"]
    assert "secure" in response.headers["set-cookie"].lower()

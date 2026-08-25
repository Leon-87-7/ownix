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
        self._sets: dict[str, set[str]] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, *keys: str) -> int:
        removed = sum(1 for k in keys if self._store.pop(k, None) is not None)
        removed += sum(1 for k in keys if self._sets.pop(k, None) is not None)
        return removed

    async def getdel(self, key: str) -> str | None:
        return self._store.pop(key, None)

    async def sadd(self, key: str, *members: str) -> int:
        target = self._sets.setdefault(key, set())
        before = len(target)
        target.update(members)
        return len(target) - before

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, ()))

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._store or key in self._sets

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

    async def test_dashboard_handoff_redeems_chat_id_once(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        token = await session.mint_dashboard_handoff(42, ttl=3600)

        assert await session.redeem_dashboard_handoff(token) == 42
        assert await session.redeem_dashboard_handoff(token) is None

    async def test_dashboard_handoff_rejects_corrupt_value(self, fake_redis: FakeRedis) -> None:
        from src.auth import session

        fake_redis._store["dashboard_handoff:bad-token"] = "not-a-chat-id"

        assert await session.redeem_dashboard_handoff("bad-token") is None


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

    def test_reviewer_login_endpoint_reachable_without_cookie(
        self, auth_client: TestClient
    ) -> None:
        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": "reviewer@example.com", "password": "wrong"},
        )

        assert resp.status_code in {401, 404}

    def test_dashboard_handoff_get_only_renders_confirmation(self, auth_client: TestClient) -> None:
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["dashboard_handoff:dash-token"] = "4242"

        resp = auth_client.get(
            "/api/auth/handoff",
            params={"token": "dash-token", "job_id": "20260718_123456_AB12CD34"},
            follow_redirects=False,
        )

        assert resp.status_code == 200
        assert "Open your dashboard" in resp.text
        assert "set-cookie" not in resp.headers
        assert fr._store["dashboard_handoff:dash-token"] == "4242"

    def test_dashboard_handoff_mints_session_on_redeem(self, auth_client: TestClient) -> None:
        import src.auth.session as session_module
        from src import database

        asyncio.run(
            database.upsert_user(
                tg_id=4242,
                username="dashboard_user",
                first_name="Dash",
                last_name=None,
                photo_url="https://example.test/avatar.png",
            )
        )
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["dashboard_handoff:dash-token"] = "4242"

        resp = auth_client.post(
            "/api/auth/handoff",
            data={"token": "dash-token", "job_id": "20260718_123456_AB12CD34"},
            follow_redirects=False,
        )

        assert resp.status_code == 303, f"Unexpected: {resp.text}"
        assert resp.headers["location"] == "/jobs/20260718_123456_AB12CD34"
        assert "vig_session=" in resp.headers["set-cookie"]
        assert "dashboard_handoff:dash-token" not in fr._store
        session_values = [
            json.loads(value) for key, value in fr._store.items() if key.startswith("session:")
        ]
        assert session_values == [
            {
                "id": 4242,
                "first_name": "Dash",
                "username": "dashboard_user",
                "photo_url": "https://example.test/avatar.png",
            }
        ]

    def test_dashboard_handoff_rejects_invalid_job_id_without_consuming_token(
        self, auth_client: TestClient
    ) -> None:
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["dashboard_handoff:dash-token"] = "4242"

        resp = auth_client.get(
            "/api/auth/handoff",
            params={"token": "dash-token", "job_id": "../secret"},
            follow_redirects=False,
        )

        assert resp.status_code == 400
        assert fr._store["dashboard_handoff:dash-token"] == "4242"

    def test_dashboard_button_row_mints_only_handoff_token(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src.utils import dashboard_button_row

        monkeypatch.setattr("src.config.settings.DASHBOARD_URL", "https://dash.example.test")
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]

        row = asyncio.run(dashboard_button_row("20260718_123456_AB12CD34", 4242))

        assert row[0][0]["url"].startswith("https://dash.example.test/api/auth/handoff?")
        assert not any(key.startswith("session:") for key in fr._store)
        assert len([key for key in fr._store if key.startswith("dashboard_handoff:")]) == 1

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

    def test_blocked_telegram_login_does_not_receive_preview_cookie(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        monkeypatch.setattr("src.api.auth.settings.TELEGRAM_BOT_TOKEN", TOKEN)
        asyncio.run(database.set_user_status(100001, "blocked"))
        payload = _make_payload(TOKEN, id="100001", username="blocked_user")

        resp = auth_client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        set_cookie = resp.headers.get("set-cookie", "")
        assert "vig_session=" in set_cookie
        assert "ownix_preview=1" not in set_cookie
        assert "ownix_preview=" in set_cookie
        assert "Max-Age=0" in set_cookie

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
        user = asyncio.run(database.get_user(123456789))
        assert user is not None
        assert user["email"] is None

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

    def test_dev_login_email_save_sends_marked_ops_card_with_input_email(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        notify = AsyncMock()
        monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)
        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")
        monkeypatch.setattr("src.api.auth.random.randint", lambda _start, _end: 123456791)
        # Secure=True (the default — see SESSION_COOKIE_SECURE in src/config.py) means
        # httpx's cookie jar won't resend the login cookie on this test's second, plain
        # http://testserver request, so the /email PUT below would look unauthenticated.
        monkeypatch.setattr("src.api.auth.settings.SESSION_COOKIE_SECURE", False)

        login = auth_client.post("/api/auth/dev-login")
        assert login.status_code == 200
        notify.assert_not_awaited()

        resp = auth_client.put("/api/auth/email", json={"email": "Typed@Example.COM"})

        assert resp.status_code == 200
        assert resp.json()["email"] == "typed@example.com"
        notify.assert_awaited_once_with(123456791, "typed@example.com", dev=True)

    def test_reviewer_login_is_disabled_by_default(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_ENABLED", False)

        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": "reviewer@example.com", "password": "review-code"},
        )

        assert resp.status_code == 404
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_reviewer_login_rejects_invalid_credentials(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_EMAIL", "reviewer@example.com")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_PASSWORD", "review-code")

        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": "reviewer@example.com", "password": "wrong"},
        )

        assert resp.status_code == 401
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_reviewer_login_rejects_non_ascii_invalid_password(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_EMAIL", "reviewer@example.com")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_PASSWORD", "review-code")

        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": "reviewer@example.com", "password": "café"},
        )

        assert resp.status_code == 401
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_reviewer_login_creates_approved_email_user(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_EMAIL", "Reviewer@Example.COM")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_PASSWORD", "review-code")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_USER_ID", -900123001)

        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": " reviewer@example.com ", "password": " review-code "},
        )

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert "vig_session=" in resp.headers["set-cookie"]
        user = asyncio.run(database.get_user(-900123001))
        assert user is not None
        assert user["email"] == "reviewer@example.com"
        assert user["status"] == "approved"

    def test_disabled_reviewer_login_rejects_existing_reviewer_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database

        monkeypatch.setattr("src.auth.middleware.settings.REVIEWER_LOGIN_ENABLED", False)
        asyncio.run(database.set_user_status(-900123001, "approved"))
        user = {
            "id": -900123001,
            "username": "chrome_reviewer",
            "source": "reviewer_login",
        }
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:reviewer-sid"] = json.dumps(user)

        resp = auth_client.get("/api/jobs", cookies={"vig_session": "reviewer-sid"})

        assert resp.status_code == 401


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
        notify.assert_awaited_once_with(101, "user@example.com", dev=False)

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


class TestAccountDeletionLock:
    """Account deletion is exclusive (a "deleting" status locks out every other
    account-write route, same as "pending"/"blocked") and resumable (a deletion
    that fails partway leaves the lock in place; the next login finishes it)."""

    def test_deleting_status_blocks_other_write_routes(self, auth_client: TestClient) -> None:
        import src.auth.session as session_module
        from src import database

        asyncio.run(database.set_user_status(555001, "deleting"))
        user = {"id": 555001, "username": "deleting_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:deleting-sid"] = json.dumps(user)

        resp = auth_client.get("/api/probe", cookies={"vig_session": "deleting-sid"})

        assert resp.status_code == 403

    def test_delete_account_route_rejects_the_operator_account(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_user_status()/set_user_status() force OPERATOR_CHAT_ID to "approved"
        (src/database.py), so the "deleting" lock would silently no-op for it —
        self-service deletion must be refused outright instead."""
        import src.auth.session as session_module
        from src import database

        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 555005)
        user = {"id": 555005, "username": "operator"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:operator-sid"] = json.dumps(user)

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": "operator-sid"})

        assert resp.status_code == 403
        assert asyncio.run(database.get_user_status(555005)) == "approved"
        assert asyncio.run(session_module.resolve("operator-sid")) == user

    def test_delete_account_route_short_circuits_when_already_deleting(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second concurrent DELETE /api/auth/me (another tab/device with a
        still-valid session, since /api/auth/me stays reachable during
        deletion) must not run delete_account() a second time."""
        import src.auth.session as session_module
        from src import database
        from src.api import auth as auth_api

        asyncio.run(
            database.upsert_user(
                tg_id=555008, username="race_user", first_name="R", last_name=None, photo_url=None
            )
        )
        # Simulate the first concurrent call having already acquired the lock.
        asyncio.run(database.set_user_status(555008, "deleting"))
        user = {"id": 555008, "username": "race_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:race-sid"] = json.dumps(user)

        called = False

        async def spy_delete_account(chat_id: int) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(auth_api, "delete_account", spy_delete_account)

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": "race-sid"})

        assert resp.status_code == 204
        assert called is False

    def test_delete_account_route_revokes_losing_callers_own_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The losing side of a concurrent DELETE /api/auth/me race still owns
        a live session cookie — it must be revoked too, not just the winning
        caller's, or the loser's session token stays valid until its natural
        TTL even though the account is being deleted."""
        import src.auth.session as session_module
        from src import database
        from src.api import auth as auth_api

        asyncio.run(
            database.upsert_user(
                tg_id=555009, username="race_loser", first_name="R", last_name=None, photo_url=None
            )
        )
        # Simulate the first concurrent call having already acquired the lock.
        asyncio.run(database.set_user_status(555009, "deleting"))
        user = {"id": 555009, "username": "race_loser"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:race-loser-sid"] = json.dumps(user)
        fr._sets["account_sessions:555009"] = {"race-loser-sid"}

        async def spy_delete_account(chat_id: int) -> None:
            pass

        monkeypatch.setattr(auth_api, "delete_account", spy_delete_account)

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": "race-loser-sid"})

        assert resp.status_code == 204
        assert asyncio.run(session_module.resolve("race-loser-sid")) is None

    def test_delete_account_route_locks_and_revokes_session_before_cleanup_runs(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database
        from src.api import auth as auth_api

        asyncio.run(
            database.upsert_user(
                tg_id=555002, username="del_user", first_name="D", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555002, "approved"))
        user = {"id": 555002, "username": "del_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:delete-sid"] = json.dumps(user)
        fr._sets["account_sessions:555002"] = {"delete-sid"}

        real_delete_account = auth_api.delete_account
        seen_status_at_call: list[str] = []

        async def spy_delete_account(chat_id: int) -> None:
            seen_status_at_call.append(await database.get_user_status(chat_id))
            assert await session_module.resolve("delete-sid") is None
            await real_delete_account(chat_id)

        monkeypatch.setattr(auth_api, "delete_account", spy_delete_account)

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": "delete-sid"})

        assert resp.status_code == 204
        assert seen_status_at_call == ["deleting"]
        assert asyncio.run(database.get_user(555002)) is None

    def test_delete_account_route_revokes_every_device_session(
        self, auth_client: TestClient
    ) -> None:
        """A stale-but-still-valid session on a second device must not survive
        deletion: left alive, it could reach PUT /api/auth/email (a
        pre-approval route) after the row is gone and re-create the account
        via _upsert_minimal_user()."""
        import src.auth.session as session_module
        from src import database

        asyncio.run(
            database.upsert_user(
                tg_id=555010,
                username="multi_device",
                first_name="M",
                last_name=None,
                photo_url=None,
            )
        )
        asyncio.run(database.set_user_status(555010, "approved"))
        user = {"id": 555010, "username": "multi_device"}
        sid_a = asyncio.run(session_module.mint(user))
        sid_b = asyncio.run(session_module.mint(user))

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": sid_a})
        assert resp.status_code == 204

        assert asyncio.run(session_module.resolve(sid_b)) is None

        resurrect = auth_client.put(
            "/api/auth/email",
            cookies={"vig_session": sid_b},
            json={"email": "resurrected@example.com"},
        )
        assert resurrect.status_code == 401
        assert asyncio.run(database.get_user(555010)) is None

    def test_delete_account_route_failure_leaves_lock_for_retry(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import src.auth.session as session_module
        from src import database
        from src.api import auth as auth_api

        asyncio.run(
            database.upsert_user(
                tg_id=555003, username="fail_user", first_name="F", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555003, "approved"))
        user = {"id": 555003, "username": "fail_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fail-sid"] = json.dumps(user)
        fr._sets["account_sessions:555003"] = {"fail-sid"}

        async def failing_delete_account(chat_id: int) -> None:
            raise RuntimeError("simulated cleanup failure")

        monkeypatch.setattr(auth_api, "delete_account", failing_delete_account)

        with pytest.raises(RuntimeError):
            auth_client.delete("/api/auth/me", cookies={"vig_session": "fail-sid"})

        assert asyncio.run(database.get_user_status(555003)) == "deleting"
        assert "session:fail-sid" not in fr._store

    def test_login_resumes_stuck_deletion_instead_of_minting_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        monkeypatch.setattr("src.api.auth.settings.TELEGRAM_BOT_TOKEN", TOKEN)
        asyncio.run(
            database.upsert_user(
                tg_id=555004, username="stuck_user", first_name="S", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555004, "deleting"))

        async def _seed_leftover() -> None:
            async with database.connection() as conn:
                await conn.execute(
                    "INSERT INTO jobs (id, chat_id, url, content_type, status, created_at) "
                    "VALUES ('job_stuck', 555004, 'https://example.com/stuck', 'article', 'done', '2026-01-01')"
                )
                await conn.commit()

        asyncio.run(_seed_leftover())

        payload = _make_payload(TOKEN, id="555004", username="stuck_user")
        resp = auth_client.post("/api/auth/telegram", json=payload)

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json() == {"ok": True, "account_deleted": True}
        assert "vig_session=" not in resp.headers.get("set-cookie", "")
        assert asyncio.run(database.get_user(555004)) is None
        assert (
            asyncio.run(database._fetch_one("SELECT 1 FROM jobs WHERE chat_id = ?", (555004,)))
            is None
        )

    def test_reviewer_login_resumes_stuck_deletion_instead_of_minting_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """reviewer_login is a fourth session-minting login path (alongside
        _login_telegram_user, miniapp_session, and redeem_handoff_login) —
        it must not mint a session into, or resurrect via upsert_user, an
        account whose row is mid-deletion."""
        from src import database

        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_EMAIL", "reviewer@example.com")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_PASSWORD", "correct-horse")
        monkeypatch.setattr("src.api.auth.settings.REVIEWER_LOGIN_USER_ID", 555005)

        asyncio.run(
            database.upsert_user(
                tg_id=555005, username="chrome_reviewer", first_name="R", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555005, "deleting"))

        resp = auth_client.post(
            "/api/auth/reviewer-login",
            json={"email": "reviewer@example.com", "password": "correct-horse"},
        )

        assert resp.status_code == 200, f"Unexpected: {resp.text}"
        assert resp.json() == {"ok": True, "account_deleted": True}
        assert "vig_session=" not in resp.headers.get("set-cookie", "")
        assert asyncio.run(database.get_user(555005)) is None

    def test_set_email_rejected_during_deletion(self, auth_client: TestClient) -> None:
        """/email is pre-approval-reachable by design (middleware.py), so it
        bypasses the "deleting" lock too — a second session/device still
        holding a valid cookie must not be able to sneak in a write."""
        import src.auth.session as session_module
        from src import database

        asyncio.run(database.set_user_status(555006, "deleting"))
        user = {"id": 555006, "username": "other_device"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:other-device-sid"] = json.dumps(user)

        resp = auth_client.put(
            "/api/auth/email",
            cookies={"vig_session": "other-device-sid"},
            json={"email": "sneaky@example.com"},
        )

        assert resp.status_code == 403
        assert asyncio.run(database.get_user(555006))["email"] is None

    def test_dev_approve_rejected_during_deletion(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """dev-approve would otherwise flip "deleting" back to "approved" and
        defeat the lock entirely."""
        import src.auth.session as session_module
        from src import database

        monkeypatch.setattr("src.api.auth.settings.DEV_LOGIN_ENABLED", True)
        asyncio.run(database.set_user_status(555007, "deleting"))
        user = {"id": 555007, "username": "other_device"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:dev-approve-other-sid"] = json.dumps(user)

        resp = auth_client.post(
            "/api/auth/dev-approve", cookies={"vig_session": "dev-approve-other-sid"}
        )

        assert resp.status_code == 403
        assert asyncio.run(database.get_user_status(555007)) == "deleting"

    def test_handoff_login_resumes_stuck_deletion_instead_of_minting_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dashboard-notification handoff login is a third session-minting
        path (alongside _login_telegram_user and miniapp_session) — it must
        not mint a session into an account whose row is mid-deletion."""
        import src.auth.session as session_module
        from src import database

        asyncio.run(
            database.upsert_user(
                tg_id=555009, username="handoff_user", first_name="H", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555009, "deleting"))

        token = asyncio.run(session_module.mint_dashboard_handoff(555009, ttl=3600))

        resp = auth_client.post(
            "/api/auth/handoff",
            data={"token": token, "job_id": "job_abc"},
            follow_redirects=False,
        )

        assert resp.status_code == 401
        assert "vig_session=" not in resp.headers.get("set-cookie", "")
        assert asyncio.run(database.get_user(555009)) is None


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


def test_resume_deletion_helper_is_used_by_both_login_paths() -> None:
    """_login_telegram_user and miniapp_session must both resume a stuck
    deletion through the same shared helper, not duplicated inline logic."""
    import inspect

    from src.api import auth as auth_api

    assert callable(auth_api._resume_deletion_if_stuck)
    login_src = inspect.getsource(auth_api._login_telegram_user)
    miniapp_src = inspect.getsource(auth_api.miniapp_session)
    assert "_resume_deletion_if_stuck" in login_src
    assert "_resume_deletion_if_stuck" in miniapp_src


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

    async def fake_get_user_status(tg_id: int) -> str:
        return "pending"

    monkeypatch.setattr(auth_api.session_store, "mint", fake_mint)
    monkeypatch.setattr(auth_api.session_store, "mint_handoff", fake_mint_handoff)
    monkeypatch.setattr(auth_api.database, "upsert_user", fake_upsert_user)
    monkeypatch.setattr(auth_api.database, "get_user_status", fake_get_user_status)
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

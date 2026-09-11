"""Regression coverage for ADR-0061 identity resolution."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from src import database
from src.auth.identity import resolve_owner
from tests.test_auth import FakeRedis


@pytest.fixture
async def identity_db(tmp_path, monkeypatch):
    path = tmp_path / "identity.db"
    monkeypatch.setattr(database.settings, "DB_PATH", str(path))
    await database.init_db()
    return path


@pytest.fixture
def identity_auth_client(tmp_path, monkeypatch):
    """Same shape as tests/test_auth.py's `auth_client` — a fresh FastAPI app
    with SessionMiddleware + auth_router, a fake Redis-backed session store,
    and SESSION_COOKIE_SECURE off so the TestClient's cookie jar actually
    resends cookies across requests in the same test (required for the
    OAuth-state cookie set on /connect to come back on /callback)."""
    db_file = tmp_path / "identity_auth_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.api.auth.settings.SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr("src.api.auth.settings.DASHBOARD_URL", "https://app.example.test")

    import src.auth.session as session_module

    fr = FakeRedis()
    monkeypatch.setattr(session_module.settings, "SESSION_BACKEND", "redis")
    monkeypatch.setattr(session_module, "_redis", fr)

    from src.auth.middleware import SessionMiddleware
    from src.api.auth import auth_router

    asyncio.run(database.init_db())

    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router)

    @app.get("/api/probe")
    async def probe(request: Request) -> dict:
        return {"user": request.state.user}

    return TestClient(app, raise_server_exceptions=True)


@pytest.mark.asyncio
async def test_repeat_provider_login_is_idempotent(identity_db):
    first = await resolve_owner(
        "github", "123", email="Ada@Example.com", email_verified=True
    )
    second = await resolve_owner(
        "github", "123", email="ada@example.com", email_verified=True
    )
    assert first == second
    assert (await database.get_user(first))["email"] == "ada@example.com"


@pytest.mark.asyncio
async def test_verified_email_merges_providers(identity_db):
    github = await resolve_owner(
        "github", "1", email="same@example.com", email_verified=True
    )
    google = await resolve_owner(
        "google", "2", email="SAME@example.com", email_verified=True
    )
    assert github == google
    assert await database.get_identity_owner("github", "1") == github
    assert await database.get_identity_owner("google", "2") == github


@pytest.mark.asyncio
async def test_late_verified_email_merges_into_the_account_that_owns_it(identity_db):
    """A provider can withhold a verified email on first login and hand it over
    later (a private GitHub address). That late email still has to merge under
    ADR-0061's policy instead of stranding the identity on its own account."""
    github = await resolve_owner("github", "1", email=None, email_verified=False)
    google = await resolve_owner(
        "google", "2", email="shared@example.com", email_verified=True
    )
    assert github != google

    merged = await resolve_owner(
        "github", "1", email="SHARED@example.com", email_verified=True
    )
    assert merged == google
    assert await database.get_identity_owner("github", "1") == google


@pytest.mark.asyncio
async def test_late_verified_email_backfills_when_unclaimed(identity_db):
    owner = await resolve_owner("github", "1", email=None, email_verified=False)
    assert (await database.get_user(owner))["email"] is None

    again = await resolve_owner(
        "github", "1", email="solo@example.com", email_verified=True
    )
    assert again == owner
    assert (await database.get_user(owner))["email"] == "solo@example.com"


@pytest.mark.asyncio
async def test_late_unverified_email_never_merges(identity_db):
    github = await resolve_owner("github", "1", email=None, email_verified=False)
    google = await resolve_owner(
        "google", "2", email="shared@example.com", email_verified=True
    )
    still_separate = await resolve_owner(
        "github", "1", email="shared@example.com", email_verified=False
    )
    assert still_separate == github != google


@pytest.mark.asyncio
async def test_unverified_email_does_not_merge(identity_db):
    verified = await resolve_owner(
        "github", "1", email="same@example.com", email_verified=True
    )
    unverified = await resolve_owner(
        "google", "2", email="same@example.com", email_verified=False
    )
    assert verified != unverified


@pytest.mark.asyncio
async def test_concurrent_verified_signups_share_owner(identity_db):
    owners = await asyncio.gather(
        resolve_owner("github", "1", email="race@example.com", email_verified=True),
        resolve_owner("google", "2", email="race@example.com", email_verified=True),
    )
    assert owners[0] == owners[1]


@pytest.mark.asyncio
async def test_synthetic_owner_id_is_disjoint_from_telegram_range(identity_db):
    """Telegram bounds every id (including negative group/supergroup chat
    ids) to 52 significant bits — a synthetic owner id must stay outside
    that range so a future group-chat tenant can never collide with one."""
    owner = await resolve_owner("github", "range-check", email=None, email_verified=False)
    assert owner <= -(2**53)


@pytest.mark.asyncio
async def test_same_subject_race_does_not_leave_an_orphaned_user_row(identity_db, monkeypatch):
    """The in-process lock only protects against a race between two
    resolve_owner() calls in *this* process — it can't see a second API/
    worker process linking the same (provider, subject) first. Simulate
    that by injecting a competing identity_links row the moment our own
    call mints its user row."""
    real_upsert_user = database.upsert_user
    minted_ids: list[int] = []

    async def upsert_user_then_inject_race(**kwargs):
        await real_upsert_user(**kwargs)
        minted_ids.append(kwargs["tg_id"])
        if len(minted_ids) == 1:
            await real_upsert_user(tg_id=-999999, first_name="Other")
            await database.link_identity("github", "race-subject", -999999, verified=False)

    monkeypatch.setattr(database, "upsert_user", upsert_user_then_inject_race)

    owner = await resolve_owner("github", "race-subject", email=None, email_verified=False)

    assert owner == -999999
    assert await database.get_user(minted_ids[0]) is None


@pytest.mark.asyncio
async def test_external_login_recovers_from_email_collision_on_backfill(
    identity_db, monkeypatch
):
    """A second, already-known owner backfilling its email can collide with
    a different, already-existing account that owns it — this must not 500
    the login, per the same recovery shape resolve_owner already has for
    its own analogous case."""
    from src.api import auth as auth_api

    await database.upsert_user(tg_id=-1, first_name="OwnerA")
    await database.upsert_user(tg_id=-2, first_name="OwnerB")
    await database.set_user_email(-2, "shared@example.com")

    async def fake_resolve_owner(provider, subject, *, email, email_verified):
        return -1

    monkeypatch.setattr(auth_api, "resolve_owner", fake_resolve_owner)
    monkeypatch.setattr(auth_api, "notify_operator_invite", AsyncMock())
    monkeypatch.setattr(auth_api.settings, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr("src.auth.session.settings.SESSION_BACKEND", "memory")

    response = await auth_api._external_login(
        provider="github", subject="new-subject", email="shared@example.com",
        email_verified=True, first_name="Someone", username="someone", photo_url=None,
    )

    assert response.status_code == 303
    # The collision was caught and logged, not raised — owner A's email is
    # simply left unset rather than the login failing outright.
    owner_a = await database.get_user(-1)
    assert owner_a["email"] is None


# ---------------------------------------------------------------------------
# HTTP-level login routes (#618, #619, #620, #621)
# ---------------------------------------------------------------------------


def _state_from_redirect(location: str) -> str:
    return parse_qs(urlparse(location).query)["state"][0]


def test_github_callback_new_signup_lands_pending_and_notifies(
    identity_auth_client, monkeypatch, httpx_mock
):
    """#618 acceptance: a first-time GitHub signup lands `pending`, its
    verified GitHub email auto-fills `users.email`, and the existing
    Operator-notify path fires — same as any other first-time signup."""
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_ID", "gh-client")
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_SECRET", "gh-secret")
    monkeypatch.setattr(
        "src.api.auth.settings.GITHUB_OAUTH_REDIRECT_URI",
        "https://app.example.test/api/auth/github/callback",
    )
    notify = AsyncMock()
    monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)

    connect = identity_auth_client.get("/api/auth/github/connect", follow_redirects=False)
    assert connect.status_code == 307
    state = _state_from_redirect(connect.headers["location"])

    httpx_mock.add_response(
        url="https://github.com/login/oauth/access_token",
        json={"access_token": "gh-token"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user",
        json={"id": 555, "login": "octocat", "name": "Octo Cat",
              "avatar_url": "https://gh.example/a.png"},
    )
    httpx_mock.add_response(
        url="https://api.github.com/user/emails",
        json=[{"email": "octo@example.com", "primary": True, "verified": True}],
    )

    resp = identity_auth_client.get(
        "/api/auth/github/callback", params={"code": "abc", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    assert resp.headers["location"] == "/feed"
    assert "vig_session=" in resp.headers["set-cookie"]

    owner_id = asyncio.run(database.get_identity_owner("github", "555"))
    assert owner_id is not None
    user = asyncio.run(database.get_user(owner_id))
    assert user["email"] == "octo@example.com"
    assert user["status"] == "pending"
    notify.assert_awaited_once_with(owner_id, "octo@example.com")


def test_github_callback_rejects_state_without_matching_cookie(
    identity_auth_client, monkeypatch
):
    """Login-CSRF guard: a `state` that never went through this browser's
    /connect (no matching cookie) must be rejected before anything else."""
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_ID", "gh-client")
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_SECRET", "gh-secret")
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_REDIRECT_URI", "https://app.example.test/x")

    resp = identity_auth_client.get(
        "/api/auth/github/callback",
        params={"code": "abc", "state": "attacker-supplied-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_google_callback_rejects_state_without_matching_cookie(
    identity_auth_client, monkeypatch
):
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_ID", "g-client")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_SECRET", "g-secret")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_REDIRECT_URI", "https://app.example.test/y")

    resp = identity_auth_client.get(
        "/api/auth/google/callback",
        params={"code": "abc", "state": "attacker-supplied-state"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


def test_google_login_is_idempotent_and_isolated_from_export(
    identity_auth_client, monkeypatch, httpx_mock
):
    """#619 acceptance: repeat Google logins resolve to the same owner, and
    this slice never touches the export OAuth's own tables."""
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_ID", "g-client")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_SECRET", "g-secret")
    monkeypatch.setattr(
        "src.api.auth.settings.GOOGLE_LOGIN_REDIRECT_URI",
        "https://app.example.test/api/auth/google/callback",
    )
    # Not under test here — avoid a real outbound Telegram call from the
    # first-time-signup notify path.
    monkeypatch.setattr("src.api.auth.notify_operator_invite", AsyncMock())

    def _do_login() -> int:
        connect = identity_auth_client.get("/api/auth/google/connect", follow_redirects=False)
        state = _state_from_redirect(connect.headers["location"])
        httpx_mock.add_response(
            url="https://oauth2.googleapis.com/token", json={"access_token": "g-token"}
        )
        httpx_mock.add_response(
            url="https://openidconnect.googleapis.com/v1/userinfo",
            json={"sub": "789", "email": "ada@example.com", "email_verified": True,
                  "given_name": "Ada", "picture": "https://g.example/a.png"},
        )
        resp = identity_auth_client.get(
            "/api/auth/google/callback", params={"code": "abc", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 303, resp.text
        return resp

    first = _do_login()
    identity_auth_client.cookies.clear()
    second = _do_login()

    owner_id = asyncio.run(database.get_identity_owner("google", "789"))
    assert owner_id is not None
    # Idempotent: both logins resolved the same owner, no duplicate account.
    assert (
        asyncio.run(
            database._fetch_one(
                "SELECT COUNT(*) AS n FROM identity_links WHERE provider = 'google' AND subject = '789'"
            )
        )["n"]
        == 1
    )
    # Isolation from the export flow: this login-only path must never write
    # to either of the export OAuth's own tables.
    assert asyncio.run(database._fetch_one("SELECT 1 FROM google_oauth_tokens")) is None
    assert asyncio.run(database._fetch_one("SELECT 1 FROM google_oauth_states")) is None
    del first, second


def test_magic_link_request_then_redeem_happy_path(identity_auth_client, monkeypatch):
    sent_links: list[str] = []

    async def fake_send(email: str, link: str) -> bool:
        sent_links.append(link)
        return True

    monkeypatch.setattr("src.api.auth.send_magic_link_email", fake_send)

    resp = identity_auth_client.post("/api/auth/email/request", json={"email": "New@Example.com"})
    assert resp.status_code == 200
    token = parse_qs(urlparse(sent_links[0]).query)["token"][0]

    redeemed = identity_auth_client.get(
        "/api/auth/email/callback", params={"token": token}, follow_redirects=False
    )
    assert redeemed.status_code == 303, redeemed.text
    assert redeemed.headers["location"] == "/feed"
    assert "vig_session=" in redeemed.headers["set-cookie"]

    owner_id = asyncio.run(database.get_identity_owner("email", "new@example.com"))
    assert owner_id is not None

    # Single-use: redeeming the same token again must fail, not mint a
    # second session.
    replay = identity_auth_client.get(
        "/api/auth/email/callback", params={"token": token}, follow_redirects=False
    )
    assert replay.status_code == 400


def test_magic_link_callback_rejects_unknown_token(identity_auth_client):
    resp = identity_auth_client.get(
        "/api/auth/email/callback", params={"token": "never-issued"}, follow_redirects=False
    )
    assert resp.status_code == 400


def test_magic_link_request_does_not_leak_account_existence(identity_auth_client, monkeypatch):
    monkeypatch.setattr("src.api.auth.send_magic_link_email", AsyncMock(return_value=True))
    asyncio.run(database.upsert_user(tg_id=-42, first_name="Existing"))
    asyncio.run(database.set_user_email(-42, "existing@example.com"))

    existing = identity_auth_client.post(
        "/api/auth/email/request", json={"email": "existing@example.com"}
    )
    fresh = identity_auth_client.post(
        "/api/auth/email/request", json={"email": "brand-new@example.com"}
    )
    assert existing.status_code == fresh.status_code == 200
    assert existing.json() == fresh.json()


def test_magic_link_request_rejects_localhost_lookalike_host(identity_auth_client, monkeypatch):
    from src.intake import rate_limit

    rate_limit.reset()
    sent: list[str] = []
    monkeypatch.setattr("src.api.auth.send_magic_link_email", AsyncMock(side_effect=sent.append))
    # A prefix check would accept this remote plaintext host and mail it a
    # bearer token; the hostname must match a loopback address exactly.
    monkeypatch.setattr("src.api.auth.settings.DASHBOARD_URL", "http://localhost.attacker.example")

    resp = identity_auth_client.post("/api/auth/email/request", json={"email": "a@example.com"})
    assert resp.status_code == 503
    assert sent == []
    rate_limit.reset()


def test_magic_link_request_is_rate_limited(identity_auth_client, monkeypatch):
    from src.intake import rate_limit

    rate_limit.reset()
    monkeypatch.setattr("src.api.auth.send_magic_link_email", AsyncMock(return_value=True))

    for _ in range(5):
        resp = identity_auth_client.post(
            "/api/auth/email/request", json={"email": "hammered@example.com"}
        )
        assert resp.status_code == 200

    resp = identity_auth_client.post(
        "/api/auth/email/request", json={"email": "hammered@example.com"}
    )
    assert resp.status_code == 429
    rate_limit.reset()


def test_merge_across_providers_never_renotifies_operator(
    identity_auth_client, monkeypatch, httpx_mock
):
    """#621 acceptance (c): a second provider login that merges into an
    existing verified-email account must not re-fire the Operator-approval
    notification — that only ever happens for a genuinely new tenant."""
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_ID", "gh-client")
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_CLIENT_SECRET", "gh-secret")
    monkeypatch.setattr("src.api.auth.settings.GITHUB_OAUTH_REDIRECT_URI", "https://app.example.test/x")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_ID", "g-client")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_CLIENT_SECRET", "g-secret")
    monkeypatch.setattr("src.api.auth.settings.GOOGLE_LOGIN_REDIRECT_URI", "https://app.example.test/y")
    notify = AsyncMock()
    monkeypatch.setattr("src.api.auth.notify_operator_invite", notify)

    gh_connect = identity_auth_client.get("/api/auth/github/connect", follow_redirects=False)
    gh_state = _state_from_redirect(gh_connect.headers["location"])
    httpx_mock.add_response(url="https://github.com/login/oauth/access_token", json={"access_token": "t1"})
    httpx_mock.add_response(url="https://api.github.com/user", json={"id": 1, "login": "shared"})
    httpx_mock.add_response(
        url="https://api.github.com/user/emails",
        json=[{"email": "shared@example.com", "primary": True, "verified": True}],
    )
    first = identity_auth_client.get(
        "/api/auth/github/callback", params={"code": "c1", "state": gh_state}, follow_redirects=False
    )
    assert first.status_code == 303
    notify.assert_awaited_once()

    identity_auth_client.cookies.clear()
    g_connect = identity_auth_client.get("/api/auth/google/connect", follow_redirects=False)
    g_state = _state_from_redirect(g_connect.headers["location"])
    httpx_mock.add_response(url="https://oauth2.googleapis.com/token", json={"access_token": "t2"})
    httpx_mock.add_response(
        url="https://openidconnect.googleapis.com/v1/userinfo",
        json={"sub": "2", "email": "SHARED@example.com", "email_verified": True, "name": "Shared"},
    )
    second = identity_auth_client.get(
        "/api/auth/google/callback", params={"code": "c2", "state": g_state}, follow_redirects=False
    )
    assert second.status_code == 303

    # Still exactly one notify across both logins — the merge did not fire a second.
    notify.assert_awaited_once()
    github_owner = asyncio.run(database.get_identity_owner("github", "1"))
    google_owner = asyncio.run(database.get_identity_owner("google", "2"))
    assert github_owner == google_owner

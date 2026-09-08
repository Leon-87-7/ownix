"""Tests for POST /api/newsletter-digest/resolve (issue #608).

Read-only endpoint: it must create nothing, must enforce the per-chat rate
limit that lives in `src.services.newsletter_archive`, and must translate a
`NewsletterResolutionError` into a 422 rather than a 500.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services import newsletter_archive
from src.services.jina import JinaFetchError

CHAT_ID = 9001

_FEED_ROOT_HTML = """
<html><head><title>AlphaSignal</title>
<link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>
"""

_FEED_HTML = """
<html><body>
<a href="/news/issue-a">Issue A</a>
<a href="/news/issue-b">Issue B</a>
</body></html>
"""


@pytest.fixture(autouse=True)
def _reset_resolver_state() -> Iterator[None]:
    from src.intake import rate_limit

    rate_limit.reset()
    newsletter_archive.reset_cache()
    yield
    rate_limit.reset()
    newsletter_archive.reset_cache()


@pytest.fixture(autouse=True)
def _no_real_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_is_public_url` resolves DNS for real — stub the function itself (not
    `asyncio.get_running_loop`, which TestClient's anyio-backed portal thread
    also depends on and which a global patch would break) so these API tests
    never make a real network call, matching "tests must not hit real
    external APIs unless gated behind RUN_INTEGRATION"."""

    async def _fake_is_public_url(url: str) -> bool:
        return True

    monkeypatch.setattr(newsletter_archive, "_is_public_url", _fake_is_public_url)


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "newsletter_resolve_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.newsletter_digest import newsletter_digest_router
    from src.auth.middleware import SessionMiddleware

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(newsletter_digest_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


def test_resolve_requires_a_session(api_client: TestClient) -> None:
    response = api_client.post("/api/newsletter-digest/resolve", json={"query": "https://example.com"})
    assert response.status_code == 401


def test_resolve_returns_archive_and_recent_issues(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)

    async def fake_fetch_html(url: str, *, client=None) -> str:
        if url == "https://alphasignal.ai":
            return _FEED_ROOT_HTML
        if url == "https://alphasignal.ai/feed.xml":
            return _FEED_HTML
        raise JinaFetchError(404)

    monkeypatch.setattr(newsletter_archive, "fetch_html", fake_fetch_html)

    response = api_client.post(
        "/api/newsletter-digest/resolve", json={"query": "https://alphasignal.ai"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["feed_url"] == "https://alphasignal.ai/feed.xml"
    assert body["issue_path_prefix"] == "/news/"
    assert {issue["slug"] for issue in body["recent_issues"]} == {"issue-a", "issue-b"}


def test_resolve_returns_422_when_nothing_resolves(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)

    async def always_fail(url: str, *, client=None) -> str:
        raise JinaFetchError(404)

    monkeypatch.setattr(newsletter_archive, "fetch_html", always_fail)

    response = api_client.post(
        "/api/newsletter-digest/resolve",
        json={"query": "https://nobody-publishes-here.example"},
    )

    assert response.status_code == 422


def test_resolve_creates_nothing(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only: a successful resolve must not create any subscription row."""
    _login(api_client)

    async def fake_fetch_html(url: str, *, client=None) -> str:
        if url == "https://alphasignal.ai":
            return _FEED_ROOT_HTML
        if url == "https://alphasignal.ai/feed.xml":
            return _FEED_HTML
        raise JinaFetchError(404)

    monkeypatch.setattr(newsletter_archive, "fetch_html", fake_fetch_html)

    api_client.post("/api/newsletter-digest/resolve", json={"query": "https://alphasignal.ai"})

    listing = api_client.get("/api/newsletter-digest")
    assert listing.status_code == 200
    assert listing.json() == []


def test_resolve_is_rate_limited_per_chat(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)
    monkeypatch.setattr(newsletter_archive, "_RATE_LIMIT_MAX_REQUESTS", 1)

    async def always_fail(url: str, *, client=None) -> str:
        raise JinaFetchError(404)

    monkeypatch.setattr(newsletter_archive, "fetch_html", always_fail)

    first = api_client.post(
        "/api/newsletter-digest/resolve", json={"query": "https://example.com"}
    )
    assert first.status_code == 422

    second = api_client.post(
        "/api/newsletter-digest/resolve", json={"query": "https://example.com"}
    )
    assert second.status_code == 429

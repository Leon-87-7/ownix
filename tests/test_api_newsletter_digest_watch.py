"""Tests for the watch-creation/management endpoints (issue #609, PLAN.md §6/§8).

`POST /api/newsletter-digest` must re-resolve `archive_url` server-side rather
than trust anything the client claims about a prior `/resolve` call, create
(or reuse) the shared `publications` row, seed its issues, and enqueue an
explicit first-issue delivery — all per `database.create_newsletter_watch`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services import newsletter_archive

CHAT_ID = 9001


@pytest.fixture(autouse=True)
def _reset_resolver_state() -> Iterator[None]:
    from src.intake import rate_limit

    rate_limit.reset()
    newsletter_archive.reset_cache()
    yield
    rate_limit.reset()
    newsletter_archive.reset_cache()


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "newsletter_watch_api_test.db"
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


def _resolution(**overrides) -> newsletter_archive.NewsletterResolution:
    defaults = dict(
        archive_url="https://alphasignal.ai",
        feed_url="https://alphasignal.ai/feed.xml",
        issue_path_prefix="/news/",
        fetched_title="AlphaSignal",
        recent_issues=[
            newsletter_archive.RecentIssue(
                slug="issue-b", title="Issue B", url="https://alphasignal.ai/news/issue-b"
            ),
            newsletter_archive.RecentIssue(
                slug="issue-a", title="Issue A", url="https://alphasignal.ai/news/issue-a"
            ),
        ],
    )
    defaults.update(overrides)
    return newsletter_archive.NewsletterResolution(**defaults)


def test_create_watch_requires_a_session(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "Signals"}
    )
    assert response.status_code == 401


def test_create_watch_reresolves_server_side_and_enqueues_delivery(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client sends only `{archive_url, name}` — every other field
    (feed_url, issue_path_prefix, fetched_title, recent_issues) must come
    from the server's own fresh resolve, never a value the client supplies or
    implies from an earlier /resolve response."""
    _login(api_client)
    resolve = AsyncMock(return_value=_resolution())
    monkeypatch.setattr(newsletter_archive, "resolve_newsletter_archive", resolve)
    enqueue = AsyncMock()
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", enqueue)

    response = api_client.post(
        "/api/newsletter-digest",
        json={"archive_url": "https://alphasignal.ai/news/some-issue?utm=1", "name": "AI Signals"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["archive_url"] == "https://alphasignal.ai"
    assert body["feed_url"] == "https://alphasignal.ai/feed.xml"
    assert body["fetched_title"] == "AlphaSignal"
    assert body["name"] == "AI Signals"
    assert "delivery_job_id" not in body
    resolve.assert_awaited_once()
    # Re-resolve was called with the client's raw archive_url input, not a
    # trusted client-supplied resolution object.
    assert resolve.await_args.args[0] == "https://alphasignal.ai/news/some-issue?utm=1"
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args[0]["task"] == "email_digest"


def _make_watch_with_candidates(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str, str]:
    """Create a watch and give its Space one `pending` and one `promoting`
    candidate. Returns `(watch_id, pending_id, promoting_id)`."""
    from src import database
    from src.api import newsletter_digest

    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())
    watch = api_client.post(
        "/api/newsletter-digest",
        json={"archive_url": "https://alphasignal.ai", "name": "AI Signals"},
    ).json()

    async def _seed() -> tuple[str, str]:
        pending_id = database.generate_id()
        promoting_id = database.generate_id()
        async with database.connection() as conn:
            for cid, status in ((pending_id, "pending"), (promoting_id, "promoting")):
                await conn.execute(
                    """INSERT INTO digest_candidates
                       (id, space_id, url, canonical_url, title, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        cid,
                        watch["space_id"],
                        f"https://example.com/{cid}",
                        f"https://example.com/{cid}",
                        cid,
                        status,
                    ),
                )
            await conn.commit()
        return pending_id, promoting_id

    pending_id, promoting_id = asyncio.run(_seed())
    return watch["id"], pending_id, promoting_id


def _candidate_status(candidate_id: str) -> str:
    from src import database

    async def _get() -> str:
        row = await database._fetch_one(
            "SELECT status FROM digest_candidates WHERE id = ?", (candidate_id,)
        )
        return row["status"]

    return asyncio.run(_get())


def test_bulk_dismiss_is_pending_only(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue #613. `Dismiss rest` loops this endpoint with `pending_only=true`,
    working from a UI snapshot — so a candidate that turned `promoting` since
    that snapshot must survive rather than being flipped to `dismissed` while
    its job is being created."""
    _login(api_client)
    watch_id, pending_id, promoting_id = _make_watch_with_candidates(api_client, monkeypatch)

    assert (
        api_client.delete(
            f"/api/newsletter-digest/{watch_id}/candidates/{pending_id}?pending_only=true"
        ).status_code
        == 204
    )
    assert _candidate_status(pending_id) == "dismissed"

    # The promoting one is not claimable pending-only — 404, and it is untouched.
    assert (
        api_client.delete(
            f"/api/newsletter-digest/{watch_id}/candidates/{promoting_id}?pending_only=true"
        ).status_code
        == 404
    )
    assert _candidate_status(promoting_id) == "promoting"


def test_single_card_dismiss_still_accepts_promoting(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default (no flag) keeps today's wider `pending`/`promoting` claim —
    #613 narrows only the bulk path."""
    _login(api_client)
    watch_id, _, promoting_id = _make_watch_with_candidates(api_client, monkeypatch)

    assert (
        api_client.delete(
            f"/api/newsletter-digest/{watch_id}/candidates/{promoting_id}"
        ).status_code
        == 204
    )
    assert _candidate_status(promoting_id) == "dismissed"


def test_create_watch_conflicts_when_already_watching(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())

    first = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "A"}
    )
    assert first.status_code == 201

    second = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "B"}
    )
    assert second.status_code == 409


def test_create_watch_returns_422_when_resolution_fails(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive,
        "resolve_newsletter_archive",
        AsyncMock(side_effect=newsletter_archive.NewsletterResolutionError("nope")),
    )

    response = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://nobody.example", "name": "X"}
    )

    assert response.status_code == 422


def test_put_edits_name_only(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())

    created = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "Old name"}
    ).json()

    updated = api_client.put(f"/api/newsletter-digest/{created['id']}", json={"name": "New name"})

    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "New name"
    assert body["archive_url"] == "https://alphasignal.ai"


def test_delete_watch_removes_space_but_keeps_publication(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    from src import database
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())

    created = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "A"}
    ).json()
    publication_id = created["publication_id"]

    deleted = api_client.delete(f"/api/newsletter-digest/{created['id']}")
    assert deleted.status_code == 204

    assert api_client.get(f"/api/newsletter-digest/{created['id']}").status_code == 404
    pub = asyncio.run(database._fetch_one("SELECT id FROM publications WHERE id=?", (publication_id,)))
    assert pub is not None


def test_retry_requeues_latest_error_job(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    from src import database
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())

    created = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "A"}
    ).json()
    job_id = asyncio.run(
        database._fetch_one(
            "SELECT job_id FROM email_digest_payloads WHERE watch_id=?", (created["id"],)
        )
    )["job_id"]
    asyncio.run(database.update_job_status(job_id, "error"))

    enqueue = AsyncMock()
    monkeypatch.setattr(newsletter_digest.queue, "enqueue", enqueue)

    response = api_client.post(f"/api/newsletter-digest/{created['id']}/retry")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
    enqueue.assert_awaited_once()


def test_retry_returns_404_without_a_retryable_job(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _login(api_client)
    monkeypatch.setattr(
        newsletter_archive, "resolve_newsletter_archive", AsyncMock(return_value=_resolution())
    )
    from src.api import newsletter_digest

    monkeypatch.setattr(newsletter_digest.queue, "enqueue", AsyncMock())

    created = api_client.post(
        "/api/newsletter-digest", json={"archive_url": "https://alphasignal.ai", "name": "A"}
    ).json()

    response = api_client.post(f"/api/newsletter-digest/{created['id']}/retry")

    assert response.status_code == 404

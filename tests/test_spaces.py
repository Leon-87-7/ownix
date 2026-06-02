"""Tests for the Spaces API (issue #89 / S6) and its tenant-scoping fix.

Locks in two fixes in ``src/api/spaces.py`` (commit 894c43c):

  1. ``list_space_urls`` is now called with ``chat_id``. The API previously
     called it with a single positional arg while the DB layer already required
     ``chat_id`` — a runtime arity bug that 500'd ``GET /api/spaces/{id}/urls``.
  2. ``add_space_url`` rejects pinning a job owned by another user — a
     cross-tenant IDOR (same class as #96 for templates).

The list join is also scoped by ``chat_id`` as defence-in-depth, verified
independently of the API guard.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class FakeRedis:
    """In-memory stand-in for the session store (no Redis in tests)."""

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


USER_A = {"id": 1, "username": "alice"}
USER_B = {"id": 2, "username": "bob"}

# Cookie maps for authenticating as each tenant.
AS_A = {"vig_session": "sid-a"}
AS_B = {"vig_session": "sid-b"}


@pytest.fixture
def spaces_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A FastAPI app with SessionMiddleware + spaces_router over a fresh file DB.

    Two sessions are pre-seeded so tests can act as USER_A (cookie AS_A) or
    USER_B (cookie AS_B).
    """
    db_file = tmp_path / "spaces_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

    # Fake the session store so the middleware resolves cookies without Redis.
    import src.auth.session as session_module

    fr = FakeRedis()
    monkeypatch.setattr(session_module, "_redis", fr)

    from src import database

    asyncio.run(database.init_db())

    from src.api.spaces import spaces_router
    from src.auth.middleware import SessionMiddleware

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(spaces_router)

    fr._store["session:sid-a"] = json.dumps(USER_A)
    fr._store["session:sid-b"] = json.dumps(USER_B)

    return TestClient(test_app, raise_server_exceptions=True)


def _make_space(client: TestClient, cookies: dict[str, str], name: str = "Space") -> str:
    resp = client.post("/api/spaces", json={"name": name}, cookies=cookies)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _make_job(chat_id: int, url: str) -> str:
    from src import database

    return asyncio.run(
        database.create_job(chat_id=chat_id, url=url, content_type="long")
    )


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


def test_spaces_requires_auth(spaces_client: TestClient) -> None:
    assert spaces_client.get("/api/spaces").status_code == 401


# ---------------------------------------------------------------------------
# CRUD + tenant isolation
# ---------------------------------------------------------------------------


def test_create_and_list_space(spaces_client: TestClient) -> None:
    space_id = _make_space(spaces_client, AS_A, "Research")
    resp = spaces_client.get("/api/spaces", cookies=AS_A)
    assert resp.status_code == 200
    assert any(s["id"] == space_id for s in resp.json())


def test_spaces_are_tenant_isolated(spaces_client: TestClient) -> None:
    space_id = _make_space(spaces_client, AS_A, "Alice only")

    # B must not see A's space in the listing.
    resp_b = spaces_client.get("/api/spaces", cookies=AS_B)
    assert resp_b.status_code == 200
    assert all(s["id"] != space_id for s in resp_b.json())

    # B must not read A's space URLs (space ownership guard -> 403).
    resp_urls = spaces_client.get(f"/api/spaces/{space_id}/urls", cookies=AS_B)
    assert resp_urls.status_code == 403


# ---------------------------------------------------------------------------
# list_space_urls — arity-bug regression
# ---------------------------------------------------------------------------


def test_list_space_urls_roundtrip(spaces_client: TestClient) -> None:
    """Regression for the one-arg ``list_space_urls(space_id)`` 500."""
    space_id = _make_space(spaces_client, AS_A)
    job_id = _make_job(USER_A["id"], "https://example.com/own")

    add = spaces_client.post(
        f"/api/spaces/{space_id}/urls", json={"job_id": job_id}, cookies=AS_A
    )
    assert add.status_code == 201, add.text

    listed = spaces_client.get(f"/api/spaces/{space_id}/urls", cookies=AS_A)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [job_id]


# ---------------------------------------------------------------------------
# add_space_url — cross-tenant IDOR
# ---------------------------------------------------------------------------


def test_add_space_url_rejects_foreign_job(spaces_client: TestClient) -> None:
    """A owns the space but the job belongs to B -> 404 (no cross-tenant pin)."""
    space_id = _make_space(spaces_client, AS_A)
    foreign_job = _make_job(USER_B["id"], "https://example.com/foreign")

    resp = spaces_client.post(
        f"/api/spaces/{space_id}/urls", json={"job_id": foreign_job}, cookies=AS_A
    )
    assert resp.status_code == 404


def test_add_space_url_rejects_missing_job(spaces_client: TestClient) -> None:
    space_id = _make_space(spaces_client, AS_A)
    resp = spaces_client.post(
        f"/api/spaces/{space_id}/urls", json={"job_id": "no_such_job_0000"}, cookies=AS_A
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# list_space_urls — chat_id JOIN scoping (defence-in-depth)
# ---------------------------------------------------------------------------


def test_list_space_urls_filters_foreign_jobs(spaces_client: TestClient) -> None:
    """Even if a cross-tenant link exists in space_urls (inserted at the DB
    layer, bypassing the API guard), the chat_id JOIN must hide the foreign job.
    """
    from src import database

    space_id = _make_space(spaces_client, AS_A)
    own_job = _make_job(USER_A["id"], "https://example.com/own")
    foreign_job = _make_job(USER_B["id"], "https://example.com/foreign")

    # Link both directly at the DB layer (which has no ownership guard).
    asyncio.run(database.add_space_url(space_id=space_id, job_id=own_job))
    asyncio.run(database.add_space_url(space_id=space_id, job_id=foreign_job))

    resp = spaces_client.get(f"/api/spaces/{space_id}/urls", cookies=AS_A)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()]
    assert own_job in ids
    assert foreign_job not in ids

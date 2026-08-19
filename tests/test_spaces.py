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
    asyncio.run(database.set_user_status(USER_A["id"], "approved"))
    asyncio.run(database.set_user_status(USER_B["id"], "approved"))

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


# ---------------------------------------------------------------------------
# Context blobs (issue #93 / S7)
# ---------------------------------------------------------------------------


def test_context_blobs_crud(spaces_client: TestClient) -> None:
    """Create, list, update, and delete context blobs via the API."""
    space_id = _make_space(spaces_client, AS_A, "Blob Space")

    # Create
    r = spaces_client.post(
        f"/api/spaces/{space_id}/blobs",
        json={"name": "Frame", "content": "## Frame\nSome framing."},
        cookies=AS_A,
    )
    assert r.status_code == 201, r.text
    blob = r.json()
    blob_id = blob["id"]
    assert blob["name"] == "Frame"
    assert blob["space_id"] == space_id

    # List
    listed = spaces_client.get(f"/api/spaces/{space_id}/blobs", cookies=AS_A)
    assert listed.status_code == 200
    assert any(b["id"] == blob_id for b in listed.json())

    # Update
    put = spaces_client.put(
        f"/api/spaces/{space_id}/blobs/{blob_id}",
        json={"name": "Updated", "content": "New content"},
        cookies=AS_A,
    )
    assert put.status_code == 200
    assert put.json()["name"] == "Updated"

    # Delete
    del_r = spaces_client.delete(
        f"/api/spaces/{space_id}/blobs/{blob_id}", cookies=AS_A
    )
    assert del_r.status_code == 204
    listed2 = spaces_client.get(f"/api/spaces/{space_id}/blobs", cookies=AS_A)
    assert all(b["id"] != blob_id for b in listed2.json())


def test_context_blobs_tenant_isolation(spaces_client: TestClient) -> None:
    """User B must not read or modify blobs owned by user A."""
    space_id = _make_space(spaces_client, AS_A, "A Context Space")

    r = spaces_client.post(
        f"/api/spaces/{space_id}/blobs",
        json={"name": "Secret"},
        cookies=AS_A,
    )
    blob_id = r.json()["id"]

    # B cannot list blobs from A's space.
    assert spaces_client.get(
        f"/api/spaces/{space_id}/blobs", cookies=AS_B
    ).status_code == 403

    # B cannot update A's blob.
    assert spaces_client.put(
        f"/api/spaces/{space_id}/blobs/{blob_id}",
        json={"name": "Hijack", "content": ""},
        cookies=AS_B,
    ).status_code == 403


def test_delete_space_cascades_to_context_blobs(spaces_client: TestClient) -> None:
    """Deleting a space must remove its context_blobs (FK CASCADE, proves #83)."""
    from src import database

    space_id = _make_space(spaces_client, AS_A, "Cascade Space")

    blob = asyncio.run(
        database.create_context_blob(
            space_id=space_id, name="Will cascade", content="test"
        )
    )
    blob_id = blob["id"]

    assert asyncio.run(database.get_context_blob(blob_id)) is not None

    del_r = spaces_client.delete(f"/api/spaces/{space_id}", cookies=AS_A)
    assert del_r.status_code == 204

    assert asyncio.run(database.get_context_blob(blob_id)) is None


def test_space_and_blob_inputs_reject_blank_names_and_large_values() -> None:
    from pydantic import ValidationError
    from src.api.spaces import BlobIn, ReorderIn, SpaceIn

    with pytest.raises(ValidationError):
        SpaceIn(name="   ")
    with pytest.raises(ValidationError):
        BlobIn(name="\t", content="ok")
    with pytest.raises(ValidationError):
        BlobIn(name="Context", content="x" * 20_001)
    with pytest.raises(ValidationError):
        ReorderIn(sort_order=-1)
    with pytest.raises(ValidationError):
        ReorderIn(sort_order=10_001)
    assert ReorderIn(sort_order=10_000).sort_order == 10_000


def test_list_spaces_includes_first_ordered_note(spaces_client: TestClient) -> None:
    space_id = _make_space(spaces_client, AS_A, "Preview")
    for name in ("Later", "First"):
        response = spaces_client.post(
            f"/api/spaces/{space_id}/blobs",
            json={"name": name, "content": name * 100}, cookies=AS_A,
        )
        assert response.status_code == 201
    blobs = spaces_client.get(f"/api/spaces/{space_id}/blobs", cookies=AS_A).json()
    from src.database import reorder_context_blob

    asyncio.run(reorder_context_blob(blob_id=blobs[1]['id'], new_sort_order=0))
    listed = spaces_client.get('/api/spaces', cookies=AS_A).json()[0]
    assert listed['first_note']['name'] == 'First'
    assert len(listed['first_note']['snippet']) == 140
    assert listed['first_note']['truncated'] is True


def test_list_spaces_omits_first_note_without_blobs(spaces_client: TestClient) -> None:
    _make_space(spaces_client, AS_A, "Empty")
    listed = spaces_client.get('/api/spaces', cookies=AS_A).json()[0]
    assert 'first_note' not in listed

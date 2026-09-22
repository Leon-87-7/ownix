"""Route-level two-tenant isolation tests for /api/brain/* (ADR-0043, per-tenant
Brain isolation handoff §1).

Exercises the real `SessionMiddleware` + `brain_router` against a temp SQLite
DB end to end (not mocked scoping helpers), so a regression in the actual
owner-scope SQL predicate shows up here rather than only in `test_brain.py`'s
unit-level coverage.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_A = 1001
CHAT_B = 1002
OPERATOR_CHAT_ID = 9999
EMBEDDING_DIM = 768


def _vec() -> np.ndarray:
    v = np.ones(EMBEDDING_DIM, dtype=np.float32)
    return v / np.linalg.norm(v)


def _blob(vec: np.ndarray) -> bytes:
    return vec.astype(np.float32).tobytes()


@pytest.fixture
def iso_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "brain_tenant_isolation.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR_CHAT_ID)

    from src import database
    from src.api.brain import brain_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import rate_limit

    rate_limit.reset()

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_A, "approved"))
    asyncio.run(database.set_user_status(CHAT_B, "approved"))

    vec = _vec()

    async def _seed() -> None:
        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status) "
                "VALUES ('job-a', ?, 'https://a.example.com', 'link', 'done')",
                (CHAT_A,),
            )
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status) "
                "VALUES ('job-b', ?, 'https://b.example.com', 'link', 'done')",
                (CHAT_B,),
            )
            await conn.execute(
                """INSERT INTO links
                   (id, url, title, topic, chat_id, source_job, embedding,
                    seen_count, last_seen_at, created_at, updated_at)
                   VALUES ('link-a', 'https://a.example.com/x', 'A Link', 'topic', ?, 'job-a', ?,
                           1, 't1', 't1', 't1')""",
                (CHAT_A, _blob(vec)),
            )
            await conn.execute(
                """INSERT INTO links
                   (id, url, title, topic, chat_id, source_job, embedding,
                    seen_count, last_seen_at, created_at, updated_at)
                   VALUES ('link-b', 'https://b.example.com/y', 'B Link', 'topic', ?, 'job-b', ?,
                           1, 't2', 't2', 't2')""",
                (CHAT_B, _blob(vec)),
            )
            await conn.commit()

    asyncio.run(_seed())

    monkeypatch.setattr("src.brain._embed", AsyncMock(return_value=vec))
    monkeypatch.setattr("src.config.settings.BRAIN_MIN_SCORE", 0.5)

    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(brain_router)
    return TestClient(app, raise_server_exceptions=True)


def _login(client: TestClient, chat_id: int) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": chat_id, "first_name": "Test"}))
    client.cookies.clear()
    client.cookies.set("vig_session", session_id)


class TestLinksListIsolation:
    def test_a_sees_only_own_link(self, iso_client: TestClient) -> None:
        _login(iso_client, CHAT_A)
        resp = iso_client.get("/api/brain/links")
        assert resp.status_code == 200
        assert {i["url"] for i in resp.json()["items"]} == {"https://a.example.com/x"}

    def test_b_sees_only_own_link(self, iso_client: TestClient) -> None:
        _login(iso_client, CHAT_B)
        resp = iso_client.get("/api/brain/links")
        assert resp.status_code == 200
        assert {i["url"] for i in resp.json()["items"]} == {"https://b.example.com/y"}


class TestSearchIsolation:
    def test_search_is_scoped_to_the_caller(self, iso_client: TestClient) -> None:
        _login(iso_client, CHAT_A)
        resp = iso_client.get("/api/brain/search", params={"q": "anything"})
        assert resp.status_code == 200
        assert {r["url"] for r in resp.json()} == {"https://a.example.com/x"}


class TestGraphIsolation:
    def test_graph_is_scoped_to_the_caller(self, iso_client: TestClient) -> None:
        _login(iso_client, CHAT_B)
        resp = iso_client.get("/api/brain/graph")
        assert resp.status_code == 200
        assert {n["url"] for n in resp.json()["nodes"]} == {"https://b.example.com/y"}


class TestPreviewIsolation:
    def test_b_cannot_preview_as_link(self, iso_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.utils.public_html.fetch_public_html", AsyncMock(return_value=None))
        _login(iso_client, CHAT_B)
        resp = iso_client.get("/api/brain/links/link-a/preview")
        assert resp.status_code == 404

    def test_a_can_preview_own_link(self, iso_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.utils.public_html.fetch_public_html", AsyncMock(return_value=None))
        _login(iso_client, CHAT_A)
        resp = iso_client.get("/api/brain/links/link-a/preview")
        assert resp.status_code == 200

    def test_b_cannot_proxy_as_preview_image(
        self, iso_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The image proxy must not fetch the remote OG image before ownership
        is proven — otherwise it's an IDOR *and* a server-paid fetch oracle."""
        fetch_image = AsyncMock()
        monkeypatch.setattr("src.utils.public_html.fetch_public_image", fetch_image)
        _login(iso_client, CHAT_B)
        resp = iso_client.get("/api/brain/links/link-a/preview/image")
        assert resp.status_code == 404
        fetch_image.assert_not_awaited()


class TestTagMutationIsolation:
    """ADR-0043: tag mutations must prove ownership of both the tag *and* the
    link — the pre-fix code only checked the tag."""

    def test_b_cannot_attach_own_tag_to_as_link(self, iso_client: TestClient) -> None:
        from src import database

        _login(iso_client, CHAT_B)
        tag = asyncio.run(
            database.create_tag(chat_id=CHAT_B, name="mine", meaning="", color="#111111")
        )
        resp = iso_client.post(f"/api/brain/links/link-a/tags/{tag['id']}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Link not found"

    def test_a_can_attach_own_tag_to_own_link(self, iso_client: TestClient) -> None:
        from src import database

        _login(iso_client, CHAT_A)
        tag = asyncio.run(
            database.create_tag(chat_id=CHAT_A, name="mine", meaning="", color="#111111")
        )
        resp = iso_client.post(f"/api/brain/links/link-a/tags/{tag['id']}")
        assert resp.status_code == 201

    def test_b_cannot_detach_own_tag_from_as_link(self, iso_client: TestClient) -> None:
        from src import database

        _login(iso_client, CHAT_B)
        tag = asyncio.run(
            database.create_tag(chat_id=CHAT_B, name="mine2", meaning="", color="#111111")
        )
        resp = iso_client.delete(f"/api/brain/links/link-a/tags/{tag['id']}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Link not found"


class TestRebuildIsolation:
    def test_rebuild_only_touches_the_callers_own_links(
        self, iso_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.brain.upload_file", AsyncMock(return_value=("file-id", "https://drive.example/x")))
        monkeypatch.setattr("src.brain.update_file", AsyncMock())
        _login(iso_client, CHAT_A)
        resp = iso_client.post("/api/brain/rebuild")
        assert resp.status_code == 200
        assert resp.json()["nodes"] == 1  # only A's own link, never B's


class TestLegacyNullFallsBackToOperatorOnly:
    def test_orphan_link_is_visible_only_to_the_operator(
        self, iso_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src import database

        async def _insert_orphan() -> None:
            async with database.connection() as conn:
                await conn.execute(
                    """INSERT INTO links
                       (id, url, title, topic, source_job, embedding,
                        seen_count, last_seen_at, created_at, updated_at)
                       VALUES ('link-orphan', 'https://orphan.example.com', 'Orphan', 'topic',
                               'gone-job', ?, 1, 't3', 't3', 't3')""",
                    (_blob(_vec()),),
                )
                await conn.commit()

        asyncio.run(_insert_orphan())
        asyncio.run(database.set_user_status(OPERATOR_CHAT_ID, "approved"))

        _login(iso_client, CHAT_A)
        resp = iso_client.get("/api/brain/links")
        assert "https://orphan.example.com" not in {i["url"] for i in resp.json()["items"]}

        _login(iso_client, OPERATOR_CHAT_ID)
        resp = iso_client.get("/api/brain/links")
        assert "https://orphan.example.com" in {i["url"] for i in resp.json()["items"]}

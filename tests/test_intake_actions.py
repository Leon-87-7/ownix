"""Tests for POST /api/intake/action (issue #475): generic dashboard actions,
idempotent per (actor, action_id) so a double-fired action never double-applies."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 888
OTHER_CHAT_ID = 999


@pytest.fixture
def action_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "intake_action_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database
    from src.api.intake import intake_router
    from src.auth.middleware import SessionMiddleware
    from src.intake import idempotency, rate_limit

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    rate_limit.reset()
    idempotency._memory.clear()

    async def _fake_enqueue(_payload: dict) -> None:
        return None

    monkeypatch.setattr("src.services.jobs.queue.enqueue", _fake_enqueue)

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(intake_router)
    return TestClient(test_app, raise_server_exceptions=True)


def _login(client: TestClient) -> None:
    from src.auth import session as session_store

    session_id = asyncio.run(session_store.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", session_id)


async def _insert_error_job(job_id: str, chat_id: int = CHAT_ID) -> None:
    from src import database

    async with database.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status) VALUES (?, ?, ?, 'short', 'error')",
            (job_id, chat_id, "https://youtube.com/shorts/abc123"),
        )
        await conn.commit()


async def _count_jobs_for_url(url: str) -> int:
    from src import database

    async with database.connection() as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM jobs WHERE url = ?", (url,))
        row = await cur.fetchone()
        return row[0]


class TestActionIdempotency:
    def test_double_fired_retry_job_does_not_double_apply(self, action_client: TestClient) -> None:
        asyncio.run(_insert_error_job("job_retry_1"))
        _login(action_client)

        body = {"action_id": "retry-job_retry_1", "kind": "retry_job", "job_id": "job_retry_1"}
        first = action_client.post("/api/intake/action", json=body)
        second = action_client.post("/api/intake/action", json=body)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["job_id"] == second.json()["job_id"]
        # Original error job + exactly one retry replacement — never two.
        assert asyncio.run(_count_jobs_for_url("https://youtube.com/shorts/abc123")) == 2

    def test_retry_job_rejects_foreign_job(self, action_client: TestClient) -> None:
        asyncio.run(_insert_error_job("job_foreign", chat_id=OTHER_CHAT_ID))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a1", "kind": "retry_job", "job_id": "job_foreign"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "error"

    def test_cancel_pending_action(self, action_client: TestClient) -> None:
        from src.intake import state

        asyncio.run(state.set_state(CHAT_ID, "awaiting_intent", "job_x"))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "cancel-1", "kind": "cancel_pending"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "command_result"
        assert asyncio.run(state.get_state(CHAT_ID)) is None

    def test_unknown_action_kind_is_unsupported(self, action_client: TestClient) -> None:
        _login(action_client)
        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a2", "kind": "not_a_real_action"},
        )
        assert resp.status_code == 200
        assert resp.json()["kind"] == "unsupported"

    def test_auth_required(self, action_client: TestClient) -> None:
        resp = action_client.post(
            "/api/intake/action",
            json={"action_id": "a3", "kind": "cancel_pending"},
        )
        assert resp.status_code == 401


async def _insert_job(job_id: str, status: str = "pending", chat_id: int = CHAT_ID) -> None:
    from src import database

    async with database.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status) VALUES (?, ?, ?, 'short', ?)",
            (job_id, chat_id, f"https://youtube.com/shorts/{job_id}", status),
        )
        await conn.commit()


class TestCreateTagAction:
    """Inline tag creation from an unknown `#tag` token (issue #489, ADR-0047)."""

    @staticmethod
    def _tags():
        from src import database

        return asyncio.run(database.list_tags(CHAT_ID))

    def test_creates_the_tag_and_attaches_it(self, action_client: TestClient) -> None:
        from src import database

        asyncio.run(_insert_job("job_tag_1"))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={
                "action_id": "create-tag-1",
                "kind": "create_tag",
                "job_id": "job_tag_1",
                "payload": {"tag_name": "GoTo", "meaning": "read soon", "color": "#4ade80"},
            },
        )

        assert resp.status_code == 200
        assert resp.json()["kind"] == "action_ack"
        created = [t for t in self._tags() if t["name"] == "GoTo"]
        assert len(created) == 1
        assert created[0]["meaning"] == "read soon"
        assert created[0]["color"] == "#4ade80"
        attached = asyncio.run(database.list_job_tags("job_tag_1"))
        assert [t["name"] for t in attached] == ["GoTo"]

    def test_double_fire_does_not_create_two_tags(self, action_client: TestClient) -> None:
        asyncio.run(_insert_job("job_tag_2"))
        _login(action_client)

        body = {
            "action_id": "create-tag-2",
            "kind": "create_tag",
            "job_id": "job_tag_2",
            "payload": {"tag_name": "Later"},
        }
        first = action_client.post("/api/intake/action", json=body)
        second = action_client.post("/api/intake/action", json=body)

        assert first.status_code == 200 and second.status_code == 200
        assert len([t for t in self._tags() if t["name"] == "Later"]) == 1

    def test_existing_tag_is_reused_not_duplicated(self, action_client: TestClient) -> None:
        from src import database

        asyncio.run(
            database.create_tag(chat_id=CHAT_ID, name="Read Later", meaning="", color="#60a5fa")
        )
        asyncio.run(_insert_job("job_tag_3"))
        _login(action_client)

        # Normalized match: `#readlater` must find the existing "Read Later".
        resp = action_client.post(
            "/api/intake/action",
            json={
                "action_id": "create-tag-3",
                "kind": "create_tag",
                "job_id": "job_tag_3",
                "payload": {"tag_name": "readlater"},
            },
        )

        assert resp.status_code == 200
        names = [t["name"] for t in self._tags()]
        assert names.count("Read Later") == 1
        assert "readlater" not in names
        attached = asyncio.run(database.list_job_tags("job_tag_3"))
        assert [t["name"] for t in attached] == ["Read Later"]

    def test_concurrent_create_same_name_does_not_raise_or_duplicate(
        self, action_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two requests racing on the same exact name both miss the pre-insert
        lookup; the DB's UNIQUE(chat_id, name) constraint must not surface as
        an unhandled exception, and only one tag must land."""
        from src import database
        from src.intake.actions import _create_tag
        from src.intake.models import IntakeAction

        asyncio.run(_insert_job("job_tag_race"))

        # Synchronization barrier: ensures both tasks signal entry before either
        # proceeds to the real insert, making the race deterministic.
        entered = asyncio.Event()
        call_count = 0
        original_create_tag = database.create_tag

        async def _barrier_create_tag(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First caller: wait for the second to also enter.
                entered.set()
                await asyncio.sleep(0.05)  # Give second task time to reach this point.
            else:
                # Second caller: signal that we're both here, then proceed.
                await entered.wait()
            # Both tasks now proceed to the real insert in parallel.
            return await original_create_tag(**kwargs)

        monkeypatch.setattr("src.database.create_tag", _barrier_create_tag)
        monkeypatch.setattr("src.intake.actions.database.create_tag", _barrier_create_tag)

        async def _run() -> None:
            action = IntakeAction(
                action_id="create-tag-race",
                kind="create_tag",
                job_id="job_tag_race",
                payload={"tag_name": "Racey"},
            )
            results = await asyncio.gather(
                _create_tag(CHAT_ID, action), _create_tag(CHAT_ID, action)
            )
            assert all(r.kind == "action_ack" for r in results)

        asyncio.run(_run())
        assert len([t for t in self._tags() if t["name"] == "Racey"]) == 1

    def test_rejects_a_foreign_job(self, action_client: TestClient) -> None:
        asyncio.run(_insert_job("job_tag_foreign", chat_id=OTHER_CHAT_ID))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={
                "action_id": "create-tag-4",
                "kind": "create_tag",
                "job_id": "job_tag_foreign",
                "payload": {"tag_name": "Sneaky"},
            },
        )

        assert resp.json()["kind"] == "error"
        assert [t for t in self._tags() if t["name"] == "Sneaky"] == []

    def test_blank_name_is_rejected(self, action_client: TestClient) -> None:
        asyncio.run(_insert_job("job_tag_5"))
        _login(action_client)

        resp = action_client.post(
            "/api/intake/action",
            json={
                "action_id": "create-tag-5",
                "kind": "create_tag",
                "job_id": "job_tag_5",
                "payload": {"tag_name": "   "},
            },
        )

        assert resp.json()["kind"] == "error"

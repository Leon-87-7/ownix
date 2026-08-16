"""Tests for GET/POST /api/jobs/{id}/repo-followups — the dashboard-facing
surface for src/services/repo_followup.py, which until now only reached
Telegram (an inline keyboard sent directly to the chat, with no API or UI
equivalent on the intake page or job detail pages)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 6001


class FakeRedis:
    def __init__(self) -> None:
        self._strings: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._strings[key] = value

    async def get(self, key: str) -> str | None:
        return self._strings.get(key)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "repo_followups.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    from src import database
    from src.api.jobs import jobs_router
    from src.auth.middleware import SessionMiddleware

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(jobs_router)
    return TestClient(app)


def login(client: TestClient, chat_id: int = CHAT_ID) -> None:
    from src.auth import session
    token = asyncio.run(session.mint({"id": chat_id, "first_name": "Test"}))
    client.cookies.set("vig_session", token)


def seed_job(*, content_type: str = "short", chat_id: int = CHAT_ID) -> None:
    from src.config import settings

    async def insert() -> None:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status) VALUES (?, ?, ?, ?, ?)",
                ("job_repo1", chat_id, "https://instagram.com/reel/abc", content_type, "done"),
            )
            await conn.commit()
    asyncio.run(insert())


def test_no_cached_candidates_returns_empty_list(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    fake = FakeRedis()
    monkeypatch.setattr("src.queue._client", lambda: fake)

    response = client.get("/api/jobs/job_repo1/repo-followups")
    assert response.status_code == 200
    assert response.json() == []


def test_returns_cached_candidates(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    fake = FakeRedis()
    candidates = [{"url": "https://github.com/octocat/hello-world", "name": "octocat/hello-world"}]
    asyncio.run(fake.set("repo_pick:job_repo1", json.dumps(candidates)))
    monkeypatch.setattr("src.queue._client", lambda: fake)

    response = client.get("/api/jobs/job_repo1/repo-followups")
    assert response.status_code == 200
    assert response.json() == candidates


def test_other_users_job_is_forbidden(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job(chat_id=CHAT_ID + 1)
    login(client)
    fake = FakeRedis()
    monkeypatch.setattr("src.queue._client", lambda: fake)

    response = client.get("/api/jobs/job_repo1/repo-followups")
    assert response.status_code == 403


def test_pick_enqueues_a_new_repo_job(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    fake = FakeRedis()
    candidates = [{"url": "https://github.com/octocat/hello-world", "name": "octocat/hello-world"}]
    asyncio.run(fake.set("repo_pick:job_repo1", json.dumps(candidates)))
    monkeypatch.setattr("src.queue._client", lambda: fake)
    monkeypatch.setattr("src.services.repo_followup.queue._client", lambda: fake)

    queued: list[dict] = []

    async def enqueue(payload: dict) -> None:
        queued.append(payload)

    monkeypatch.setattr("src.services.jobs.queue.enqueue", enqueue)

    response = client.post("/api/jobs/job_repo1/repo-followups/0")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] in ("pending", "queued")
    assert queued and queued[0]["task"] == "repo"


def test_pick_missing_candidate_is_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    fake = FakeRedis()
    monkeypatch.setattr("src.queue._client", lambda: fake)

    response = client.post("/api/jobs/job_repo1/repo-followups/0")
    assert response.status_code == 404

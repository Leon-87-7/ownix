"""Tests for POST /api/jobs/{id}/screenshots. Mirrors test_jobs_api_checklists.py.

The capture run itself is covered by tests/test_screenshots.py — here we only
need `trigger()`'s outcome mapped onto the right HTTP status.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 4242


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "screenshots.db"
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


def login(client: TestClient) -> None:
    from src.auth import session
    token = asyncio.run(session.mint({"id": CHAT_ID, "first_name": "Test"}))
    client.cookies.set("vig_session", token)


def seed_job(
    *,
    content_type: str = "long",
    status: str = "done",
    video_duration_seconds: float | None = None,
    screenshots_status: str | None = None,
) -> None:
    from src.config import settings

    async def insert() -> None:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, "
                "video_duration_seconds, screenshots_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "job_abcd", CHAT_ID, "https://example.com/video", content_type, status,
                    video_duration_seconds, screenshots_status,
                ),
            )
            await conn.commit()

    asyncio.run(insert())


def _no_op_background(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.processors.screenshots.spawn_background", lambda coro: coro.close())


def test_starts_capture(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    _no_op_background(monkeypatch)

    response = client.post("/api/jobs/job_abcd/screenshots")
    assert response.status_code == 202
    assert response.json()["screenshots_status"] == "generating"

    detail = client.get("/api/jobs/job_abcd").json()
    assert detail["screenshots_status"] == "generating"


def test_short_job_returns_422(client: TestClient) -> None:
    seed_job(content_type="short")
    login(client)
    assert client.post("/api/jobs/job_abcd/screenshots").status_code == 422


def test_over_duration_cap_returns_422(client: TestClient) -> None:
    seed_job(video_duration_seconds=5_401)
    login(client)
    assert client.post("/api/jobs/job_abcd/screenshots").status_code == 422


def test_already_generating_returns_409(client: TestClient) -> None:
    seed_job(screenshots_status="generating")
    login(client)
    assert client.post("/api/jobs/job_abcd/screenshots").status_code == 409

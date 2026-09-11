from __future__ import annotations

import asyncio
from pathlib import Path

from urllib.parse import quote

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 4242


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "checklists.db"
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


def seed_job(*, content_type: str = "long", status: str = "done", transcript: str | None = "text") -> None:
    from src.config import settings
    async def insert() -> None:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, transcript) VALUES (?, ?, ?, ?, ?, ?)",
                ("job_abcd", CHAT_ID, "https://example.com/video", content_type, status, transcript),
            )
            await conn.commit()
    asyncio.run(insert())


def test_generates_and_returns_checklist(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    async def generate(_job: dict) -> tuple[dict, str]:
        return {"topics": []}, "# Checklist\n"
    monkeypatch.setattr("src.processors.checklists.run_checklists", generate)
    response = client.post("/api/jobs/job_abcd/checklists")
    assert response.status_code == 200
    assert response.json()["checklists_md"] == "# Checklist\n"
    detail = client.get("/api/jobs/job_abcd").json()
    assert detail["checklists_md"] == "# Checklist\n"
    assert detail["checklists_generated_at"]


@pytest.mark.parametrize(
    ("content_type", "status", "transcript"),
    [
        ("article", "done", "text"),
        ("long", "processing", "text"),
        ("short", "done", None),
        ("short", "done", "   "),
    ],
)
def test_rejects_ineligible_jobs(client: TestClient, content_type: str, status: str, transcript: str | None) -> None:
    seed_job(content_type=content_type, status=status, transcript=transcript)
    login(client)
    assert client.post("/api/jobs/job_abcd/checklists").status_code == 422


def test_gemini_unavailable_returns_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services.gemini import GeminiUnavailableError

    seed_job()
    login(client)

    async def fail(_job: dict) -> tuple[dict, str]:
        raise GeminiUnavailableError("both keys failed")

    monkeypatch.setattr("src.processors.checklists.run_checklists", fail)
    response = client.post("/api/jobs/job_abcd/checklists")
    assert response.status_code == 502


def test_generation_failure_returns_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)

    async def fail(_job: dict) -> tuple[dict, str]:
        raise ValueError("malformed model output")

    monkeypatch.setattr("src.processors.checklists.run_checklists", fail)
    response = client.post("/api/jobs/job_abcd/checklists")
    assert response.status_code == 502


def test_delete_clears_checklist(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)

    async def generate(_job: dict) -> tuple[dict, str]:
        return {"topics": []}, "# Checklist\n"

    monkeypatch.setattr("src.processors.checklists.run_checklists", generate)
    client.post("/api/jobs/job_abcd/checklists")

    assert client.delete("/api/jobs/job_abcd/checklists").status_code == 204
    detail = client.get("/api/jobs/job_abcd").json()
    assert detail["checklists_md"] is None
    assert detail["checklists_generated_at"] is None


def test_delete_is_idempotent(client: TestClient) -> None:
    """A job that never had a checklist - or a stale tab deleting twice - gets
    the same 204; the caller's intent is already satisfied."""
    seed_job()
    login(client)
    assert client.delete("/api/jobs/job_abcd/checklists").status_code == 204
    assert client.delete("/api/jobs/job_abcd/checklists").status_code == 204


def test_delete_requires_ownership(client: TestClient) -> None:
    seed_job()
    assert client.delete("/api/jobs/job_abcd/checklists").status_code == 401


def test_delete_rejects_a_stale_version(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tab holding checklist A must not erase checklist B generated since."""
    seed_job()
    login(client)

    async def generate(_job: dict) -> tuple[dict, str]:
        return {"topics": []}, "# Checklist\n"

    monkeypatch.setattr("src.processors.checklists.run_checklists", generate)
    stale = client.post("/api/jobs/job_abcd/checklists").json()["checklists_generated_at"]
    # A second generation lands while the first tab still shows the old one.
    client.post("/api/jobs/job_abcd/checklists")

    response = client.delete(f"/api/jobs/job_abcd/checklists?generated_at={quote(stale, safe='')}")
    assert response.status_code == 409
    assert client.get("/api/jobs/job_abcd").json()["checklists_md"] == "# Checklist\n"


def test_delete_with_matching_version_clears(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)

    async def generate(_job: dict) -> tuple[dict, str]:
        return {"topics": []}, "# Checklist\n"

    monkeypatch.setattr("src.processors.checklists.run_checklists", generate)
    current = client.post("/api/jobs/job_abcd/checklists").json()["checklists_generated_at"]

    assert (
        client.delete(
            f"/api/jobs/job_abcd/checklists?generated_at={quote(current, safe='')}"
        ).status_code
        == 204
    )
    assert client.get("/api/jobs/job_abcd").json()["checklists_md"] is None


def test_delete_with_version_on_empty_job_is_idempotent(client: TestClient) -> None:
    """Already cleared: the caller's intent holds, so no 409."""
    seed_job()
    login(client)
    assert client.delete("/api/jobs/job_abcd/checklists?generated_at=2026-01-01T00:00:00").status_code == 204

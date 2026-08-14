from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

CHAT_ID = 5280


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "enrich.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")
    from src import database
    from src.api.jobs import jobs_router
    from src.auth.middleware import SessionMiddleware

    asyncio.run(database.init_db())
    asyncio.run(database.set_user_status(CHAT_ID, "approved"))
    asyncio.run(database.set_user_status(CHAT_ID + 1, "approved"))
    app = FastAPI()
    app.add_middleware(SessionMiddleware)
    app.include_router(jobs_router)
    return TestClient(app)


def login(client: TestClient, chat_id: int = CHAT_ID) -> None:
    from src.auth import session
    token = asyncio.run(session.mint({"id": chat_id, "first_name": "Test"}))
    client.cookies.set("vig_session", token)


def seed_job(*, content_type: str = "long", status: str = "transcript_done", chat_id: int = CHAT_ID, freestyle_prompt: str | None = None) -> None:
    from src.config import settings

    async def insert() -> None:
        async with aiosqlite.connect(settings.DB_PATH) as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, transcript, freestyle_prompt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("job_abcd", chat_id, "https://youtube.com/watch?v=abc", content_type, status, "text", freestyle_prompt),
            )
            await conn.commit()
    asyncio.run(insert())


def read_job() -> dict:
    from src import database
    return asyncio.run(database.get_job("job_abcd"))


def test_successfully_claims_and_enqueues(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    queued: list[dict] = []

    async def enqueue(payload: dict) -> None:
        queued.append(payload)

    monkeypatch.setattr("src.queue.enqueue", enqueue)
    response = client.post("/api/jobs/job_abcd/enrich", json={"template": "summary", "freestyle_prompt": "stale"})
    assert response.status_code == 202
    assert queued == [{"task": "enrichment", "job_id": "job_abcd"}]
    assert read_job()["status"] == "enriching"
    assert read_job()["template"] == "summary"
    assert read_job()["freestyle_prompt"] is None


def test_persists_freestyle_prompt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job()
    login(client)
    async def enqueue(_payload: dict) -> None: pass
    monkeypatch.setattr("src.queue.enqueue", enqueue)
    response = client.post("/api/jobs/job_abcd/enrich", json={"template": "freestyle", "freestyle_prompt": "Compare the tradeoffs"})
    assert response.status_code == 202
    assert read_job()["freestyle_prompt"] == "Compare the tradeoffs"


@pytest.mark.parametrize("body", [{"template": "unknown"}, {"template": "freestyle"}])
def test_rejects_invalid_template(client: TestClient, body: dict) -> None:
    seed_job(); login(client)
    assert client.post("/api/jobs/job_abcd/enrich", json=body).status_code == 422


@pytest.mark.parametrize(("content_type", "status"), [("article", "transcript_done"), ("long", "done")])
def test_rejects_ineligible_job(client: TestClient, content_type: str, status: str) -> None:
    seed_job(content_type=content_type, status=status); login(client)
    assert client.post("/api/jobs/job_abcd/enrich", json={"template": "summary"}).status_code == 422


def test_rejects_job_owned_by_another_chat(client: TestClient) -> None:
    seed_job(chat_id=CHAT_ID + 1); login(client)
    assert client.post("/api/jobs/job_abcd/enrich", json={"template": "summary"}).status_code == 403


def test_second_claim_returns_conflict_without_enqueuing_again(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_job()
    login(client)
    queued: list[dict] = []

    async def enqueue(payload: dict) -> None:
        queued.append(payload)

    monkeypatch.setattr("src.queue.enqueue", enqueue)

    first = client.post("/api/jobs/job_abcd/enrich", json={"template": "summary"})
    second = client.post("/api/jobs/job_abcd/enrich", json={"template": "summary"})

    assert first.status_code == 202
    assert second.status_code == 409
    assert queued == [{"task": "enrichment", "job_id": "job_abcd"}]


def test_enqueue_failure_releases_claim(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_job(); login(client)
    async def fail(_payload: dict) -> None: raise RuntimeError("redis unavailable")
    monkeypatch.setattr("src.queue.enqueue", fail)
    response = client.post("/api/jobs/job_abcd/enrich", json={"template": "summary"})
    assert response.status_code == 503
    assert read_job()["status"] == "transcript_done"

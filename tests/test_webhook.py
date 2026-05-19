"""Webhook handler integration test — uses FastAPI's TestClient against an in-memory DB and the FakeRedis."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure required settings exist before importing src.* modules that touch settings.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import database, queue
from src.telegram import sender, webhook
import src.queue as queue_module
import src.telegram.sender as sender_module


class FakeRedis:
    def __init__(self) -> None:
        self._lists: dict[str, list[str]] = {}

    async def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    async def brpop(self, keys, timeout=0):  # noqa: ANN001
        key = keys[0] if isinstance(keys, list) else keys
        items = self._lists.get(key, [])
        if not items:
            return None
        return (key, items.pop())

    async def close(self) -> None:
        pass


class FakeHttpClient:
    """Captures every Telegram API call instead of hitting the network."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def post(self, url: str, json: dict):  # noqa: A002, ANN001
        self.calls.append({"url": url, "json": json})

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return {"ok": True, "result": {"message_id": 999}}

        return _Response()

    async def aclose(self) -> None:
        pass


@pytest.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "test_jobs.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    await database.init_db()

    fake_redis = FakeRedis()
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    fake_http = FakeHttpClient()
    monkeypatch.setattr(sender_module, "_client", fake_http)

    app = FastAPI()
    app.include_router(webhook.router)
    with TestClient(app) as c:
        yield c, fake_redis, fake_http


def _telegram_update(text: str, chat_id: int = 12345, message_id: int = 1) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": message_id,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


async def test_webhook_rejects_missing_secret(client) -> None:
    c, _, _ = client
    response = c.post("/webhook", json=_telegram_update("https://youtu.be/abc"))
    assert response.status_code == 403


async def test_webhook_rejects_wrong_secret(client) -> None:
    c, _, _ = client
    response = c.post(
        "/webhook",
        json=_telegram_update("https://youtu.be/abc"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert response.status_code == 403


async def test_webhook_accepts_long_url_and_enqueues(client) -> None:
    c, fake_redis, fake_http = client
    response = c.post(
        "/webhook",
        json=_telegram_update("https://youtu.be/qZkX_gIlwsY"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert response.status_code == 200

    # A task envelope was pushed to Redis
    queued = fake_redis._lists.get("video_jobs", [])
    assert len(queued) == 1
    import json
    env = json.loads(queued[0])
    assert env["task"] == "video"
    assert env["job_id"].startswith("20")  # YYYYMMDD prefix

    # A reply was sent to Telegram including the job_id
    assert len(fake_http.calls) == 1
    sent = fake_http.calls[0]["json"]
    assert sent["chat_id"] == 12345
    assert "Received" in sent["text"]
    assert env["job_id"][-4:] in sent["text"]


async def test_webhook_accepts_short_url(client) -> None:
    c, fake_redis, _ = client
    response = c.post(
        "/webhook",
        json=_telegram_update("https://instagram.com/reel/DVNolBNE6vV/"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert response.status_code == 200
    assert len(fake_redis._lists.get("video_jobs", [])) == 1


async def test_webhook_rejects_unsupported_url(client) -> None:
    c, fake_redis, fake_http = client
    response = c.post(
        "/webhook",
        json=_telegram_update("https://instagram.com/p/abc/"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert response.status_code == 200
    # No job enqueued
    assert fake_redis._lists.get("video_jobs", []) == []
    # User got the rejection reply
    assert len(fake_http.calls) == 1
    assert "Unsupported" in fake_http.calls[0]["json"]["text"]


async def test_webhook_ignores_non_text_messages(client) -> None:
    c, fake_redis, fake_http = client
    update = {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}}}
    response = c.post(
        "/webhook",
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
    )
    assert response.status_code == 200
    assert fake_redis._lists.get("video_jobs", []) == []
    assert fake_http.calls == []

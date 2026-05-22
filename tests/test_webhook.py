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


# ---------------------------------------------------------------------------
# Callback handler unit tests (slice #7)
# ---------------------------------------------------------------------------

import tempfile
from unittest.mock import AsyncMock, patch

import aiosqlite


@pytest.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db
        await db.init_db()
        yield path
    os.unlink(path)


async def _seed_job(path: str, job_id: str, chat_id: int = 1, **fields) -> None:
    cols = ["id", "chat_id", "url", "content_type", "status"]
    vals = [job_id, chat_id, "u", fields.get("content_type", "long"), fields.get("status", "done")]
    for k, v in fields.items():
        if k in ("content_type", "status"):
            continue
        cols.append(k)
        vals.append(v)
    placeholders = ",".join("?" * len(cols))
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            f"INSERT INTO jobs ({','.join(cols)}) VALUES ({placeholders})", vals
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_callback_prd_build_spec_sends_submenu(temp_db, monkeypatch):
    from src.telegram import webhook
    sent_kb = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_inline_keyboard", sent_kb)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    callback = {"id": "CB1", "data": "prd_build_spec:J1", "message": {"chat": {"id": 100}}}
    await webhook._handle_callback(callback)
    sent_kb.assert_awaited_once()
    args, kwargs = sent_kb.await_args
    # Should send a 2-button sub-menu
    buttons = kwargs.get("buttons") or args[2]
    btn_texts = [b["text"] for row in buttons for b in row]
    assert "🤖 Build auto Spec" in btn_texts
    assert "✍️ Text your intent" in btn_texts


@pytest.mark.asyncio
async def test_callback_prd_auto_resend_when_status_done(temp_db, monkeypatch):
    from src.telegram import webhook
    await _seed_job(temp_db, "J_DONE", chat_id=100, prd_auto_status="done", prd_auto_json='{"x":1}')
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "prd_auto:J_DONE", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_awaited_once_with({"task": "prd_auto_resend", "job_id": "J_DONE"})


@pytest.mark.asyncio
async def test_callback_prd_auto_lazy_when_status_null(temp_db, monkeypatch):
    from src.telegram import webhook
    await _seed_job(temp_db, "J_NULL", chat_id=100)
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "prd_auto:J_NULL", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_awaited_once_with({"task": "prd_auto", "job_id": "J_NULL"})
    # Webhook MUST NOT pre-acquire the lock — worker is the single source of truth.
    # Otherwise run_auto's own atomic lock fails with lock_contention and the PRD never generates.
    from src import database as db
    job = await db.get_job("J_NULL")
    assert job["prd_auto_status"] is None


@pytest.mark.asyncio
async def test_callback_prd_auto_already_generating(temp_db, monkeypatch):
    """If status='generating', reply 'already generating' and skip enqueue."""
    from src.telegram import webhook
    await _seed_job(temp_db, "J_GEN", chat_id=100, prd_auto_status="generating")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "prd_auto:J_GEN", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_not_awaited()
    assert "already generating" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_callback_prd_intent_prompt_arms_state(temp_db, monkeypatch):
    from src.telegram import webhook
    from src import database as db
    await _seed_job(temp_db, "J_ARM", chat_id=100)
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "prd_intent_prompt:J_ARM", "message": {"chat": {"id": 100}}}
    )
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["job_id"] == "J_ARM"
    fr.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_prd_intent_prompt_debounces_same_job(temp_db, monkeypatch):
    from src.telegram import webhook
    from src import database as db
    await _seed_job(temp_db, "J_DBN", chat_id=100)
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_DBN")
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "prd_intent_prompt:J_DBN", "message": {"chat": {"id": 100}}}
    )
    fr.assert_not_awaited()


# ---------------------------------------------------------------------------
# Routing + /spec + /cancel tests (Task 13)
# ---------------------------------------------------------------------------

async def _post_webhook(text: str, chat_id: int = 100, secret: str = "S"):
    """Helper that invokes the webhook handler with a text message."""
    class _Req:
        def __init__(self, body): self._body = body
        async def json(self): return self._body
    from src.telegram.webhook import webhook
    body = {"message": {"chat": {"id": chat_id}, "text": text, "message_id": 1}}
    return await webhook(_Req(body), x_telegram_bot_api_secret_token=secret)


@pytest.fixture
def _patch_webhook_secret(monkeypatch):
    monkeypatch.setattr("src.config.settings.TELEGRAM_WEBHOOK_SECRET", "S")


@pytest.mark.asyncio
async def test_routing_awaiting_intent_plain_text_enqueues(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await _seed_job(temp_db, "J_TXT", chat_id=100, transcript="t")
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_TXT")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("a smart desktop tool for managing my photos")
    enq.assert_awaited_once_with({"task": "prd_intent", "job_id": "J_TXT"})
    job = await db.get_job("J_TXT")
    assert job["prd_intent_text"] == "a smart desktop tool for managing my photos"
    assert await db.get_chat_state(100) is None


@pytest.mark.asyncio
async def test_routing_awaiting_intent_too_short(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await _seed_job(temp_db, "J_S", chat_id=100)
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_S")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("hi")
    enq.assert_not_awaited()
    assert await db.get_chat_state(100) is not None
    args, _ = sent.await_args
    assert "too short" in args[1].lower() or "5" in args[1]


@pytest.mark.asyncio
async def test_routing_awaiting_intent_too_long(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await _seed_job(temp_db, "J_L", chat_id=100)
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_L")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("x" * 1001)
    enq.assert_not_awaited()
    assert await db.get_chat_state(100) is not None
    args, _ = sent.await_args
    assert "too long" in args[1].lower() or "1000" in args[1]


@pytest.mark.asyncio
async def test_routing_awaiting_intent_url_starts_new_job(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await _seed_job(temp_db, "J_U", chat_id=100)
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_U")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("https://youtu.be/dQw4w9WgXcQ")
    assert enq.await_args.args[0]["task"] == "video"
    assert await db.get_chat_state(100) is None


@pytest.mark.asyncio
async def test_cancel_with_armed_state(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/cancel")
    assert "Intent canceled" in sent.await_args.args[1]
    assert await db.get_chat_state(100) is None


@pytest.mark.asyncio
async def test_cancel_with_no_state(temp_db, _patch_webhook_secret, monkeypatch):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/cancel")
    assert "Nothing to cancel" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_no_args_usage(temp_db, _patch_webhook_secret, monkeypatch):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec")
    assert "Usage" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_no_match_shows_recent(temp_db, _patch_webhook_secret, monkeypatch):
    await _seed_job(temp_db, "20260101_120000_AAAA", chat_id=100, title="A")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec XXXX")
    msg = sent.await_args.args[1]
    assert "No job ending in XXXX" in msg
    assert "AAAA" in msg


@pytest.mark.asyncio
async def test_spec_short_only_rejection(temp_db, _patch_webhook_secret, monkeypatch):
    await _seed_job(temp_db, "20260101_120000_AAAA", chat_id=100, content_type="short", title="S")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec AAAA")
    assert "only available for long videos" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_single_long_match_enqueues_auto(temp_db, _patch_webhook_secret, monkeypatch):
    await _seed_job(
        temp_db, "20260101_120000_AAAA", chat_id=100, content_type="long",
        status="done", title="Tutorial"
    )
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/spec AAAA")
    assert enq.await_args.args[0]["task"] in ("prd_auto", "prd_auto_resend")


@pytest.mark.asyncio
async def test_spec_with_intent_enqueues_intent(temp_db, _patch_webhook_secret, monkeypatch):
    from src import database as db
    await _seed_job(
        temp_db, "20260101_120000_AAAA", chat_id=100, content_type="long",
        status="done", title="Tutorial", transcript="t"
    )
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/spec AAAA desktop app for image processing")
    assert enq.await_args.args[0] == {"task": "prd_intent", "job_id": "20260101_120000_AAAA"}
    job = await db.get_job("20260101_120000_AAAA")
    assert job["prd_intent_text"] == "desktop app for image processing"


# ---------------------------------------------------------------------------
# enrichment_retry callback tests (issue #13)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_callback_enrichment_retry_enqueues_on_error_status(temp_db, monkeypatch):
    from src.telegram import webhook
    await _seed_job(temp_db, "J_ERR", chat_id=100, status="error")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "enrichment_retry:J_ERR", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_awaited_once_with({"task": "enrichment", "job_id": "J_ERR"})
    from src import database as db
    job = await db.get_job("J_ERR")
    assert job["status"] == "enriching"


@pytest.mark.asyncio
async def test_callback_enrichment_retry_rejects_on_done_status(temp_db, monkeypatch):
    from src.telegram import webhook
    await _seed_job(temp_db, "J_DONE2", chat_id=100, status="done")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    await webhook._handle_callback(
        {"id": "CB", "data": "enrichment_retry:J_DONE2", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_not_awaited()
    _, kwargs = ack.await_args
    assert "done" in kwargs.get("text", "")


@pytest.mark.asyncio
async def test_intent_text_never_appears_in_log_records(temp_db, _patch_webhook_secret, monkeypatch, caplog):
    """intent_text must never appear in any log record — only intent_text_len."""
    import logging
    from src import database as db
    await _seed_job(temp_db, "J_PRIV", chat_id=100, transcript="t")
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_PRIV")
    monkeypatch.setattr("src.queue.enqueue", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    # Suppress aiosqlite DEBUG logs which expose SQL parameters containing intent_text
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    secret_intent = "Sphinx of black quartz judge my vow — please log only the length"
    with caplog.at_level(logging.DEBUG):
        await _post_webhook(secret_intent, chat_id=100)

    for record in caplog.records:
        assert secret_intent not in record.getMessage(), (
            f"intent_text leaked in log record: {record.getMessage()!r}"
        )
        for key, value in record.__dict__.items():
            if isinstance(value, str) and secret_intent in value:
                raise AssertionError(
                    f"intent_text leaked in record attribute {key!r}: {value!r}"
                )

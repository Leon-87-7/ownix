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
        self._strings: dict[str, str] = {}

    async def lpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).insert(0, value)
        return len(self._lists[key])

    async def rpush(self, key: str, value: str) -> int:
        self._lists.setdefault(key, []).append(value)
        return len(self._lists[key])

    async def brpop(self, keys, timeout=0):  # noqa: ANN001
        key = keys[0] if isinstance(keys, list) else keys
        items = self._lists.get(key, [])
        if not items:
            return None
        return (key, items.pop())

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        return items[start:] if end == -1 else items[start : end + 1]

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._strings[key] = value

    async def get(self, key: str) -> str | None:
        return self._strings.get(key)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for k in keys:
            removed += self._strings.pop(k, None) is not None
            removed += self._lists.pop(k, None) is not None
        return removed

    async def expire(self, key: str, seconds: int) -> None:
        pass

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
    await database.set_user_status(12345, "approved")

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
    update = {
        "update_id": 1,
        "message": {"message_id": 1, "chat": {"id": 1, "type": "private"}},
    }
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
    vals = [
        job_id,
        chat_id,
        "u",
        fields.get("content_type", "long"),
        fields.get("status", "done"),
    ]
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


async def _approve_user(chat_id: int, email: str | None = None) -> None:
    from src import database as db

    await db.set_user_email(chat_id, email or f"user{chat_id}@example.com")
    await db.set_user_status(chat_id, "approved")


@pytest.mark.asyncio
async def test_callback_prd_build_spec_sends_submenu(temp_db, monkeypatch):
    from src.telegram import webhook

    await _approve_user(100)
    sent_kb = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_inline_keyboard", sent_kb)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    callback = {
        "id": "CB1",
        "data": "prd_build_spec:J1",
        "message": {"chat": {"id": 100}},
    }
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

    await _approve_user(100)
    await _seed_job(
        temp_db, "J_DONE", chat_id=100, prd_auto_status="done", prd_auto_json='{"x":1}'
    )
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

    await _approve_user(100)
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

    await _approve_user(100)
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

    await _approve_user(100)
    await _seed_job(temp_db, "J_ARM", chat_id=100)
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "prd_intent_prompt:J_ARM",
            "message": {"chat": {"id": 100}},
        }
    )
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["job_id"] == "J_ARM"
    fr.assert_awaited_once()


@pytest.mark.asyncio
async def test_callback_prd_intent_prompt_debounces_same_job(temp_db, monkeypatch):
    from src.telegram import webhook
    from src import database as db

    await _approve_user(100)
    await _seed_job(temp_db, "J_DBN", chat_id=100)
    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J_DBN")
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "prd_intent_prompt:J_DBN",
            "message": {"chat": {"id": 100}},
        }
    )
    fr.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_document_md_rejects_foreign_chat(temp_db, monkeypatch):
    """Ownership guard: a document_md callback from a chat that doesn't own the
    job is denied before any markdown delivery (CodeRabbit, PR #200)."""
    from src.telegram import webhook

    await _approve_user(200)
    await _seed_job(temp_db, "J_DOC", chat_id=100, content_type="document")
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)
    # Button pressed from chat 200, but the job belongs to chat 100.
    await webhook._handle_callback(
        {"id": "CB", "data": "document_md:J_DOC", "message": {"chat": {"id": 200}}}
    )
    answered.assert_awaited_once_with("CB", text="Job not found.")


# ---------------------------------------------------------------------------
# Routing + /spec + /cancel tests (Task 13)
# ---------------------------------------------------------------------------


async def _post_webhook(
    text: str,
    chat_id: int = 100,
    secret: str = "S",
    *,
    approved: bool = True,
    from_user: dict | None = None,
):
    """Helper that invokes the webhook handler with a text message."""

    class _Req:
        def __init__(self, body):
            self._body = body

        async def json(self):
            return self._body

    from src.telegram.webhook import webhook

    if approved:
        await database.set_user_status(chat_id, "approved")

    body = {
        "message": {
            "chat": {"id": chat_id},
            "from": from_user
            or {"id": chat_id, "first_name": "Test", "username": "tester"},
            "text": text,
            "message_id": 1,
        }
    }
    return await webhook(_Req(body), x_telegram_bot_api_secret_token=secret)


@pytest.fixture
def _patch_webhook_secret(monkeypatch):
    monkeypatch.setattr("src.config.settings.TELEGRAM_WEBHOOK_SECRET", "S")


@pytest.fixture
def _patch_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(queue_module, "_redis", fake)
    return fake


def test_invite_prompt_uses_configured_admin_name(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "Alex")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "Alex"


def test_invite_prompt_falls_back_when_unset(monkeypatch):
    monkeypatch.setattr("src.config.settings.ADMIN_CONTACT_NAME", "")
    from src.telegram.webhook import _admin_label

    assert _admin_label() == "the operator"


@pytest.mark.asyncio
async def test_invite_gate_prompts_for_email_and_drops_first_url(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    enq = AsyncMock()
    sent = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    await _post_webhook("https://youtu.be/dQw4w9WgXcQ", approved=False)

    enq.assert_not_awaited()
    assert await db.get_recent_jobs(100, 5) == []
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["mode"] == "awaiting_email"
    assert "what's your email" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_invite_gate_captures_email_notifies_operator_and_keeps_pending(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    monkeypatch.setattr("src.database.settings.OPERATOR_CHAT_ID", 999)
    sent = AsyncMock()
    keyboard = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.services.invite_notifications.send_inline_keyboard", keyboard)

    await _post_webhook("hello", approved=False)
    await _post_webhook(
        "User@Example.COM",
        approved=False,
        from_user={
            "id": 100,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "username": "ada",
        },
    )

    user = await db.get_user(100)
    assert user is not None
    assert user["email"] == "user@example.com"
    assert user["status"] == "pending"
    keyboard.assert_awaited_once()
    args, kwargs = keyboard.await_args
    assert args[0] == 999
    assert "Ada Lovelace" in args[1]
    assert "user@example.com" in args[1]
    buttons = kwargs["buttons"]
    assert buttons[0][0]["callback_data"] == "invite_approve:100"
    assert buttons[0][1]["callback_data"] == "invite_block:100"
    assert "still waiting on the operator" in sent.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_invite_callback_approve_flips_status_and_notifies_user(
    temp_db, monkeypatch
):
    from src import database as db
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    await db.set_user_email(100, "user@example.com")
    sent = AsyncMock()
    edited_markup = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.edit_message_reply_markup", edited_markup)

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_approve:100",
            "message": {"message_id": 7, "chat": {"id": 999}},
        }
    )

    assert await db.get_user_status(100) == "approved"
    sent.assert_awaited_once_with(100, "You're in, send a link.")
    edited_markup.assert_awaited_once_with(
        999,
        7,
        [[{"text": "✅ Approved", "callback_data": "invite_status:approved:100"}]],
    )


@pytest.mark.asyncio
async def test_invite_callback_block_flips_status_and_notifies_user(
    temp_db, monkeypatch
):
    """Operator-chat block callback still works after the auth-gate change (mirrors approve test)."""
    from src import database as db
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    await db.set_user_email(100, "user@example.com")
    sent = AsyncMock()
    edited_markup = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.edit_message_reply_markup", edited_markup)

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_block:100",
            "message": {"message_id": 7, "chat": {"id": 999}},
        }
    )

    assert await db.get_user_status(100) == "blocked"
    sent.assert_awaited_once_with(100, "Access blocked.")
    edited_markup.assert_awaited_once_with(
        999,
        7,
        [[{"text": "🚫 Blocked", "callback_data": "invite_status:blocked:100"}]],
    )


@pytest.mark.asyncio
async def test_invite_status_callback_acknowledges_already_decided(
    temp_db, monkeypatch
):
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_status:approved:100",
            "message": {"message_id": 7, "chat": {"id": 999}},
        }
    )

    answered.assert_awaited_once_with("CB", text="Already approved.")


@pytest.mark.asyncio
async def test_invite_callback_approve_rejects_non_operator_chat(temp_db, monkeypatch):
    """A chat that isn't the operator must not be able to approve invites (blocker fix)."""
    from src import database as db
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    await db.set_user_email(100, "user@example.com")
    await db.set_user_status(100, "pending")
    set_status = AsyncMock(wraps=db.set_user_status)
    monkeypatch.setattr("src.telegram.webhook.database.set_user_status", set_status)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)
    monkeypatch.setattr("src.telegram.webhook.edit_message_text", AsyncMock())

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_approve:100",
            "message": {"message_id": 7, "chat": {"id": 111}},
        }
    )

    set_status.assert_not_awaited()
    sent.assert_not_awaited()
    answered.assert_awaited_once_with("CB", text="Not authorized.")
    assert await db.get_user_status(100) == "pending"


@pytest.mark.asyncio
async def test_invite_callback_approve_rejects_unset_operator_and_missing_chat(
    temp_db, monkeypatch
):
    """Unset operator config plus missing chat id must not approve invites."""
    from src import database as db
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)
    await db.set_user_email(100, "user@example.com")
    await db.set_user_status(100, "pending")
    set_status = AsyncMock(wraps=db.set_user_status)
    monkeypatch.setattr("src.telegram.webhook.database.set_user_status", set_status)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)
    monkeypatch.setattr("src.telegram.webhook.edit_message_text", AsyncMock())

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_approve:100",
            "message": {"message_id": 7},
        }
    )

    set_status.assert_not_awaited()
    sent.assert_not_awaited()
    answered.assert_awaited_once_with("CB", text="Not authorized.")
    assert await db.get_user_status(100) == "pending"


@pytest.mark.asyncio
async def test_invite_callback_block_rejects_non_operator_chat(temp_db, monkeypatch):
    """A chat that isn't the operator must not be able to block invites (blocker fix)."""
    from src import database as db
    from src.telegram import webhook

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
    await db.set_user_email(100, "user@example.com")
    await db.set_user_status(100, "pending")
    set_status = AsyncMock(wraps=db.set_user_status)
    monkeypatch.setattr("src.telegram.webhook.database.set_user_status", set_status)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)
    monkeypatch.setattr("src.telegram.webhook.edit_message_text", AsyncMock())

    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "invite_block:100",
            "message": {"message_id": 7, "chat": {"id": 111}},
        }
    )

    set_status.assert_not_awaited()
    sent.assert_not_awaited()
    answered.assert_awaited_once_with("CB", text="Not authorized.")
    assert await db.get_user_status(100) == "pending"


@pytest.mark.asyncio
async def test_invite_gate_skips_unchanged_approved_upsert_but_keeps_pending_upsert(
    temp_db, monkeypatch
):
    from src import database as db
    from src.telegram import webhook

    identity = {"first_name": "Ada", "last_name": "Lovelace", "username": "ada"}
    await db.upsert_user(
        tg_id=100, first_name="Ada", last_name="Lovelace", username="ada"
    )
    await db.set_user_status(100, "approved")
    upsert = AsyncMock(wraps=db.upsert_user)
    monkeypatch.setattr("src.telegram.webhook.database.upsert_user", upsert)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())

    assert await webhook._invite_gate_allows(100, "", identity) is True
    upsert.assert_not_awaited()

    pending_identity = {
        "first_name": "Grace",
        "last_name": "Hopper",
        "username": "grace",
    }
    assert await webhook._invite_gate_allows(101, "", pending_identity) is False
    upsert.assert_awaited_once_with(
        tg_id=101,
        first_name="Grace",
        last_name="Hopper",
        username="grace",
    )


@pytest.mark.asyncio
async def test_callback_from_pending_awaiting_email_does_not_send_email_validation_error(monkeypatch):
    """A button press from a pending, awaiting_email chat must not trigger the
    'Please send a valid email address' text-input error message."""
    from src.telegram import webhook

    sent: list[str] = []

    async def fake_send_message(chat_id, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(webhook, "send_message", fake_send_message)
    monkeypatch.setattr(webhook.database, "get_user_status", AsyncMock(return_value="pending"))
    monkeypatch.setattr(webhook.database, "get_user", AsyncMock(return_value={"email": None}))
    monkeypatch.setattr(webhook.database, "get_chat_state", AsyncMock(return_value={"mode": "awaiting_email"}))
    monkeypatch.setattr(webhook, "_resolve_chat_state", lambda state: True)
    monkeypatch.setattr(webhook.database, "upsert_user", AsyncMock())
    set_chat_state = AsyncMock()
    monkeypatch.setattr(webhook.database, "set_chat_state", set_chat_state)

    allowed = await webhook._invite_gate_allows(
        123,
        "",
        {"first_name": "X", "last_name": None, "username": None},
        via_callback=True,
    )

    assert allowed is False
    assert sent == []
    set_chat_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_reprocess_rejects_blocked_chat(temp_db, monkeypatch):
    from src import database as db
    from src.telegram import webhook

    await db.set_user_email(100, "user@example.com")
    await db.set_user_status(100, "blocked")
    await _seed_job(
        temp_db, "J_BLOCKED", chat_id=100, status="error", content_type="short"
    )
    create_job = AsyncMock(wraps=db.create_job)
    monkeypatch.setattr("src.telegram.webhook.database.create_job", create_job)
    sent = AsyncMock()
    answered = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", answered)
    monkeypatch.setattr("src.queue.enqueue", AsyncMock())

    await webhook._handle_callback(
        {"id": "CB", "data": "reprocess:J_BLOCKED", "message": {"chat": {"id": 100}}}
    )

    create_job.assert_not_awaited()
    sent.assert_awaited_once_with(100, "Access blocked.")
    answered.assert_awaited_once_with("CB", text="Access restricted.")


@pytest.mark.asyncio
async def test_invite_gate_skips_upsert_for_unchanged_approved_identity(
    temp_db, monkeypatch
):
    from src import database as db
    from src.telegram import webhook

    await db.upsert_user(
        tg_id=100, first_name="Ada", last_name="Lovelace", username="ada"
    )
    await db.set_user_status(100, "approved")
    upsert = AsyncMock(wraps=db.upsert_user)
    monkeypatch.setattr("src.telegram.webhook.database.upsert_user", upsert)

    allowed = await webhook._invite_gate_allows(
        100,
        "https://youtu.be/dQw4w9WgXcQ",
        {"first_name": "Ada", "last_name": "Lovelace", "username": "ada"},
    )

    assert allowed is True
    upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_invite_gate_still_upserts_pending_identity(temp_db, monkeypatch):
    from src import database as db
    from src.telegram import webhook

    await db.upsert_user(
        tg_id=100, first_name="Ada", last_name="Lovelace", username="ada"
    )
    await db.set_user_status(100, "pending")
    upsert = AsyncMock(wraps=db.upsert_user)
    monkeypatch.setattr("src.telegram.webhook.database.upsert_user", upsert)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())

    allowed = await webhook._invite_gate_allows(
        100,
        "",
        {"first_name": "Ada", "last_name": "Lovelace", "username": "ada"},
    )

    assert allowed is False
    upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_routing_awaiting_intent_plain_text_enqueues(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
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
async def test_routing_awaiting_intent_too_short(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
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
async def test_routing_awaiting_intent_too_long(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
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
async def test_routing_awaiting_intent_url_starts_new_job(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
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
async def test_cancel_with_armed_state(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await db.set_chat_state(chat_id=100, mode="awaiting_intent", job_id="J")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/cancel")
    assert "Intent canceled" in sent.await_args.args[1]
    assert await db.get_chat_state(100) is None


@pytest.mark.asyncio
async def test_cancel_with_no_state(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/cancel")
    assert "Nothing to cancel" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_no_args_usage(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec")
    assert "Usage" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_no_match_shows_recent(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    await _seed_job(temp_db, "20260101_120000_AAAA", chat_id=100, title="A")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec XXXX")
    msg = sent.await_args.args[1]
    assert "No job ending in XXXX" in msg
    assert "AAAA" in msg


@pytest.mark.asyncio
async def test_spec_short_only_rejection(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    await _seed_job(
        temp_db, "20260101_120000_AAAA", chat_id=100, content_type="short", title="S"
    )
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/spec AAAA")
    assert "only available for long videos" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_spec_single_long_match_enqueues_auto(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    await _seed_job(
        temp_db,
        "20260101_120000_AAAA",
        chat_id=100,
        content_type="long",
        status="done",
        title="Tutorial",
    )
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/spec AAAA")
    assert enq.await_args.args[0]["task"] in ("prd_auto", "prd_auto_resend")


@pytest.mark.asyncio
async def test_spec_with_intent_enqueues_intent(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await _seed_job(
        temp_db,
        "20260101_120000_AAAA",
        chat_id=100,
        content_type="long",
        status="done",
        title="Tutorial",
        transcript="t",
    )
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/spec AAAA desktop app for image processing")
    assert enq.await_args.args[0] == {
        "task": "prd_intent",
        "job_id": "20260101_120000_AAAA",
    }
    job = await db.get_job("20260101_120000_AAAA")
    assert job["prd_intent_text"] == "desktop app for image processing"


# ---------------------------------------------------------------------------
# enrichment_retry callback tests (issue #13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_enrichment_retry_enqueues_on_error_status(temp_db, monkeypatch):
    from src.telegram import webhook

    await _approve_user(100)
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

    await _approve_user(100)
    await _seed_job(temp_db, "J_DONE2", chat_id=100, status="done")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "enrichment_retry:J_DONE2",
            "message": {"chat": {"id": 100}},
        }
    )
    enqueued.assert_not_awaited()
    _, kwargs = ack.await_args
    assert "done" in kwargs.get("text", "")


# ---------------------------------------------------------------------------
# Template picker keyboard tests (issue #53)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_yes_sends_template_picker_keyboard(temp_db, monkeypatch):
    """Tapping Run Gemini now shows the template picker, not directly enqueuing."""
    from src.telegram import webhook

    await _approve_user(100)
    await _seed_job(temp_db, "J_KB", chat_id=100, status="transcript_done")
    sent_kb = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_inline_keyboard", sent_kb)
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {"id": "CB", "data": "gemini_yes:J_KB", "message": {"chat": {"id": 100}}}
    )
    enqueued.assert_not_awaited()
    sent_kb.assert_awaited_once()
    args, kwargs = sent_kb.await_args
    buttons = kwargs.get("buttons") or args[2]
    btn_texts = [b["text"] for row in buttons for b in row]
    assert any("Summary" in t for t in btn_texts)
    assert any("Freestyle" in t for t in btn_texts)
    # callback_data carries job_id
    btn_data = [b["callback_data"] for row in buttons for b in row]
    assert any("template_pick:summary:J_KB" in d for d in btn_data)
    assert any("template_freestyle:J_KB" in d for d in btn_data)


@pytest.mark.asyncio
async def test_gemini_yes_rejects_job_not_ready(temp_db, monkeypatch):
    from src.telegram import webhook

    await _approve_user(100)
    await _seed_job(temp_db, "J_PROC", chat_id=100, status="processing")
    sent_kb = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_inline_keyboard", sent_kb)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    await webhook._handle_callback(
        {"id": "CB", "data": "gemini_yes:J_PROC", "message": {"chat": {"id": 100}}}
    )
    sent_kb.assert_not_awaited()
    _, kwargs = ack.await_args
    assert "not ready" in kwargs.get("text", "").lower()


@pytest.mark.asyncio
async def test_template_pick_collapses_keyboard_and_enqueues(temp_db, monkeypatch):
    from src.telegram import webhook
    from src import database as db

    await _approve_user(100)
    await _seed_job(temp_db, "J_PICK", chat_id=100, status="transcript_done")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    edited = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.edit_message_text", edited)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    callback = {
        "id": "CB",
        "data": "template_pick:technical:J_PICK",
        "message": {"chat": {"id": 100}, "message_id": 42},
    }
    await webhook._handle_callback(callback)
    enqueued.assert_awaited_once_with({"task": "enrichment", "job_id": "J_PICK"})
    edited.assert_awaited_once_with(100, 42, "You chose Technical")
    job = await db.get_job("J_PICK")
    assert job["template"] == "technical"


@pytest.mark.asyncio
async def test_template_pick_rejects_job_not_ready(temp_db, monkeypatch):
    from src.telegram import webhook

    await _approve_user(100)
    await _seed_job(temp_db, "J_NR", chat_id=100, status="processing")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "template_pick:summary:J_NR",
            "message": {"chat": {"id": 100}},
        }
    )
    enqueued.assert_not_awaited()
    _, kwargs = ack.await_args
    assert "not ready" in kwargs.get("text", "").lower()


@pytest.mark.asyncio
async def test_template_freestyle_arms_state_and_sends_force_reply(
    temp_db, monkeypatch
):
    from src.telegram import webhook
    from src import database as db

    await _approve_user(100)
    await _seed_job(temp_db, "J_FS", chat_id=100, status="transcript_done")
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", AsyncMock())
    await webhook._handle_callback(
        {
            "id": "CB",
            "data": "template_freestyle:J_FS",
            "message": {"chat": {"id": 100}},
        }
    )
    fr.assert_awaited_once()
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["mode"] == "awaiting_freestyle"
    assert state["job_id"] == "J_FS"
    job = await db.get_job("J_FS")
    assert job["template"] == "freestyle"


@pytest.mark.asyncio
async def test_awaiting_freestyle_enqueues_when_transcript_done(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await _seed_job(temp_db, "J_FT", chat_id=100, status="transcript_done")
    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_FT")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("Summarize the key business lessons from this video")
    enq.assert_awaited_once_with({"task": "enrichment", "job_id": "J_FT"})
    job = await db.get_job("J_FT")
    assert (
        job["freestyle_prompt"] == "Summarize the key business lessons from this video"
    )
    assert await db.get_chat_state(100) is None


@pytest.mark.asyncio
async def test_awaiting_freestyle_defers_when_still_processing(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await _seed_job(temp_db, "J_FP", chat_id=100, status="processing")
    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_FP")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("Tell me the main takeaways in bullet points")
    enq.assert_not_awaited()
    job = await db.get_job("J_FP")
    assert job["freestyle_prompt"] == "Tell me the main takeaways in bullet points"
    assert await db.get_chat_state(100) is None
    msg = sent.await_args.args[1]
    assert "transcript" in msg.lower() or "ready" in msg.lower()


@pytest.mark.asyncio
async def test_awaiting_freestyle_rejects_too_short(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await _seed_job(temp_db, "J_FS2", chat_id=100, status="transcript_done")
    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_FS2")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("hi")
    enq.assert_not_awaited()
    assert await db.get_chat_state(100) is not None
    assert "too short" in sent.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_awaiting_freestyle_rejects_too_long(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await _seed_job(temp_db, "J_FS3", chat_id=100, status="transcript_done")
    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_FS3")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("x" * 1001)
    enq.assert_not_awaited()
    assert await db.get_chat_state(100) is not None
    assert "too long" in sent.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_cancel_clears_awaiting_freestyle_state(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    from src import database as db

    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_X")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/cancel")
    assert "abandoned" in sent.await_args.args[1].lower()
    assert await db.get_chat_state(100) is None


# ---------------------------------------------------------------------------
# reprocess callback tests (startup-recovery one-tap retry, ADR-0010)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_reprocess_creates_fresh_job_and_enqueues(temp_db, monkeypatch):
    from src.telegram.webhook import CallbackCtx, _cb_reprocess
    from src import database as db

    await _seed_job(
        temp_db, "J_ORPH", chat_id=100, status="error", content_type="short"
    )
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)

    ctx = CallbackCtx(chat_id=100, job_id="J_ORPH", cq_id="CQ", data="reprocess:J_ORPH")
    await _cb_reprocess(ctx)

    # A brand-new job is enqueued — never the orphaned row (avoids Drive/Sheets dup).
    enqueued.assert_awaited_once()
    task = enqueued.await_args.args[0]
    assert task["task"] == "video"
    new_id = task["job_id"]
    assert new_id != "J_ORPH"

    fresh = await db.get_job(new_id)
    assert fresh["status"] == "pending"
    assert fresh["content_type"] == "short"  # carried over from the orphaned job
    assert fresh["url"] == "u"
    ack.assert_awaited()


@pytest.mark.asyncio
async def test_cb_reprocess_job_not_found_acks_error(temp_db, monkeypatch):
    from src.telegram.webhook import CallbackCtx, _cb_reprocess

    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)

    ctx = CallbackCtx(chat_id=1, job_id="NOPE", cq_id="CQ", data="reprocess:NOPE")
    await _cb_reprocess(ctx)

    enqueued.assert_not_awaited()
    _, kwargs = ack.await_args
    assert "not found" in (kwargs.get("text") or "").lower()


# ---------------------------------------------------------------------------
# Dispatch table handler unit tests (issue #25)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cb_gemini_no_marks_done(temp_db, monkeypatch):
    from src.telegram.webhook import CallbackCtx, _cb_gemini_no
    from src import database as db

    await _seed_job(temp_db, "J_NO", chat_id=1, status="transcript_done")
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    ctx = CallbackCtx(chat_id=1, job_id="J_NO", cq_id="CQ1", data="gemini_no:J_NO")
    await _cb_gemini_no(ctx)
    job = await db.get_job("J_NO")
    assert job["status"] == "done"
    ack.assert_awaited_once_with("CQ1")


@pytest.mark.asyncio
async def test_cb_enrichment_retry_rejects_wrong_status(temp_db, monkeypatch):
    from src.telegram.webhook import CallbackCtx, _cb_enrichment_retry

    await _seed_job(temp_db, "J_ENR", chat_id=1, status="enriching")
    enqueued = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enqueued)
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)
    ctx = CallbackCtx(
        chat_id=1, job_id="J_ENR", cq_id="CQ2", data="enrichment_retry:J_ENR"
    )
    await _cb_enrichment_retry(ctx)
    enqueued.assert_not_awaited()
    _, kwargs = ack.await_args
    assert kwargs.get("text") and "enriching" in kwargs["text"]


@pytest.mark.asyncio
async def test_intent_text_never_appears_in_log_records(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch, caplog
):
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
        assert (
            secret_intent not in record.getMessage()
        ), f"intent_text leaked in log record: {record.getMessage()!r}"
        for key, value in record.__dict__.items():
            if isinstance(value, str) and secret_intent in value:
                raise AssertionError(
                    f"intent_text leaked in record attribute {key!r}: {value!r}"
                )


# ---------------------------------------------------------------------------
# Two-step pending-template flow (issue #24)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_template_command_alone_arms_redis(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/method with no URL stores the template in Redis and prompts the user."""
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/method")
    assert _patch_redis._strings.get("pending_template:100") == "method"
    assert "ready" in sent.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_template_command_alone_then_url_uses_template(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """URL sent after a bare /method command is processed with that template."""
    from src import database as db

    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)

    await _post_webhook("/method")
    await _post_webhook("https://instagram.com/reel/DVNolBNE6vV/")

    assert enq.await_args.args[0]["task"] == "video"
    job_id = enq.await_args.args[0]["job_id"]
    job = await db.get_job(job_id)
    assert job["template"] == "method"
    assert job["template_detection_method"] == "explicit_command"
    assert _patch_redis._strings.get("pending_template:100") is None


@pytest.mark.asyncio
async def test_template_pending_cleared_by_slash_command(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """A subsequent slash command clears the pending template."""
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    monkeypatch.setattr("src.queue.enqueue", AsyncMock())

    await _post_webhook("/method")
    assert _patch_redis._strings.get("pending_template:100") == "method"
    await _post_webhook("/cancel")
    assert _patch_redis._strings.get("pending_template:100") is None


@pytest.mark.asyncio
async def test_template_pending_not_applied_to_rejected_url(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """A rejected URL does not consume the pending template."""
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    monkeypatch.setattr("src.queue.enqueue", AsyncMock())

    await _post_webhook("/method")
    await _post_webhook("https://instagram.com/p/abc/")

    assert "Unsupported" in sent.await_args.args[1]
    assert _patch_redis._strings.get("pending_template:100") is None


# ---------------------------------------------------------------------------
# SlashCtx handler unit tests (issue #27)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_find_no_query_sends_usage(monkeypatch):
    """/find with no arguments sends the usage hint and nothing else."""
    from src.telegram.webhook import SlashCtx, _cmd_find

    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    ctx = SlashCtx(chat_id=42, parts=["/find"], message_id=None)
    await _cmd_find(ctx)

    sent.assert_awaited_once()
    args, _ = sent.await_args
    assert args[0] == 42
    assert "Usage: /find <query>" in args[1]


@pytest.mark.asyncio
async def test_cmd_cancel_awaiting_intent_sends_intent_canceled(temp_db, monkeypatch):
    """/cancel when state.mode == 'awaiting_intent' sends the Intent-canceled message."""
    from src.telegram.webhook import SlashCtx, _cmd_cancel
    from src import database as db

    await db.set_chat_state(chat_id=7, mode="awaiting_intent", job_id="J_TEST")

    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    fake = FakeRedis()
    import src.queue as q_module

    monkeypatch.setattr(q_module, "_redis", fake)

    ctx = SlashCtx(chat_id=7, parts=["/cancel"], message_id=None)
    await _cmd_cancel(ctx)

    sent.assert_awaited_once()
    args, _ = sent.await_args
    assert args[0] == 7
    assert "✍️ Intent canceled." in args[1]
    assert await db.get_chat_state(7) is None


# ---------------------------------------------------------------------------
# /freestyle slash command tests (issue #54)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cmd_freestyle_no_url_sets_pending_template(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/freestyle with no URL sets pending_template in Redis and prompts the user."""
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/freestyle")
    assert _patch_redis._strings.get("pending_template:100") == "freestyle"
    assert "ready" in sent.await_args.args[1].lower()


@pytest.mark.asyncio
async def test_cmd_freestyle_long_url_enqueues_and_arms_state(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/freestyle <long_url> enqueues video task immediately and arms awaiting_freestyle."""
    from src import database as db

    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/freestyle https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    enq.assert_awaited_once()
    task = enq.await_args.args[0]
    assert task["task"] == "video"
    fr.assert_awaited_once()
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["mode"] == "awaiting_freestyle"
    job = await db.get_job(task["job_id"])
    assert job["template"] == "freestyle"
    assert job["content_type"] == "long"


@pytest.mark.asyncio
async def test_cmd_freestyle_short_url_arms_state_no_enqueue(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/freestyle <short_url> arms awaiting_freestyle but does NOT enqueue video yet."""
    from src import database as db

    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    fr = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", fr)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())
    await _post_webhook("/freestyle https://instagram.com/reel/DVNolBNE6vV/")
    enq.assert_not_awaited()
    fr.assert_awaited_once()
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["mode"] == "awaiting_freestyle"


@pytest.mark.asyncio
async def test_pending_template_freestyle_with_url_message(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/freestyle then URL message: long video enqueues immediately; short video defers."""
    from src import database as db

    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_force_reply", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())

    await _post_webhook("/freestyle")
    await _post_webhook("https://instagram.com/reel/DVNolBNE6vV/")

    enq.assert_not_awaited()
    state = await db.get_chat_state(100)
    assert state is not None
    assert state["mode"] == "awaiting_freestyle"
    assert _patch_redis._strings.get("pending_template:100") is None


@pytest.mark.asyncio
async def test_awaiting_freestyle_short_video_enqueues_video_task(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """For short video: user reply with prompt enqueues video task and sends confirmation."""
    from src import database as db

    await _seed_job(
        temp_db, "J_SH", chat_id=100, content_type="short", status="pending"
    )
    await db.set_chat_state(chat_id=100, mode="awaiting_freestyle", job_id="J_SH")
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("Extract the key frameworks from this video")
    enq.assert_awaited_once_with({"task": "video", "job_id": "J_SH"})
    job = await db.get_job("J_SH")
    assert job["freestyle_prompt"] == "Extract the key frameworks from this video"
    assert await db.get_chat_state(100) is None
    msg = sent.await_args.args[1]
    assert "freestyle" in msg.lower()
    assert "J_SH"[-4:] in msg


# ---------------------------------------------------------------------------
# /allowlist family tests (issue #61)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowlist_multi_arg_adds_both_domains(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """Multi-arg /allowlist foo.com bar.com adds both domains."""
    from src import database as db

    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/allowlist foo.com bar.com")
    domains = await db.list_allowed_domains(100)
    assert "foo.com" in domains
    assert "bar.com" in domains


@pytest.mark.asyncio
async def test_unallowlist_nonexistent_returns_friendly_message(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/unallowlist nonexistent.com sends a friendly not-found message."""
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/unallowlist nonexistent.com")
    msg = sent.await_args.args[1]
    assert "nonexistent.com" in msg
    # Should NOT send an error traceback — a friendly user-facing message.
    assert "Not in your allowlist" in msg or "not in" in msg.lower()


@pytest.mark.asyncio
async def test_allowlist_list_returns_custom_rows_only(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/allowlist_list shows only rows the user added — defaults are NOT surfaced."""
    from src import database as db

    await db.add_allowed_domain(100, "myblog.com")
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/allowlist_list")
    msg = sent.await_args.args[1]
    assert "myblog.com" in msg
    # Default domains must NOT appear in the list output
    assert "substack.com" not in msg
    assert "medium.com" not in msg


@pytest.mark.asyncio
async def test_allowlist_plain_text_shortcut(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """Plain-text 'allowlist foo.com' (no leading slash) is dispatched as /allowlist."""
    from src import database as db

    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("allowlist foo.com")
    domains = await db.list_allowed_domains(100)
    assert "foo.com" in domains


# ---------------------------------------------------------------------------
# /download_md tests (issue #60)
# ---------------------------------------------------------------------------


async def test_download_md_cache_miss_calls_jina_and_sends_document(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/download_md on a URL not yet cached: calls Jina once and sends document."""
    from src import database as db
    from src.services import jina as jina_module

    url = "https://example.com/article"
    fetch_mock = AsyncMock(
        return_value=("Great Article", "# Great Article\n\nBody text.")
    )
    monkeypatch.setattr(jina_module, "fetch_markdown", fetch_mock)
    send_doc = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_document", send_doc)

    await _post_webhook(f"/download_md {url}")

    # Jina must have been called exactly once
    fetch_mock.assert_awaited_once_with(url)

    # Document was sent
    send_doc.assert_awaited_once()
    args = send_doc.await_args.args
    assert args[0] == 100  # chat_id
    assert isinstance(args[1], bytes)  # file_bytes
    assert args[2].endswith(".md")  # filename

    # Content is cached
    cached = await db.get_markdown_cache(url)
    assert cached is not None
    assert "Great Article" in cached["content"]


@pytest.mark.asyncio
async def test_download_md_cache_hit_does_not_call_jina(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """Second /download_md for the same URL: Jina must NOT be called."""
    from src import database as db
    from src.services import jina as jina_module

    url = "https://example.com/cached"
    # Pre-populate cache
    await db.insert_markdown_cache(url, "# Cached Article\n\nPre-stored body.")

    fetch_mock = AsyncMock(return_value=("Cached Article", "Pre-stored body."))
    monkeypatch.setattr(jina_module, "fetch_markdown", fetch_mock)
    send_doc = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_document", send_doc)

    await _post_webhook(f"/download_md {url}")

    # Jina must NOT be called
    assert fetch_mock.await_count == 0, "Jina must not be called on cache hit"
    # Document was still sent
    send_doc.assert_awaited_once()


@pytest.mark.asyncio
async def test_download_md_jina_error_sends_error_message(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """/download_md with Jina returning 404 must send an error message, not crash."""
    from src.services import jina as jina_module

    url = "https://example.com/missing"
    monkeypatch.setattr(
        jina_module,
        "fetch_markdown",
        AsyncMock(side_effect=jina_module.JinaFetchError(404)),
    )
    send_doc = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_document", send_doc)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    await _post_webhook(f"/download_md {url}")

    send_doc.assert_not_awaited()
    sent.assert_awaited_once()
    assert "404" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_download_md_plain_text_shortcut(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """Plain-text 'download_md <url>' must be routed the same as the slash command."""
    from src.services import jina as jina_module

    url = "https://example.com/shortcut"
    fetch_mock = AsyncMock(return_value=("Title", "Body."))
    monkeypatch.setattr(jina_module, "fetch_markdown", fetch_mock)
    send_doc = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_document", send_doc)

    await _post_webhook(f"download_md {url}")

    fetch_mock.assert_awaited_once_with(url)
    send_doc.assert_awaited_once()


# ---------------------------------------------------------------------------
# /force with markdown_cache — three-state tests (issue #60)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_jobs_and_cache_clears_cache_and_reprocesses(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """State 1: job exists + cache exists → cache deleted, job reset, video enqueued."""
    from src import database as db

    url = "https://youtu.be/abc123"
    # Create a real job with the actual URL so find_recent_job_by_url can find it.
    await db.create_job(chat_id=100, url=url, content_type="long")
    await db.insert_markdown_cache(url, "cached content")

    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())

    await _post_webhook(f"/force {url}")

    # Cache must be gone
    assert await db.get_markdown_cache(url) is None
    # Job was enqueued
    enq.assert_awaited_once()
    assert enq.await_args.args[0]["task"] == "video"


@pytest.mark.asyncio
async def test_force_cache_only_deletes_cache_and_acks(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """State 2: no video job, cache exists → cache deleted, ack sent."""
    from src import database as db

    url = "https://example.com/article"
    await db.insert_markdown_cache(url, "cached content")

    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    await _post_webhook(f"/force {url}")

    assert await db.get_markdown_cache(url) is None
    enq.assert_not_awaited()
    sent.assert_awaited_once()
    # Ack message must mention cache/cleared
    msg = sent.await_args.args[1].lower()
    assert "cache" in msg or "cleared" in msg


@pytest.mark.asyncio
async def test_force_neither_job_nor_cache_rejects_unsupported_url(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """State 3: no job, no cache, unsupported URL → rejection message."""
    enq = AsyncMock()
    monkeypatch.setattr("src.queue.enqueue", enq)
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)

    await _post_webhook("/force https://example.com/not-a-video")

    enq.assert_not_awaited()
    sent.assert_awaited_once()
    msg = sent.await_args.args[1]
    assert "Unsupported" in msg or "unsupported" in msg.lower()


@pytest.mark.asyncio
async def test_force_repo_deletes_both_redis_cache_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When /force is called with a repo URL and an existing job, both Redis keys are deleted."""
    deleted: list[str] = []

    class SpyRedis:
        async def delete(self, *keys: str) -> int:
            deleted.extend(keys)
            return len(keys)

        async def get(self, key: str) -> None:
            return None

        async def lpos(self, *a, **kw) -> None:
            return None

    monkeypatch.setattr("src.queue._redis", SpyRedis())
    monkeypatch.setattr("src.telegram.webhook.queue._client", lambda: SpyRedis())

    existing_job = {
        "id": "20260101_120000_ABCD",
        "content_type": "repo",
        "bot_message_id": None,
        "drive_url": None,
        "status": "done",
    }
    monkeypatch.setattr(
        "src.telegram.webhook.database.find_recent_job_by_url",
        AsyncMock(return_value=existing_job),
    )
    monkeypatch.setattr(
        "src.telegram.webhook.database.list_allowed_domains",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "src.telegram.webhook.database.get_markdown_cache", AsyncMock(return_value=None)
    )
    monkeypatch.setattr("src.telegram.webhook.database.reset_job", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.database.clear_chat_state", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.queue.enqueue", AsyncMock())
    monkeypatch.setattr("src.telegram.webhook.send_message", AsyncMock())

    # Dispatch /force via the slash handler directly
    from src.telegram.webhook import _cmd_force, SlashCtx

    ctx = SlashCtx(
        chat_id=1, parts=["/force", "https://github.com/owner/repo"], message_id=None
    )
    await _cmd_force(ctx)

    assert "github_repo_bundle:owner/repo" in deleted
    assert "github_meta:owner/repo" in deleted


# ---------------------------------------------------------------------------
# /start and /help tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_sends_welcome_message(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/start")
    sent.assert_awaited_once()
    args, kwargs = sent.await_args
    assert args[0] == 100
    assert "Video Intelligence Gateway" in args[1]
    assert kwargs.get("parse_mode") == "Markdown"


@pytest.mark.asyncio
async def test_help_sends_command_list(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    await _post_webhook("/help")
    sent.assert_awaited_once()
    args, kwargs = sent.await_args
    assert "/find" in args[1]
    assert "/spec" in args[1]
    assert "/cancel" in args[1]
    assert kwargs.get("parse_mode") == "Markdown"


# ---------------------------------------------------------------------------
# Webhook error handling tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_handler_error_returns_ok_and_notifies_user(
    temp_db, _patch_webhook_secret, _patch_redis, monkeypatch
):
    """An exception in _route_text must not 500 the webhook — return ok and notify."""
    monkeypatch.setattr(
        "src.telegram.webhook._route_text",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    sent = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.send_message", sent)
    result = await _post_webhook("https://youtu.be/abc")
    assert result == {"ok": True}
    sent.assert_awaited_once()
    assert "went wrong" in sent.await_args.args[1]


@pytest.mark.asyncio
async def test_webhook_callback_error_acknowledges_query(
    _patch_webhook_secret, monkeypatch
):
    """A failing callback must still answer the query so the button stops spinning."""
    from src.telegram.webhook import webhook

    monkeypatch.setattr(
        "src.telegram.webhook._handle_callback",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    ack = AsyncMock()
    monkeypatch.setattr("src.telegram.webhook.answer_callback_query", ack)

    class _Req:
        async def json(self):
            return {"callback_query": {"id": "cb1", "data": "x"}}

    result = await webhook(_Req(), x_telegram_bot_api_secret_token="S")
    assert result == {"ok": True}
    ack.assert_awaited_once_with("cb1")

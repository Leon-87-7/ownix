from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import database
from src.api import email_webhook, newsletter_digest
from src.config import settings
from src.services import job_recovery

pytestmark = pytest.mark.asyncio


async def _init_db(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "email_digest.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    await database.init_db()


async def _subscription(name: str = "Signals") -> dict:
    return await database.create_newsletter_subscription(
        chat_id=123,
        name=name,
        sender_email="editor@example.com",
        alias_local_part=f"u_{name.lower()}",
    )


def _payload(sub: dict, message_id: str = "<digest@example.com>") -> email_webhook.EmailDigestPayload:
    return email_webhook.EmailDigestPayload.model_validate(
        {
            "envelopeTo": f"{sub['alias_local_part']}@leondev.xyz",
            "from": "Editor <editor@example.com>",
            "subject": "Issue 1",
            "html": '<a href="https://example.com/a?utm_source=x">A</a>',
            "text": "A",
            "messageId": message_id,
        }
    )


async def test_concurrent_duplicate_receipt_creates_one_job(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    sub = await _subscription()
    key = email_webhook.receipt_key(
        sub["alias_local_part"],
        "<same@example.com>",
        subject="Issue",
        html="<p>body</p>",
        text="body",
    )

    async def create() -> dict:
        return await database.create_email_digest_receipt_job(
            subscription=sub,
            receipt_key=key,
            receipt_url=f"email_digest:{key[:16]}",
            subject="Issue",
            html="<p>body</p>",
            text="body",
            daily_cap=20,
        )

    results = await asyncio.gather(create(), create())

    assert sorted(result["status"] for result in results) == ["created", "deduped"]
    row = await database._fetch_one("SELECT COUNT(*) AS n FROM email_digest_payloads")
    assert row["n"] == 1
    row = await database._fetch_one("SELECT COUNT(*) AS n FROM jobs WHERE url LIKE 'email_digest:%'")
    assert row["n"] == 1


async def test_duplicate_pending_receipt_repushes_same_job(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    sub = await _subscription()
    enqueue = AsyncMock()
    monkeypatch.setattr(email_webhook.queue, "enqueue", enqueue)

    body = _payload(sub)
    first = await email_webhook.receive_email_digest(
        body,
        x_ownix_email_secret=settings.EMAIL_WEBHOOK_SECRET,
    )
    second = await email_webhook.receive_email_digest(
        body,
        x_ownix_email_secret=settings.EMAIL_WEBHOOK_SECRET,
    )

    assert first["job_id"] == second["job_id"]
    assert second["deduped"] is True
    assert enqueue.await_count == 2
    assert enqueue.await_args_list[0].args[0]["job_id"] == enqueue.await_args_list[1].args[0]["job_id"]


async def test_generic_recovery_excludes_email_digest_receipts(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    enqueue = AsyncMock()
    monkeypatch.setattr(job_recovery.queue, "enqueue", enqueue)
    digest_job = await database.create_job(
        chat_id=123,
        url="email_digest:abc123",
        content_type="link",
        status="error",
    )
    normal_job = await database.create_job(
        chat_id=123,
        url="https://example.com/normal",
        content_type="short",
        status="error",
    )

    summary = await job_recovery.recovery_summary(123)
    retried = await job_recovery.retry_error(123)

    assert summary["error_jobs"] == 1
    assert retried["replaced"] == 1
    assert enqueue.await_count == 1
    assert (await database.get_job(digest_job))["status"] == "error"
    assert (await database.get_job(normal_job))["status"] == "cancelled"


async def test_subscription_delete_clears_failed_payload_content(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    sub = await _subscription()
    key = email_webhook.receipt_key(
        sub["alias_local_part"],
        "<failed@example.com>",
        subject="Issue",
        html="<p>secret</p>",
        text="secret",
    )
    created = await database.create_email_digest_receipt_job(
        subscription=sub,
        receipt_key=key,
        receipt_url=f"email_digest:{key[:16]}",
        subject="Issue",
        html="<p>secret</p>",
        text="secret",
        daily_cap=20,
    )
    await database.update_job_status(created["job"]["id"], "error")

    assert await database.delete_newsletter_subscription(
        subscription_id=sub["id"],
        chat_id=123,
    )

    row = await database._fetch_one(
        "SELECT subscription_id, subject, html, text FROM email_digest_payloads WHERE job_id = ?",
        (created["job"]["id"],),
    )
    assert dict(row) == {"subscription_id": None, "subject": None, "html": None, "text": None}


async def test_document_candidate_promotion_delegates_to_doc_parser(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    sub = await _subscription()
    candidate_id = await database.insert_digest_candidate(
        space_id=sub["space_id"],
        url="https://example.com/report.pdf",
        canonical_url="https://example.com/report.pdf",
        title="Report",
    )
    job_id = await database.create_job(
        chat_id=123,
        url="documents/report.pdf",
        content_type="document",
    )
    upload_url = AsyncMock(return_value={"job_id": job_id, "status": "pending", "content_type": "document"})
    create_job = AsyncMock()
    monkeypatch.setattr(newsletter_digest, "upload_url", upload_url)
    monkeypatch.setattr(newsletter_digest, "create_job", create_job)
    request = SimpleNamespace(state=SimpleNamespace(user={"id": 123}))

    result = await newsletter_digest.promote_candidate(sub["id"], candidate_id, request)

    assert result["job_id"] == job_id
    upload_url.assert_awaited_once()
    create_job.assert_not_awaited()
    candidate = await database.get_digest_candidate(sub["space_id"], candidate_id)
    assert candidate["status"] == "promoted"
    assert candidate["job_id"] == job_id
    row = await database._fetch_one(
        "SELECT 1 FROM space_urls WHERE space_id = ? AND job_id = ?",
        (sub["space_id"], job_id),
    )
    assert row is not None

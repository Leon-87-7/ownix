"""Unit tests for Telegram PDF upload ingestion (#151) + URL routing (#152)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def patched(monkeypatch):
    """Patch the I/O seams the document handlers touch; return the mocks."""
    from src.telegram import webhook

    mocks = {
        "send_message": AsyncMock(),
        "download_file": AsyncMock(return_value=b"%PDF-1.4 data"),
        "create_job": AsyncMock(return_value="20260618_000000_ABCD"),
        "enqueue": AsyncMock(),
        "upload": AsyncMock(),
    }
    monkeypatch.setattr(webhook, "send_message", mocks["send_message"])
    monkeypatch.setattr(webhook, "download_file", mocks["download_file"])
    monkeypatch.setattr(webhook.database, "create_job", mocks["create_job"])
    monkeypatch.setattr(webhook.queue, "enqueue", mocks["enqueue"])
    monkeypatch.setattr(webhook.storage, "upload", mocks["upload"])
    return webhook, mocks


@pytest.mark.asyncio
async def test_accepted_pdf_uploads_creates_job_enqueues(patched):
    webhook, m = patched
    doc = {"file_id": "F1", "file_name": "paper.pdf", "mime_type": "application/pdf", "file_size": 1234}

    await webhook._ingest_document(chat_id=42, document=doc, message_id=7)

    m["download_file"].assert_awaited_once_with("F1")
    # content-addressed key: documents/<sha>.pdf
    (key, data, ctype), _ = m["upload"].call_args
    assert key.startswith("documents/") and key.endswith(".pdf")
    assert ctype == "application/pdf"
    m["create_job"].assert_awaited_once()
    assert m["create_job"].call_args.kwargs["content_type"] == "document"
    assert m["create_job"].call_args.kwargs["url"] == key
    m["enqueue"].assert_awaited_once_with({"task": "document", "job_id": "20260618_000000_ABCD"})


@pytest.mark.asyncio
async def test_unsupported_type_rejected_no_job(patched):
    webhook, m = patched
    doc = {"file_id": "F1", "file_name": "notes.docx", "mime_type": "application/vnd.openxml", "file_size": 10}

    await webhook._handle_document_update(chat_id=42, message={}, document=doc)

    m["send_message"].assert_awaited_once()
    assert "PDF" in m["send_message"].call_args.args[1]
    m["create_job"].assert_not_called()


@pytest.mark.asyncio
async def test_oversized_pdf_rejected_no_job(patched):
    webhook, m = patched
    doc = {"file_id": "F1", "file_name": "huge.pdf", "mime_type": "application/pdf",
           "file_size": 21 * 1024 * 1024}

    await webhook._handle_document_update(chat_id=42, message={}, document=doc)

    assert "too large" in m["send_message"].call_args.args[1].lower()
    m["create_job"].assert_not_called()


@pytest.mark.asyncio
async def test_pdf_by_extension_when_mime_missing(patched):
    """Telegram sometimes omits mime_type; a .pdf filename must still be accepted."""
    webhook, m = patched
    doc = {"file_id": "F1", "file_name": "paper.pdf", "file_size": 100}

    await webhook._handle_document_update(chat_id=42, message={"message_id": 1}, document=doc)
    # accepted → no rejection message sent synchronously
    m["send_message"].assert_not_called()


@pytest.mark.asyncio
async def test_photo_message_does_not_hit_document_handler(monkeypatch):
    """A message.photo still routes to the photo pipeline, not the document one."""
    from src.telegram import webhook

    photo_handler = AsyncMock()
    doc_handler = AsyncMock()
    monkeypatch.setattr(webhook, "_handle_photo_update", photo_handler)
    monkeypatch.setattr(webhook, "_handle_document_update", doc_handler)

    class _Req:
        async def json(self):
            return {"message": {"chat": {"id": 1}, "photo": [{"file_id": "P1"}]}}

    await webhook.webhook(_Req(), x_telegram_bot_api_secret_token=webhook.settings.TELEGRAM_WEBHOOK_SECRET)

    photo_handler.assert_awaited_once()
    doc_handler.assert_not_called()


def _patch_httpx(monkeypatch, webhook, *, content: bytes, raise_exc: Exception | None = None,
                 content_length: int | None = None):
    """Patch the SSRF host check + httpx streaming client to yield `content` (no redirect)."""
    monkeypatch.setattr(webhook, "_is_public_host", AsyncMock(return_value=True))

    resp = MagicMock()
    resp.is_redirect = False
    resp.next_request = None
    resp.raise_for_status = MagicMock()
    resp.headers = {"content-length": str(content_length if content_length is not None else len(content))}

    async def _aiter_bytes():
        yield content
    resp.aiter_bytes = _aiter_bytes

    @asynccontextmanager
    async def _stream(*a, **k):
        if raise_exc:
            raise raise_exc
        yield resp

    client = MagicMock()
    client.stream = _stream

    @asynccontextmanager
    async def _fake_client(*a, **k):
        yield client

    monkeypatch.setattr(webhook.httpx, "AsyncClient", _fake_client)


@pytest.mark.asyncio
async def test_route_document_url_fetches_uploads_enqueues(patched, monkeypatch):
    webhook, m = patched
    _patch_httpx(monkeypatch, webhook, content=b"%PDF-1.5 from url")

    await webhook._route_document_url(chat_id=9, url="https://x.tld/a.pdf", message_id=3)

    (key, data, ctype), _ = m["upload"].call_args
    assert key.startswith("documents/") and key.endswith(".pdf")
    assert data == b"%PDF-1.5 from url"
    assert m["create_job"].call_args.kwargs["content_type"] == "document"
    m["enqueue"].assert_awaited_once_with({"task": "document", "job_id": "20260618_000000_ABCD"})


@pytest.mark.asyncio
async def test_route_document_url_non_pdf_body_rejected(patched, monkeypatch):
    webhook, m = patched
    _patch_httpx(monkeypatch, webhook, content=b"<html>not a pdf</html>")

    await webhook._route_document_url(chat_id=9, url="https://x.tld/a.pdf", message_id=3)

    m["create_job"].assert_not_called()
    assert "didn't return a pdf" in m["send_message"].call_args.args[1].lower()


@pytest.mark.asyncio
async def test_route_document_url_fetch_failure_rejected(patched, monkeypatch):
    webhook, m = patched
    _patch_httpx(monkeypatch, webhook, content=b"", raise_exc=RuntimeError("boom"))

    await webhook._route_document_url(chat_id=9, url="https://x.tld/a.pdf", message_id=3)

    m["create_job"].assert_not_called()
    m["upload"].assert_not_called()


@pytest.mark.asyncio
async def test_route_document_url_oversized_body_rejected(patched, monkeypatch):
    """A body exceeding the 20MB cap is dropped mid-stream, never uploaded."""
    webhook, m = patched
    _patch_httpx(monkeypatch, webhook, content=b"%PDF" + b"x" * (21 * 1024 * 1024),
                 content_length=0)  # lie about length → must be caught by the stream counter

    await webhook._route_document_url(chat_id=9, url="https://x.tld/a.pdf", message_id=3)

    m["upload"].assert_not_called()
    m["create_job"].assert_not_called()


@pytest.mark.asyncio
async def test_ingest_document_non_pdf_rejected(patched):
    webhook, m = patched
    m["download_file"].return_value = b"<html>nope</html>"

    await webhook._ingest_document(chat_id=42, document={"file_id": "F1"}, message_id=1)

    m["upload"].assert_not_called()
    assert "valid pdf" in m["send_message"].call_args.args[1].lower()


@pytest.mark.asyncio
async def test_ingest_document_download_error_notifies_user(patched):
    webhook, m = patched
    m["download_file"].side_effect = RuntimeError("telegram down")

    await webhook._ingest_document(chat_id=42, document={"file_id": "F1"}, message_id=1)

    m["create_job"].assert_not_called()
    assert "couldn't process" in m["send_message"].call_args.args[1].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "http://127.0.0.1/secret.pdf",
    "http://169.254.169.254/latest/meta-data/x.pdf",  # cloud metadata
    "http://[::1]/x.pdf",
    "file:///etc/passwd.pdf",
])
async def test_route_document_url_blocks_ssrf(patched, monkeypatch, url):
    """Internal/loopback/metadata/non-http targets are blocked before any fetch."""
    webhook, m = patched
    # Real _is_public_host (not patched); ensure no network even if it slipped through.
    called = {"got": False}

    @asynccontextmanager
    async def _boom(*a, **k):
        called["got"] = True
        yield MagicMock()

    monkeypatch.setattr(webhook.httpx, "AsyncClient", _boom)

    await webhook._route_document_url(chat_id=9, url=url, message_id=3)

    m["upload"].assert_not_called()
    m["create_job"].assert_not_called()
    assert called["got"] is False  # never opened a client for a blocked literal IP

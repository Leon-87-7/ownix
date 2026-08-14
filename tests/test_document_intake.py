"""Regression tests for shared remote Document intake orchestration."""

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_duplicate_remote_document_skips_fetch_and_upload(monkeypatch):
    from src.services import document_intake

    existing = {
        "id": "JOB1",
        "status": "done",
        "content_type": "document",
    }
    monkeypatch.setattr(
        document_intake.database,
        "find_recent_job_by_url",
        AsyncMock(return_value=existing),
    )
    fetch = AsyncMock()
    upload = AsyncMock()
    monkeypatch.setattr(document_intake, "fetch_remote_document", fetch)
    monkeypatch.setattr(document_intake.storage, "upload", upload)

    result = await document_intake.create_remote_document_job(
        7, "https://example.com/report.pdf"
    )

    assert result == {
        "job_id": "JOB1",
        "status": "done",
        "content_type": "document",
        "_deduped": True,
    }
    fetch.assert_not_awaited()
    upload.assert_not_awaited()

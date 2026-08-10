"""Unit tests for src/api/parsed.py — document-job output generation (ADR-0029).

Trust-boundary intake (SSRF guard, PDF validation, capped reads) moved to
tests/test_pdf_intake.py with the src/services/pdf_intake.py module (#228).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


def test_python_multipart_declared_in_runtime_requirements():
    # /api/parsed/upload calls request.form() to parse the multipart body. Plain
    # `fastapi` does NOT pull in python-multipart, so if it isn't declared in
    # requirements.txt the prod image (built from requirements.txt only) 500s on
    # every upload. The dev env happens to have it installed, so an endpoint test
    # can't catch this — guard the declared dependency itself.
    reqs = Path(__file__).resolve().parent.parent / "requirements.txt"
    assert "python-multipart" in reqs.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_generate_output_rejects_non_document_job():
    from src.api.parsed import _generate_output
    # An article/repo job (plain URL) must be rejected before SHA extraction, not 500.
    job = {"id": "J", "chat_id": 1, "content_type": "article", "url": "https://example.com/post"}
    with pytest.raises(HTTPException) as exc:
        await _generate_output(job, "clean")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_generate_output_parse_error_returns_422(monkeypatch):
    from src.api import parsed
    from src.services.parse import ParseError

    async def boom(*a, **k):
        raise ParseError("scanned or image-only")

    monkeypatch.setattr(parsed.document_processor, "_cached_parse", boom)
    job = {"id": "J", "chat_id": 1, "content_type": "document", "url": "documents/abc.pdf"}
    with pytest.raises(HTTPException) as exc:
        await parsed._generate_output(job, "clean")
    assert exc.value.status_code == 422
    assert exc.value.detail == {"field": "job", "message": "Document text could not be extracted"}


@pytest.mark.asyncio
async def test_create_document_job_stores_office_under_source_ext(monkeypatch, office_samples):
    """An office upload is content-addressed under documents/<sha>.<srcext> with an
    honest MIME, so the processor can route it back to anydoc (ADR-0023)."""
    from src.api import parsed

    uploaded: dict = {}

    async def fake_upload(key, data, ctype):
        uploaded["key"] = key
        uploaded["ctype"] = ctype

    monkeypatch.setattr(parsed.storage, "upload", fake_upload)
    monkeypatch.setattr(
        parsed,
        "create_and_enqueue_job",
        AsyncMock(return_value={"id": "JOB1", "status": "pending"}),
    )
    monkeypatch.setattr(parsed.database, "set_job_telegram_delivery", AsyncMock())

    result = await parsed._create_document_job(7, office_samples["deck.pptx"], "deck.pptx")

    assert uploaded["key"].startswith("documents/") and uploaded["key"].endswith(".pptx")
    assert "presentationml" in uploaded["ctype"]
    parsed.create_and_enqueue_job.assert_awaited_once_with(
        chat_id=7,
        url=uploaded["key"],
        content_type="document",
    )
    parsed.database.set_job_telegram_delivery.assert_awaited_once_with("JOB1", "off")
    assert result["gcs_key"].endswith(".pptx")


@pytest.mark.asyncio
async def test_create_document_job_preserves_macro_enabled_source_ext(monkeypatch, office_samples):
    from src.api import parsed

    uploaded: dict = {}

    async def fake_upload(key, data, ctype):
        uploaded["key"] = key
        uploaded["ctype"] = ctype

    monkeypatch.setattr(parsed.storage, "upload", fake_upload)
    monkeypatch.setattr(
        parsed,
        "create_and_enqueue_job",
        AsyncMock(return_value={"id": "JOB1", "status": "pending"}),
    )
    monkeypatch.setattr(parsed.database, "set_job_telegram_delivery", AsyncMock())

    result = await parsed._create_document_job(7, office_samples["deck.pptx"], "deck.pptm")

    assert uploaded["key"].startswith("documents/") and uploaded["key"].endswith(".pptm")
    assert "powerpoint.presentation.macroEnabled" in uploaded["ctype"]
    assert result["gcs_key"].endswith(".pptm")


@pytest.mark.asyncio
async def test_create_document_job_preserves_delivery_on_deduped_job(monkeypatch, office_samples):
    from src.api import parsed

    monkeypatch.setattr(parsed.storage, "upload", AsyncMock())
    monkeypatch.setattr(
        parsed,
        "create_and_enqueue_job",
        AsyncMock(return_value={"id": "JOB1", "status": "done", "_deduped": True}),
    )
    monkeypatch.setattr(parsed.database, "set_job_telegram_delivery", AsyncMock())

    result = await parsed._create_document_job(7, office_samples["deck.pptx"], "deck.pptx")

    assert result["job_id"] == "JOB1"
    parsed.database.set_job_telegram_delivery.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_document_job_rejects_unsupported(monkeypatch):
    from src.api import parsed

    monkeypatch.setattr(parsed.storage, "upload", AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await parsed._create_document_job(7, b"just some plain notes", "notes.txt")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_forks_to_photo_ocr(monkeypatch):
    """The /upload image branch returns an OCR links payload, not a document job."""
    from src.api import parsed

    monkeypatch.setattr(
        "src.intake.uploads.ocr_image_links",
        AsyncMock(return_value={"links": [{"url": "https://a.tld"}], "summary": "s"}),
    )
    result = await parsed._ocr_image_response(7, b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")

    assert result["kind"] == "links"
    assert result["links"] == [{"url": "https://a.tld"}]


@pytest.mark.asyncio
async def test_upload_rejects_oversized_image_before_ocr(monkeypatch):
    from src.api import parsed

    ocr = AsyncMock()
    monkeypatch.setattr(parsed, "_ocr_image_response", ocr)

    class FakeRequest:
        headers = {"x-filename": "shot.png"}
        state = SimpleNamespace(user={"id": 7})

        async def stream(self):
            yield b"\x89PNG\r\n\x1a\n" + b"0" * parsed.MAX_DOC_BYTES

    with pytest.raises(HTTPException) as exc:
        await parsed.upload_document(FakeRequest())

    assert exc.value.status_code == 400
    assert exc.value.detail == {"field": "file", "message": "File must be 20 MB or smaller"}
    ocr.assert_not_awaited()

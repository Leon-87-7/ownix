"""Unit tests for src/api/parsed.py — document-job output generation (ADR-0029).

Trust-boundary intake (SSRF guard, PDF validation, capped reads) moved to
tests/test_pdf_intake.py with the src/services/pdf_intake.py module (#228).
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException


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

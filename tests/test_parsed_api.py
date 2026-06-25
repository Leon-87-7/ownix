"""Unit tests for src/api/parsed.py — SSRF guard + PDF validation (ADR-0029)."""
from __future__ import annotations

import socket

import pytest
from fastapi import HTTPException

from src.api.parsed import MAX_PDF_BYTES, _assert_public_host, _validate_pdf


@pytest.mark.asyncio
async def test_assert_public_host_rejects_loopback():
    with pytest.raises(HTTPException):
        await _assert_public_host("localhost")


@pytest.mark.asyncio
async def test_assert_public_host_rejects_cloud_metadata(monkeypatch):
    # 169.254.169.254 is link-local — the classic SSRF metadata target.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))])
    with pytest.raises(HTTPException):
        await _assert_public_host("metadata.example")


@pytest.mark.asyncio
async def test_assert_public_host_allows_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    await _assert_public_host("example.com")  # no raise


@pytest.mark.asyncio
async def test_assert_public_host_dns_failure_is_400(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("name resolution failed")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(HTTPException) as exc:
        await _assert_public_host("no-such-host.invalid")
    assert exc.value.status_code == 400


def test_validate_pdf_rejects_non_pdf():
    with pytest.raises(HTTPException):
        _validate_pdf(b"not a pdf", "x.pdf")


def test_validate_pdf_rejects_oversize():
    with pytest.raises(HTTPException):
        _validate_pdf(b"%PDF" + b"0" * MAX_PDF_BYTES, "x.pdf")


def test_validate_pdf_accepts_pdf():
    _validate_pdf(b"%PDF-1.4 ...", "doc.pdf")  # no raise


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

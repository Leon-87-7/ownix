"""Unit tests for src/services/pdf_intake.py — trust-boundary PDF intake (#228, ADR-0029)."""
from __future__ import annotations

import socket
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import HTTPException

from src.services.pdf_intake import (
    MAX_PDF_BYTES,
    REMOTE_PDF_HEADERS,
    assert_public_host,
    fetch_remote_document,
    read_capped_body,
    validate_document,
    validate_pdf,
)


@pytest.mark.asyncio
async def test_assert_public_host_rejects_loopback(monkeypatch):
    # Mock the resolver so the test is hermetic (no real DNS for "localhost").
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(HTTPException):
        await assert_public_host("localhost")


@pytest.mark.asyncio
async def test_assert_public_host_rejects_cloud_metadata(monkeypatch):
    # 169.254.169.254 is link-local — the classic SSRF metadata target.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))])
    with pytest.raises(HTTPException):
        await assert_public_host("metadata.example")


@pytest.mark.asyncio
async def test_assert_public_host_allows_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    await assert_public_host("example.com")  # no raise


@pytest.mark.asyncio
async def test_assert_public_host_dns_failure_is_400(monkeypatch):
    def boom(*a, **k):
        raise socket.gaierror("name resolution failed")
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    with pytest.raises(HTTPException) as exc:
        await assert_public_host("no-such-host.invalid")
    assert exc.value.status_code == 400


def test_validate_pdf_rejects_non_pdf():
    with pytest.raises(HTTPException):
        validate_pdf(b"not a pdf", "x.pdf")


def test_validate_pdf_rejects_oversize():
    with pytest.raises(HTTPException):
        validate_pdf(b"%PDF" + b"0" * MAX_PDF_BYTES, "x.pdf")


def test_validate_pdf_accepts_pdf():
    validate_pdf(b"%PDF-1.4 ...", "doc.pdf")  # no raise


def test_validate_document_accepts_pdf_returns_ext():
    assert validate_document(b"%PDF-1.4 ...", "doc.pdf") == "pdf"


def test_validate_document_accepts_office_by_content(office_samples):
    # Content-sniffed, so a mislabeled extension still resolves to the true format.
    assert validate_document(office_samples["report.docx"], "report.pdf") == "docx"
    assert validate_document(office_samples["costs.xlsx"], "costs.xlsx") == "xlsx"
    assert validate_document(office_samples["deck.pptx"], "deck.pptx") == "pptx"


def test_validate_document_accepts_csv_by_filename(office_samples):
    # CSV is signature-less: accepted only when the filename names it.
    assert validate_document(office_samples["data.csv"], "data.csv") == "csv"
    with pytest.raises(HTTPException):
        validate_document(office_samples["data.csv"], "data.bin")


def test_validate_document_rejects_unknown():
    with pytest.raises(HTTPException) as exc:
        validate_document(b"just some plain text", "notes.txt")
    assert exc.value.status_code == 400


def test_validate_document_rejects_oversize():
    with pytest.raises(HTTPException):
        validate_document(b"%PDF" + b"0" * MAX_PDF_BYTES, "x.pdf")


@pytest.mark.asyncio
async def test_fetch_remote_document_rejects_non_https():
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_document("http://example.com/doc.pdf")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_remote_document_rejects_unsupported_path():
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_document("https://example.com/notadoc")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_remote_document_blocks_ssrf_before_network(monkeypatch):
    # Scheme/path pass; the SSRF guard must reject before any fetch happens.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_document("https://internal.example/doc.pdf")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_fetch_remote_document_accepts_office_url(monkeypatch, office_samples):
    # A .docx URL passes the extension gate and returns the content-sniffed ext.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    docx = office_samples["report.docx"]

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            yield docx

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @asynccontextmanager
        async def stream(self, method, url):
            yield FakeStreamResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    data, filename, ext = await fetch_remote_document("https://example.com/report.docx")
    assert data == docx
    assert filename == "report.docx"
    assert ext == "docx"


@pytest.mark.asyncio
async def test_fetch_remote_document_sends_pdf_request_headers(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    seen_headers = {}

    class FakeStreamResponse:
        def raise_for_status(self):
            pass

        async def aiter_bytes(self):
            yield b"%PDF-1.4 small"

    class FakeClient:
        def __init__(self, *, headers=None, **kwargs):
            seen_headers.update(headers or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @asynccontextmanager
        async def stream(self, method, url):
            yield FakeStreamResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    data, filename, ext = await fetch_remote_document("https://example.com/doc.pdf")

    assert data == b"%PDF-1.4 small"
    assert filename == "doc.pdf"
    assert ext == "pdf"
    assert seen_headers == REMOTE_PDF_HEADERS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("upstream_status", "expected_message"),
    [
        (401, "Document URL rejected the download request (401)"),
        (403, "Document URL rejected the download request (403)"),
        (404, "Document URL was not found (404)"),
    ],
)
async def test_fetch_remote_document_maps_upstream_error_to_url_field(monkeypatch, upstream_status, expected_message):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])

    class ErrorStreamResponse:
        request = httpx.Request("GET", "https://example.com/doc.pdf")

        def raise_for_status(self):
            response = httpx.Response(upstream_status, request=self.request)
            raise httpx.HTTPStatusError("blocked", request=self.request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @asynccontextmanager
        async def stream(self, method, url):
            yield ErrorStreamResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(HTTPException) as exc:
        await fetch_remote_document("https://example.com/doc.pdf")

    assert exc.value.status_code == 422
    assert exc.value.detail == {"field": "url", "message": expected_message}


@pytest.mark.asyncio
async def test_fetch_remote_document_unmapped_status_falls_back_to_502(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])

    class ErrorStreamResponse:
        request = httpx.Request("GET", "https://example.com/doc.pdf")

        def raise_for_status(self):
            response = httpx.Response(429, request=self.request)
            raise httpx.HTTPStatusError("throttled", request=self.request, response=response)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        @asynccontextmanager
        async def stream(self, method, url):
            yield ErrorStreamResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    with pytest.raises(HTTPException) as exc:
        await fetch_remote_document("https://example.com/doc.pdf")

    assert exc.value.status_code == 502
    assert exc.value.detail == "Document URL returned HTTP 429"


@pytest.mark.asyncio
async def test_read_capped_body_clamps_to_cap():
    # A multi-chunk body over the cap is buffered to exactly MAX_PDF_BYTES+1,
    # not held whole, so validate_pdf can 400 it without memory blowup.
    class FakeRequest:
        async def stream(self):
            for _ in range(3):
                yield b"x" * (MAX_PDF_BYTES // 2)  # 1.5x the cap across chunks

    data = await read_capped_body(FakeRequest())
    assert len(data) == MAX_PDF_BYTES + 1


@pytest.mark.asyncio
async def test_read_capped_body_clamps_single_huge_chunk():
    # One chunk larger than the cap must not buffer past MAX_PDF_BYTES+1.
    class FakeRequest:
        async def stream(self):
            yield b"x" * (MAX_PDF_BYTES * 3)

    data = await read_capped_body(FakeRequest())
    assert len(data) == MAX_PDF_BYTES + 1


@pytest.mark.asyncio
async def test_read_capped_body_returns_small_body_whole():
    class FakeRequest:
        async def stream(self):
            yield b"%PDF-1.4 small"

    data = await read_capped_body(FakeRequest())
    assert data == b"%PDF-1.4 small"

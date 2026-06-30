"""Unit tests for src/services/pdf_intake.py — trust-boundary PDF intake (#228, ADR-0029)."""
from __future__ import annotations

import socket

import pytest
from fastapi import HTTPException

from src.services.pdf_intake import (
    MAX_PDF_BYTES,
    assert_public_host,
    fetch_remote_pdf,
    read_capped_body,
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


@pytest.mark.asyncio
async def test_fetch_remote_pdf_rejects_non_https():
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_pdf("http://example.com/doc.pdf")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_remote_pdf_rejects_non_pdf_path():
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_pdf("https://example.com/notapdf")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_fetch_remote_pdf_blocks_ssrf_before_network(monkeypatch):
    # Scheme/path pass; the SSRF guard must reject before any fetch happens.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))])
    with pytest.raises(HTTPException) as exc:
        await fetch_remote_pdf("https://internal.example/doc.pdf")
    assert exc.value.status_code == 422


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

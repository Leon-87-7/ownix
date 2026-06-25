"""Unit tests for src/api/parsed.py — SSRF guard + PDF validation (ADR-0029)."""
from __future__ import annotations

import socket

import pytest
from fastapi import HTTPException

from src.api.parsed import MAX_PDF_BYTES, _assert_public_host, _validate_pdf


def test_assert_public_host_rejects_loopback():
    with pytest.raises(HTTPException):
        _assert_public_host("localhost")


def test_assert_public_host_rejects_cloud_metadata(monkeypatch):
    # 169.254.169.254 is link-local — the classic SSRF metadata target.
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))])
    with pytest.raises(HTTPException):
        _assert_public_host("metadata.example")


def test_assert_public_host_allows_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    _assert_public_host("example.com")  # no raise


def test_validate_pdf_rejects_non_pdf():
    with pytest.raises(HTTPException):
        _validate_pdf(b"not a pdf", "x.pdf")


def test_validate_pdf_rejects_oversize():
    with pytest.raises(HTTPException):
        _validate_pdf(b"%PDF" + b"0" * MAX_PDF_BYTES, "x.pdf")


def test_validate_pdf_accepts_pdf():
    _validate_pdf(b"%PDF-1.4 ...", "doc.pdf")  # no raise

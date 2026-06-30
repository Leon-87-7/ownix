"""Trust-boundary PDF intake (ADR-0029, extracted from parsed.py per #228).

Everything a user-supplied PDF crosses on the way in: magic-byte/size validation,
the SSRF guard, the capped remote fetch, and the capped raw-body read. Kept in one
module so the trust-boundary logic is consolidated and directly unit-testable
(no router, no event-loop hazards). Raises HTTPException so route handlers stay thin.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request

MAX_PDF_BYTES = 20 * 1024 * 1024


def validate_pdf(data: bytes, name: str = "document.pdf") -> None:
    # Field-level 400s for malformed input (wrong type / oversized), per #217.
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail={"field": "file", "message": "PDF must be 20 MB or smaller"})
    if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail={"field": "file", "message": "Only PDF files are supported"})


async def assert_public_host(host: str | None) -> None:
    # SSRF guard: refuse hosts that resolve to non-public addresses (loopback,
    # private, link-local cloud metadata at 169.254.169.254, etc.).
    # getaddrinfo is blocking — run it off the event loop.
    if not host:
        raise HTTPException(status_code=400, detail={"field": "url", "message": "Enter a direct HTTPS PDF URL"})
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail={"field": "url", "message": "Could not resolve URL host"}) from exc
    for *_, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(status_code=422, detail={"field": "url", "message": "URL host is not allowed"})


async def fetch_remote_pdf(url: str) -> tuple[bytes, str]:
    """Validate, SSRF-check, and stream-fetch a remote PDF. Returns (data, filename)."""
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.path.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail={"field": "url", "message": "Enter a direct HTTPS PDF URL"})
    await assert_public_host(parsed.hostname)
    try:
        # follow_redirects=False: a redirect could bounce to an internal host
        # past the assert_public_host check (TOCTOU / redirect-based SSRF).
        # Stream with an early abort so a huge/slow body can't exhaust memory
        # before validate_pdf runs (httpx has no max-response-size option).
        async with httpx.AsyncClient(follow_redirects=False, timeout=20) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        raise HTTPException(status_code=422, detail={"field": "url", "message": "PDF must be 20 MB or smaller"})
                    chunks.append(chunk)
                data = b"".join(chunks)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not fetch PDF URL") from exc
    filename = parsed.path.rsplit("/", 1)[-1] or "document.pdf"
    validate_pdf(data, filename)  # magic-byte check so the function honors its "Validate" contract
    return data, filename


async def read_capped_body(request: Request) -> bytes:
    # Stream-read a raw body with a cap so a giant body can't exhaust memory
    # before validate_pdf checks the size. Clamp the boundary-crossing chunk so a
    # single huge chunk can't buffer past the cap (mirrors the multipart +1 read).
    limit = MAX_PDF_BYTES + 1
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        remaining = limit - total
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        total += min(len(chunk), remaining)
        if len(chunk) >= remaining:
            break
    return b"".join(chunks)

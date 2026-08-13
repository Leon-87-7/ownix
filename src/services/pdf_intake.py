"""Trust-boundary document intake (ADR-0029, extracted from parsed.py per #228).

Everything a user-supplied document crosses on the way in: content-sniffed format
validation, the SSRF guard, the capped remote fetch, and the capped raw-body read.
Kept in one module so the trust-boundary logic is consolidated and directly
unit-testable (no router, no event-loop hazards). Raises HTTPException so route
handlers stay thin.

Format support is content-based via `src.services.parse.detect_format` (ADR-0023
Office support): PDF stays on liteparse, DOCX/PPTX/XLSX/ODF/RTF/EPUB/CSV go through
anydoc. A client-declared Content-Type or extension is never trusted for a format
that carries a signature — only CSV (signature-less) falls back to the filename.
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request

from src.services.parse import SUPPORTED_EXTS, _ext_from_name, detect_format
from src.utils.ssrf import is_public_ip, resolve_public_host

MAX_DOC_BYTES = 20 * 1024 * 1024
REMOTE_DOCUMENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; vig/1.0; +https://github.com/Leon-87-7/vig)",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_UNSUPPORTED_FILE_MSG = (
    "Unsupported file type — upload a PDF, Word, Excel, PowerPoint, OpenDocument, RTF, EPUB, or CSV file"
)
_UNSUPPORTED_URL_MSG = (
    "Enter a direct HTTPS document URL (.pdf, .docx, .xlsx, .pptx, .odt, .rtf, .epub, .csv, …)"
)


def validate_document(data: bytes, name: str = "document") -> str:
    """Validate size + format of an uploaded document. Returns the canonical
    source extension (e.g. 'pdf', 'docx'). Raises HTTPException(400) otherwise."""
    if len(data) > MAX_DOC_BYTES:
        raise HTTPException(status_code=400, detail={"field": "file", "message": "File must be 20 MB or smaller"})
    ext = detect_format(data, name)
    if ext is None:
        raise HTTPException(status_code=400, detail={"field": "file", "message": _UNSUPPORTED_FILE_MSG})
    return ext


def validate_remote_document_url(url: str, *, require_document_path: bool = True) -> str:
    """Normalize and validate the URL shape without resolving or fetching it."""
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or (
        require_document_path and _ext_from_name(parsed.path) not in SUPPORTED_EXTS
    ):
        raise HTTPException(status_code=400, detail={"field": "url", "message": _UNSUPPORTED_URL_MSG})
    return normalized


async def assert_public_host(host: str | None) -> None:
    # SSRF guard: refuse hosts that resolve to non-public addresses (loopback,
    # private, link-local cloud metadata at 169.254.169.254, etc.).
    if not host:
        raise HTTPException(status_code=400, detail={"field": "url", "message": "Enter a direct HTTPS PDF URL"})
    infos = await resolve_public_host(host)
    if infos is None:
        raise HTTPException(status_code=400, detail={"field": "url", "message": "Could not resolve URL host"})
    if not all(is_public_ip(sockaddr[0]) for *_, sockaddr in infos):
        raise HTTPException(status_code=422, detail={"field": "url", "message": "URL host is not allowed"})


async def fetch_remote_document(url: str, *, require_document_path: bool = True) -> tuple[bytes, str, str]:
    """Validate, SSRF-check, and stream-fetch a remote document.

    Returns (data, filename, canonical_ext). The URL extension only gates *which
    links look like documents*; the returned ext comes from content sniffing the
    fetched bytes, so a mislabeled URL still stores under its true format.
    """
    url = validate_remote_document_url(url, require_document_path=require_document_path)
    parsed = urlparse(url)
    await assert_public_host(parsed.hostname)
    try:
        # follow_redirects=False: a redirect could bounce to an internal host
        # past the assert_public_host check (TOCTOU / redirect-based SSRF).
        # Stream with an early abort so a huge/slow body can't exhaust memory
        # before validate_document runs (httpx has no max-response-size option).
        async with httpx.AsyncClient(
            follow_redirects=False,
            headers=REMOTE_DOCUMENT_HEADERS,
            timeout=20,
        ) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_DOC_BYTES:
                        raise HTTPException(status_code=422, detail={"field": "url", "message": "File must be 20 MB or smaller"})
                    chunks.append(chunk)
                data = b"".join(chunks)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            raise HTTPException(
                status_code=422,
                detail={
                    "field": "url",
                    "message": f"Document URL rejected the download request ({status})",
                },
            ) from exc
        if status == 404:
            raise HTTPException(
                status_code=422,
                detail={"field": "url", "message": "Document URL was not found (404)"},
            ) from exc
        raise HTTPException(status_code=502, detail=f"Document URL returned HTTP {status}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not fetch document URL") from exc
    filename = parsed.path.rsplit("/", 1)[-1] or "document"
    ext = validate_document(data, filename)  # content sniff so the function honors its "Validate" contract
    return data, filename, ext


async def read_capped_body(request: Request) -> bytes:
    # Stream-read a raw body with a cap so a giant body can't exhaust memory
    # before validate_document checks the size. Clamp the boundary-crossing chunk
    # so a single huge chunk can't buffer past the cap (mirrors the multipart +1 read).
    limit = MAX_DOC_BYTES + 1
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

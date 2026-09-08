"""Jina Reader service — fetch a URL as clean Markdown (or HTML) via r.jina.ai."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_JINA_BASE = "https://r.jina.ai/"

# Shared cap for every Jina fetch in the newsletter-digest feature (archive,
# feed, and issue pages alike) — mirrors the 2 MB cap the email digest webhook
# enforces on inbound payloads (src/api/email_webhook.py). `fetch_raw` aborts
# the instant the running byte count exceeds this, so it never buffers a body
# larger than the cap into memory even transiently.
_MAX_JINA_BYTES = 4 * 1024 * 1024

# Preamble line prefixes that Jina prepends before the real Markdown content.
_PREAMBLE_PREFIXES = (
    "Title:",
    "URL Source:",
    "Published Time:",
    "Markdown Content:",
)


class JinaFetchError(Exception):
    """Raised when the Jina Reader API returns a non-200 status."""

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(message or f"Jina returned HTTP {status_code}")
        self.status_code = status_code


class JinaOversizeError(Exception):
    """Raised when a streamed Jina response exceeds the byte cap before completing.

    Raised as soon as the running total crosses `max_bytes` — the helper stops
    pulling further chunks the moment this happens, so the oversized body is
    never fully materialised in memory.
    """

    def __init__(self, url: str, max_bytes: int = _MAX_JINA_BYTES) -> None:
        super().__init__(f"Jina response for {url!r} exceeded {max_bytes} bytes")
        self.url = url
        self.max_bytes = max_bytes


def _strip_preamble(text: str) -> tuple[str, str]:
    """Remove Jina preamble lines and extract the title.

    Jina prepends structured lines like::

        Title: Some Title

        URL Source: https://...

        Published Time: 2026-01-01T00:00:00Z

        Markdown Content:
        # Actual article …

    Returns ``(title, body)`` where *body* is everything after the last
    preamble line (leading blank lines stripped).  If no preamble is found the
    whole text is returned as body with an empty title.
    """
    title = ""
    lines = text.splitlines()

    last_preamble_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        for prefix in _PREAMBLE_PREFIXES:
            if stripped.startswith(prefix):
                if prefix == "Title:":
                    title = stripped[len("Title:") :].strip()
                last_preamble_idx = i
                break

    if last_preamble_idx == -1:
        # No preamble at all — return as-is.
        return "", text

    # Everything after the last preamble line, skipping leading blank lines.
    body_lines = lines[last_preamble_idx + 1 :]
    # Drop leading blank lines
    while body_lines and not body_lines[0].strip():
        body_lines = body_lines[1:]

    body = "\n".join(body_lines)
    return title, body


async def fetch_raw(
    url: str,
    *,
    return_format: str | None = None,
    max_bytes: int = _MAX_JINA_BYTES,
    client: httpx.AsyncClient | None = None,
) -> tuple[int, str]:
    """Stream *url* through the Jina Reader proxy and return ``(status_code, text)``.

    This is the one shared byte-counted streaming fetch used by every Jina
    caller — archive, feed, and issue pages in the newsletter-digest feature,
    plus `fetch_markdown`'s existing plain-Markdown callers. It never reads
    the whole response before checking size: the running byte count is
    checked after every chunk, and the fetch raises :class:`JinaOversizeError`
    the moment it would exceed *max_bytes*, before the rest of the body is
    read.

    Pass ``return_format="html"`` to request ``X-Return-Format: html`` — used
    to fetch feed/archive/issue pages as rendered HTML so no XML parser is
    ever needed for RSS/Atom feeds. On a non-200 response the body is not
    read at all; the caller decides how to react to the status code.

    Callers gate the *original* URL through `is_public_url()`, but Jina does
    not re-validate its own redirect hops (known gap, no documented header to
    disable it — tracked in #615) — accepted residual risk, not something
    this function can close.
    """
    jina_url = _JINA_BASE + quote(url, safe="")
    headers: dict[str, str] = {"Accept": "text/plain"}
    if return_format:
        headers["X-Return-Format"] = return_format
    if settings.JINA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=30)
    try:
        async with active_client.stream("GET", jina_url, headers=headers) as response:
            status_code = response.status_code
            if status_code != 200:
                return status_code, ""
            total = 0
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise JinaOversizeError(url, max_bytes)
                chunks.append(chunk)
            return status_code, b"".join(chunks).decode("utf-8", errors="replace")
    finally:
        if owns_client:
            await active_client.aclose()


async def fetch_markdown(url: str, *, client: httpx.AsyncClient | None = None) -> tuple[str, str]:
    """Fetch *url* via the Jina Reader proxy and return ``(title, body)``.

    The title and body are extracted by stripping the Jina preamble block.
    Raises :class:`JinaFetchError` on any non-200 HTTP response, and
    :class:`JinaOversizeError` if the body exceeds the shared byte cap.
    """
    log.info("jina.fetch", url=url)
    status_code, text = await fetch_raw(url, client=client)

    if status_code != 200:
        log.warning("jina.fetch_error", url=url, status=status_code)
        raise JinaFetchError(status_code)

    title, body = _strip_preamble(text)
    log.info("jina.fetch_ok", url=url, title=title[:80] if title else "")
    return title, body


async def fetch_html(url: str, *, client: httpx.AsyncClient | None = None) -> str:
    """Fetch *url* via Jina Reader requesting rendered HTML (``X-Return-Format: html``).

    Shared by the newsletter archive resolver and poller for archive, feed,
    and issue pages alike — feeds are fetched through this same HTML path,
    never parsed as XML. Raises :class:`JinaFetchError` on a non-200 response
    and :class:`JinaOversizeError` if the body exceeds the shared byte cap.
    """
    log.info("jina.fetch_html", url=url)
    status_code, html = await fetch_raw(url, return_format="html", client=client)

    if status_code != 200:
        log.warning("jina.fetch_html_error", url=url, status=status_code)
        raise JinaFetchError(status_code)

    log.info("jina.fetch_html_ok", url=url, bytes=len(html))
    return html

"""Jina Reader service — fetch a URL as clean Markdown via r.jina.ai."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_JINA_BASE = "https://r.jina.ai/"

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


async def fetch_markdown(url: str) -> tuple[str, str]:
    """Fetch *url* via the Jina Reader proxy and return ``(title, body)``.

    The title and body are extracted by stripping the Jina preamble block.
    Raises :class:`JinaFetchError` on any non-200 HTTP response.
    """
    jina_url = _JINA_BASE + quote(url, safe="")
    headers: dict[str, str] = {"Accept": "text/plain"}
    if settings.JINA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"

    log.info("jina.fetch", url=url)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(jina_url, headers=headers)

    if response.status_code != 200:
        log.warning("jina.fetch_error", url=url, status=response.status_code)
        raise JinaFetchError(response.status_code)

    title, body = _strip_preamble(response.text)
    log.info("jina.fetch_ok", url=url, title=title[:80] if title else "")
    return title, body

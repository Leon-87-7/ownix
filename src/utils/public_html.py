"""Hardened public-HTML fetching for content-derived URLs."""

from __future__ import annotations

import asyncio
import ipaddress
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from src.utils.logger import get_logger

log = get_logger(__name__)

_MAX_REDIRECTS = 3
_MAX_BYTES = 128_000
_USER_AGENT = "vig-public-html/1.0 (+https://github.com/Leon-87-7/vig)"


@dataclass(frozen=True)
class PublicHtmlResult:
    """A successfully fetched HTML document and its final public URL."""

    html: str
    final_url: str


async def _is_safe_public_url(url: str) -> bool:
    """Return whether an HTTP(S) URL resolves only to public addresses."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    safe_ports = {"http": {None, 80}, "https": {None, 443}}
    if port not in safe_ports[parts.scheme]:
        return False
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, None)
        return bool(infos) and all(
            ipaddress.ip_address(info[4][0]).is_global for info in infos
        )
    except (OSError, ValueError):
        return False


async def fetch_public_html(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> PublicHtmlResult | None:
    """Fetch one public HTML page, revalidating every redirect destination."""
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(5.0),
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
    )
    try:
        target = url
        for _ in range(_MAX_REDIRECTS + 1):
            if not await _is_safe_public_url(target):
                log.info("public_html.fetch_blocked", url=target[:200])
                return None
            async with active_client.stream(
                "GET", target, follow_redirects=False
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        return PublicHtmlResult(html="", final_url=str(response.url))
                    target = urljoin(str(response.url), location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
                if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
                    log.info(
                        "public_html.content_type_rejected",
                        url=str(response.url)[:200],
                        content_type=content_type[:80],
                    )
                    return None
                chunks: list[bytes] = []
                remaining = _MAX_BYTES
                async for chunk in response.aiter_bytes():
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    remaining -= len(chunks[-1])
                markup = b"".join(chunks).decode("utf-8", errors="replace")
                return PublicHtmlResult(html=markup, final_url=str(response.url))
        return None
    except Exception as exc:
        log.info("public_html.fetch_failed", url=url, error=str(exc)[:120])
        return None
    finally:
        if owns_client:
            await active_client.aclose()

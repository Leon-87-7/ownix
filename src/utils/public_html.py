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
_MAX_IMAGE_BYTES = 5_000_000
_USER_AGENT = "vig-public-html/1.0 (+https://github.com/Leon-87-7/vig)"
_ALLOWED_IMAGE_TYPES = {"image/avif", "image/gif", "image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True)
class PublicHtmlResult:
    """A successfully fetched HTML document and its final public URL."""

    html: str
    final_url: str


@dataclass(frozen=True)
class PublicImageResult:
    """A safely fetched raster image for a same-origin preview response."""

    content: bytes
    content_type: str


async def _resolve_safe_public_url(url: str) -> tuple[str, str] | None:
    """Validate *url* and return ``(pinned_ip, hostname)`` or ``None``.

    Resolves DNS with a finite 5-second timeout so a slow/attacker-controlled
    nameserver cannot hang the caller indefinitely.  Returns the first globally-
    routable address so the caller can pin the TCP connection to that IP while
    preserving the original ``Host`` / SNI header — preventing DNS rebinding.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    safe_ports = {"http": {None, 80}, "https": {None, 443}}
    if port not in safe_ports[parts.scheme]:
        return None
    try:
        infos = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(parts.hostname, None),
            timeout=5.0,
        )
        if not infos or not all(
            ipaddress.ip_address(info[4][0]).is_global for info in infos
        ):
            return None
        return infos[0][4][0], parts.hostname
    except (OSError, ValueError, asyncio.TimeoutError):
        return None


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
            resolved = await _resolve_safe_public_url(target)
            if resolved is None:
                log.info("public_html.fetch_blocked", url=target[:200])
                return None
            pinned_ip, hostname = resolved
            # Route the TCP connection to the pinned IP so a DNS rebind after
            # our guard check cannot swap in a private address.  Preserve the
            # original hostname in Host and (for HTTPS) SNI so that the remote
            # server and TLS certificate validation use the right name.
            parts = urlsplit(target)
            pinned_url = parts._replace(netloc=pinned_ip).geturl()
            extra_headers = {"Host": hostname}
            extensions: dict = {}
            if parts.scheme == "https":
                extensions["sni_hostname"] = hostname
            async with active_client.stream(
                "GET",
                pinned_url,
                follow_redirects=False,
                headers=extra_headers,
                extensions=extensions,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        return PublicHtmlResult(html="", final_url=str(response.url))
                    target = urljoin(target, location)
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


async def fetch_public_image(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> PublicImageResult | None:
    """Fetch a public raster image, validating every redirect against SSRF.

    Browser-side direct loads are routinely rejected by OG-image hosts. This
    keeps that request same-origin without turning the endpoint into an open
    proxy: only previously resolved public URLs and a small raster MIME allowlist
    are accepted.
    """
    owns_client = client is None
    active_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(8.0),
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
    )
    try:
        target = url
        for _ in range(_MAX_REDIRECTS + 1):
            resolved = await _resolve_safe_public_url(target)
            if resolved is None:
                log.info("public_image.fetch_blocked", url=target[:200])
                return None
            pinned_ip, hostname = resolved
            parts = urlsplit(target)
            pinned_url = parts._replace(netloc=pinned_ip).geturl()
            extra_headers = {"Host": hostname}
            extensions: dict = {}
            if parts.scheme == "https":
                extensions["sni_hostname"] = hostname
            async with active_client.stream(
                "GET",
                pinned_url,
                follow_redirects=False,
                headers=extra_headers,
                extensions=extensions,
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    if not location:
                        return None
                    target = urljoin(target, location)
                    continue
                response.raise_for_status()
                content_type = (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type not in _ALLOWED_IMAGE_TYPES:
                    log.info(
                        "public_image.content_type_rejected",
                        url=str(response.url)[:200],
                        content_type=content_type[:80],
                    )
                    return None
                chunks: list[bytes] = []
                remaining = _MAX_IMAGE_BYTES
                async for chunk in response.aiter_bytes():
                    if remaining <= 0:
                        break
                    chunks.append(chunk[:remaining])
                    remaining -= len(chunks[-1])
                return PublicImageResult(content=b"".join(chunks), content_type=content_type)
        return None
    except Exception as exc:
        log.info("public_image.fetch_failed", url=url, error=str(exc)[:120])
        return None
    finally:
        if owns_client:
            await active_client.aclose()

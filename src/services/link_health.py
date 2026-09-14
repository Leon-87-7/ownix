"""Live, non-cached reachability classification for Gardener link tools."""

from __future__ import annotations

import socket
from typing import Literal, TypedDict
from urllib.parse import urljoin, urlsplit

import httpx

from src.utils.ssrf import is_public_ip, resolve_public_host

HealthStatus = Literal["reachable", "confirmed_dead", "transient_failure"]
_MAX_REDIRECTS = 5


class LinkHealth(TypedDict):
    status: HealthStatus
    http_status: int | None
    reason: str | None


def _result(
    status: HealthStatus, *, http_status: int | None = None, reason: str | None = None
) -> LinkHealth:
    return {"status": status, "http_status": http_status, "reason": reason}


def _is_dns_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, socket.gaierror):
            return True
        current = current.__cause__ or current.__context__
    return False


async def _host_is_blocked(hostname: str) -> bool:
    """True when *hostname* resolves to a private/loopback/link-local/cloud-metadata
    address (see `src.utils.ssrf`). An unresolvable hostname is *not* blocked here —
    that's a DNS failure, left for the request below to raise and classify."""
    resolved = await resolve_public_host(hostname)
    return resolved is not None and not all(is_public_ip(info[4][0]) for info in resolved)


async def check_link(url: str, *, client: httpx.AsyncClient | None = None) -> LinkHealth:
    """Check *url* now; callers deliberately do not persist or cache this signal.

    Reachable from the Gardener MCP tools — i.e. from an external agent, over
    stored, user-supplied link URLs — so every hop (initial URL and each
    redirect) is re-validated against the SSRF host guard before it's requested,
    the same way `src.telegram.routing._safe_get_pdf` re-validates manually
    followed redirects.
    """
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0), follow_redirects=False)
    try:
        target = url
        for _ in range(_MAX_REDIRECTS + 1):
            parts = urlsplit(target)
            if parts.scheme not in {"http", "https"} or not parts.hostname:
                return _result("confirmed_dead", reason="invalid_url")
            if await _host_is_blocked(parts.hostname):
                return _result("confirmed_dead", reason="blocked_host")

            response = await active_client.head(target)
            if not response.is_redirect:
                break
            location = response.headers.get("location")
            if not location:
                break
            target = urljoin(target, location)
        else:
            return _result("transient_failure", reason="too_many_redirects")

        if response.status_code == 404:
            return _result("confirmed_dead", http_status=404, reason="not_found")
        if response.status_code == 429:
            return _result("transient_failure", http_status=429, reason="rate_limited")
        if response.status_code >= 500:
            return _result(
                "transient_failure", http_status=response.status_code, reason="server_error"
            )
        return _result("reachable", http_status=response.status_code)
    except httpx.TimeoutException:
        return _result("transient_failure", reason="timeout")
    except httpx.ConnectError as exc:
        if _is_dns_failure(exc):
            return _result("confirmed_dead", reason="dns_failure")
        return _result("transient_failure", reason="connection_failure")
    except httpx.HTTPError:
        return _result("transient_failure", reason="fetch_failure")
    finally:
        if owns_client:
            await active_client.aclose()

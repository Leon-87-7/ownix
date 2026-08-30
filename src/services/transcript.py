from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def _is_local_host(hostname: str) -> bool:
    """True for loopback, private-network, and unqualified (docker/k8s service-name) hosts."""
    if not hostname:
        return False
    if hostname in _LOCAL_HOSTS or "." not in hostname:
        return True
    try:
        return ipaddress.ip_address(hostname).is_private
    except ValueError:
        return False


def _auth_headers() -> dict[str, str]:
    if not settings.TRANSCRIPT_SERVICE_TOKEN:
        return {}
    parsed = urlsplit(settings.TRANSCRIPT_SERVICE_URL)
    if parsed.scheme == "https" or _is_local_host(parsed.hostname or ""):
        return {"X-Ownix-Internal-Token": settings.TRANSCRIPT_SERVICE_TOKEN}
    log.warning("transcript_token_omitted_insecure_url", url=settings.TRANSCRIPT_SERVICE_URL)
    return {}


_TIMEOUT = httpx.Timeout(90.0)


async def fetch_transcript(url: str) -> dict:
    """GET /transcript?url=... Returns the first element of the array response."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.TRANSCRIPT_SERVICE_URL}/transcript",
            params={"url": url},
            headers=_auth_headers(),
        )
        resp.raise_for_status()
    data = resp.json()
    result = data[0] if isinstance(data, list) and data else {}
    if "error" in result:
        err = result.get("error", {})
        log.warning("transcript_error", url=url, error_type=err.get("type"), error_msg=err.get("message", "")[:200])
    else:
        log.info("transcript_fetched", url=url, fallback=result.get("fallback"))
    return result


async def fetch_metadata(url: str) -> dict:
    """GET /metadata?url=... Returns the parsed JSON dict."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.TRANSCRIPT_SERVICE_URL}/metadata",
            params={"url": url},
            headers=_auth_headers(),
        )
        resp.raise_for_status()
    data = resp.json()
    log.info("metadata_fetched", url=url, has_error="error" in data)
    return data


async def fetch_screenshot_candidates(url: str) -> dict:
    """Extract visually distinct long-video candidates in the sidecar."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
        resp = await client.post(
            f"{settings.TRANSCRIPT_SERVICE_URL}/screenshot_candidates",
            json={"url": url},
            headers=_auth_headers(),
        )
        resp.raise_for_status()
    return resp.json()

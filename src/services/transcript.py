from __future__ import annotations

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = httpx.Timeout(90.0)


async def fetch_transcript(url: str) -> dict:
    """GET /transcript?url=... Returns the first element of the array response."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.TRANSCRIPT_SERVICE_URL}/transcript",
            params={"url": url},
        )
        resp.raise_for_status()
    data = resp.json()
    result = data[0] if isinstance(data, list) and data else {}
    log.info("transcript_fetched", url=url, has_error="error" in result)
    return result


async def fetch_metadata(url: str) -> dict:
    """GET /metadata?url=... Returns the parsed JSON dict."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{settings.TRANSCRIPT_SERVICE_URL}/metadata",
            params={"url": url},
        )
        resp.raise_for_status()
    data = resp.json()
    log.info("metadata_fetched", url=url, has_error="error" in data)
    return data

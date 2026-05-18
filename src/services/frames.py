from __future__ import annotations

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_TIMEOUT = httpx.Timeout(200.0)  # sidecar needs time to download + extract frames


async def fetch_frames(url: str) -> dict:
    """GET FRAME_SERVICE_URL/short_frames. Returns the parsed JSON response dict."""
    params = {"url": url, "interval": "1.0", "max_frames": "20", "max_width": "768"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{settings.FRAME_SERVICE_URL}/short_frames", params=params)
        resp.raise_for_status()
    data = resp.json()
    log.info("frames_fetched", url=url, frame_count=data.get("frame_count", 0))
    return data

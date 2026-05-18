from __future__ import annotations

from urllib.parse import urlparse

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


async def verify_links(links: list[dict]) -> list[dict]:
    """
    Enrich up to 5 links with Brave Search title/description.
    Returns links unchanged when Brave is disabled, key is missing, or any per-link call fails.
    """
    if not settings.ENABLE_BRAVE_SEARCH or not settings.BRAVE_API_KEY:
        return links

    enriched: list[dict] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for link in links[:5]:
            try:
                query = urlparse(link["url"]).hostname or link["url"]
                resp = await client.get(
                    _BRAVE_URL,
                    params={"q": query, "count": "1"},
                    headers={"X-Subscription-Token": settings.BRAVE_API_KEY},
                )
                if resp.status_code == 200:
                    results = resp.json().get("web", {}).get("results", [])
                    if results:
                        link = {
                            **link,
                            "label": results[0].get("title") or link.get("label"),
                            "description": results[0].get("description") or link.get("description"),
                        }
            except Exception:
                log.warning("brave_link_failed", url=link.get("url"))
            enriched.append(link)

    # append any links beyond the first 5 unchanged
    enriched.extend(links[5:])
    return enriched

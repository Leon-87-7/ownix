from __future__ import annotations

import html
import re

import httpx

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str | None:
    if not text:
        return text
    return html.unescape(_TAG_RE.sub("", text)).strip() or None


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
                query = link["url"]
                resp = await client.get(
                    _BRAVE_URL,
                    params={"q": query, "count": "1"},
                    headers={"X-Subscription-Token": settings.BRAVE_API_KEY},
                )
                if resp.status_code == 200:
                    results = resp.json().get("web", {}).get("results", [])
                    if results:
                        hit = results[0]
                        link = {
                            **link,
                            "url": hit.get("url") or link["url"],
                            "label": _clean(hit.get("title")) or link.get("label"),
                            "description": _clean(hit.get("description")) or link.get("description"),
                        }
            except Exception:
                log.warning("brave_link_failed", url=link.get("url"))
            enriched.append(link)

    # append any links beyond the first 5 unchanged
    enriched.extend(links[5:])
    return enriched

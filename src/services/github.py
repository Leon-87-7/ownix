"""GitHub REST API client with Redis cache."""
from __future__ import annotations

import json

import requests

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_TTL = 86_400  # 24 hours


def _fetch_sync(owner: str, repo: str, token: str) -> dict | None:
    """Blocking HTTP call — run via asyncio.to_thread."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()
    return {
        "stars": data["stargazers_count"],
        "forks": data["forks_count"],
        "language": data.get("language"),
        "pushed_at": data.get("pushed_at"),
        "description": data.get("description"),
        "archived": data.get("archived", False),
    }


async def enrich_repo(owner: str, repo: str, token: str) -> dict | None:
    """Return GitHub metadata for owner/repo, using Redis cache (TTL 24h).

    Returns None on 404, rate-limit, or network error; never raises.
    Cache key: github_meta:{owner}/{repo}
    """
    import asyncio
    from src import queue  # lazy import — Redis client lives here

    cache_key = f"github_meta:{owner}/{repo}"
    client = queue._client()

    # Cache read
    try:
        cached = await client.get(cache_key)
        if cached:
            log.info("github_cache_hit", repo=f"{owner}/{repo}")
            return json.loads(cached)
    except Exception:
        log.warning("github_cache_read_failed", repo=f"{owner}/{repo}")

    # API call
    try:
        result = await asyncio.to_thread(_fetch_sync, owner, repo, token)
    except Exception as exc:
        log.warning("github_fetch_failed", repo=f"{owner}/{repo}", error=str(exc)[:120])
        return None

    if result is None:
        log.info("github_repo_not_found", repo=f"{owner}/{repo}")
        return None

    # Cache write
    try:
        await client.set(cache_key, json.dumps(result), ex=_TTL)
        log.info("github_cache_written", repo=f"{owner}/{repo}")
    except Exception:
        log.warning("github_cache_write_failed", repo=f"{owner}/{repo}")

    return result

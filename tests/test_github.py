"""Unit tests for src/services/github.py — no real network or Redis calls."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from src.services.github import enrich_repo, _fetch_sync


# ---------------------------------------------------------------------------
# Fake Redis — in-memory key/value store with get/set
# ---------------------------------------------------------------------------

class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_META = {
    "stars": 42,
    "forks": 7,
    "language": "Python",
    "pushed_at": "2026-05-01T12:00:00Z",
    "description": "A test repo",
    "archived": False,
}


# ---------------------------------------------------------------------------
# Test: cache hit — _fetch_sync is never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_repo_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Redis has a cached value, _fetch_sync must not be called."""
    fake_redis = FakeRedis()
    fake_redis._store["github_meta:octocat/Hello-World"] = json.dumps(_SAMPLE_META)

    import src.queue as queue_module
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    with patch("src.services.github._fetch_sync") as mock_fetch:
        result = await enrich_repo("octocat", "Hello-World", token="tok")

    mock_fetch.assert_not_called()
    assert result == _SAMPLE_META


# ---------------------------------------------------------------------------
# Test: cache miss → API success — result is cached and returned
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_repo_cache_miss_api_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """On cache miss, _fetch_sync is called, result is stored in Redis and returned."""
    fake_redis = FakeRedis()

    import src.queue as queue_module
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    with patch("src.services.github._fetch_sync", return_value=_SAMPLE_META):
        result = await enrich_repo("octocat", "Hello-World", token="tok")

    assert result is not None
    assert result["stars"] == 42
    assert result["language"] == "Python"

    # Result must have been written to Redis
    cached_raw = fake_redis._store.get("github_meta:octocat/Hello-World")
    assert cached_raw is not None
    assert json.loads(cached_raw) == _SAMPLE_META


# ---------------------------------------------------------------------------
# Test: cache miss → 404 — enrich_repo returns None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_repo_cache_miss_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _fetch_sync returns None (404), enrich_repo returns None without caching."""
    fake_redis = FakeRedis()

    import src.queue as queue_module
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    with patch("src.services.github._fetch_sync", return_value=None):
        result = await enrich_repo("ghost", "missing-repo", token="tok")

    assert result is None
    # Nothing should be cached for a 404
    assert "github_meta:ghost/missing-repo" not in fake_redis._store


# ---------------------------------------------------------------------------
# Test: cache miss → network error — enrich_repo returns None, never raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_repo_network_error_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """When _fetch_sync raises, enrich_repo must return None and not propagate."""
    fake_redis = FakeRedis()

    import src.queue as queue_module
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    with patch("src.services.github._fetch_sync", side_effect=ConnectionError("timeout")):
        result = await enrich_repo("octocat", "Hello-World", token="tok")

    assert result is None

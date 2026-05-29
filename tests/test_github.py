"""Unit tests for src/services/github.py — no real network or Redis calls."""

from __future__ import annotations

import base64
import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from src.services.github import (
    enrich_repo,
    _fetch_sync,
    preprocess_readme,
    fetch_readme,
    fetch_tree,
    fetch_manifest,
    _detect_manifests,
)


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


# ---------------------------------------------------------------------------
# preprocess_readme
# ---------------------------------------------------------------------------

def test_preprocess_readme_strips_badge_line() -> None:
    raw = "[![Build](https://img.shields.io/badge/build-ok.svg)](https://github.com/x)\nHello world"
    result = preprocess_readme(raw)
    assert "shields.io" not in result
    assert "Hello world" in result

def test_preprocess_readme_strips_details_html() -> None:
    raw = "<details><summary>More</summary>Hidden text</details>\nVisible"
    result = preprocess_readme(raw)
    assert "<details>" not in result
    assert "Visible" in result

def test_preprocess_readme_strips_img_tag() -> None:
    raw = "Some text\n<img src='logo.png' />\nMore text"
    result = preprocess_readme(raw)
    assert "<img" not in result
    assert "Some text" in result

def test_preprocess_readme_truncates_at_50000() -> None:
    assert len(preprocess_readme("x" * 60_000)) == 50_000

def test_preprocess_readme_short_text_unchanged() -> None:
    raw = "Just a simple README.\nNo HTML here."
    assert preprocess_readme(raw) == raw


# ---------------------------------------------------------------------------
# _detect_manifests
# ---------------------------------------------------------------------------

def test_detect_manifests_depth1() -> None:
    tree = ["pyproject.toml", "src/main.py", "go.mod", "Dockerfile"]
    detected = _detect_manifests(tree)
    assert "pyproject.toml" in detected
    assert "go.mod" in detected
    assert "Dockerfile" in detected
    assert "src/main.py" not in detected

def test_detect_manifests_depth2_included() -> None:
    assert "src/package.json" in _detect_manifests(["src/package.json", "README.md"])

def test_detect_manifests_depth3_excluded() -> None:
    assert "a/b/Cargo.toml" not in _detect_manifests(["a/b/Cargo.toml"])


# ---------------------------------------------------------------------------
# fetch_readme
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_readme_returns_content() -> None:
    with patch("src.services.github._readme_sync", return_value=b"# Hello World"):
        result = await fetch_readme("owner", "repo", "tok")
    assert result == "# Hello World"

@pytest.mark.asyncio
async def test_fetch_readme_returns_none_on_404() -> None:
    with patch("src.services.github._readme_sync", return_value=None):
        result = await fetch_readme("owner", "missing", "tok")
    assert result is None

@pytest.mark.asyncio
async def test_fetch_readme_returns_none_on_error() -> None:
    with patch("src.services.github._readme_sync", side_effect=ConnectionError("timeout")):
        result = await fetch_readme("owner", "repo", "tok")
    assert result is None


# ---------------------------------------------------------------------------
# fetch_tree
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_tree_returns_paths() -> None:
    paths = ["src/main.py", "README.md", "go.mod"]
    with patch("src.services.github._tree_sync", return_value=paths):
        result = await fetch_tree("owner", "repo", "main", "tok")
    assert result == paths

@pytest.mark.asyncio
async def test_fetch_tree_returns_empty_on_error() -> None:
    with patch("src.services.github._tree_sync", side_effect=RuntimeError("5xx")):
        result = await fetch_tree("owner", "repo", "main", "tok")
    assert result == []


# ---------------------------------------------------------------------------
# fetch_manifest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_manifest_returns_content() -> None:
    with patch("src.services.github._manifest_sync", return_value="[tool.poetry]"):
        result = await fetch_manifest("owner", "repo", "pyproject.toml", "tok")
    assert result == "[tool.poetry]"

@pytest.mark.asyncio
async def test_fetch_manifest_returns_none_on_404() -> None:
    with patch("src.services.github._manifest_sync", return_value=None):
        result = await fetch_manifest("owner", "repo", "Cargo.toml", "tok")
    assert result is None

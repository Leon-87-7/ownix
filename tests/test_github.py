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
    _fetch_bundle_meta_sync,
    preprocess_readme,
    fetch_readme,
    fetch_tree,
    fetch_manifest,
    _detect_manifests,
    _detect_sub_readmes,
    fetch_repo_bundle,
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
# _detect_sub_readmes (#311)
# ---------------------------------------------------------------------------

def test_detect_sub_readmes_depth2_only() -> None:
    tree = ["README.md", "okf/README.md", "okf/deep/README.md", "toolbox/readme.md", "src/main.py"]
    assert _detect_sub_readmes(tree) == ["okf/README.md", "toolbox/readme.md"]


def test_detect_sub_readmes_capped_at_4() -> None:
    tree = [f"dir{i}/README.md" for i in range(6)]
    assert len(_detect_sub_readmes(tree)) == 4


@pytest.mark.asyncio
async def test_fetch_repo_bundle_includes_sub_readmes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monorepo sub-READMEs land in bundle['sub_readmes'], truncated and preprocessed."""
    fake_redis = FakeRedis()
    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    meta = {"stars": 5, "forks": 1, "language": "Go", "pushed_at": None,
            "description": None, "archived": False, "default_branch": "main", "topics": []}

    with (
        patch("src.services.github._fetch_bundle_meta_sync", return_value=meta),
        patch("src.services.github._readme_sync", return_value=b"# Root"),
        patch("src.services.github._tree_sync", return_value=["README.md", "okf/README.md"]),
        patch("src.services.github._manifest_sync", return_value="# OKF sub-project\n" + "x" * 10_000),
    ):
        result = await fetch_repo_bundle("octocat", "monorepo", "tok")

    assert "okf/README.md" in result["sub_readmes"]
    assert len(result["sub_readmes"]["okf/README.md"]) <= 4_000


@pytest.mark.asyncio
async def test_fetch_repo_bundle_survives_optional_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient error on a sub-README (or manifest) fetch must not abort the bundle."""
    fake_redis = FakeRedis()
    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    meta = {"stars": 5, "forks": 1, "language": "Go", "pushed_at": None,
            "description": None, "archived": False, "default_branch": "main", "topics": []}

    def flaky_manifest_sync(owner, repo, path, token):
        if path == "okf/README.md":
            raise RuntimeError("503 from GitHub")
        return "module x"

    with (
        patch("src.services.github._fetch_bundle_meta_sync", return_value=meta),
        patch("src.services.github._readme_sync", return_value=b"# Root"),
        patch("src.services.github._tree_sync", return_value=["README.md", "go.mod", "okf/README.md"]),
        patch("src.services.github._manifest_sync", side_effect=flaky_manifest_sync),
    ):
        result = await fetch_repo_bundle("octocat", "monorepo", "tok")

    assert result["manifests"] == {"go.mod": "module x"}
    assert result["sub_readmes"] == {}


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


# ---------------------------------------------------------------------------
# fetch_repo_bundle
# ---------------------------------------------------------------------------

class TrackingRedis:
    """In-memory Redis double that tracks TTLs."""
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
        if ex is not None:
            self._ttls[key] = ex


_SAMPLE_BUNDLE = {
    "owner": "octocat", "repo": "Hello-World",
    "metadata": {"stars": 10, "forks": 2, "language": "Python",
                 "pushed_at": "2026-01-01T00:00:00Z", "description": "hi",
                 "archived": False},
    "default_branch": "main",
    "readme": "Hello", "readme_raw_bytes": 5,
    "tree": ["README.md"], "manifests": {}, "no_readme": False,
}


@pytest.mark.asyncio
async def test_fetch_repo_bundle_cache_hit_no_api_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache hit: bundle returned from Redis, no GitHub API calls made."""
    fake_redis = TrackingRedis()
    fake_redis._store["github_repo_bundle:v3:octocat/Hello-World"] = json.dumps(_SAMPLE_BUNDLE)

    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    with patch("src.services.github._fetch_bundle_meta_sync") as mock_meta:
        result = await fetch_repo_bundle("octocat", "Hello-World", "tok")

    mock_meta.assert_not_called()
    assert result["owner"] == "octocat"
    assert result["readme"] == "Hello"


@pytest.mark.asyncio
async def test_fetch_repo_bundle_cold_cache_written_with_7day_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cache miss: bundle assembled, written to Redis with 7-day TTL."""
    fake_redis = TrackingRedis()

    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    meta = {"stars": 5, "forks": 1, "language": "Go", "pushed_at": "2026-01-01T00:00:00Z",
            "description": None, "archived": False, "default_branch": "main"}

    with (
        patch("src.services.github._fetch_bundle_meta_sync", return_value=meta),
        patch("src.services.github._readme_sync", return_value=b"# Hello"),
        patch("src.services.github._tree_sync", return_value=["README.md", "go.mod"]),
        patch("src.services.github._manifest_sync", return_value="module x\n\ngo 1.21"),
    ):
        result = await fetch_repo_bundle("octocat", "myrepo", "tok")

    assert "go.mod" in result["manifests"]
    cached_raw = fake_redis._store.get("github_repo_bundle:v3:octocat/myrepo")
    assert cached_raw is not None
    assert fake_redis._ttls.get("github_repo_bundle:v3:octocat/myrepo") == 86_400 * 7


@pytest.mark.asyncio
async def test_fetch_repo_bundle_no_readme_sets_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """When README is 404, bundle has no_readme=True and empty readme string."""
    fake_redis = TrackingRedis()
    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    meta = {"stars": 0, "forks": 0, "language": None, "pushed_at": None,
            "description": None, "archived": False, "default_branch": "main"}

    with (
        patch("src.services.github._fetch_bundle_meta_sync", return_value=meta),
        patch("src.services.github._readme_sync", return_value=None),
        patch("src.services.github._tree_sync", return_value=[".gitignore"]),
        patch("src.services.github._manifest_sync", return_value=None),
    ):
        result = await fetch_repo_bundle("ghost", "empty-repo", "tok")

    assert result["no_readme"] is True
    assert result["readme"] == ""
    assert result["readme_raw_bytes"] == 0


@pytest.mark.asyncio
async def test_fetch_repo_bundle_404_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When metadata call returns None (404), fetch_repo_bundle raises FileNotFoundError."""
    fake_redis = TrackingRedis()
    import src.queue as q
    monkeypatch.setattr(q, "_redis", fake_redis)

    with patch("src.services.github._fetch_bundle_meta_sync", return_value=None):
        with pytest.raises(FileNotFoundError):
            await fetch_repo_bundle("ghost", "private-repo", "tok")


# ---------------------------------------------------------------------------
# Task 1 — topics field + v2 cache key (#118)
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock


def test_fetch_bundle_meta_sync_includes_topics() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "stargazers_count": 100,
        "forks_count": 10,
        "language": "Python",
        "pushed_at": "2026-01-01T00:00:00Z",
        "description": "A repo",
        "archived": False,
        "default_branch": "main",
        "topics": ["machine-learning", "nlp"],
    }

    with patch("src.services.github.requests.get", return_value=mock_resp):
        result = _fetch_bundle_meta_sync("owner", "repo", token=None)

    assert result is not None
    assert result["topics"] == ["machine-learning", "nlp"]


def test_fetch_bundle_meta_sync_topics_defaults_to_empty_list() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "stargazers_count": 5,
        "forks_count": 0,
        "language": None,
        "pushed_at": None,
        "description": None,
        "archived": False,
        "default_branch": "main",
        # no "topics" key
    }

    with patch("src.services.github.requests.get", return_value=mock_resp):
        result = _fetch_bundle_meta_sync("owner", "repo", token=None)

    assert result is not None
    assert result["topics"] == []


@pytest.mark.asyncio
async def test_fetch_repo_bundle_uses_v3_cache_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bundle pre-seeded under the v3 key must be returned as a cache hit."""
    fake_redis = FakeRedis()
    bundle_data = {
        "owner": "owner", "repo": "repo",
        "metadata": {"stars": 1, "forks": 0, "language": None,
                     "pushed_at": None, "description": None,
                     "archived": False, "topics": []},
        "default_branch": "main", "readme": "", "readme_raw_bytes": 0,
        "tree": [], "manifests": {}, "no_readme": True,
    }
    fake_redis._store["github_repo_bundle:v3:owner/repo"] = json.dumps(bundle_data)

    import src.queue as queue_module
    monkeypatch.setattr(queue_module, "_redis", fake_redis)

    with patch("src.services.github._fetch_bundle_meta_sync") as mock_meta:
        result = await fetch_repo_bundle("owner", "repo", token=None)

    mock_meta.assert_not_called()
    assert result["owner"] == "owner"

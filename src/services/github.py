"""GitHub REST API client with Redis cache."""
from __future__ import annotations

import asyncio
import base64 as _base64
import json
import re as _re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_TTL = 86_400  # 24 hours

_BADGE_LINE_RE = _re.compile(r"^\s*[\[!].*\]\(.*\)\s*$")
_INLINE_HTML_TAGS = {"details", "picture", "img", "table", "sub", "sup", "kbd", "p"}
_HTML_TAG_RE = _re.compile(
    r"</?(" + "|".join(_INLINE_HTML_TAGS) + r")(\s[^>]*)?>",
    _re.IGNORECASE,
)
_README_MAX = 50_000
_BUNDLE_TTL = 86_400 * 7  # 7 days

_MANIFEST_NAMES = frozenset([
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "pnpm-lock.yaml", "go.mod", "Cargo.toml",
    "Gemfile", "mix.exs", "composer.json", "build.gradle", "build.gradle.kts",
    "pom.xml", "Dockerfile",
])


def preprocess_readme(raw: str) -> str:
    """Strip badge lines and inline HTML tags, then truncate to _README_MAX chars."""
    lines = [line for line in raw.splitlines() if not _BADGE_LINE_RE.match(line)]
    text = _HTML_TAG_RE.sub("", "\n".join(lines))
    return text[:_README_MAX]


def _detect_manifests(tree: list[str]) -> list[str]:
    """Return paths whose filename is in _MANIFEST_NAMES and depth <= 2."""
    return [p for p in tree if len(p.split("/")) <= 2 and p.split("/")[-1] in _MANIFEST_NAMES]


_SUB_README_MAX = 4_000
_SUB_README_LIMIT = 4


def _detect_sub_readmes(tree: list[str]) -> list[str]:
    """Return `<dir>/README.md` paths one level deep (monorepo sub-projects), capped at 4."""
    paths = [p for p in tree if len(p.split("/")) == 2 and p.split("/")[-1].lower() == "readme.md"]
    return sorted(paths)[:_SUB_README_LIMIT]


def _readme_sync(owner: str, repo: str, token: str | None) -> bytes | None:
    """Blocking HTTP call — run via asyncio.to_thread. Returns None on 404."""
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _base64.b64decode(resp.json()["content"].replace("\n", ""))


def _tree_sync(owner: str, repo: str, branch: str, token: str | None) -> list[str]:
    """Blocking HTTP call — run via asyncio.to_thread. Returns list of blob paths."""
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return [item["path"] for item in resp.json().get("tree", []) if item.get("type") == "blob"]


def _manifest_sync(owner: str, repo: str, path: str, token: str | None) -> str | None:
    """Blocking HTTP call — run via asyncio.to_thread. Returns None on 404."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return _base64.b64decode(resp.json()["content"].replace("\n", "")).decode("utf-8", errors="replace")


async def fetch_readme(owner: str, repo: str, token: str) -> str | None:
    """Fetch and decode the README for owner/repo. Never raises — returns None on error."""
    try:
        raw = await asyncio.to_thread(_readme_sync, owner, repo, token)
    except Exception as exc:
        log.warning("github_readme_fetch_failed", repo=f"{owner}/{repo}", error=str(exc)[:120])
        return None
    return raw.decode("utf-8", errors="replace") if raw is not None else None


async def fetch_tree(owner: str, repo: str, branch: str, token: str) -> list[str]:
    """Fetch the recursive file tree for owner/repo@branch. Never raises — returns [] on error."""
    try:
        return await asyncio.to_thread(_tree_sync, owner, repo, branch, token)
    except Exception as exc:
        log.warning("github_tree_fetch_failed", repo=f"{owner}/{repo}", error=str(exc)[:120])
        return []


async def fetch_manifest(owner: str, repo: str, path: str, token: str) -> str | None:
    """Fetch and decode a manifest file at path. Never raises — returns None on error."""
    try:
        return await asyncio.to_thread(_manifest_sync, owner, repo, path, token)
    except Exception as exc:
        log.warning("github_manifest_fetch_failed", repo=f"{owner}/{repo}", path=path, error=str(exc)[:120])
        return None


async def fetch_repo_description(owner: str, repo: str, token: str | None) -> str | None:
    """Fetch owner/repo's GitHub description. Never raises; returns None on error."""
    try:
        meta = await asyncio.to_thread(_fetch_bundle_meta_sync, owner, repo, token or None)
    except Exception as exc:
        log.warning("github_description_fetch_failed", repo=f"{owner}/{repo}", error=str(exc)[:120])
        return None
    description = (meta or {}).get("description")
    return description.strip() if isinstance(description, str) and description.strip() else None


def _fetch_bundle_meta_sync(owner: str, repo: str, token: str | None) -> dict | None:
    """Full metadata including default_branch. Returns None on 404. Raises on 403/5xx."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {token}"} if token else {})}
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
        "default_branch": data.get("default_branch", "main"),
        "topics": data.get("topics") or [],
    }


async def fetch_repo_bundle(owner: str, repo: str, token: str | None) -> dict:
    """Assemble the full repo bundle with README, file tree, and manifests.

    Cache key: github_repo_bundle:v3:{owner}/{repo}, TTL 7 days.
    Raises FileNotFoundError on 404, requests.HTTPError on 403/5xx.
    """
    from src import queue

    cache_key = f"github_repo_bundle:v3:{owner}/{repo}"
    client = queue._client()

    try:
        cached = await client.get(cache_key)
        if cached:
            log.info("github_bundle_cache_hit", repo=f"{owner}/{repo}")
            return json.loads(cached)
    except Exception:
        log.warning("github_bundle_cache_read_failed", repo=f"{owner}/{repo}")

    meta = await asyncio.to_thread(_fetch_bundle_meta_sync, owner, repo, token)
    if meta is None:
        raise FileNotFoundError(f"{owner}/{repo} not found or private")

    default_branch = meta.pop("default_branch")

    readme_raw_bytes_obj, tree = await asyncio.gather(
        asyncio.to_thread(_readme_sync, owner, repo, token),
        asyncio.to_thread(_tree_sync, owner, repo, default_branch, token),
    )

    no_readme = readme_raw_bytes_obj is None
    readme_raw_bytes = len(readme_raw_bytes_obj) if readme_raw_bytes_obj else 0
    readme_text = readme_raw_bytes_obj.decode("utf-8", errors="replace") if readme_raw_bytes_obj else ""
    readme_preprocessed = preprocess_readme(readme_text)

    # Manifests and sub-READMEs are optional context: fetch both sets in one
    # gather, and never let a transient per-file error abort the bundle.
    manifest_paths = _detect_manifests(tree)
    sub_readme_paths = _detect_sub_readmes(tree)
    optional_paths = manifest_paths + sub_readme_paths
    optional_contents: list[str | None] = []
    if optional_paths:
        results = await asyncio.gather(
            *[asyncio.to_thread(_manifest_sync, owner, repo, path, token) for path in optional_paths],
            return_exceptions=True,
        )
        for path, res in zip(optional_paths, results, strict=True):
            if isinstance(res, BaseException):
                log.warning(
                    "github_optional_fetch_failed",
                    repo=f"{owner}/{repo}", path=path, error=str(res)[:120],
                )
        optional_contents = [r if isinstance(r, str) else None for r in results]

    manifests = {
        path: content
        for path, content in zip(manifest_paths, optional_contents[: len(manifest_paths)], strict=True)
        if content is not None
    }

    sub_readmes = {
        path: preprocess_readme(content)[:_SUB_README_MAX]
        for path, content in zip(sub_readme_paths, optional_contents[len(manifest_paths):], strict=True)
        if content is not None
    }

    bundle = {
        "owner": owner,
        "repo": repo,
        "metadata": meta,
        "default_branch": default_branch,
        "readme": readme_preprocessed,
        "readme_raw_bytes": readme_raw_bytes,
        "tree": tree,
        "manifests": manifests,
        "sub_readmes": sub_readmes,
        "no_readme": no_readme,
    }

    try:
        await client.set(cache_key, json.dumps(bundle), ex=_BUNDLE_TTL)
        log.info("github_bundle_cache_written", repo=f"{owner}/{repo}")
    except Exception:
        log.warning("github_bundle_cache_write_failed", repo=f"{owner}/{repo}")

    return bundle


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


def _parse_owner_repo(url: str) -> tuple[str, str] | None:
    segments = [s for s in urlparse(url).path.split("/") if s]
    if len(segments) >= 2:
        return segments[0], segments[1]
    return None


async def enrich_github_links(links: list[dict]) -> list[dict]:
    """Mutate links in-place with GitHub repo metadata for any github.com URLs.

    Sets ``_enriched=True`` and attaches ``_stars``, ``_forks``,
    ``_language``, ``_days_ago``, ``_gh_description`` on success;
    ``_enriched=False`` on failure (404, network error, or missing token).
    Non-GitHub links are passed through unchanged.
    """
    token = settings.GITHUB_TOKEN
    if not token:
        return links

    gh_links = [lnk for lnk in links if "github.com" in lnk.get("url", "")]
    if not gh_links:
        return links

    parsed_pairs = [_parse_owner_repo(lnk["url"]) for lnk in gh_links]
    valid_indices = [(i, pair) for i, pair in enumerate(parsed_pairs) if pair is not None]
    if valid_indices:
        coros = [enrich_repo(owner, repo, token) for _, (owner, repo) in valid_indices]
        api_results: list[dict | None] = list(await asyncio.gather(*coros, return_exceptions=False))
    else:
        api_results = []

    now = datetime.now(timezone.utc)
    result_iter = iter(api_results)

    for i, lnk in enumerate(gh_links):
        pair = parsed_pairs[i]
        if pair is None:
            lnk["_enriched"] = False
            continue
        data = next(result_iter)
        if data is None:
            lnk["_enriched"] = False
        else:
            _apply_repo_metadata(lnk, data, now)

    return links


def _apply_repo_metadata(lnk: dict, data: dict, now: datetime) -> None:
    """Attach the underscore-prefixed enrichment fields from an API result."""
    pushed_at_raw = data.get("pushed_at") or ""
    try:
        pushed = datetime.fromisoformat(pushed_at_raw.replace("Z", "+00:00"))
        days_ago = (now - pushed).days
    except Exception:
        days_ago = 0
    lnk["_enriched"] = True
    lnk["_stars"] = data.get("stars", 0)
    lnk["_forks"] = data.get("forks", 0)
    lnk["_language"] = data.get("language")
    lnk["_days_ago"] = days_ago
    lnk["_gh_description"] = data.get("description")

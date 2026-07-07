"""Offer extracted GitHub repositories as follow-up repo-analysis jobs."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from src import database, queue
from src.services.jobs import create_and_enqueue_job
from src.telegram.sender import send_inline_keyboard
from src.utils import job_tag
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline, extract_description_links, normalize_repo_url

log = get_logger(__name__)

_REPO_PICK_TTL_SECONDS = 60 * 60
_REPO_PICK_LIMIT = 5


def _candidate_name(item: dict[str, Any], normalized_url: str) -> str:
    name = str(item.get("name") or "").strip()
    if name:
        return name[:40]
    parts = [p for p in urlparse(normalized_url).path.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return normalized_url.removeprefix("https://")[:40]


def extract_repo_candidates(
    items: list[dict[str, Any]] | None, text: str | None = None
) -> list[dict[str, str]]:
    """Filter arbitrary tool/link items to normalized GitHub repo candidates.

    ``text`` (transcript / article body) is scanned for URLs Gemini's tools
    list missed; explicit items win the dedupe, so their names take priority.
    """
    merged = list(items or [])
    if text:
        merged += extract_description_links(text)
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in merged:
        url = str(item.get("url") or "").strip()
        if not url or detect_pipeline(url) != "repo":
            continue
        normalized = normalize_repo_url(url)
        key = normalized.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"url": normalized, "name": _candidate_name(item, normalized)})
        if len(candidates) >= _REPO_PICK_LIMIT:
            break
    return candidates


def _job_links(job: dict) -> list[dict[str, Any]]:
    """The job's persisted extracted-links list (JSON column or already-parsed list)."""
    raw = job.get("links")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


async def offer_repo_followups(
    job: dict, items: list[dict[str, Any]] | None, text: str | None = None
) -> list[dict[str, str]]:
    """Cache repo candidates and send a one-tap follow-up keyboard."""
    candidates = extract_repo_candidates(list(items or []) + _job_links(job), text=text)
    if not candidates:
        return []
    job_id = job["id"]
    await queue._client().set(
        f"repo_pick:{job_id}",
        json.dumps(candidates),
        ex=_REPO_PICK_TTL_SECONDS,
    )
    buttons = [
        [{"text": f"Analyze {candidate['name']}", "callback_data": f"repo_pick:{job_id}:{idx}"}]
        for idx, candidate in enumerate(candidates)
    ]
    await send_inline_keyboard(
        job["chat_id"],
        f"{job_tag(job_id)}\nFound GitHub repos — analyze one next?",
        buttons=buttons,
    )
    log.info("repo_followup.offered", job_id=job_id, count=len(candidates))
    return candidates


async def enqueue_repo_pick(source_job_id: str, idx_raw: str) -> dict[str, Any] | None:
    raw = await queue._client().get(f"repo_pick:{source_job_id}")
    if not raw:
        return None
    try:
        candidates = json.loads(raw)
        idx = int(idx_raw)
        candidate = candidates[idx]
    except (ValueError, TypeError, IndexError, KeyError, json.JSONDecodeError):
        return None
    source = await database.get_job(source_job_id)
    if not source:
        return None
    return await create_and_enqueue_job(source["chat_id"], candidate["url"], "repo")

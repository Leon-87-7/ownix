"""Repo pipeline — stub processor (phase 1 tracer bullet)."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from src import database
from src.config import settings
from src.telegram.sender import send_message
from src.utils.logger import get_logger

log = get_logger(__name__)


def _parse_owner_repo(url: str) -> tuple[str, str]:
    segments = [s for s in urlparse(url).path.split("/") if s]
    return segments[0], segments[1]


def _days_ago(pushed_at: str | None) -> int:
    if not pushed_at:
        return 0
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - pushed).days
    except Exception:
        return 0


def _format_stub_message(owner: str, repo: str, meta: dict | None) -> str:
    repo_url = f"https://github.com/{owner}/{repo}"
    if meta:
        stars = meta.get("stars", 0)
        forks = meta.get("forks", 0)
        language = meta.get("language") or "Unknown"
        days = _days_ago(meta.get("pushed_at"))
        stats = f"⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {days} days ago"
    else:
        stats = "⭐ — | 🔀 — | 💻 — | 📅 —"

    return (
        f"📦 {owner}/{repo}\n"
        f"{stats}\n"
        "\n"
        "🚧 Full analysis coming soon — this is a placeholder while the repo pipeline rolls out.\n"
        "\n"
        f"🔗 {repo_url}"
    )


async def run(job: dict) -> None:
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]

    await database.update_job_status(job_id, "processing")

    owner, repo = _parse_owner_repo(url)

    meta = None
    token = settings.GITHUB_TOKEN
    if token:
        from src.services.github import enrich_repo
        meta = await enrich_repo(owner, repo, token)

    msg = _format_stub_message(owner, repo, meta)
    await send_message(chat_id, msg)

    await database.update_job_status(job_id, "done")
    log.info("repo_stub_sent", job_id=job_id, repo=f"{owner}/{repo}")

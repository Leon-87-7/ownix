"""Shared job creation and enqueueing helpers."""

from __future__ import annotations

from typing import Any

from src import database, queue
from src.utils.logger import get_logger

log = get_logger(__name__)


def task_for_content_type(content_type: str | None, *, default: str | None) -> str | None:
    """Worker task name for a pipeline / content_type. short/long collapse to 'video'."""
    if content_type in {"short", "long"}:
        return "video"
    if content_type in {"article", "repo", "document", "link"}:
        return content_type
    return default


async def flush_held_jobs(chat_id: int) -> int:
    """Release and enqueue every held job owned by an approved chat."""
    rows = await database._fetch_dicts(
        "SELECT id, content_type FROM jobs WHERE chat_id = ? AND status = 'held' ORDER BY created_at, id",
        (chat_id,),
    )
    enqueued = 0
    for row in rows:
        job_id = row["id"]
        changed = await database._execute_rowcount(
            "UPDATE jobs SET status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND chat_id = ? AND status = 'held'",
            (job_id, chat_id),
        )
        if changed != 1:
            continue
        try:
            await queue.enqueue(
                {
                    "task": task_for_content_type(row["content_type"], default=row["content_type"]),
                    "job_id": job_id,
                }
            )
        except Exception:
            await database._execute_rowcount(
                "UPDATE jobs SET status = 'held', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND chat_id = ? AND status = 'pending'",
                (job_id, chat_id),
            )
            log.exception("held_job_enqueue_failed", chat_id=chat_id, job_id=job_id)
            continue
        enqueued += 1
    return enqueued


async def create_and_enqueue_job(
    chat_id: int,
    url: str,
    content_type: str,
    *,
    template: str | None = None,
    message_id: int | None = None,
    freestyle_prompt: str | None = None,
    skip_cache: bool = False,
) -> dict[str, Any]:
    """Create and enqueue a job, or return a recent matching job.

    The helper intentionally does not notify Telegram or HTTP callers. It owns
    the cache/dedup decision and the create+enqueue write path so all ingest
    surfaces share identical behavior.
    """
    # Explicit template/freestyle requests always run fresh — a cached
    # URL-only job would silently ignore the requested analysis. Callers
    # with template intent the arguments can't express set skip_cache.
    if not skip_cache and template is None and freestyle_prompt is None:
        cached = await database.find_recent_job_by_url(chat_id, url)
        if cached:
            log.info(
                "job_create_dedup_hit", chat_id=chat_id, job_id=cached["id"], url=url
            )
            return {**cached, "_deduped": True}

    job_id = await database.create_job(
        chat_id=chat_id,
        url=url,
        content_type=content_type,
        message_id=message_id,
        template=template,
        freestyle_prompt=freestyle_prompt,
    )
    if template:
        await database.update_job_status(
            job_id,
            "pending",
            template_detection_method="explicit_command",
        )
    await queue.enqueue(
        {"task": task_for_content_type(content_type, default=content_type), "job_id": job_id}
    )
    created = await database.get_job(job_id)
    if created is None:
        return {
            "id": job_id,
            "chat_id": chat_id,
            "url": url,
            "content_type": content_type,
            "status": "pending",
        }
    return {**created, "_deduped": False}

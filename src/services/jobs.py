"""Shared job creation and enqueueing helpers."""

from __future__ import annotations

from typing import Any

from src import database, queue
from src.utils.logger import get_logger

log = get_logger(__name__)


def task_for_content_type(content_type: str) -> str:
    if content_type in {"short", "long"}:
        return "video"
    return content_type


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
    await queue.enqueue({"task": task_for_content_type(content_type), "job_id": job_id})
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

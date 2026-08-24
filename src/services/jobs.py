"""Shared job creation and enqueueing helpers."""

from __future__ import annotations

from typing import Any

from src import database, queue
from src.intake.rate_limit import enforce as _enforce_rate_limit
from src.services import drive
from src.utils.logger import get_logger

log = get_logger(__name__)

# Shared cost-control gate (ADR-0033 chokepoint): every ingest surface
# (Telegram, dashboard API, repo follow-up) funnels through this function, so
# gating here — rather than per-surface — is the one place that bounds how
# often a single chat can drive a Gemini/GCS-costing job, including the
# Telegram URL path that had no rate limit before (unlike the upload-only
# limiter in src/intake/rate_limit.py's other caller).
_JOB_CREATE_MAX = 20
_JOB_CREATE_WINDOW_SECONDS = 60.0


def enforce_job_rate_limit(chat_id: int) -> None:
    """Rate-limit gate shared by every job-creation path (ADR-0033), including
    callers that build the job row directly instead of going through
    `create_and_enqueue_job` below.

    Raises fastapi.HTTPException(429) if chat_id has created too many jobs in
    the last minute.
    """
    _enforce_rate_limit(
        f"job_create:{chat_id}",
        max_requests=_JOB_CREATE_MAX,
        window_seconds=_JOB_CREATE_WINDOW_SECONDS,
    )


def task_for_content_type(content_type: str | None, *, default: str | None) -> str | None:
    """Worker task name for a pipeline / content_type. short/long/unsized collapse to 'video'."""
    if content_type in {"short", "long", "unsized"}:
        return "video"
    if content_type in {"article", "repo", "document", "link"}:
        return content_type
    return default


async def build_job_purge_task(job: dict[str, Any]) -> dict[str, Any]:
    """Purge-task payload for a job delete: its Drive files, GCS outputs, and Sheets row.

    Shared by the single-job delete route and full-account deletion so both
    queue identical cleanup (src/processors/purge.py).
    """
    outputs = await database.list_document_outputs(job["id"])
    return {
        "task": "job_purge",
        "job_id": job["id"],
        "chat_id": job["chat_id"],
        "drive_file_ids": [
            file_id
            for file_id in (
                drive.file_id_from_url(job.get("drive_url")),
                job.get("prd_auto_drive_file_id"),
                job.get("prd_intent_drive_file_id"),
            )
            if file_id
        ],
        "gcs_keys": [output["gcs_key"] for output in outputs if output.get("gcs_key")],
        "url": job.get("url"),
    }


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
    template_detection_method: str | None = None,
    skip_cache: bool = False,
    task: str | None = None,
    task_payload: dict[str, Any] | None = None,
    dedup_url: str | None = None,
) -> dict[str, Any]:
    """Create and enqueue a job, or return a recent matching job.

    The helper intentionally does not notify Telegram or HTTP callers. It owns
    the cache/dedup decision and the create+enqueue write path so all ingest
    surfaces share identical behavior.

    Raises fastapi.HTTPException(429) if chat_id has created too many jobs in
    the last minute — a bare Exception to non-HTTP callers (e.g. Telegram),
    so catch it explicitly for a specific reply there.
    """
    enforce_job_rate_limit(chat_id)
    # Explicit template/freestyle requests always run fresh — a cached
    # URL-only job would silently ignore the requested analysis. Callers
    # with template intent the arguments can't express set skip_cache.
    if not skip_cache and template is None and freestyle_prompt is None:
        cached = await database.find_recent_job_by_url(chat_id, dedup_url or url)
        if cached:
            log.info(
                "job_create_dedup_hit", chat_id=chat_id, job_id=cached["id"], url=url
            )
            return {**cached, "_deduped": True}

    job_id = await database.create_job(
        chat_id=chat_id,
        url=url,
        content_type=content_type,
        source_url=dedup_url,
        message_id=message_id,
        template=template,
        freestyle_prompt=freestyle_prompt,
    )
    if template or template_detection_method:
        await database.update_job_status(
            job_id,
            "pending",
            template_detection_method=template_detection_method or "explicit_command",
        )
    envelope: dict[str, Any] = {
        "task": task or task_for_content_type(content_type, default=content_type),
        "job_id": job_id,
    }
    if task_payload:
        envelope.update(task_payload)
    try:
        await queue.enqueue(envelope)
    except Exception:
        await database.update_job_status(
            job_id,
            "error",
            error_msg="Failed to enqueue job",
        )
        log.exception("job_enqueue_failed", chat_id=chat_id, job_id=job_id, task=envelope["task"])
        raise
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

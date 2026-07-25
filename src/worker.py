"""Background worker — dequeues task envelopes and dispatches to processors.

Task discriminators handled by _dispatch:
    - 'video'           → short_video.run | long_video.run (by content_type)
    - 'enrichment'      → processors.enrichment.run
    - 'article'         → processors.article.run
    - 'repo'            → processors.repo.run
    - 'document'        → processors.document.run
    - 'link'            → processors.link.run
    - 'prd_auto'        → processors.prd.run_auto
    - 'prd_auto_resend' → processors.prd.run_auto_resend
    - 'prd_intent'      → processors.prd.run_intent

On startup runs prd.reaper() + prd.reaper_intent() to release stale 'generating' PRD locks.
"""

from __future__ import annotations

import asyncio
import importlib
import time

from src import database, queue
from src.utils import job_tag
from src.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


async def _load_job_or_log(job_id: str) -> dict | None:
    job = await database.get_job(job_id)
    if not job:
        log.error("job_not_found", job_id=job_id)
    return job


async def _notify_failure(chat_id: int, job_id: str, text: str) -> None:
    """Best-effort failure message — never raises (worker must keep dequeuing)."""
    try:
        from src.telegram.sender import send_message
        await send_message(chat_id, f"{job_tag(job_id)}\n{text}")
    except Exception:
        pass


async def _handle_enrichment(task: dict) -> None:
    job_id = task["job_id"]
    job = await _load_job_or_log(job_id)
    if not job:
        return
    try:
        from src.processors import enrichment
        await enrichment.run(job_id)
    except Exception:
        log.exception("enrichment_processor_error", job_id=job_id)
        await _notify_failure(job["chat_id"], job_id, "❌ Enrichment failed. Please try again.")


async def _maybe_auto_enqueue_enrichment(job: dict, job_id: str) -> None:
    """After a long-video run with an explicit template, chain the enrichment task."""
    if job.get("template_detection_method") != "explicit_command":
        return
    refreshed = await database.get_job(job_id)
    if refreshed and refreshed.get("status") == "transcript_done":
        if refreshed.get("template") == "freestyle" and not refreshed.get("freestyle_prompt"):
            log.info("enrichment_auto_enqueue_deferred_awaiting_freestyle", job_id=job_id)
        else:
            await queue.enqueue({"task": "enrichment", "job_id": job_id})
            log.info("enrichment_auto_enqueued", job_id=job_id)


async def _handle_video(task: dict) -> None:
    job_id = task["job_id"]
    job = await _load_job_or_log(job_id)
    if not job:
        return
    try:
        if job["content_type"] == "short":
            from src.processors import short_video
            await short_video.run(job)
        elif job["content_type"] == "long":
            from src.processors import long_video
            await long_video.run(job)
            await _maybe_auto_enqueue_enrichment(job, job_id)
        else:
            log.error("unknown_content_type", job_id=job_id, content_type=job["content_type"])
    except Exception:
        log.exception("processor_error", job_id=job_id)
        await database.update_job_status(job_id, "error")
        await _notify_failure(job["chat_id"], job_id, "❌ Processing failed. Please try again.")


def _make_handler(
    module_name: str, error_event: str, error_message: str, *, pass_skip_document: bool = False
):
    """Build a task handler: load job → processor.run(job) → error status + notify on failure."""

    async def handler(task: dict) -> None:
        job_id = task["job_id"]
        job = await _load_job_or_log(job_id)
        if not job:
            return
        try:
            processor = importlib.import_module(f"src.processors.{module_name}")
            if pass_skip_document:
                await processor.run(job, skip_document=task.get("skip_document", False))
            else:
                await processor.run(job)
        except Exception:
            log.exception(error_event, job_id=job_id)
            await database.update_job_status(job_id, "error")
            await _notify_failure(job["chat_id"], job_id, error_message)

    return handler


_handle_article = _make_handler(
    "article", "article_processor_error", "❌ Article processing failed. Please try again.",
    pass_skip_document=True,
)
_handle_repo = _make_handler("repo", "repo_processor_error", "❌ Repo processing failed. Please try again.")
_handle_document = _make_handler(
    "document", "document_processor_error", "❌ Document processing failed. Please try again.",
    pass_skip_document=True,
)
_handle_link = _make_handler("link", "link_processor_error", "❌ Link pipeline failed. Please try again.")


async def _reset_prd_slot_and_notify(job_id: str, status_col: str, buttons: list) -> None:
    """Roll a crashed PRD slot back to 'error' and offer retry buttons. Never raises."""
    # status_col is interpolated into SQL — keep it pinned to known columns.
    assert status_col in {"prd_auto_status", "prd_intent_status"}
    try:
        job = await database.get_job(job_id)
        if job and job.get(status_col) == "generating":
            async with database.connection() as conn:
                await conn.execute(
                    f"UPDATE jobs SET {status_col}='error', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (job_id,),
                )
                await conn.commit()
        if job:
            from src.telegram.sender import send_inline_keyboard
            await send_inline_keyboard(
                job["chat_id"],
                "⚠️ PRD generation failed unexpectedly.",
                buttons=buttons,
            )
    except Exception:
        pass


async def _handle_prd_auto(task: dict) -> None:
    job_id = task["job_id"]
    try:
        from src.processors import prd as _prd
        await _prd.run_auto(job_id)
    except Exception:
        log.exception("prd_auto_error", job_id=job_id)
        await _reset_prd_slot_and_notify(
            job_id, "prd_auto_status",
            [[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]],
        )


async def _handle_prd_auto_resend(task: dict) -> None:
    job_id = task["job_id"]
    try:
        from src.processors import prd as _prd
        await _prd.run_auto_resend(job_id)
    except Exception:
        log.exception("prd_auto_resend_error", job_id=job_id)


async def _handle_prd_intent(task: dict) -> None:
    job_id = task["job_id"]
    try:
        from src.processors import prd as _prd
        await _prd.run_intent(job_id)
    except Exception:
        log.exception("prd_intent_error", job_id=job_id)
        await _reset_prd_slot_and_notify(
            job_id, "prd_intent_status",
            [[
                {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
                {"text": "✍️ New Intent", "callback_data": f"prd_intent_prompt:{job_id}"},
            ]],
        )


_TASK_HANDLERS = {
    "enrichment": _handle_enrichment,
    "video": _handle_video,
    "article": _handle_article,
    "repo": _handle_repo,
    "document": _handle_document,
    "link": _handle_link,
    "prd_auto": _handle_prd_auto,
    "prd_auto_resend": _handle_prd_auto_resend,
    "prd_intent": _handle_prd_intent,
}


async def _dispatch(task: dict) -> None:
    handler = _TASK_HANDLERS.get(task["task"])
    if handler is None:
        log.error("unknown_task", task=task["task"], job_id=task["job_id"])
        return
    await handler(task)


async def reap_stale_jobs() -> None:
    """Recover jobs orphaned by a crash: reset stuck 'processing'/'enriching' rows to
    'error' and notify the user per state. Run once at startup. ADR-0010.

    The worker is the only writer of 'processing' and the sequential owner of the
    dequeue loop, so any reapable row present at boot was orphaned by a prior crash.
    """
    rows = await database.fetch_and_mark_stale_jobs()
    if not rows:
        return
    log.info("jobs.reaper.released", count=len(rows))
    from src.telegram.sender import send_inline_keyboard

    for row in rows:
        chat_id = row["chat_id"]
        job_id = row["id"]
        tag = job_tag(job_id)
        try:
            if row["status"] == "enriching":
                # Transcript is already stored — offer the existing one-tap retry.
                await send_inline_keyboard(
                    chat_id,
                    f"{tag}\n⚠️ Enrichment was interrupted by a restart.",
                    buttons=[[{"text": "🔄 Retry", "callback_data": f"enrichment_retry:{job_id}"}]],
                )
            else:  # 'processing' — the Retry button re-submits the stored URL as a
                # fresh job (same as resending the link), so the orphaned row's
                # Drive file / Sheets row are never re-touched.
                await send_inline_keyboard(
                    chat_id,
                    f"{tag}\n⚠️ Processing was interrupted by a restart.",
                    buttons=[[{"text": "🔄 Retry", "callback_data": f"reprocess:{job_id}"}]],
                )
        except Exception:
            log.exception("jobs.reaper.notify_failed", job_id=job_id)


async def loop() -> None:
    log.info("worker_started")
    await database.init_db()  # idempotent — safe if api container ran it first

    from src.processors import prd as _prd
    await _prd.reaper()
    await _prd.reaper_intent()
    await reap_stale_jobs()

    while True:
        try:
            task = await queue.dequeue()
            if task is None:
                continue

            started = time.time()
            log.info("task_started", task=task["task"], job_id=task["job_id"])
            await _dispatch(task)
            elapsed_ms = int((time.time() - started) * 1000)
            log.info(
                "task_complete",
                task=task["task"],
                job_id=task["job_id"],
                duration_ms=elapsed_ms,
            )
        except asyncio.CancelledError:
            log.info("worker_cancelled")
            raise
        except Exception:
            log.exception("worker_error")
            await asyncio.sleep(2)


def main() -> None:
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        log.info("worker_shutdown")


if __name__ == "__main__":
    main()

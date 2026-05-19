"""Background worker — dequeues task envelopes and dispatches to processors.

Later slices add cases:
    - slice #4:    'enrichment' → processors.enrichment.run
    - slice #6:    'prd_auto'   → processors.prd.run_auto
    - slice #7:    'prd_intent' → processors.prd.run_intent
"""

from __future__ import annotations

import asyncio
import time

from src import database, queue
from src.utils.logger import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)


async def _dispatch(task: dict) -> None:
    task_type = task["task"]
    job_id = task["job_id"]

    if task_type == "enrichment":
        job = await database.get_job(job_id)
        if not job:
            log.error("job_not_found", job_id=job_id)
            return
        try:
            from src.processors import enrichment
            await enrichment.run(job_id)
        except Exception:
            log.exception("enrichment_processor_error", job_id=job_id)
            try:
                from src.telegram.sender import send_message
                await send_message(job["chat_id"], f"job_{job_id[-4:]}:\n❌ Enrichment failed. Please try again.")
            except Exception:
                pass
    elif task_type == "video":
        job = await database.get_job(job_id)
        if not job:
            log.error("job_not_found", job_id=job_id)
            return
        try:
            if job["content_type"] == "short":
                from src.processors import short_video
                await short_video.run(job)
            elif job["content_type"] == "long":
                from src.processors import long_video
                await long_video.run(job)
            else:
                log.error("unknown_content_type", job_id=job_id, content_type=job["content_type"])
        except Exception:
            log.exception("processor_error", job_id=job_id)
            await database.update_job_status(job_id, "error")
            try:
                from src.telegram.sender import send_message
                await send_message(job["chat_id"], f"job_{job_id[-4:]}:\n❌ Processing failed. Please try again.")
            except Exception:
                pass
    else:
        log.error("unknown_task", task=task_type, job_id=job_id)


async def loop() -> None:
    log.info("worker_started")
    await database.init_db()  # idempotent — safe if api container ran it first

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

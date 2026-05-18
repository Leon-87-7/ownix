"""Background worker — dequeues task envelopes and dispatches to processors.

Slice #1 scope: dispatch on `task["task"]`, log task_started / task_complete, no real
processing yet. Later slices add cases:
    - slice #2/#3: 'video'      → processors.short_video / long_video
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

    if task_type == "video":
        job = await database.get_job(job_id)
        if not job:
            log.error("job_not_found", job_id=job_id)
            return
        try:
            if job["content_type"] == "short":
                from src.processors import short_video
                await short_video.run(job)
            elif job["content_type"] == "long":
                # Slice #3 implements this
                log.info("long_video_stub", job_id=job_id)
            else:
                log.error("unknown_content_type", job_id=job_id, content_type=job["content_type"])
        except Exception:
            log.exception("processor_error", job_id=job_id)
            await database.update_job_status(job_id, "error")
            try:
                from src.telegram.sender import send_message
                await send_message(job["chat_id"], "❌ Processing failed. Please try again.")
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

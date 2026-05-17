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
    """Slice #1 stub: log only. Later slices replace this with real processor calls."""
    task_type = task["task"]
    job_id = task["job_id"]

    if task_type == "video":
        # Slice #2 / #3 implement the real pipelines here.
        job = await database.get_job(job_id)
        if not job:
            log.error("job_not_found", job_id=job_id)
            return
        log.info(
            "video_task_stub",
            job_id=job_id,
            content_type=job.get("content_type"),
            note="pipeline not yet implemented (slice #2 short / #3 long)",
        )
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

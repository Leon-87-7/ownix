"""On-demand long-video screenshot capture orchestration."""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime

from src import database
from src.config import settings
from src.services import drive, gemini, transcript
from src.telegram.sender import send_message
from src.utils.background_tasks import spawn_background
from src.utils.logger import get_logger
from src.utils.validators import slugify

log = get_logger(__name__)

_UPLOAD_CONCURRENCY = 4


async def trigger(job: dict) -> str:
    """Atomically claim an eligible job and launch capture. Returns an outcome token."""
    if job.get("content_type") != "long" or job.get("status") not in {"transcript_done", "done"}:
        return "ineligible"
    duration = job.get("video_duration_seconds")
    if duration is not None and duration > settings.SCREENSHOTS_MAX_DURATION_SECONDS:
        return "too_long"
    async with database.connection() as conn:
        cur = await conn.execute(
            "UPDATE jobs SET screenshots_status='generating', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND (screenshots_status IS NULL OR screenshots_status IN ('error','done'))",
            (job["id"],),
        )
        await conn.commit()
    if cur.rowcount != 1:
        return "busy"
    spawn_background(run(job))
    return "started"


async def run(job: dict) -> None:
    job_id = job["id"]
    chat_id = job["chat_id"]
    folder_id = None
    try:
        metadata = await transcript.fetch_metadata(job["url"])
        duration = metadata.get("duration")
        if duration is None:
            raise RuntimeError("Video duration is unavailable")
        await database.update_job_fields(job_id, video_duration_seconds=duration)
        if duration > settings.SCREENSHOTS_MAX_DURATION_SECONDS:
            raise ValueError("Video exceeds the screenshot duration limit")

        result = await transcript.fetch_screenshot_candidates(job["url"])
        if result.get("error"):
            raise RuntimeError(result["error"].get("message", "Frame extraction failed"))
        frames = result.get("frames", [])
        selections = await gemini.select_informative_screenshots(frames)
        valid_selections = [
            (number, selected)
            for number, selected in enumerate(selections, 1)
            if isinstance(selected.get("index"), int) and 0 <= selected["index"] < len(frames)
        ]
        if not valid_selections:
            raise RuntimeError("No informative frames were found")

        title = metadata.get("title") or job.get("title") or "untitled"
        folder_id, folder_url = await drive.create_subfolder(
            f"{job_id}_{slugify(title) or 'untitled'}",
            settings.GOOGLE_DRIVE_FOLDER_SCREENSHOTS,
            chat_id=chat_id,
        )
        if not folder_id:
            raise RuntimeError("Screenshot Drive export is unavailable")
        semaphore = asyncio.Semaphore(_UPLOAD_CONCURRENCY)

        async def _upload(number: int, selected: dict) -> None:
            async with semaphore:
                caption = slugify(selected.get("caption", ""))[:60] or "frame"
                await drive.upload_file(
                    base64.b64decode(frames[selected["index"]]["data"]),
                    f"{number:02d}_{caption}.jpg",
                    folder_id,
                    "image/jpeg",
                    chat_id=chat_id,
                )

        uploads = await asyncio.gather(
            *(_upload(number, selected) for number, selected in valid_selections),
            return_exceptions=True,
        )
        upload_failure = next((r for r in uploads if isinstance(r, Exception)), None)
        if upload_failure is not None:
            raise upload_failure
        generated_at = datetime.now(UTC).isoformat()
        await database.update_job_fields(
            job_id,
            screenshots_status="done",
            screenshots_drive_url=folder_url,
            screenshots_drive_folder_id=folder_id,
            screenshots_generated_at=generated_at,
        )
        await send_message(chat_id, f'🖼 Screenshots ready: {folder_url}')
    except Exception as exc:
        log.exception("screenshots.failed", job_id=job_id)
        fields: dict = {"screenshots_status": "error"}
        if folder_id:
            try:
                await drive.delete_file(folder_id, chat_id=chat_id)
            except Exception:
                log.exception(
                    "screenshots.folder_cleanup_failed", job_id=job_id, folder_id=folder_id
                )
                existing = await database.get_job(job_id)
                if not existing or not existing.get("screenshots_drive_folder_id"):
                    fields["screenshots_drive_folder_id"] = folder_id
        await database.update_job_fields(job_id, **fields)
        await send_message(chat_id, f"⚠️ Screenshot capture failed: {exc}")

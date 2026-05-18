from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from src import database
from src.config import settings
from src.services import brave, frames, gemini, sheets
from src.services.drive import upload_file
from src.telegram.sender import send_message, send_photo
from src.utils.logger import get_logger

log = get_logger(__name__)


def _build_analysis_markdown(job: dict, platform: str, video_id: str, summary: str, links: list[dict]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    parts = [
        f"# Short Video Analysis\n",
        f"**Source:** {job['url']}",
        f"**Platform:** {platform}",
        f"**Video ID:** {video_id}",
        f"**Processed:** {ts}",
        f"**Job ID:** {job['id']}",
        "",
        "---",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]
    if links:
        parts.append("## Extracted Links\n")
        for lnk in links:
            label = lnk.get("label") or lnk.get("url")
            desc = lnk.get("description", "")
            parts.append(f"### {label}")
            if desc:
                parts.append(desc)
            parts.append(f"🔗 {lnk['url']}\n")
    return "\n".join(parts)


def _build_links_message(links: list[dict]) -> str:
    labeled = "\n".join(
        f"• {lnk.get('label') or lnk['url']} — {lnk.get('description') or ''}\n  🔗 {lnk['url']}"
        for lnk in links
    )
    bare = "\n".join(lnk["url"] for lnk in links)
    return f"🔗 Links Found:\n{labeled}\n\n---\n\n🔗 Quick Links:\n{bare}"


async def run(job: dict) -> None:
    """End-to-end short-video pipeline."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    started = time.time()

    await database.update_job_status(job_id, "processing")
    await send_message(chat_id, "🔊 Processing your short video...")

    # 1. Fetch frames from sidecar
    frame_resp = await frames.fetch_frames(url)
    if "error" in frame_resp:
        err = frame_resp["error"]
        if err.get("type") == "too_long":
            await send_message(chat_id, "❌ Video too long for short pipeline (max 3 minutes).")
        else:
            await send_message(chat_id, f"❌ Frame extraction failed: {err.get('message', 'unknown error')}")
        raise RuntimeError(f"frame_service_error: {err}")

    raw_frames = frame_resp.get("frames", [])
    platform = frame_resp.get("platform", "unknown")
    video_id = frame_resp.get("video_id", "")
    title = frame_resp.get("title", "")

    if not raw_frames:
        await send_message(chat_id, "❌ No frames extracted from video.")
        raise RuntimeError("no_frames_extracted")

    # 2. Gemini Vision analysis
    vision = await gemini.call_gemini_vision(
        raw_frames,
        free_key=settings.GEMINI_FREE_API_KEY,
        paid_key=settings.GEMINI_PAID_API_KEY,
    )
    main_idx = max(0, min(vision.get("main_frame_index", 0), len(raw_frames) - 1))
    summary = vision.get("summary", "")
    links: list[dict] = vision.get("links", [])

    # 3. Brave Search enrichment (opt-in)
    if links:
        links = await brave.verify_links(links)

    # 4. Upload analysis markdown to Drive
    md_content = _build_analysis_markdown(job, platform, video_id, summary, links)
    file_id, drive_url = await upload_file(md_content, f"{job_id}_short.md", settings.GOOGLE_DRIVE_FOLDER_SHORT)

    # 5. Update job status
    elapsed_ms = int((time.time() - started) * 1000)
    await database.update_job_status(
        job_id, "complete",
        drive_url=drive_url,
        title=title,
        processing_time_ms=elapsed_ms,
    )

    # 6. Send best frame photo
    import base64
    best_frame_b64 = raw_frames[main_idx]["base64"]
    best_frame_bytes = base64.b64decode(best_frame_b64)
    await send_photo(chat_id, best_frame_bytes, caption=f"🖼️Main frame: {summary}")

    # 7. Send links message (if any)
    if links:
        await send_message(chat_id, _build_links_message(links))

    # 8. Sheets logging (fire-and-forget)
    refreshed = await database.get_job(job_id) or job
    asyncio.create_task(sheets.append_short_row({**refreshed, "platform": platform}))

    log.info("short_video_complete", job_id=job_id, duration_ms=elapsed_ms)

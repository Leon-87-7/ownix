from __future__ import annotations

import asyncio

from src import database
from src.config import settings
from src.services.drive import upload_file
from src.services import sheets, transcript as transcript_svc
from src.telegram.sender import send_document, send_inline_keyboard, send_message
from src.utils.logger import get_logger
from src.utils.markdown import build_transcript_markdown
from src.utils.validators import extract_description_links, slugify

log = get_logger(__name__)


async def run(job: dict) -> None:
    """End-to-end long-video Phase 1 pipeline."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]

    await database.update_job_status(job_id, "processing")
    await send_message(chat_id, "🔊 Analyzing your video, It is on it's way 🪽🪽")

    # 1. Fetch transcript + metadata in parallel
    transcript_resp, meta_resp = await asyncio.gather(
        transcript_svc.fetch_transcript(url),
        transcript_svc.fetch_metadata(url),
    )

    video_id = transcript_resp.get("videoId", "")
    transcript = transcript_resp.get("text", "")
    if "error" in transcript_resp:
        log.warning("transcript_error", job_id=job_id, error=transcript_resp["error"])
        transcript = ""

    title = meta_resp.get("title", "") or "Untitled"
    channel = meta_resp.get("channel", "")
    views = meta_resp.get("views", "")
    description = meta_resp.get("description", "")

    # 2. Extract description links (failure must not block the pipeline)
    try:
        description_links = extract_description_links(description)
    except Exception:
        log.exception("description_link_extraction_failed", job_id=job_id)
        description_links = []

    description_links_raw = "\n".join(lnk["url"] for lnk in description_links)

    # 3. Build transcript markdown and upload to Drive
    slug = slugify(title) or "untitled"
    md_text = build_transcript_markdown(title, channel, views, video_id, url, transcript)

    await send_message(chat_id, "🍪 video is in-progress. Transcript done, now sent to Drive")

    file_id, drive_url = await upload_file(md_text, f"{slug}.md", settings.GOOGLE_DRIVE_FOLDER_LONG)

    # 4. Update job to transcript_done, caching title + transcript for Phase 2
    await database.update_job_status(
        job_id, "transcript_done",
        drive_url=drive_url,
        title=title,
        transcript=transcript,
    )

    # 5. Telegram delivery sequence
    await send_document(chat_id, md_text.encode(), filename=f"{slug}.md", caption="📜 The transcript is here")
    await send_message(chat_id, "✅ Transcript saved to Drive!")
    await send_inline_keyboard(
        chat_id,
        "Run Gemini analysis on this video?",
        buttons=[
            [
                {"text": "👎 No Thanks", "callback_data": f"gemini_no:{job_id}"},
                {"text": "✨ Run Gemini", "callback_data": f"gemini_yes:{job_id}"},
            ],
            [
                {"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"},
            ],
        ],
    )

    # 6. Sheets logging (fire-and-forget)
    refreshed = await database.get_job(job_id) or job
    asyncio.create_task(
        sheets.append_long_row(
            refreshed,
            video_id=video_id,
            channel=channel,
            views=views,
            description_links_raw=description_links_raw,
            char_count=len(transcript),
            drive_file_id=file_id,
        )
    )

    log.info("long_video_phase1_complete", job_id=job_id)

from __future__ import annotations

import asyncio
from src import database
from src.config import settings
from src.services.drive import upload_file
from src.services import sheets, transcript as transcript_svc
from src.telegram.sender import edit_message_text, send_document, send_inline_keyboard, send_message
from src.templates import PROMPT_TEMPLATES
from src.utils.logger import get_logger
from src.services.github import enrich_github_links
from src.utils.markdown import build_enriched_links_message, build_transcript_markdown
from src.utils import job_tag
from src.utils.validators import extract_description_links, slugify

log = get_logger(__name__)


def detect_template(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    scores = {
        name: sum(1 for p in tmpl.trigger_patterns if p in text)
        for name, tmpl in PROMPT_TEMPLATES.items()
        if name != "summary"
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "summary"


async def _fetch_transcript_or_fail(
    job_id: str, chat_id: int, tag: str, url: str
) -> tuple[dict, dict] | None:
    """Fetch transcript + metadata; mark error and notify when no transcript exists."""
    transcript_resp, meta_resp = await asyncio.gather(
        transcript_svc.fetch_transcript(url),
        transcript_svc.fetch_metadata(url),
    )

    transcript = transcript_resp.get("text", "")
    if "error" in transcript_resp:
        log.warning("transcript_error", job_id=job_id, error=transcript_resp["error"])
        transcript = ""
        transcript_resp = {**transcript_resp, "text": ""}

    if not transcript.strip():
        await database.update_job_status(job_id, "error", error_msg="transcript_empty")
        await send_message(
            chat_id,
            f"{tag}\n⚠️ No transcript available for this video — it may have auto-captions disabled or be too new. Try again later or use /force &lt;url&gt;.",
            parse_mode="HTML",
        )
        return None
    return transcript_resp, meta_resp


async def _collect_description_links(description: str, job_id: str) -> list[dict]:
    """Extract + enrich description links (failure must not block the pipeline)."""
    try:
        description_links = extract_description_links(description)
    except Exception:
        log.exception("description_link_extraction_failed", job_id=job_id)
        description_links = []

    if description_links:
        description_links = await enrich_github_links(description_links)
    return description_links


async def run(job: dict) -> None:
    """End-to-end long-video Phase 1 pipeline."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]

    tag = job_tag(job_id)

    await database.update_job_status(job_id, "processing")
    status_result = await send_message(chat_id, f"{tag}\n🔊 Analyzing your video, It is on it's way 🪽🪽")
    status_msg_id: int | None = status_result.get("message_id")

    # 1. Fetch transcript + metadata in parallel
    fetched = await _fetch_transcript_or_fail(job_id, chat_id, tag, url)
    if fetched is None:
        return
    transcript_resp, meta_resp = fetched
    video_id = transcript_resp.get("videoId", "")
    transcript = transcript_resp.get("text", "")

    title = meta_resp.get("title", "") or "Untitled"
    channel = meta_resp.get("channel", "")
    views = meta_resp.get("views", "")
    description = meta_resp.get("description", "")

    # 2. Auto-detect template (plain URL jobs only)
    if not job.get("template"):
        detected = detect_template(title, description)
        await database.update_job_status(
            job_id, "processing",
            template=detected,
            template_detection_method="metadata",
        )

    # 3. Extract description links (failure must not block the pipeline)
    description_links = await _collect_description_links(description, job_id)
    description_links_raw = "\n".join(lnk["url"] for lnk in description_links)

    # 4. Build transcript markdown and upload to Drive
    slug = slugify(title) or "untitled"
    md_text = build_transcript_markdown(title, channel, views, video_id, url, transcript)

    if status_msg_id:
        await edit_message_text(chat_id, status_msg_id, f"{tag}\n🍪 video is in-progress. Transcript done, now sent to Drive")
    else:
        await send_message(chat_id, f"{tag}\n🍪 video is in-progress. Transcript done, now sent to Drive")

    file_id, drive_url = await upload_file(md_text, f"{slug}.md", settings.GOOGLE_DRIVE_FOLDER_LONG, chat_id=chat_id)

    # 5. Update job to transcript_done, caching title + transcript for Phase 2
    await database.update_job_status(
        job_id, "transcript_done",
        drive_url=drive_url,
        title=title,
        transcript=transcript,
    )

    # 6. Telegram delivery sequence
    doc_caption = f"{tag}\n📜 Transcript ready"
    if drive_url:
        doc_caption += f'\n📄 <a href="{drive_url}">Open in Drive</a>'
    doc_result = await send_document(chat_id, md_text.encode(), filename=f"{slug}.md", caption=doc_caption, parse_mode="HTML")
    bot_message_id = doc_result.get("message_id")
    if bot_message_id:
        await database.update_job_status(job_id, "transcript_done", bot_message_id=bot_message_id)
    if job.get("template_detection_method") != "explicit_command":
        await send_inline_keyboard(
            chat_id,
            f"{tag}\nRun Gemini analysis on this video?",
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

    if description_links:
        await send_message(chat_id, f"{tag}\n{build_enriched_links_message(description_links)}")

    # 7. Sheets logging (fire-and-forget)
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

    if description_links and settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain
        asyncio.create_task(brain.ingest_links(description_links, topic=title, source_job_id=job_id))

    log.info("long_video_phase1_complete", job_id=job_id)

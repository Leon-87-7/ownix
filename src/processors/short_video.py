from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone

from src import database
from src.analysis import extract_key_phrases
from src.config import settings
from src.services import brave, frames, gemini, sheets
from src.services import transcript as transcript_svc
from src.services.drive import upload_file
from src.telegram.sender import send_message, send_photo
from src.utils.logger import get_logger
from src.utils.markdown import build_enriched_links_message

log = get_logger(__name__)


def _build_analysis_markdown(
    job: dict, platform: str, video_id: str, summary: str, links: list[dict]
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    parts = [
        "# Short Video Analysis\n",
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


def _tag(job_id: str) -> str:
    return f"job_{job_id[-4:]}:"


async def run(job: dict) -> None:
    """End-to-end short-video pipeline."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    started = time.time()
    tag = _tag(job_id)

    await database.update_job_status(job_id, "processing")
    await send_message(chat_id, f"{tag}\n🔊 Processing your short video...")

    # 1. Fetch frames from sidecar
    frame_resp = await frames.fetch_frames(url)
    if "error" in frame_resp:
        err = frame_resp["error"]
        if err.get("type") == "too_long":
            await send_message(
                chat_id, f"{tag}\n❌ Video too long for short pipeline (max 3 minutes)."
            )
        else:
            await send_message(
                chat_id, f"{tag}\n❌ Frame extraction failed: {err.get('message', 'unknown error')}"
            )
        raise RuntimeError(f"frame_service_error: {err}")

    raw_frames = frame_resp.get("frames", [])
    platform = frame_resp.get("platform", "unknown")
    video_id = frame_resp.get("video_id", "")
    title = frame_resp.get("title", "")

    if not raw_frames:
        await send_message(chat_id, f"{tag}\n❌ No frames extracted from video.")
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
    file_id, drive_url = await upload_file(
        md_content, f"{job_id}_short.md", settings.GOOGLE_DRIVE_FOLDER_SHORT
    )

    # 5. Update job status
    elapsed_ms = int((time.time() - started) * 1000)
    await database.update_job_status(
        job_id,
        "done",
        drive_url=drive_url,
        title=title,
        processing_time_ms=elapsed_ms,
    )

    # 6. Send best frame photo
    import base64

    best_frame_b64 = raw_frames[main_idx]["base64"]
    best_frame_bytes = base64.b64decode(best_frame_b64)
    await send_photo(chat_id, best_frame_bytes, caption=f"{tag}\n🖼️ Main frame: {summary}")

    # 7. Send links message (if any)
    if links:
        await send_message(chat_id, f"{tag}\n{build_enriched_links_message(links)}")

    # 8. Sheets logging (fire-and-forget)
    refreshed = await database.get_job(job_id) or job
    asyncio.create_task(
        sheets.append_short_row(
            {
                **refreshed,
                "platform": platform,
                "duration_s": frame_resp.get("duration", ""),
                "frame_count": len(raw_frames),
                "best_frame_index": main_idx,
                "tools_message": summary,
                "links": links,
                "tools_count": len(links),
            }
        )
    )

    if links and settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain

        asyncio.create_task(
            brain.ingest_links(links, topic=vision.get("summary", ""), source_job_id=job_id)
        )

    log.info("short_video_complete", job_id=job_id, duration_ms=elapsed_ms)

    # Template path — explicit slash command only; plain URL jobs exit above
    template = job.get("template")
    if not template:
        return

    try:
        transcript_resp = await transcript_svc.fetch_transcript(url)
    except Exception:
        await send_message(
            chat_id,
            f"{tag}\nNo transcript available — template analysis skipped.",
        )
        return

    from src.processors import enrichment as enrichment_proc

    # Caption-less path (issue #32): transcript service returns audio bytes instead of
    # text. One Gemini call transcribes + analyzes the audio; no transcript is stored.
    if transcript_resp.get("fallback") == "audio":
        audio_b64 = transcript_resp.get("audio_b64", "")
        mime_type = transcript_resp.get("mime_type", "audio/mp4")
        if not audio_b64:
            await send_message(
                chat_id,
                f"{tag}\nNo transcript available — template analysis skipped.",
            )
            return
        try:
            template_analysis = await enrichment_proc.enrich_audio(job, audio_b64, mime_type)
        except enrichment_proc.EnrichmentUnavailableError:
            await send_message(chat_id, f"{tag}\n⚠️ Template analysis failed — Gemini unavailable.")
            return
        if template_analysis:
            section = enrichment_proc._format_template_analysis(template, template_analysis)
            await send_message(chat_id, f"{tag}{section}")
        return

    # Caption-based path (unchanged)
    short_transcript = transcript_resp.get("text", "")
    if not short_transcript:
        await send_message(
            chat_id,
            f"{tag}\nNo transcript available — template analysis skipped.",
        )
        return

    key_phrases = extract_key_phrases(short_transcript, max_phrases=8)
    await database.update_job_status(
        job_id, "done",
        transcript=short_transcript,
        key_phrases=json.dumps(key_phrases),
    )
    enriched_job = await database.get_job(job_id)
    if not enriched_job:
        return

    try:
        enrichment_result, template_analysis = await enrichment_proc.enrich(enriched_job)
    except enrichment_proc.EnrichmentUnavailableError as exc:
        await send_message(chat_id, f"{tag}\n⚠️ Template analysis failed\nerror: {exc}\njob_title: {title}")
        return

    if template_analysis:
        section = enrichment_proc._format_template_analysis(template, template_analysis)
        await send_message(chat_id, f"{tag}{section}")
        await database.update_job_status(
            job_id, "done",
            template_analysis=json.dumps(template_analysis),
        )

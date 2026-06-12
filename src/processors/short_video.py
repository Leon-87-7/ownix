from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone

from src import database
from src.analysis import extract_key_phrases
from src.config import settings
from src.processors import enrichment as enrichment_proc
from src.services import brave, frames, gemini, sheets
from src.services import transcript as transcript_svc
from src.services.drive import upload_file
from src.services.github import enrich_github_links
from src.telegram.sender import edit_message_text, send_document, send_message, send_photo
from src.utils.logger import get_logger
from src.utils.markdown import build_enriched_links_message
from src.utils.validators import filter_vision_links

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


def _build_transcript_markdown(
    job: dict, platform: str, video_id: str, transcript: str
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return "\n".join([
        "# Transcript",
        "",
        f"**Source:** {job['url']}",
        f"**Platform:** {platform}",
        f"**Video ID:** {video_id}",
        f"**Processed:** {ts}",
        f"**Job ID:** {job['id']}",
        "",
        "---",
        "",
        transcript,
    ])


def _tag(job_id: str) -> str:
    return f"job_{job_id[-4:]}:"


async def _acquire_transcript(
    job: dict,
    url: str,
    chat_id: int,
    tag: str,
    title: str,
    template: str | None,
) -> tuple[str | None, dict | None, bool]:
    transcript_text: str | None = None
    template_analysis: dict | None = None
    wordless = False
    try:
        transcript_resp = await transcript_svc.fetch_transcript(url)
        if "error" in transcript_resp:
            err_val = transcript_resp["error"]
            err_msg = err_val.get("message", "unknown") if isinstance(err_val, dict) else str(err_val)
            await send_message(chat_id, f"{tag}\n⚠️ Transcript service error: {err_msg}")
        elif transcript_resp.get("fallback") == "audio":
            audio_b64 = transcript_resp.get("audio_b64", "")
            mime_audio = transcript_resp.get("mime_type", "audio/mp4")
            if audio_b64:
                if template:
                    template_analysis, transcript_text = await enrichment_proc.enrich_audio(
                        job, audio_b64, mime_audio
                    )
                else:
                    transcript_text = await enrichment_proc.transcribe_audio(
                        audio_b64, mime_audio, title
                    )
                    if not transcript_text:
                        wordless = True
            else:
                wordless = True
        else:
            raw_text = transcript_resp.get("text", "").strip()
            if raw_text:
                transcript_text = raw_text
            else:
                wordless = True
    except enrichment_proc.EnrichmentUnavailableError:
        await send_message(chat_id, f"{tag}\n⚠️ Transcription failed — Gemini unavailable")
    except Exception as exc:
        await send_message(chat_id, f"{tag}\n⚠️ Transcript service error: {exc}")
    return transcript_text, template_analysis, wordless


async def _fetch_validated_frames(url: str, chat_id: int, tag: str) -> dict:
    """Fetch frames from the sidecar; message the user and raise on failure."""
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
    if not frame_resp.get("frames"):
        await send_message(chat_id, f"{tag}\n❌ No frames extracted from video.")
        raise RuntimeError("no_frames_extracted")
    return frame_resp


async def _deliver_media(
    chat_id: int, tag: str, raw_frames: list, main_idx: int, summary: str, links: list[dict]
) -> tuple[int | None, list[dict]]:
    """Send best frame + links message; return (anchor message_id, enriched links)."""
    import base64

    best_frame_bytes = base64.b64decode(raw_frames[main_idx]["base64"])
    photo_result = await send_photo(chat_id, best_frame_bytes, caption=f"{tag}\n🖼️ Main frame: {summary}")
    bot_message_id: int | None = photo_result.get("message_id")

    if links:
        links = await enrich_github_links(links)
        links_result = await send_message(chat_id, f"{tag}\n{build_enriched_links_message(links)}")
        bot_message_id = links_result.get("message_id", bot_message_id)
    return bot_message_id, links


async def run(job: dict) -> None:
    """End-to-end short-video pipeline."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    started = time.time()
    tag = _tag(job_id)

    await database.update_job_status(job_id, "processing")
    status_result = await send_message(chat_id, f"{tag}\n🔊 Processing your short video...")
    status_msg_id: int | None = status_result.get("message_id")

    # 1. Fetch frames from sidecar
    frame_resp = await _fetch_validated_frames(url, chat_id, tag)
    raw_frames = frame_resp.get("frames", [])
    platform = frame_resp.get("platform", "unknown")
    video_id = frame_resp.get("video_id", "")
    title = frame_resp.get("title", "")

    # 2. Gemini Vision analysis
    vision = await gemini.call_gemini_vision(raw_frames)
    main_idx = max(0, min(vision.get("main_frame_index", 0), len(raw_frames) - 1))
    summary = vision.get("summary", "")
    ignored = await database.get_ignored_domains(chat_id)
    links: list[dict] = filter_vision_links(vision.get("links", []), extra_ignored=ignored)

    # 3. Brave Search enrichment (opt-in)
    if links:
        links = await brave.verify_links(links)

    if status_msg_id:
        await edit_message_text(chat_id, status_msg_id, f"{tag}\n🍪 Analysis done, uploading to Drive...")
    else:
        await send_message(chat_id, f"{tag}\n🍪 Analysis done, uploading to Drive...")

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

    # 6+7. Send best frame photo, then links message (its message_id wins as anchor)
    bot_message_id, links = await _deliver_media(chat_id, tag, raw_frames, main_idx, summary, links)

    if bot_message_id:
        await database.update_job_status(job_id, "done", bot_message_id=bot_message_id)

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

    # -------------------------------------------------------------------------
    # Phase 2 (ADR-0020): Transcript acquisition — always, regardless of template
    # -------------------------------------------------------------------------
    await _transcript_phase(job, url, chat_id, tag, title, platform, video_id)


async def _run_template_enrichment(
    job_id: str, chat_id: int, tag: str, title: str,
    template: str | None, template_analysis, transcript_text: str | None,
) -> object:
    """Caption-path template enrichment + delivery (audio path enriched earlier)."""
    if template and template_analysis is None and transcript_text:
        enriched_job = await database.get_job(job_id)
        if enriched_job:
            try:
                _, template_analysis, _ = await enrichment_proc.enrich(enriched_job)
            except enrichment_proc.EnrichmentUnavailableError as exc:
                await send_message(
                    chat_id, f"{tag}\n⚠️ Template analysis failed\nerror: {exc}\njob_title: {title}"
                )

    if template and template_analysis:
        try:
            section = enrichment_proc._format_template_analysis(template, template_analysis)
            await send_message(chat_id, f"{tag}{section}")
        except Exception as exc:
            log.warning("template_analysis_send_failed", error=str(exc))
        await database.update_job_status(
            job_id, "done",
            template_analysis=json.dumps(template_analysis),
        )
    return template_analysis


async def _deliver_transcript_doc(
    job: dict, job_id: str, chat_id: int, platform: str, video_id: str, transcript_text: str
) -> None:
    """Drive upload + Telegram document — always last, always after enrichment."""
    transcript_md = _build_transcript_markdown(job, platform, video_id, transcript_text)
    try:
        await upload_file(
            transcript_md, f"{job_id}_transcript.md", settings.GOOGLE_DRIVE_FOLDER_SHORT
        )
    except Exception as exc:
        log.warning("transcript_drive_upload_failed", error=str(exc))
    try:
        await send_document(
            chat_id,
            transcript_md.encode("utf-8"),
            f"{job_id}_transcript.md",
        )
    except Exception as exc:
        log.warning("transcript_send_document_failed", error=str(exc))


async def _transcript_phase(
    job: dict, url: str, chat_id: int, tag: str, title: str, platform: str, video_id: str
) -> None:
    """Acquire transcript, persist it, run template enrichment, deliver the .md doc."""
    job_id = job["id"]
    template = job.get("template")
    transcript_text, template_analysis, wordless = await _acquire_transcript(
        job, url, chat_id, tag, title, template
    )

    if wordless:
        await send_message(chat_id, f"{tag}\n⚠️ I'm wordless")

    # Persist transcript + key_phrases immediately on acquisition
    if transcript_text:
        key_phrases = extract_key_phrases(transcript_text, max_phrases=8)
        await database.update_job_status(
            job_id, "done",
            transcript=transcript_text,
            key_phrases=json.dumps(key_phrases),
        )

    await _run_template_enrichment(
        job_id, chat_id, tag, title, template, template_analysis, transcript_text
    )

    if transcript_text:
        await _deliver_transcript_doc(job, job_id, chat_id, platform, video_id, transcript_text)

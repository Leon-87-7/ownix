"""File-shaped intake routing (issue #475).

PDF bytes reuse the exact same document-job creation path as the Doc Parser
dashboard upload (`src/api/parsed.py`'s `_create_document_job` — validate,
hash, GCS upload, create the `document` job, queue it) rather than forking a
second copy of that logic. Image bytes reuse the existing inline photo-OCR
core (`call_gemini_photo_links`) — ADR-0003 keeps photo processing inline,
never queued, and this endpoint already has raw bytes, so there is no
Telegram `file_id` download left to route around.

Content-type sniffing and size/quota enforcement happen in `src/api/intake.py`
*before* an `IntakeMessage` is even built — this module only routes an
already-validated file.
"""

from __future__ import annotations

from src.intake import responses
from src.intake.models import IntakeFile, IntakeMessage, IntakeResponse
from src.services import parse
from src.utils.logger import get_logger

log = get_logger(__name__)


async def handle_files(msg: IntakeMessage) -> IntakeResponse:
    chat_id = msg.actor.legacy_chat_id
    if chat_id is None:
        return responses.error("No owner resolved for this upload.", retryable=False)
    if len(msg.files) != 1:
        return responses.rejected("Upload exactly one file per submit.")
    file = msg.files[0]

    if file.content_type.startswith("image/"):
        return await _handle_image(chat_id, file)
    if file.content_type == "text/x-bookmarks":
        return await _handle_bookmarks(chat_id, file)
    # PDF + every anydoc-supported office/document format (content-detected, so a
    # mislabeled Content-Type still routes right — see parse.detect_format).
    if parse.detect_format(file.data, file.filename) is not None:
        return await _handle_document(chat_id, file)
    return responses.rejected(f"Unsupported file type: {file.content_type}")


async def _handle_document(chat_id: int, file: IntakeFile) -> IntakeResponse:
    from fastapi import HTTPException

    from src.api.parsed import _create_document_job

    # _create_document_job's own validate_document() can raise HTTPException (e.g.
    # bytes that don't sniff as any supported format) — the intake contract
    # promises every outcome renders through IntakeResponse, so that must never
    # leak past this module. The filename is passed as-is; format is content-based.
    try:
        result = await _create_document_job(chat_id, file.data, file.filename)
    except HTTPException as exc:
        detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
        return responses.rejected(detail or "This file could not be accepted.")
    except Exception:
        # GCS/storage/hash failures are transient infra errors, not the
        # client's fault — never let them leak past the IntakeResponse
        # contract this module's docstring promises.
        log.exception("intake_document_job_failed")
        return responses.error("Could not process this document right now.", retryable=True)
    return IntakeResponse(
        kind="job_created",
        text=f"Received {file.filename} — job_{result['job_id'][-4:]} (document).",
        job_id=result["job_id"],
    )


async def ocr_image_links(chat_id: int, data: bytes, content_type: str) -> dict:
    """Run the photo-OCR link-extraction pipeline on image bytes (ADR-0003).

    Returns {"links": [...], "summary": str}. Shared by the intake image branch
    and the Doc Parser image upload so images route through one place. Raises on a
    total OCR failure — the caller maps that to its own error response.
    """
    from src.services.gemini import call_gemini_photo_links
    from src.services.github import enrich_github_links

    result = await call_gemini_photo_links(
        [{"bytes": data, "mime_type": content_type}],
        caption=None,
    )
    links = result.get("links", [])
    summary = result.get("summary", "")
    if links:
        try:
            links = await enrich_github_links(links)
        except Exception:
            # Enrichment is a nice-to-have on top of links already found — don't
            # fail the whole response over it.
            log.exception("intake_github_enrich_failed")
        _maybe_ingest_brain(links, summary, chat_id)
    return {"links": links, "summary": summary}


async def _handle_image(chat_id: int, file: IntakeFile) -> IntakeResponse:
    try:
        result = await ocr_image_links(chat_id, file.data, file.content_type)
    except Exception:
        log.exception("intake_photo_links_failed")
        return responses.error("Could not process this image right now.", retryable=True)
    links = result["links"]
    summary = result["summary"]
    if not links:
        return IntakeResponse(
            kind="action_ack",
            text=f"No links found in this image.\n{summary}".strip(),
        )
    return IntakeResponse(
        kind="action_ack",
        text=f"Found {len(links)} link(s) in this image.",
        artifacts=[{"links": links}],
    )


async def _handle_bookmarks(chat_id: int, file: IntakeFile) -> IntakeResponse:
    """Create the import's job card and queue the parse (#492, ADR-0048).

    The HTML is not persisted (no GCS/Drive object) — it travels in the queue
    task envelope as base64 and is discarded once the worker dequeues it.
    `jobs.url` gets a content-hash placeholder, never a navigable link.
    """
    import base64
    import hashlib
    from datetime import datetime, timezone

    from src import database
    from src.services.jobs import create_and_enqueue_job

    digest = hashlib.sha256(file.data).hexdigest()[:16]
    url = f"bookmarks:{digest}"
    now = datetime.now(timezone.utc)
    title = f"Bookmarks {now.month}/{now.day}/{now.strftime('%y')}"

    try:
        job = await create_and_enqueue_job(
            chat_id,
            url,
            "link",
            task="bookmarks",
            task_payload={"html_b64": base64.b64encode(file.data).decode("ascii")},
        )
    except Exception:
        log.exception("intake_bookmarks_job_failed")
        return responses.error("Could not process this bookmark file right now.", retryable=True)
    job_id = job["id"]
    if not job.get("_deduped"):
        await database.update_job_status(job_id, "pending", title=title)
    return IntakeResponse(
        kind="job_created",
        text=f"Received {file.filename} — job_{job_id[-4:]} ({title}).",
        job_id=job_id,
    )


def _maybe_ingest_brain(links: list[dict], summary: str, chat_id: int) -> None:
    from src.config import settings

    if not settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        return
    from src import brain
    from src.utils.background_tasks import spawn_background

    spawn_background(brain.ingest_links(links, topic=summary, source_job_id=f"photo_{chat_id}"))

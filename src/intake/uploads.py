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
from src.utils.logger import get_logger

log = get_logger(__name__)


async def handle_files(msg: IntakeMessage) -> IntakeResponse:
    chat_id = msg.actor.legacy_chat_id
    if chat_id is None:
        return responses.error("No owner resolved for this upload.", retryable=False)
    if len(msg.files) != 1:
        return responses.rejected("Upload exactly one file per submit.")
    file = msg.files[0]

    if file.content_type == "application/pdf":
        return await _handle_pdf(chat_id, file)
    if file.content_type.startswith("image/"):
        return await _handle_image(chat_id, file)
    if file.content_type == "text/x-bookmarks":
        return await _handle_bookmarks(chat_id, file)
    return responses.rejected(f"Unsupported file type: {file.content_type}")


async def _handle_pdf(chat_id: int, file: IntakeFile) -> IntakeResponse:
    from fastapi import HTTPException

    from src.api.parsed import _create_document_job

    # _create_document_job's own validate_pdf() can raise HTTPException (e.g.
    # a filename that doesn't end in .pdf, even though the bytes sniffed as
    # application/pdf) — the intake contract promises every outcome renders
    # through IntakeResponse, so that must never leak past this module.
    filename = file.filename if file.filename.lower().endswith(".pdf") else f"{file.filename}.pdf"
    try:
        result = await _create_document_job(chat_id, file.data, filename)
    except HTTPException as exc:
        detail = exc.detail.get("message") if isinstance(exc.detail, dict) else str(exc.detail)
        return responses.rejected(detail or "This PDF could not be accepted.")
    except Exception:
        # GCS/storage/hash failures are transient infra errors, not the
        # client's fault — never let them leak past the IntakeResponse
        # contract this module's docstring promises.
        log.exception("intake_pdf_job_failed")
        return responses.error("Could not process this PDF right now.", retryable=True)
    return IntakeResponse(
        kind="job_created",
        text=f"Received {filename} — job_{result['job_id'][-4:]} (document).",
        job_id=result["job_id"],
    )


async def _handle_image(chat_id: int, file: IntakeFile) -> IntakeResponse:
    from src.services.gemini import call_gemini_photo_links
    from src.services.github import enrich_github_links

    try:
        result = await call_gemini_photo_links(
            [{"bytes": file.data, "mime_type": file.content_type}],
            caption=None,
        )
    except Exception:
        log.exception("intake_photo_links_failed")
        return responses.error("Could not process this image right now.", retryable=True)
    links = result.get("links", [])
    summary = result.get("summary", "")
    if not links:
        return IntakeResponse(
            kind="action_ack",
            text=f"No links found in this image.\n{summary}".strip(),
        )

    try:
        links = await enrich_github_links(links)
    except Exception:
        # Enrichment is a nice-to-have on top of links already found — don't
        # fail the whole response over it.
        log.exception("intake_github_enrich_failed")
    _maybe_ingest_brain(links, summary, chat_id)
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

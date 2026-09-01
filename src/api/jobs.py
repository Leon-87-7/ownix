"""HTTP endpoints for job listing, stats, detail, annotations, and tag links."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from src import database
from src.brain import normalize_url
from src.api.deps import get_owned_job
from src.services import job_recovery
from src.services.jobs import build_job_purge_task, create_and_enqueue_job
from src.templates import PROMPT_TEMPLATES
from src.utils.logger import get_logger
from src.utils.validators import coerce_url, detect_pipeline, normalize_repo_url

log = get_logger(__name__)

jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])

ThumbnailKind = Literal["landscape", "portrait"]
RecoveryContentType = Literal["short", "long", "article", "repo"]
LINK_BACKED_CONTENT_TYPES = {"link", "article", "repo"}


async def _add_link_ids(items: list[dict], chat_id: int) -> None:
    """Resolve and sweep link-backed jobs without changing carrier jobs."""
    candidates = [item for item in items if item.get("content_type") in LINK_BACKED_CONTENT_TYPES]
    normalized_by_job = {item["id"]: normalize_url(item["url"]) for item in candidates}
    links_by_url = await database.resolve_link_ids(chat_id, list(normalized_by_job.values()))
    resolved = [item for item in candidates if normalized_by_job[item["id"]] in links_by_url]
    # Most requests hit already-swept jobs — skip the per-job sweep query for those.
    sweepable = await database.job_ids_with_tags([item["id"] for item in resolved])
    for item in resolved:
        item["link_id"] = links_by_url[normalized_by_job[item["id"]]]
        if item["id"] in sweepable:
            await database.sweep_job_tags_to_link(item["id"], item["link_id"])


class RecoveryRequest(BaseModel):
    content_type: RecoveryContentType | None = None


def _recovery_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /api/jobs/stats  — MUST be declared before /{job_id}
# ---------------------------------------------------------------------------


@jobs_router.get("/stats")
async def get_job_stats(
    request: Request,
    content_type: str | None = Query(default=None),
) -> dict:
    """Return hero counts for the authenticated user's jobs.

    The status breakdown is scoped to *content_type* when provided so the
    Overview cards reflect the active content-type tab; filtering is by
    content type only (never status), so the cards always show the full
    status split for the selected type. ``by_content_type`` stays unfiltered
    so the per-tab count chips are unaffected.
    """
    chat_id: int = request.state.user["id"]

    async with database.connection() as conn:
        # Status breakdown — scoped to content_type when a tab is active.
        status_conditions = ["chat_id = ?", "status != 'cancelled'"]
        status_params: list = [chat_id]
        if content_type is not None:
            status_conditions.append("content_type = ?")
            status_params.append(content_type)
        status_where = " AND ".join(status_conditions)

        cur = await conn.execute(
            f"SELECT status, COUNT(*) AS cnt FROM jobs WHERE {status_where} GROUP BY status",
            status_params,
        )
        rows = await cur.fetchall()
        by_status: dict[str, int] = {row["status"]: row["cnt"] for row in rows}
        total = sum(by_status.values())

        # Content-type breakdown — always global so the tab count chips stay correct.
        cur2 = await conn.execute(
            "SELECT content_type, COUNT(*) AS cnt FROM jobs WHERE chat_id = ? AND status != 'cancelled' GROUP BY content_type",
            (chat_id,),
        )
        rows2 = await cur2.fetchall()
        by_content_type: dict[str, int] = {row["content_type"]: row["cnt"] for row in rows2}

    return {
        "total": total,
        "by_status": by_status,
        "by_content_type": by_content_type,
    }


@jobs_router.get("/recovery/summary")
async def get_recovery_summary(
    request: Request,
    content_type: RecoveryContentType | None = Query(default=None),
) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.recovery_summary(chat_id, content_type)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


@jobs_router.post("/recovery/retry-pending")
async def retry_recovery_pending(
    request: Request, body: RecoveryRequest | None = None
) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.retry_pending(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


@jobs_router.post("/recovery/retry-error")
async def retry_recovery_error(
    request: Request, body: RecoveryRequest | None = None
) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.retry_error(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


@jobs_router.post("/recovery/clear-failed")
async def clear_recovery_failed(
    request: Request, body: RecoveryRequest | None = None
) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.clear_failed(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


class JobCreateRequest(BaseModel):
    url: str
    template: str | None = None
    freestyle_prompt: str | None = Field(default=None, max_length=4_000)
    content_type: Literal["link"] | None = None


class JobEnrichRequest(BaseModel):
    template: str
    freestyle_prompt: str | None = Field(default=None, max_length=4_000)


async def _create_link_job(chat_id: int, url: str) -> dict:
    # coerce_url, not is_fetchable_url: a bare domain gains https:// so
    # "land-book.com" works, while a whitespace-joined URL blob is rejected
    # instead of being stored as one job (#490, CONTEXT.md "URL coercion").
    coerced = coerce_url(url)
    if coerced is None:
        raise HTTPException(status_code=422, detail="Add Link needs a valid HTTP(S) URL or bare domain")
    url = coerced
    warning = "Add Link saves the link as-is; it does not process it through the pipeline-detection flow."
    # create_and_enqueue_job owns dedup (ADR-0033): a cache hit on any
    # content_type returns the existing job instead of creating one, so a
    # URL already tracked as another type never gains a duplicate link job.
    job = await create_and_enqueue_job(chat_id, url, "link")
    if job.get("content_type", "link") != "link":
        raise HTTPException(
            status_code=409,
            detail=(
                f"⚠️ This URL already exists as a {job.get('content_type')} job "
                f"(job_{job['id'][-4:]}) — no link entry was created. {warning}"
            ),
        )
    return {
        "id": job["id"],
        "job_id": job["id"],
        "url": job.get("url", url),
        "content_type": job.get("content_type", "link"),
        "status": job.get("status", "pending"),
        "title": job.get("title"),
        "warning": warning,
    }


def _resolve_job_template(pipeline: str, template: str | None, freestyle_prompt: str | None) -> tuple[str | None, str | None]:
    if pipeline == "repo":
        return None, None
    if template == "freestyle" and not freestyle_prompt:
        raise HTTPException(status_code=422, detail="freestyle_prompt is required for freestyle")
    if template and template != "freestyle" and template not in PROMPT_TEMPLATES:
        raise HTTPException(status_code=422, detail="Unknown template")
    return template, freestyle_prompt


async def _create_pipeline_job(body: JobCreateRequest, chat_id: int, url: str) -> dict:
    pipeline = detect_pipeline(url, frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "document":
        raise HTTPException(status_code=422, detail="Document URLs belong in the Doc Parser")
    if pipeline not in {"short", "long", "unsized", "article", "repo"}:
        raise HTTPException(status_code=422, detail="Unsupported URL")

    template = body.template.strip() if body.template else None
    freestyle_prompt = body.freestyle_prompt.strip() if body.freestyle_prompt else None
    template, freestyle_prompt = _resolve_job_template(pipeline, template, freestyle_prompt)

    url_for_job = normalize_repo_url(url) if pipeline == "repo" else url
    job = await create_and_enqueue_job(
        chat_id,
        url_for_job,
        pipeline,
        template=template,
        freestyle_prompt=freestyle_prompt if template == "freestyle" else None,
    )
    return {
        "id": job["id"],
        "job_id": job["id"],
        "url": job.get("url", url_for_job),
        "content_type": job.get("content_type", pipeline),
        "status": job.get("status", "pending"),
        "title": job.get("title"),
    }


@jobs_router.post("")
async def create_job(request: Request, body: JobCreateRequest) -> dict:
    """Create a dashboard-submitted job using the shared Telegram ingest core."""
    chat_id: int = request.state.user["id"]
    url = body.url.strip()
    if body.content_type == "link":
        return await _create_link_job(chat_id, url)
    return await _create_pipeline_job(body, chat_id, url)


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------


def _youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if host.endswith("youtube.com") and path == "/watch":
        return parse_qs(parsed.query).get("v", [""])[0] or None
    if host == "youtu.be" and len(path) > 1:
        return path.strip("/").split("/", 1)[0] or None
    if host.endswith("youtube.com") and path.startswith("/shorts/"):
        return path.removeprefix("/shorts/").split("/", 1)[0] or None
    if host.endswith("youtube.com") and path.startswith("/live/"):
        return path.removeprefix("/live/").split("/", 1)[0] or None
    return None


def _github_repo_path(url: str) -> str | None:
    if detect_pipeline(url) != "repo":
        return None

    normalized = normalize_repo_url(url)
    segments = [segment for segment in urlparse(normalized).path.split("/") if segment]
    if len(segments) < 2:
        return None
    return f"{segments[0]}/{segments[1]}"


def _stored_thumbnail_url(job_id: str) -> str:
    return f"/api/jobs/{job_id}/thumbnail"


def is_persistable_short_platform(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower().removeprefix("www.")
    # host.endswith("tiktok.com") already matches vt.tiktok.com as a suffix.
    return any(
        host == target or host.endswith("." + target)
        for target in ("instagram.com", "tiktok.com", "facebook.com", "x.com", "twitter.com")
    )


async def resolve_thumbnail(
    job: dict, stored_ids: set[str] | None = None
) -> tuple[str | None, ThumbnailKind | None]:
    """Return the server-resolved thumbnail URL and aspect hint for a list item."""
    url = job["url"]
    content_type = job["content_type"]

    if content_type == "article" and job.get("og_image_url"):
        return job["og_image_url"], "landscape"

    if content_type == "long" and detect_pipeline(url) == "long":
        video_id = _youtube_video_id(url)
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", "landscape"

    if content_type == "repo":
        repo_path = _github_repo_path(url)
        if repo_path:
            return f"https://opengraph.githubassets.com/0/{repo_path}", "landscape"

    if content_type == "short" and detect_pipeline(url) in {"short", "unsized"}:
        video_id = _youtube_video_id(url)
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", "portrait"
        if is_persistable_short_platform(url):
            has_stored = (
                job["id"] in stored_ids
                if stored_ids is not None
                else await database.has_thumbnail(job["id"])
            )
            if has_stored:
                return _stored_thumbnail_url(job["id"]), "portrait"

    return None, None


def _job_scope_where(
    chat_id: int, content_type: str | None, status: str | None
) -> tuple[str, list]:
    """Feed-scope filter shared by list_jobs and get_adjacent_jobs — the two must
    agree on what's visible or prev/next navigation drifts from the feed."""
    conditions = ["chat_id = ?"]
    params: list = [chat_id]
    if content_type is not None:
        conditions.append("content_type = ?")
        params.append(content_type)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    else:
        conditions.append("status != 'cancelled'")
    return " AND ".join(conditions), params


@jobs_router.get("")
async def list_jobs(
    request: Request,
    content_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=1000),
) -> dict:
    """List jobs for the authenticated user with optional filters and pagination."""
    chat_id: int = request.state.user["id"]
    offset = (page - 1) * limit

    where, params = _job_scope_where(chat_id, content_type, status)

    async with database.connection() as conn:
        cur_total = await conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {where}", params)
        row_total = await cur_total.fetchone()
        total: int = row_total[0] if row_total else 0

        cur_items = await conn.execute(
            f"""
            SELECT id, title, content_type, status, url, created_at, og_image_url, telegram_delivery,
                   checklists_generated_at,
                   (SELECT MAX(created_at) FROM document_outputs
                    WHERE job_id = jobs.id AND kind IN ('clean', 'freestyle')) AS document_enriched_at
            FROM jobs
            WHERE {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        rows = await cur_items.fetchall()

    # First connection released; resolve thumbnails with a single follow-up query.
    short_ids = [
        r["id"]
        for r in rows
        if r["content_type"] == "short" and is_persistable_short_platform(r["url"])
    ]
    stored_ids = await database.get_thumbnail_job_ids(short_ids)
    items = []
    for row in rows:
        item = dict(row)
        item["thumbnail_url"], item["thumbnail_kind"] = await resolve_thumbnail(item, stored_ids)
        items.append(item)
    await _add_link_ids(items, chat_id)

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# Annotations — declared before /{job_id} to avoid routing conflicts
# ---------------------------------------------------------------------------


class AnnotationIn(BaseModel):
    notes: str = Field(..., max_length=4_000)


@jobs_router.get("/{job_id}/annotations")
async def get_annotation(job_id: str, request: Request) -> dict:
    """Return the annotation for *job_id*. Returns {notes: '', updated_at: null} when absent."""
    await get_owned_job(job_id, request)

    row = await database.get_job_annotation(job_id)
    if row is None:
        return {"notes": "", "updated_at": None}
    return {"notes": row["notes"], "updated_at": row["updated_at"]}


@jobs_router.put("/{job_id}/annotations")
async def upsert_annotation(job_id: str, body: AnnotationIn, request: Request) -> dict:
    """Create or update the annotation for *job_id*."""
    await get_owned_job(job_id, request)

    row = await database.upsert_job_annotation(job_id, body.notes)
    return {"notes": row["notes"], "updated_at": row["updated_at"]}


# ---------------------------------------------------------------------------
# Title — declared before /{job_id} to avoid routing conflicts
# ---------------------------------------------------------------------------


class TitleIn(BaseModel):
    title: str = Field(..., max_length=500)


@jobs_router.put("/{job_id}/title")
async def update_job_title(job_id: str, body: TitleIn, request: Request) -> dict:
    """Rename *job_id*. An empty/whitespace title restores the pipeline-derived
    original (snapshotted into `original_title` on the first rename), not NULL."""
    job = await get_owned_job(job_id, request)

    original = job.get("original_title") or job.get("title")
    new_title = body.title.strip() or original

    fields: dict[str, str | None] = {"title": new_title}
    if job.get("original_title") is None:
        fields["original_title"] = original
    await database.update_job_fields(job_id, **fields)
    return {"title": new_title}


# ---------------------------------------------------------------------------
# Transcript — declared before /{job_id} to avoid routing conflicts
# ---------------------------------------------------------------------------


class TranscriptIn(BaseModel):
    transcript: str = Field(..., max_length=500_000)


@jobs_router.put("/{job_id}/transcript")
async def update_job_transcript(job_id: str, body: TranscriptIn, request: Request) -> dict:
    """Persist an operator edit to *job_id*'s transcript and best-effort mirror
    it to the transcript Drive doc if one exists (transcript_drive_url, ADR-0057).
    A Drive failure never blocks the save — SQLite is the source of truth."""
    job = await get_owned_job(job_id, request)

    await database.update_job_fields(job_id, transcript=body.transcript)
    await _resync_transcript_drive_doc(job, body.transcript)
    return {"transcript": body.transcript}


async def _resync_transcript_drive_doc(job: dict, transcript: str) -> None:
    from src.services.drive import file_id_from_url, update_file
    from src.utils.markdown import build_transcript_markdown

    file_id = file_id_from_url(job.get("transcript_drive_url"))
    if not file_id:
        return
    md_text = build_transcript_markdown(
        job.get("title") or "", "", "", "", job.get("url") or "", transcript
    )
    try:
        await update_file(file_id, md_text, chat_id=job["chat_id"])
    except Exception as exc:
        log.warning("transcript_drive_resync_failed", job_id=job["id"], error=str(exc))


# ---------------------------------------------------------------------------
# Job-tag links — declared before /{job_id} to avoid routing conflicts
# ---------------------------------------------------------------------------


@jobs_router.get("/{job_id}/tags")
async def get_job_tags(job_id: str, request: Request) -> list[dict]:
    """Return tags attached to *job_id*."""
    await get_owned_job(job_id, request)

    return await database.list_job_tags(job_id)


@jobs_router.post("/{job_id}/tags/{tag_id}", status_code=201)
async def attach_tag(job_id: str, tag_id: str, request: Request) -> dict:
    """Attach *tag_id* to *job_id*. Returns the tag summary."""
    chat_id: int = request.state.user["id"]
    await get_owned_job(job_id, request)

    tag = await database.get_tag(chat_id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    await database.attach_job_tag(job_id, tag_id)
    return {
        "id": tag["id"],
        "name": tag["name"],
        "color": tag["color"],
        "meaning": tag["meaning"],
    }


@jobs_router.delete("/{job_id}/tags/{tag_id}", status_code=204)
async def detach_tag(job_id: str, tag_id: str, request: Request) -> Response:
    """Detach *tag_id* from *job_id*."""
    chat_id: int = request.state.user["id"]
    await get_owned_job(job_id, request)

    tag = await database.get_tag(chat_id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    deleted = await database.detach_job_tag(job_id, tag_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tag not attached to this job")
    return Response(status_code=204)


@jobs_router.get("/{job_id}/adjacent")
async def get_adjacent_jobs(
    job_id: str,
    request: Request,
    content_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, str | None]:
    """Return neighboring job IDs for the caller within an optional Feed scope.

    Semantics are chronological by design: previous_id = closest OLDER job,
    next_id = closest NEWER job ("Next →" moves forward in time, not down the
    newest-first feed list). Won't-fix suggestions to invert this.
    """
    job = await get_owned_job(job_id, request)
    chat_id: int = request.state.user["id"]

    where, params = _job_scope_where(chat_id, content_type, status)

    created_at = job["created_at"]
    async with database.connection() as conn:
        prev_cur = await conn.execute(
            f"""
            SELECT id FROM jobs
            WHERE {where} AND (created_at < ? OR (created_at = ? AND id < ?))
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [*params, created_at, created_at, job_id],
        )
        prev = await prev_cur.fetchone()
        next_cur = await conn.execute(
            f"""
            SELECT id FROM jobs
            WHERE {where} AND (created_at > ? OR (created_at = ? AND id > ?))
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            [*params, created_at, created_at, job_id],
        )
        next_row = await next_cur.fetchone()

    return {
        "previous_id": prev["id"] if prev else None,
        "next_id": next_row["id"] if next_row else None,
    }


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

# Fields common to all content types
_DETAIL_FIELDS_COMMON = (
    "id",
    "url",
    "content_type",
    "status",
    "title",
    "created_at",
    "updated_at",
    "completed_at",
    "error_msg",
    "drive_url",
    "transcript_drive_url",
    "telegram_delivery",
    "sheets_row_id",
    "checklists_md",
    "checklists_generated_at",
    "screenshots_status",
    "screenshots_drive_url",
    "screenshots_generated_at",
    "video_duration_seconds",
)

# Extra fields for long/article/repo jobs (AI enrichment schema)
_DETAIL_FIELDS_ENRICHMENT = (
    "ai_topic",
    "ai_objective",
    "ai_action_points",
    "ai_tools",
    "ai_market_data",
    "promise_gap",
    "template_analysis",
    "template",
)

# Extra fields for short jobs
_DETAIL_FIELDS_SHORT = (
    "summary",
    "transcript",
    "code",
    "code_lang",
    "links",
)


def detail_fields_for(content_type: str) -> tuple[str, ...]:
    """Return the full set of detail field names for a given content_type."""
    if content_type == "short":
        return _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_SHORT
    if content_type == "long":
        return (*_DETAIL_FIELDS_COMMON, "transcript", "links", *_DETAIL_FIELDS_ENRICHMENT)
    return _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_ENRICHMENT


def thumbnail_response(
    thumbnail: dict, request: Request, *, extra_headers: dict[str, str] | None = None
) -> Response:
    """Build a cached image Response for a stored thumbnail row.

    ETag hashes the stored bytes rather than a timestamp column: save_thumbnail's
    ON CONFLICT(job_id) DO UPDATE overwrites bytes/mime/width/height but never
    bumps job_thumbnails.created_at, so a reprocess or backfill can swap the
    frame without that column changing — a timestamp-derived ETag would keep
    validating a stale image forever after such a swap (see ADR-0025 follow-up).
    """
    # Never echo back a non-image content type, even for rows stored before the
    # save-time allowlist existed — keeps the browser from sniffing active content.
    mime = (
        thumbnail["mime"] if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES else "image/jpeg"
    )
    etag = f'"{hashlib.sha256(thumbnail["bytes"]).hexdigest()}"'
    if _if_none_match_matches(request.headers.get("if-none-match"), etag):
        # RFC 7232 §4.1: a 304 should repeat the ETag it would have sent on a 200.
        return Response(status_code=304, headers={**(extra_headers or {}), "ETag": etag})
    headers = {
        "Cache-Control": "private, max-age=2592000, must-revalidate",
        "ETag": etag,
        **(extra_headers or {}),
    }
    return Response(content=thumbnail["bytes"], media_type=mime, headers=headers)


def _if_none_match_matches(if_none_match: str | None, etag: str) -> bool:
    if if_none_match is None:
        return False
    for validator in if_none_match.split(","):
        validator = validator.strip()
        if validator == "*":
            return True
        if validator.startswith("W/"):
            validator = validator[2:].strip()
        if validator == etag:
            return True
    return False


@jobs_router.get("/{job_id}/thumbnail")
async def get_job_thumbnail(job_id: str, request: Request) -> Response:
    """Return a persisted thumbnail for an owned job."""
    await get_owned_job(job_id, request)
    thumbnail = await database.get_thumbnail(job_id)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return thumbnail_response(thumbnail, request)


@jobs_router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    """Return full job detail for a job the caller owns."""
    job = await get_owned_job(job_id, request)

    fields = detail_fields_for(job.get("content_type", ""))
    detail = {k: job.get(k) for k in fields}
    await _add_link_ids([detail], request.state.user["id"])
    # Not a job column — one COUNT query, only consumed by the delete-confirm
    # checkbox (ADR-0046), so it rides outside the content-type field filter.
    detail["link_count"] = await database.count_job_links(job_id)
    return detail


@jobs_router.post("/{job_id}/checklists")
async def generate_job_checklists(job_id: str, request: Request) -> dict:
    """Generate and persist a checklist for an owned video job."""
    job = await get_owned_job(job_id, request)
    if job.get("content_type") not in {"short", "long"}:
        raise HTTPException(status_code=422, detail="Checklists require a short or long video")
    if job.get("status") not in {"transcript_done", "done"} or not (
        job.get("transcript") or ""
    ).strip():
        raise HTTPException(status_code=422, detail="A completed transcript is required")

    from src.processors.checklists import run_checklists
    from src.services.gemini import GeminiUnavailableError

    try:
        _, markdown = await run_checklists(job)
    except GeminiUnavailableError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Checklist generation failed") from exc

    generated_at = datetime.now(UTC).isoformat()
    await database.update_job_fields(
        job_id,
        checklists_md=markdown,
        checklists_generated_at=generated_at,
    )
    return {"checklists_md": markdown, "checklists_generated_at": generated_at}


@jobs_router.post("/{job_id}/screenshots", status_code=202)
async def generate_job_screenshots(job_id: str, request: Request) -> dict:
    """Claim screenshot capture and return immediately while it runs."""
    job = await get_owned_job(job_id, request)
    from src.processors.screenshots import trigger

    outcome = await trigger(job)
    if outcome == "ineligible":
        raise HTTPException(status_code=422, detail="Screenshots require a completed long video")
    if outcome == "too_long":
        raise HTTPException(status_code=422, detail="Video exceeds the screenshot duration limit")
    if outcome == "busy":
        raise HTTPException(status_code=409, detail="Screenshot capture is already running")
    return {"screenshots_status": "generating"}


@jobs_router.post("/{job_id}/enrich", status_code=202)
async def enrich_job(job_id: str, request: Request, body: JobEnrichRequest) -> dict:
    """Atomically claim an owned long-video transcript and queue enrichment."""
    job = await get_owned_job(job_id, request)
    if job.get("content_type") != "long":
        raise HTTPException(
            status_code=422, detail="Enrichment requires a transcript-complete long video"
        )
    if job.get("status") == "enriching":
        raise HTTPException(status_code=409, detail="Job enrichment was already claimed")
    if job.get("status") != "transcript_done":
        raise HTTPException(
            status_code=422, detail="Enrichment requires a transcript-complete long video"
        )

    template = body.template.strip()
    if not template:
        raise HTTPException(status_code=422, detail="template is required")
    freestyle_prompt = body.freestyle_prompt.strip() if body.freestyle_prompt else None
    template, freestyle_prompt = _resolve_job_template("long", template, freestyle_prompt)
    claimed = await database.claim_job_enrichment(
        job_id, template, freestyle_prompt if template == "freestyle" else None
    )
    if not claimed:
        raise HTTPException(status_code=409, detail="Job enrichment was already claimed")

    try:
        from src import job_queue as queue

        await queue.enqueue({"task": "enrichment", "job_id": job_id})
    except Exception as exc:
        await database.release_job_enrichment_claim(job_id)
        raise HTTPException(status_code=503, detail="Could not queue enrichment") from exc
    return {"job_id": job_id, "status": "enriching"}


@jobs_router.get("/{job_id}/repo-followups")
async def get_repo_followups(job_id: str, request: Request) -> list[dict]:
    """Cached GitHub repo candidates offered after this job finished (long/short
    pipelines) — the dashboard-facing read side of `offer_repo_followups`
    (`src/services/repo_followup.py`), which until now only reached Telegram."""
    await get_owned_job(job_id, request)
    from src import job_queue as queue

    raw = await queue._client().get(f"repo_pick:{job_id}")
    return json.loads(raw) if raw else []


@jobs_router.post("/{job_id}/repo-followups/{idx}", status_code=202)
async def pick_repo_followup(job_id: str, idx: int, request: Request) -> dict:
    """Enqueue a cached repo candidate as a new job (mirrors Telegram's
    `repo_pick:{job_id}:{idx}` callback via the same channel-neutral
    `enqueue_repo_pick`)."""
    await get_owned_job(job_id, request)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Repo candidate not found or expired")
    from src.services.repo_followup import enqueue_repo_pick

    job = await enqueue_repo_pick(job_id, str(idx))
    if job is None:
        raise HTTPException(status_code=404, detail="Repo candidate not found or expired")
    return {"job_id": job["id"], "status": job.get("status", "pending")}


@jobs_router.get("/{job_id}/link-topics")
async def get_job_link_topics(job_id: str, request: Request) -> list[dict]:
    """Distinct folders among this job's Brain links (#497 — the
    folder-to-tag opt-in form). Re-openable any time: topic is persisted at
    import regardless of whether the form is ever used."""
    await get_owned_job(job_id, request)
    return await database.list_job_link_topics(job_id)


@jobs_router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str, request: Request, with_links: bool = False) -> Response:
    """Job delete: remove owned database state and durably record its Job purge.

    The purge task is written to a transactional outbox in the same transaction as the
    delete, ensuring it cannot be lost even if Redis is unavailable. A background drainer
    moves tasks from the outbox to Redis.

    The job's Brain links are left standing (ADR-0046) unless `?with_links=1` is
    passed — a bookmark import card owns hundreds of them, and there is no undo.
    """
    job = await get_owned_job(job_id, request)
    purge_task = await build_job_purge_task(job)
    # Atomically delete the job and record the purge task in the outbox.
    await database.delete_job(job_id, purge_payload=purge_task, with_links=with_links)
    return Response(status_code=204)

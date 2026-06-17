"""HTTP endpoints for job listing, stats, detail, annotations, and tag links."""

from __future__ import annotations

from typing import Literal
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from src import database
from src.api.deps import get_owned_job
from src.services import job_recovery
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline, normalize_repo_url

log = get_logger(__name__)

jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])

ThumbnailKind = Literal["landscape", "portrait"]
RecoveryContentType = Literal["short", "long", "article", "repo"]


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
        status_conditions = ["chat_id = ?"]
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
            "SELECT content_type, COUNT(*) AS cnt FROM jobs WHERE chat_id = ? GROUP BY content_type",
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
async def retry_recovery_pending(request: Request, body: RecoveryRequest | None = None) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.retry_pending(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


@jobs_router.post("/recovery/retry-error")
async def retry_recovery_error(request: Request, body: RecoveryRequest | None = None) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.retry_error(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


@jobs_router.post("/recovery/clear-failed")
async def clear_recovery_failed(request: Request, body: RecoveryRequest | None = None) -> dict[str, int]:
    chat_id: int = request.state.user["id"]
    try:
        return await job_recovery.clear_failed(chat_id, body.content_type if body else None)
    except ValueError as exc:
        raise _recovery_error(exc) from exc


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


def _is_persistable_short_platform(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower().removeprefix("www.")
    return host.endswith("instagram.com") or host.endswith("tiktok.com")


async def _resolve_thumbnail(
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

    if content_type == "short" and detect_pipeline(url) == "short":
        video_id = _youtube_video_id(url)
        if video_id:
            return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", "portrait"
        if _is_persistable_short_platform(url):
            has_stored = (
                job["id"] in stored_ids
                if stored_ids is not None
                else await database.has_thumbnail(job["id"])
            )
            if has_stored:
                return _stored_thumbnail_url(job["id"]), "portrait"

    return None, None


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

    conditions = ["chat_id = ?"]
    params: list = [chat_id]

    if content_type is not None:
        conditions.append("content_type = ?")
        params.append(content_type)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)

    where = " AND ".join(conditions)

    async with database.connection() as conn:
        cur_total = await conn.execute(
            f"SELECT COUNT(*) FROM jobs WHERE {where}", params
        )
        row_total = await cur_total.fetchone()
        total: int = row_total[0] if row_total else 0

        cur_items = await conn.execute(
            f"""
            SELECT id, title, content_type, status, url, created_at, og_image_url
            FROM jobs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        rows = await cur_items.fetchall()

    # First connection released; resolve thumbnails with a single follow-up query.
    short_ids = [
        r["id"] for r in rows
        if r["content_type"] == "short" and _is_persistable_short_platform(r["url"])
    ]
    stored_ids = await database.get_thumbnail_job_ids(short_ids)
    items = []
    for row in rows:
        item = dict(row)
        item["thumbnail_url"], item["thumbnail_kind"] = await _resolve_thumbnail(item, stored_ids)
        items.append(item)

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
    notes: str


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
    return {"id": tag["id"], "name": tag["name"], "color": tag["color"], "meaning": tag["meaning"]}


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


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------

# Fields common to all content types
_DETAIL_FIELDS_COMMON = (
    "id", "url", "content_type", "status", "title",
    "created_at", "updated_at", "completed_at",
    "error_msg", "drive_url",
)

# Extra fields for long/article/repo jobs (AI enrichment schema)
_DETAIL_FIELDS_LONG = (
    "ai_topic", "ai_objective", "ai_action_points", "ai_tools",
    "ai_market_data", "promise_gap", "template_analysis", "template",
)

# Extra fields for short jobs
_DETAIL_FIELDS_SHORT = (
    "summary", "transcript", "key_phrases",
)

# Legacy flat tuple kept for callers that import it directly (e.g. tests)
_DETAIL_FIELDS = _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG


def _detail_fields_for(content_type: str) -> tuple[str, ...]:
    """Return the full set of detail field names for a given content_type."""
    if content_type == "short":
        return _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_SHORT
    return _DETAIL_FIELDS_COMMON + _DETAIL_FIELDS_LONG


@jobs_router.get("/{job_id}/thumbnail")
async def get_job_thumbnail(job_id: str, request: Request) -> Response:
    """Return a persisted thumbnail for an owned job."""
    await get_owned_job(job_id, request)
    thumbnail = await database.get_thumbnail(job_id)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    # Never echo back a non-image content type, even for rows stored before the
    # save-time allowlist existed — keeps the browser from sniffing active content.
    mime = (
        thumbnail["mime"]
        if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES
        else "image/jpeg"
    )
    return Response(content=thumbnail["bytes"], media_type=mime)


@jobs_router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    """Return full job detail for a job the caller owns."""
    job = await get_owned_job(job_id, request)

    fields = _detail_fields_for(job.get("content_type", ""))
    return {k: job.get(k) for k in fields}

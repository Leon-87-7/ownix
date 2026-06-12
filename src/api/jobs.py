"""HTTP endpoints for job listing, stats, detail, annotations, and tag links."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from src import database
from src.api.deps import get_owned_job
from src.utils.logger import get_logger

log = get_logger(__name__)

jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# GET /api/jobs/stats  — MUST be declared before /{job_id}
# ---------------------------------------------------------------------------

@jobs_router.get("/stats")
async def get_job_stats(request: Request) -> dict:
    """Return hero counts for the authenticated user's jobs."""
    chat_id: int = request.state.user["id"]

    async with database.connection() as conn:
        # Status breakdown
        cur = await conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM jobs WHERE chat_id = ? GROUP BY status",
            (chat_id,),
        )
        rows = await cur.fetchall()
        by_status: dict[str, int] = {row["status"]: row["cnt"] for row in rows}
        total = sum(by_status.values())

        # Content-type breakdown
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


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------

@jobs_router.get("")
async def list_jobs(
    request: Request,
    content_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
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
            SELECT id, title, content_type, status, url, created_at
            FROM jobs
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        rows = await cur_items.fetchall()
        items = [dict(row) for row in rows]

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

_DETAIL_FIELDS = (
    "id", "url", "content_type", "status", "title",
    "created_at", "updated_at", "completed_at",
    "ai_topic", "ai_objective", "ai_action_points", "ai_tools",
    "ai_market_data", "promise_gap", "template_analysis", "template",
    "error_msg", "drive_url",
)


@jobs_router.get("/{job_id}")
async def get_job(job_id: str, request: Request) -> dict:
    """Return full job detail for a job the caller owns."""
    job = await get_owned_job(job_id, request)

    return {k: job.get(k) for k in _DETAIL_FIELDS}

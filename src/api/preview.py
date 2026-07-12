"""Read-only Restricted mode preview endpoints (ADR-0035).

Public, cookie-gated reads over an Operator-derived sample corpus. The cookie
is a functional gate, not authentication — everything served here must stay
safe for anonymous visitors: server-side Operator scope only, private/export
fields stripped, corpus-membership checks on detail routes, and noindex
headers on every response.
"""

from __future__ import annotations

import asyncio
from ipaddress import ip_address, ip_network
import time

from fastapi import APIRouter, HTTPException, Query, Request, Response

from src import database
from src.api.jobs import (
    detail_fields_for,
    is_persistable_short_platform,
    resolve_thumbnail,
)
from src.config import settings

PREVIEW_COOKIE_NAME = "ownix_preview"
PREVIEW_LIMIT = 50
TAB_LIMIT = 20
TRANSCRIPT_CAP = 1200

# Never shown to anonymous visitors: export/integration links plus
# operator-internal state (error messages can leak pipeline internals).
# Keys stay in the payload as None so the response shape matches the
# authenticated detail route.
PRIVATE_DETAIL_FIELDS = frozenset(
    {"drive_url", "sheets_row_id", "error_msg", "telegram_delivery"}
)

# These endpoints are public reads, so per-request corpus recomputes would
# hand visitors a free DB-load loop. One shared snapshot per TTL is the
# "lightweight scrape protection" ADR-0035 asks for; corpus freshness within
# a minute is irrelevant for a demo sample.
_CACHE_TTL_SECONDS = 60.0
_corpus_cache: dict = {"expires": 0.0, "ids": [], "rows": []}
_corpus_lock = asyncio.Lock()
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 120
_preview_rate_limit: dict[str, list[float]] = {}

preview_router = APIRouter(prefix="/api/preview", tags=["preview"])


def _require_preview(request: Request) -> None:
    if request.cookies.get(PREVIEW_COOKIE_NAME) != "1":
        raise HTTPException(status_code=401, detail="Restricted preview required")
    if settings.OPERATOR_CHAT_ID is None:
        raise HTTPException(status_code=503, detail="Preview operator is not configured")


def _preview_client_key(request: Request) -> str:
    peer = request.client.host if request.client is not None else None
    if peer and _trusted_proxy_peer(peer):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.rsplit(",", 1)[-1].strip() or peer
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip() or peer
    if peer:
        return peer
    return "unknown"


def _trusted_proxy_peer(peer: str) -> bool:
    try:
        peer_ip = ip_address(peer)
    except ValueError:
        return False
    for raw_network in settings.PREVIEW_TRUSTED_PROXY_CIDRS.split(","):
        raw_network = raw_network.strip()
        if not raw_network:
            continue
        try:
            if peer_ip in ip_network(raw_network, strict=False):
                return True
        except ValueError:
            continue
    return False


def _enforce_preview_rate_limit(request: Request) -> None:
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    for stale_key, stale_hits in list(_preview_rate_limit.items()):
        while stale_hits and stale_hits[0] <= cutoff:
            stale_hits.pop(0)
        if not stale_hits:
            _preview_rate_limit.pop(stale_key, None)
    key = _preview_client_key(request)
    hits = _preview_rate_limit.setdefault(key, [])
    if len(hits) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Preview rate limit exceeded")
    hits.append(now)


def _require_preview_access(request: Request) -> None:
    _require_preview(request)
    _enforce_preview_rate_limit(request)


def _preview_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "private, max-age=30"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


async def _load_corpus() -> tuple[list[str], list[dict]]:
    """Query the diversified Operator corpus: ≤50 non-cancelled jobs, ≤20 per
    tab, preferring the last 12 hours and backfilling older items (ADR-0035 §4).

    The per-tab rank is computed over the operator's whole history, so a
    Reels-heavy burst can never crowd older articles/repos out of the sample.
    """
    operator = settings.OPERATOR_CHAT_ID
    if operator is None:
        return [], []
    async with database.connection() as conn:
        cur = await conn.execute(
            """
            WITH ranked AS (
                SELECT id, content_type, created_at,
                       CASE WHEN created_at >= datetime('now', '-12 hours')
                            THEN 0 ELSE 1 END AS age_bucket,
                       ROW_NUMBER() OVER (
                           PARTITION BY content_type
                           ORDER BY CASE WHEN created_at >= datetime('now', '-12 hours')
                                         THEN 0 ELSE 1 END ASC,
                                    created_at DESC, id DESC
                       ) AS tab_rank
                FROM jobs
                WHERE chat_id = ? AND status != 'cancelled'
            )
            SELECT id FROM ranked
            WHERE tab_rank <= ?
            ORDER BY age_bucket ASC, created_at DESC, id DESC
            LIMIT ?
            """,
            (operator, TAB_LIMIT, PREVIEW_LIMIT),
        )
        ids = [row["id"] for row in await cur.fetchall()]
        if not ids:
            return [], []
        placeholders = ",".join("?" for _ in ids)
        cur = await conn.execute(
            f"""
            SELECT id, title, content_type, status, url, created_at, og_image_url, telegram_delivery
            FROM jobs
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC, id DESC
            """,
            ids,
        )
        rows = [dict(row) for row in await cur.fetchall()]

    short_ids = [
        r["id"]
        for r in rows
        if r["content_type"] == "short" and is_persistable_short_platform(r["url"])
    ]
    stored_ids = await database.get_thumbnail_job_ids(short_ids)
    for item in rows:
        item["thumbnail_url"], item["thumbnail_kind"] = await resolve_thumbnail(
            item, stored_ids
        )
        # Stored short thumbnails resolve to the ownership-gated
        # /api/jobs/{id}/thumbnail — anonymous visitors would 401 on it.
        # Reroute through the corpus-gated preview twin.
        if item["thumbnail_url"] == f"/api/jobs/{item['id']}/thumbnail":
            item["thumbnail_url"] = f"/api/preview/jobs/{item['id']}/thumbnail"
        # List-shape parity with /api/jobs, minus operator-internal state.
        item["telegram_delivery"] = None
    return ids, rows


async def _corpus() -> tuple[list[str], list[dict]]:
    now = time.monotonic()
    if now < _corpus_cache["expires"]:
        return _corpus_cache["ids"], _corpus_cache["rows"]
    async with _corpus_lock:
        now = time.monotonic()
        if now < _corpus_cache["expires"]:
            return _corpus_cache["ids"], _corpus_cache["rows"]
        ids, rows = await _load_corpus()
        _corpus_cache.update(
            {
                "expires": time.monotonic() + _CACHE_TTL_SECONDS,
                "ids": ids,
                "rows": rows,
            }
        )
        return ids, rows


@preview_router.get("/jobs")
async def list_preview_jobs(
    request: Request,
    response: Response,
    content_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=1000),
) -> dict:
    _require_preview_access(request)
    _preview_headers(response)
    _, rows = await _corpus()
    if content_type is not None:
        rows = [row for row in rows if row.get("content_type") == content_type]
    if status is not None:
        rows = [row for row in rows if row.get("status") == status]
    total = len(rows)
    offset = (page - 1) * limit
    return {"items": rows[offset : offset + limit], "total": total, "page": page, "limit": limit}


@preview_router.get("/jobs/stats")
async def get_preview_stats(
    request: Request,
    response: Response,
    content_type: str | None = Query(default=None),
) -> dict:
    _require_preview_access(request)
    _preview_headers(response)
    _, rows = await _corpus()
    by_content_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for row in rows:
        by_content_type[row["content_type"]] = by_content_type.get(row["content_type"], 0) + 1
        if content_type is None or row["content_type"] == content_type:
            by_status[row["status"]] = by_status.get(row["status"], 0) + 1
    return {"total": sum(by_status.values()), "by_status": by_status, "by_content_type": by_content_type}


@preview_router.get("/jobs/{job_id}/thumbnail")
async def get_preview_thumbnail(job_id: str, request: Request) -> Response:
    """Corpus-gated twin of /api/jobs/{id}/thumbnail for anonymous preview."""
    _require_preview_access(request)
    ids, _ = await _corpus()
    if job_id not in ids:
        raise HTTPException(status_code=404, detail="Preview job not found")
    thumbnail = await database.get_thumbnail(job_id)
    if thumbnail is None:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    # Same MIME allowlist as the owned route: never echo active content types.
    mime = (
        thumbnail["mime"]
        if thumbnail["mime"] in database.ALLOWED_THUMBNAIL_MIMES
        else "image/jpeg"
    )
    return Response(
        content=thumbnail["bytes"],
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@preview_router.get("/jobs/{job_id}")
async def get_preview_job(job_id: str, request: Request, response: Response) -> dict:
    _require_preview_access(request)
    _preview_headers(response)
    ids, _ = await _corpus()
    if job_id not in ids:
        raise HTTPException(status_code=404, detail="Preview job not found")
    async with database.connection() as conn:
        cur = await conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Preview job not found")
    job = dict(row)
    fields = detail_fields_for(job.get("content_type", ""))
    payload = {k: (None if k in PRIVATE_DETAIL_FIELDS else job.get(k)) for k in fields}
    if isinstance(payload.get("transcript"), str) and len(payload["transcript"]) > TRANSCRIPT_CAP:
        payload["transcript"] = payload["transcript"][:TRANSCRIPT_CAP].rstrip() + "…"
    return payload

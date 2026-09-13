"""Thumbnail resolution and the cached image response for job list/detail.

Split out of `src/api/jobs.py` (finding 7): self-contained, and the route file
was one feature away from 1,000 lines. Nothing here touches request auth or job
ownership -- the routes still do that before calling in.
"""

from __future__ import annotations

import hashlib
from typing import Literal
from urllib.parse import parse_qs, urlparse

from fastapi import Request, Response

from src import database
from src.utils.validators import detect_pipeline, normalize_repo_url

ThumbnailKind = Literal["landscape", "portrait"]


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

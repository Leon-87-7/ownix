"""HTTP endpoints for Spaces CRUD + URLs tab (S6) + Context blobs (S7)."""
from __future__ import annotations

import asyncio

from typing import Literal

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

# Curated Lucide icon names a space may use (issue #189). Literal → 422 on anything else.
SpaceIcon = Literal[
    "folder", "star", "bookmark", "globe", "zap", "heart", "code", "music",
    "film", "camera", "coffee", "flame", "rocket", "target", "compass",
    "anchor", "crown", "diamond", "shield", "lightbulb",
]

from src import database
from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

spaces_router = APIRouter(prefix="/api/spaces", tags=["spaces"])


class SpaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: SpaceIcon = "folder"


class SpaceUpdateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: SpaceIcon | None = None  # omit to leave the existing icon unchanged


class UrlIn(BaseModel):
    job_id: str = Field(..., min_length=1)


class ReorderIn(BaseModel):
    sort_order: int


class BlobIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="")


class BlobContentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    content: str


class ExportIn(BaseModel):
    format: str = Field(default="gdoc", pattern=r"^gdoc$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_owned_space(space_id: str, chat_id: int) -> dict:
    """Fetch a space and raise 404/403 if missing or not owned."""
    space = await database.get_space(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    if space["chat_id"] != chat_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return space


# ---------------------------------------------------------------------------
# Space CRUD
# ---------------------------------------------------------------------------


@spaces_router.get("")
async def list_spaces(request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    return await database.list_spaces(chat_id)


@spaces_router.post("", status_code=201)
async def create_space(body: SpaceIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    try:
        return await database.create_space(
            chat_id=chat_id, name=body.name.strip(), color=body.color, icon=body.icon
        )
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=409, detail="Space name already exists")


@spaces_router.get("/{space_id}")
async def get_space(space_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    return await _get_owned_space(space_id, chat_id)


@spaces_router.put("/{space_id}")
async def update_space(space_id: str, body: SpaceUpdateIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    ok = await database.update_space(
        chat_id=chat_id, space_id=space_id, name=body.name.strip(), color=body.color, icon=body.icon
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Space not found")
    space = await database.get_space(space_id)
    if space is None:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


@spaces_router.delete("/{space_id}", status_code=204)
async def delete_space(space_id: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    await database.delete_space(chat_id=chat_id, space_id=space_id)


# ---------------------------------------------------------------------------
# URLs sub-resource
# ---------------------------------------------------------------------------


@spaces_router.get("/{space_id}/urls")
async def list_space_urls(space_id: str, request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    return await database.list_space_urls(space_id, chat_id)


@spaces_router.post("/{space_id}/urls", status_code=201)
async def add_space_url(space_id: str, body: UrlIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    job = await database.get_job(body.job_id)
    if job is None or job["chat_id"] != chat_id:
        raise HTTPException(status_code=404, detail="Job not found")
    await database.add_space_url(space_id=space_id, job_id=body.job_id)
    return {"space_id": space_id, "job_id": body.job_id}


@spaces_router.delete("/{space_id}/urls/{job_id}", status_code=204)
async def remove_space_url(space_id: str, job_id: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    ok = await database.remove_space_url(space_id=space_id, job_id=job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="URL not in space")


@spaces_router.patch("/{space_id}/urls/{job_id}")
async def reorder_space_url(
    space_id: str, job_id: str, body: ReorderIn, request: Request
) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    ok = await database.reorder_space_url(
        space_id=space_id, job_id=job_id, new_sort_order=body.sort_order
    )
    if not ok:
        raise HTTPException(status_code=404, detail="URL not in space")
    return {"space_id": space_id, "job_id": job_id, "sort_order": body.sort_order}


# ---------------------------------------------------------------------------
# Context blobs sub-resource (issue #93 / S7)
# ---------------------------------------------------------------------------


async def _get_owned_blob(blob_id: str, space_id: str) -> dict:
    """Fetch a blob and raise 404 if missing or not linked to this space."""
    blob = await database.get_context_blob(blob_id)
    if blob is None or blob["space_id"] != space_id:
        raise HTTPException(status_code=404, detail="Blob not found")
    return blob


@spaces_router.get("/{space_id}/blobs")
async def list_blobs(space_id: str, request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    return await database.list_context_blobs(space_id)


@spaces_router.post("/{space_id}/blobs", status_code=201)
async def create_blob(space_id: str, body: BlobIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    return await database.create_context_blob(
        space_id=space_id, name=body.name.strip(), content=body.content
    )


@spaces_router.get("/{space_id}/blobs/{blob_id}")
async def get_blob(space_id: str, blob_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    return await _get_owned_blob(blob_id, space_id)


@spaces_router.put("/{space_id}/blobs/{blob_id}")
async def update_blob(
    space_id: str, blob_id: str, body: BlobContentIn, request: Request
) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    await _get_owned_blob(blob_id, space_id)
    ok = await database.update_context_blob(
        blob_id=blob_id, name=body.name.strip(), content=body.content
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Blob not found")
    blob = await database.get_context_blob(blob_id)
    if blob is None:
        raise HTTPException(status_code=404, detail="Blob not found")
    return blob


@spaces_router.delete("/{space_id}/blobs/{blob_id}", status_code=204)
async def delete_blob(space_id: str, blob_id: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    await _get_owned_blob(blob_id, space_id)
    await database.delete_context_blob(blob_id)


@spaces_router.patch("/{space_id}/blobs/{blob_id}")
async def reorder_blob(
    space_id: str, blob_id: str, body: ReorderIn, request: Request
) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    await _get_owned_blob(blob_id, space_id)
    ok = await database.reorder_context_blob(
        blob_id=blob_id, new_sort_order=body.sort_order
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Blob not found")
    return {"blob_id": blob_id, "sort_order": body.sort_order}


# ---------------------------------------------------------------------------
# Export (issue #95 / S8) — server handles gdoc path only
# ---------------------------------------------------------------------------


async def _enrich_space_jobs(space_urls: list[dict]) -> list[dict]:
    """Fetch annotation + tags for all pinned jobs in 3 batched queries."""
    if not space_urls:
        return []
    job_ids = [item["id"] for item in space_urls]
    jobs_map, annotations_map, tags_map = await asyncio.gather(
        database.batch_get_jobs(job_ids),
        database.batch_get_job_annotations(job_ids),
        database.batch_list_job_tags(job_ids),
    )
    return [
        {**job, "notes": annotations_map.get(item["id"], ""), "tags": tags_map.get(item["id"], [])}
        for item in space_urls
        if (job := jobs_map.get(item["id"])) is not None
    ]


@spaces_router.get("/{space_id}/export/markdown")
async def get_export_markdown(space_id: str, request: Request) -> dict:
    """Return the pre-composed export markdown so the client can download it."""
    from src.services.space_export import compose_space_export

    chat_id: int = request.state.user["id"]
    space = await _get_owned_space(space_id, chat_id)
    blobs = await database.list_context_blobs(space_id)
    space_urls = await database.list_space_urls(space_id, chat_id)
    all_tags = await database.list_tags(chat_id)

    jobs = await _enrich_space_jobs(space_urls)
    markdown = compose_space_export(space=space, blobs=blobs, jobs=jobs, tags=all_tags)
    return {"markdown": markdown}


@spaces_router.post("/{space_id}/export")
async def export_space(space_id: str, body: ExportIn, request: Request) -> dict:
    """Build a full space export and push it to Google Drive as a real Doc.

    md/txt/pdf are client-side; this endpoint handles the gdoc path only.
    Returns {"url": <webViewLink>} or {"error": "drive_not_configured"}.
    """
    from src.services.space_export import compose_space_export
    from src.services.drive import export_to_gdoc

    chat_id: int = request.state.user["id"]
    space = await _get_owned_space(space_id, chat_id)

    if not settings.GOOGLE_DRIVE_FOLDER_EXPORTS:
        return {"error": "drive_not_configured"}

    blobs = await database.list_context_blobs(space_id)
    space_urls = await database.list_space_urls(space_id, chat_id)
    all_tags = await database.list_tags(chat_id)

    jobs = await _enrich_space_jobs(space_urls)
    markdown = compose_space_export(space=space, blobs=blobs, jobs=jobs, tags=all_tags)
    doc_name = f"{space['name']} — export"
    url = await export_to_gdoc(
        markdown=markdown,
        name=doc_name,
        folder_id=settings.GOOGLE_DRIVE_FOLDER_EXPORTS,
    )
    return {"url": url}

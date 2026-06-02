"""HTTP endpoints for Spaces CRUD + URLs tab (issue #89 / S6)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src import database
from src.utils.logger import get_logger

log = get_logger(__name__)

spaces_router = APIRouter(prefix="/api/spaces", tags=["spaces"])


class SpaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")


class UrlIn(BaseModel):
    job_id: str = Field(..., min_length=1)


class ReorderIn(BaseModel):
    sort_order: int


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
            chat_id=chat_id, name=body.name.strip(), color=body.color
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Space name already exists")
        raise


@spaces_router.get("/{space_id}")
async def get_space(space_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    return await _get_owned_space(space_id, chat_id)


@spaces_router.put("/{space_id}")
async def update_space(space_id: str, body: SpaceIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
    ok = await database.update_space(
        chat_id=chat_id, space_id=space_id, name=body.name.strip(), color=body.color
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Space not found")
    space = await database.get_space(space_id)
    return space  # type: ignore[return-value]


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
    return await database.list_space_urls(space_id)


@spaces_router.post("/{space_id}/urls", status_code=201)
async def add_space_url(space_id: str, body: UrlIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_space(space_id, chat_id)
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

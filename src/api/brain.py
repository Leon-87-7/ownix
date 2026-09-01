"""HTTP endpoints for the Second Brain (links search and graph rebuild)."""

from __future__ import annotations

# Scoping note (confirmed): /search, /graph, /links, and /rebuild intentionally
# return the single shared Second Brain link graph, not a per-user view — the
# Second Brain is one operator-wide knowledge graph (see docs/seed/PRD.md §5).
# Only /links/view (display preferences, not data) is scoped per-user.

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from src import brain, database
from src.intake import rate_limit
from src.utils.logger import get_logger

log = get_logger(__name__)

brain_router = APIRouter(prefix="/api/brain", tags=["brain"])


class BrainLinksViewIn(BaseModel):
    # Server clamps every value in set_brain_links_view; this is just typed parsing.
    order: str
    size: int


@brain_router.get("/search")
async def search_links(q: str = Query(..., max_length=300), k: int = Query(default=5, ge=1, le=20)) -> list[dict]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty")
    return await brain.search_links(q.strip(), top_k=k)


@brain_router.get("/graph")
async def get_graph() -> dict[str, list[dict]]:
    return await brain.get_graph()


@brain_router.get("/links")
async def list_links(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default="", max_length=300),
    order: str = Query(default="desc"),
    pinned: bool = Query(default=False),
) -> dict:
    # Link inventory stays operator-wide; tag matching/payload is viewer-private.
    return await brain.list_links(
        limit=limit,
        offset=offset,
        q=q,
        order=order,
        viewer_chat_id=request.state.user["id"],
        pinned_only=pinned,
    )


@brain_router.get("/links/{link_id}/preview")
async def get_link_preview(link_id: str) -> dict:
    preview = await brain.get_link_preview(link_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return preview


@brain_router.get("/links/{link_id}/preview/image")
async def get_link_preview_image(link_id: str) -> Response:
    """Serve a resolved OG image from our origin when external hosts reject hotlinking."""
    from src.utils.public_html import fetch_public_image

    preview = await brain.get_link_preview(link_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Link not found")
    image_url = preview.get("og_image_url")
    if not isinstance(image_url, str) or not image_url:
        raise HTTPException(status_code=404, detail="Preview image not found")
    image = await fetch_public_image(image_url)
    if image is None:
        raise HTTPException(status_code=404, detail="Preview image unavailable")
    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@brain_router.delete("/links/{link_id}", status_code=204)
async def delete_link(link_id: str, request: Request) -> Response:
    # Deletion is scoped to the owning tenant even though reads above are not:
    # ADR-0043 §Context names "one tenant's delete removes another's link" as a
    # bug to close, and a destructive endpoint on an enumerable ID is a worse
    # failure than a shared read. 404 (not 403) so a miss can't confirm the row.
    chat_id: int = request.state.user["id"]
    if not await database.delete_link(link_id, chat_id):
        raise HTTPException(status_code=404, detail="Link not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Link-tag links
# ---------------------------------------------------------------------------


@brain_router.get("/links/{link_id}/tags")
async def get_link_tags(link_id: str, request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    return await database.list_link_tags(link_id, chat_id=chat_id)


@brain_router.post("/links/{link_id}/tags/{tag_id}", status_code=201)
async def attach_link_tag(link_id: str, tag_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    tag = await database.get_tag(chat_id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    try:
        await database.attach_link_tag(link_id, tag_id)
    except Exception as exc:
        # FK violation — the link row doesn't exist.
        raise HTTPException(status_code=404, detail="Link not found") from exc
    return {
        "id": tag["id"],
        "name": tag["name"],
        "color": tag["color"],
        "meaning": tag["meaning"],
        "icon": tag.get("icon"),
    }


@brain_router.delete("/links/{link_id}/tags/{tag_id}", status_code=204)
async def detach_link_tag(link_id: str, tag_id: str, request: Request):
    chat_id: int = request.state.user["id"]
    tag = await database.get_tag(chat_id, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    deleted = await database.detach_link_tag(link_id, tag_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tag not attached to this link")
    return Response(status_code=204)


@brain_router.get("/links/view")
async def get_links_view(request: Request) -> dict[str, int | str]:
    chat_id: int = request.state.user["id"]
    return await database.get_brain_links_view(chat_id)


@brain_router.put("/links/view")
async def update_links_view(body: BrainLinksViewIn, request: Request) -> dict[str, int | str]:
    chat_id: int = request.state.user["id"]
    return await database.set_brain_links_view(
        chat_id,
        order=body.order,
        size=body.size,
    )


@brain_router.post("/rebuild")
async def rebuild_graph() -> dict[str, int]:
    # Shared operator-wide resource (see scoping note above) — one key for
    # every caller, not per-user.
    rate_limit.enforce("brain_rebuild", max_requests=3, window_seconds=60)
    try:
        n = await brain.rebuild_graph()
        return {"nodes": n}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

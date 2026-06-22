"""HTTP endpoints for the Second Brain (links search and graph rebuild)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src import brain
from src.utils.logger import get_logger

log = get_logger(__name__)

brain_router = APIRouter(prefix="/api/brain", tags=["brain"])


@brain_router.get("/search")
async def search_links(q: str = Query(...), k: int = Query(default=5, le=20)) -> list[dict]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty")
    return await brain.search_links(q.strip(), top_k=k)


@brain_router.get("/graph")
async def get_graph() -> dict[str, list[dict]]:
    return await brain.get_graph()


@brain_router.post("/rebuild")
async def rebuild_graph() -> dict[str, int]:
    try:
        n = await brain.rebuild_graph()
        return {"nodes": n}
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))

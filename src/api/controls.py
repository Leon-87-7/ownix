"""HTTP endpoints for user Controls (tags CRUD — issue #87; domain lists — issue #91)."""
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src import database
from src.utils.logger import get_logger

log = get_logger(__name__)

controls_router = APIRouter(prefix="/api/controls", tags=["controls"])


class TagIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    meaning: str = Field(default="", max_length=500)
    color: str = Field(default="#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=80)


class DomainIn(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253)


class RecoverySettingsIn(BaseModel):
    telegram_notifications: bool


def _normalize_domain(raw: str) -> str:
    """Strip to hostname, lowercase, drop www. prefix."""
    s = raw.strip()
    if "://" not in s:
        s = "https://" + s
    host = urlparse(s).hostname or ""
    return host.lower().removeprefix("www.")


@controls_router.get("/tags")
async def list_tags(request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    return await database.list_tags(chat_id)


@controls_router.post("/tags", status_code=201)
async def create_tag(body: TagIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    try:
        return await database.create_tag(
            chat_id=chat_id, name=body.name.strip(), meaning=body.meaning, color=body.color, icon=body.icon
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Tag name already exists")
        raise


@controls_router.put("/tags/{tag_id}")
async def update_tag(tag_id: str, body: TagIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    ok = await database.update_tag(
        chat_id=chat_id, tag_id=tag_id, name=body.name.strip(), meaning=body.meaning, color=body.color, icon=body.icon
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"id": tag_id, "name": body.name, "meaning": body.meaning, "color": body.color, "icon": body.icon}


@controls_router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    ok = await database.delete_tag(chat_id=chat_id, tag_id=tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")


# ---------------------------------------------------------------------------
# Allowed domains
# ---------------------------------------------------------------------------

@controls_router.get("/allowed-domains")
async def list_allowed_domains(request: Request) -> list[str]:
    chat_id: int = request.state.user["id"]
    domains = await database.list_allowed_domains(chat_id)
    return sorted(domains)


@controls_router.post("/allowed-domains", status_code=201)
async def add_allowed_domain(body: DomainIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    domain = _normalize_domain(body.domain)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid domain: normalization produced an empty string")
    inserted = await database.add_allowed_domain(chat_id, domain)
    if not inserted:
        raise HTTPException(status_code=409, detail="Domain already exists")
    return {"domain": domain}


@controls_router.delete("/allowed-domains/{domain}", status_code=204)
async def remove_allowed_domain(domain: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    normalized = _normalize_domain(domain)
    ok = await database.remove_allowed_domain(chat_id, normalized)
    if not ok:
        raise HTTPException(status_code=404, detail="Domain not found")


# ---------------------------------------------------------------------------
# Ignored domains
# ---------------------------------------------------------------------------

@controls_router.get("/ignored-domains")
async def list_ignored_domains(request: Request) -> list[str]:
    chat_id: int = request.state.user["id"]
    domains = await database.get_ignored_domains(chat_id)
    return sorted(domains)


@controls_router.post("/ignored-domains", status_code=201)
async def add_ignored_domain(body: DomainIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    domain = _normalize_domain(body.domain)
    if not domain:
        raise HTTPException(status_code=422, detail="Invalid domain: normalization produced an empty string")
    inserted = await database.add_ignored_domain(chat_id, domain)
    if not inserted:
        raise HTTPException(status_code=409, detail="Domain already exists")
    return {"domain": domain}


@controls_router.delete("/ignored-domains/{domain}", status_code=204)
async def remove_ignored_domain(domain: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    normalized = _normalize_domain(domain)
    ok = await database.remove_ignored_domain(chat_id, normalized)
    if not ok:
        raise HTTPException(status_code=404, detail="Domain not found")


@controls_router.get("/recovery-settings")
async def get_recovery_settings(request: Request) -> dict[str, bool]:
    chat_id: int = request.state.user["id"]
    enabled = await database.get_recovery_telegram_notifications_enabled(chat_id)
    return {"telegram_notifications": enabled}


@controls_router.put("/recovery-settings")
async def update_recovery_settings(body: RecoverySettingsIn, request: Request) -> dict[str, bool]:
    chat_id: int = request.state.user["id"]
    await database.set_recovery_telegram_notifications_enabled(
        chat_id, body.telegram_notifications
    )
    return {"telegram_notifications": body.telegram_notifications}

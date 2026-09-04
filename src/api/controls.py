"""HTTP endpoints for user Controls (tags CRUD — issue #87; domain lists — issue #91)."""
from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from src import database
from src.utils.logger import get_logger
from src.utils.validators import is_valid_domain_name

log = get_logger(__name__)

controls_router = APIRouter(prefix="/api/controls", tags=["controls"])


TagIcon = Literal[
    "Brain", "Code2", "Database", "PackageOpen", "FileText", "Globe", "Lightbulb", "Link2",
    "Cog", "HatGlasses", "Heart", "Paintbrush", "BookOpen", "Wrench", "Video", "Container",
    # Retired from the icon picker (web/components/ui/tag-picker.tsx) but still
    # accepted so a tag created with one of these keeps validating on update —
    # editing name/color shouldn't 422 just because the icon field wasn't touched.
    "PawPrint", "ChessPawn", "Anvil", "Brush",
]


class TagIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    meaning: str = Field(default="", max_length=500)
    color: str = Field(default="#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: TagIcon | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value


class DomainIn(BaseModel):
    domain: str = Field(..., min_length=1, max_length=253)


class RecoverySettingsIn(BaseModel):
    telegram_notifications: bool


class AccessibilitySettingsIn(BaseModel):
    visual_motion: bool
    haptic_motion: bool
    voice_uri: str | None = Field(max_length=512)


def _normalize_domain(raw: str) -> str:
    """Strip to hostname, lowercase, drop www. prefix."""
    s = raw.strip()
    if "://" not in s:
        s = "https://" + s
    host = urlparse(s).hostname or ""
    return host.lower().removeprefix("www.").rstrip(".")


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
    except database.TagTokenCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Tag name already exists")
        raise


@controls_router.put("/tags/{tag_id}")
async def update_tag(tag_id: str, body: TagIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    try:
        ok = await database.update_tag(
            chat_id=chat_id, tag_id=tag_id, name=body.name.strip(), meaning=body.meaning, color=body.color, icon=body.icon
        )
    except database.TagTokenCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"id": tag_id, "name": body.name, "meaning": body.meaning, "color": body.color, "icon": body.icon}


@controls_router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(tag_id: str, request: Request) -> None:
    chat_id: int = request.state.user["id"]
    ok = await database.delete_tag(chat_id=chat_id, tag_id=tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tag not found")


@controls_router.post("/tags/{tag_id}/pin")
async def pin_tag(tag_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    tag = await database.set_tag_pinned(chat_id=chat_id, tag_id=tag_id, pinned=True)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@controls_router.delete("/tags/{tag_id}/pin")
async def unpin_tag(tag_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    tag = await database.set_tag_pinned(chat_id=chat_id, tag_id=tag_id, pinned=False)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


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
    if not is_valid_domain_name(domain):
        raise HTTPException(status_code=422, detail="Invalid domain")
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
    if not is_valid_domain_name(domain):
        raise HTTPException(status_code=422, detail="Invalid domain")
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


@controls_router.get("/accessibility-settings")
async def get_accessibility_settings(request: Request) -> dict[str, bool | str | None]:
    chat_id: int = request.state.user["id"]
    return await database.get_accessibility_settings(chat_id)


@controls_router.put("/accessibility-settings")
async def update_accessibility_settings(
    body: AccessibilitySettingsIn, request: Request
) -> dict[str, bool | str | None]:
    chat_id: int = request.state.user["id"]
    return await database.set_accessibility_settings(
        chat_id,
        visual_motion=body.visual_motion,
        haptic_motion=body.haptic_motion,
        voice_uri=body.voice_uri,
    )

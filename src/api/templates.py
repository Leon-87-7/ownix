"""HTTP endpoints for user-defined enrichment templates (issue #90)."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from src import database
from src.templates import PROMPT_TEMPLATES
from src.utils.logger import get_logger

log = get_logger(__name__)

templates_router = APIRouter(prefix="/api/templates", tags=["templates"])

_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


class TemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=500)
    extra_instructions: str = Field(default="", max_length=4000)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not _NAME_RE.match(v):
            raise ValueError("name must be lowercase alphanumeric, hyphens, or underscores only")
        if v.startswith("-") or v.startswith("/"):
            raise ValueError("name must not start with '-' or '/'")
        return v


class TemplateUpdateIn(BaseModel):
    description: str = Field(default="", max_length=500)
    extra_instructions: str = Field(default="", max_length=4000)


def _builtin_to_dict(name: str) -> dict:
    tmpl = PROMPT_TEMPLATES[name]
    return {
        "id": f"builtin:{name}",
        "name": name,
        "description": tmpl.description,
        "extra_instructions": tmpl.extra_instructions,
        "trigger_patterns": ",".join(tmpl.trigger_patterns),
        "brave_search": tmpl.brave_search,
        "content_type_scope": "",
        "is_builtin": True,
    }


@templates_router.get("")
async def list_templates(request: Request) -> list[dict]:
    """Return all templates: built-ins first (is_builtin=True), then caller's user templates."""
    chat_id: int = request.state.user["id"]
    builtins = [_builtin_to_dict(name) for name in PROMPT_TEMPLATES]
    user_templates = await database.list_user_templates(chat_id)
    for t in user_templates:
        t["is_builtin"] = False
    return builtins + user_templates


@templates_router.post("", status_code=201)
async def create_template(body: TemplateIn, request: Request) -> dict:
    """Create a user-defined template. Returns 409 on name collision."""
    chat_id: int = request.state.user["id"]
    if body.name in PROMPT_TEMPLATES:
        raise HTTPException(status_code=409, detail="Name collides with a built-in template")

    try:
        result = await database.create_user_template(
            chat_id=chat_id,
            name=body.name,
            description=body.description,
            extra_instructions=body.extra_instructions,
        )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(status_code=409, detail="Template name already exists")
        raise

    result["is_builtin"] = False
    return result


def _require_user_template(name: str, action: str) -> str:
    """Lowercase *name*; 403 if it names a built-in template."""
    name_lower = name.lower()
    if name_lower in PROMPT_TEMPLATES:
        raise HTTPException(status_code=403, detail=f"Cannot {action} a built-in template")
    return name_lower


@templates_router.put("/{name}")
async def update_template(name: str, body: TemplateUpdateIn, request: Request) -> dict:
    """Update a user-defined template. Returns 403 for built-ins, 404 if not found."""
    chat_id: int = request.state.user["id"]
    name_lower = _require_user_template(name, "modify")

    ok = await database.update_user_template(
        chat_id=chat_id,
        name=name_lower,
        description=body.description,
        extra_instructions=body.extra_instructions,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")

    row = await database.get_user_template_by_name(chat_id, name_lower)
    row["is_builtin"] = False
    return row


@templates_router.delete("/{name}", status_code=204)
async def delete_template(name: str, request: Request) -> None:
    """Delete a user-defined template. Returns 403 for built-ins, 404 if not found."""
    chat_id: int = request.state.user["id"]
    name_lower = _require_user_template(name, "delete")

    ok = await database.delete_user_template(chat_id, name_lower)
    if not ok:
        raise HTTPException(status_code=404, detail="Template not found")

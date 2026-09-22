"""In-process MCP Gardener server for tenant-owned Brain links and Spaces.

Phase 1 (cleanup): list_items, get_item_detail, delete_item, list_tags.
Phase 2 (connection-finding): find_related.
Phase 3 (scouting): scout, get_scout_settings.
Phase 4 (space curation): list_spaces, get_space_detail, create_space,
update_space, delete_space, add_space_url, remove_space_url,
reorder_space_url, create_context_blob, update_context_blob,
delete_context_blob, reorder_context_blob. See docs/mcp-roadmap.md and
ADR-0063 (pin-existing-jobs-only, no blob concurrency guard).
"""

from __future__ import annotations

import asyncio
import functools
import re
from contextvars import ContextVar, Token
from typing import Any
from urllib.parse import urlparse

import aiosqlite
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from src import brain, database
from src.api.spaces import SpaceIcon
from src.config import settings
from src.intake import rate_limit
from src.services.link_health import check_link

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_current_chat_id: ContextVar[int | None] = ContextVar("mcp_chat_id", default=None)
_HEALTH_CHECK_CONCURRENCY = 10


class McpIdentityMiddleware:
    """Carry the chat id resolved by SessionMiddleware into MCP tool calls.

    `src.auth.middleware.SessionMiddleware` sets `request.state.user`, which
    Starlette backs with the same dict as `scope["state"]` — that's the
    contract this reads. Keep both middlewares' user shape (`{"id", "auth"}`
    at minimum) in sync if either changes.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        user = scope.get("state", {}).get("user")
        value = int(user["id"]) if user and user.get("auth") == "mcp_token" else None
        token: Token[int | None] = _current_chat_id.set(value)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_chat_id.reset(token)


def _chat_id() -> int:
    chat_id = _current_chat_id.get()
    if chat_id is None:
        raise ToolError("Not authenticated")
    return chat_id


def _validate_name(name: str, max_length: int) -> str:
    name = name.strip()
    if not name or len(name) > max_length:
        raise ToolError(f"Name must be 1-{max_length} characters")
    return name


def _validate_color(color: str) -> None:
    if not _COLOR_RE.match(color):
        raise ToolError("Color must be a #RRGGBB hex string")


def _validate_content(content: str) -> None:
    if len(content) > 20_000:
        raise ToolError("Content must be at most 20000 characters")


def _require_confirm(confirm: bool, action: str) -> None:
    if confirm is not True:
        raise ToolError(f"{action} requires confirm=true")


async def _owned_space(space_id: str, chat_id: int) -> dict[str, Any]:
    space = await database.get_space(space_id)
    if space is None or space["chat_id"] != chat_id:
        raise ToolError("Space not found")
    return space


async def _owned_blob(blob_id: str, space_id: str) -> dict[str, Any]:
    blob = await database.get_context_blob(blob_id)
    if blob is None or blob["space_id"] != space_id:
        raise ToolError("Blob not found")
    return blob


async def _with_health(item: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(item)
    try:
        enriched["health"] = await check_link(item["url"])
    except Exception:  # noqa: BLE001 — one bad link must not fail the whole list
        enriched["health"] = {
            "status": "transient_failure",
            "http_status": None,
            "reason": "fetch_failure",
        }
    return enriched


def _allowed_hosts() -> list[str]:
    """Localhost (dev/tests) plus the real API host, from WEBHOOK_URL.

    FastMCP's DNS-rebinding guard 421s any Host header not in this list;
    left at the SDK default (localhost only) it would reject every request
    that arrives through the real domain/Cloudflare tunnel. A `:*`-suffixed
    entry only matches a header that literally starts with `host:` — a
    standard HTTPS request omits the default port, sending a bare
    `Host: api.leondev.xyz` — so the bare hostname must be listed too.
    """
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    webhook_host = urlparse(settings.WEBHOOK_URL).hostname
    if webhook_host:
        hosts.append(webhook_host)
        hosts.append(f"{webhook_host}:*")
    return hosts


mcp = FastMCP(
    "Ownix",
    instructions=(
        "Inspect and deliberately delete links in the caller's private Index. "
        "Manage the caller's Spaces (named collections of jobs plus context "
        "blobs): obtain the caller's conversational approval before calling "
        "any confirm-gated write tool. Reorder tools execute immediately and "
        "do not accept confirm."
    ),
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(allowed_hosts=_allowed_hosts()),
)


def _tool(**tool_kwargs: Any) -> Any:
    """`@mcp.tool` plus the per-chat MCP rate limit, enforced before every call.

    `functools.wraps` keeps `__wrapped__`, so `inspect.signature` (what FastMCP
    uses to build the client-facing schema) still resolves to the wrapped
    function — the tool's declared parameters are unaffected.
    """

    def decorator(fn: Any) -> Any:
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(f"_tool only supports async tool functions, got sync {fn.__name__!r}")

        @functools.wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            rate_limit.enforce(f"mcp_tools:{_chat_id()}", max_requests=60)
            return await fn(*args, **kwargs)

        return mcp.tool(**tool_kwargs)(wrapped)

    return decorator


@_tool(name="list_items")
async def list_items(
    limit: int = 50, offset: int = 0, q: str = "", order: str = "desc"
) -> dict[str, Any]:
    """List the caller's Brain links, with a fresh reachability signal for each.

    Each item carries `drive_url` — the link's own Obsidian note in Drive, or
    null if it hasn't been uploaded yet.
    """
    chat_id = _chat_id()
    if not 1 <= limit <= 100 or offset < 0 or len(q) > 300 or order not in {"asc", "desc"}:
        raise ToolError("Invalid pagination or search parameters")
    result = await brain.list_links(
        limit=limit, offset=offset, q=q, order=order, viewer_chat_id=chat_id, owner_chat_id=chat_id
    )
    semaphore = asyncio.Semaphore(_HEALTH_CHECK_CONCURRENCY)

    async def _checked(item: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _with_health(item)

    items = await asyncio.gather(*(_checked(item) for item in result["items"]))
    return {**result, "items": items}


@_tool(name="list_tags")
async def list_tags() -> dict[str, Any]:
    """List the caller's tags, each with `job_count` — how many of their jobs
    carry it (jobs + swept-to-link jobs, deduped; see `count_jobs_by_tag`).
    A tag with `job_count: 0` has no job attached, only links (or nothing).
    """
    chat_id = _chat_id()
    tags, counts = await asyncio.gather(
        database.list_tags(chat_id), database.count_jobs_by_tag(chat_id)
    )
    return {"items": [{**tag, "job_count": counts.get(tag["id"], 0)} for tag in tags]}


@_tool(name="get_item_detail")
async def get_item_detail(link_id: str) -> dict[str, Any]:
    """Get one caller-owned Brain link and its fresh reachability signal.

    Carries `drive_url` — the link's own Obsidian note in Drive, or null if
    it hasn't been uploaded yet.
    """
    chat_id = _chat_id()
    item = await brain.get_owned_link_detail(link_id, chat_id)
    if item is None:
        raise ToolError("Link not found")
    return await _with_health(item)


@_tool(name="find_related")
async def find_related(link_id: str) -> dict[str, Any]:
    """Up to 3 links from the caller's own Brain most semantically related to one link."""
    chat_id = _chat_id()
    related = await brain.find_related_links(link_id, chat_id)
    if related is None:
        raise ToolError("Link not found")
    return {"items": related}


@_tool(name="delete_item")
async def delete_item(link_id: str, confirm: bool = False) -> dict[str, Any]:
    """Hard-delete exactly one link. Set confirm=true to perform the irreversible delete."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Deletion")
    if not await database.delete_link(link_id, chat_id):
        raise ToolError("Link not found")
    return {"deleted": True, "id": link_id}


@_tool(name="get_scout_settings")
async def get_scout_settings() -> dict[str, Any]:
    """Whether the caller has opted in to autonomous scouting.

    Check this before searching the Brain unprompted. If false, only call
    `scout` when the user explicitly asks you to check their saved items.
    """
    chat_id = _chat_id()
    enabled = await database.get_scout_autonomous_enabled(chat_id)
    return {"autonomous_enabled": enabled}


@_tool(name="scout")
async def scout(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the caller's own Brain and jobs for items relevant to `query`.

    `jobs` results also match `query` against an exact tag name (e.g.
    "CTIU"), alongside the title/url substring match — `items` stays
    semantic-only (use `list_items` with a tag name for exact link matches).

    Reuse, not accumulation: this only surfaces what's already saved. Always
    fine to call when the user explicitly asks; see `get_scout_settings`
    before calling it on your own initiative. `jobs` entries carry a real
    job `id` — pin them straight into a Space with `add_space_url`. `items`
    entries are Brain-graph mentions; their `id` is not a job id and can't be
    pinned directly.
    """
    chat_id = _chat_id()
    if not query.strip() or len(query) > 300 or not 1 <= top_k <= 20:
        raise ToolError("Invalid query or top_k")
    items, jobs = await asyncio.gather(
        brain.search_links_scoped(query, chat_id, top_k=top_k),
        brain.search_jobs_scoped(query, chat_id, top_k=top_k),
    )
    return {"items": items, "jobs": jobs}


@_tool(name="list_spaces")
async def list_spaces() -> dict[str, Any]:
    """List the caller's Spaces — named collections of jobs plus context blobs."""
    chat_id = _chat_id()
    return {"items": await database.list_spaces(chat_id)}


@_tool(name="get_space_detail")
async def get_space_detail(space_id: str) -> dict[str, Any]:
    """One Space with its pinned jobs and context blobs.

    Each pinned job carries `drive_url` — its enrichment doc in Drive, or
    null if the job never produced one.
    """
    chat_id = _chat_id()
    space = await _owned_space(space_id, chat_id)
    urls = await database.list_space_urls(space_id, chat_id)
    blobs = await database.list_context_blobs(space_id)
    return {"space": space, "urls": urls, "blobs": blobs}


@_tool(name="create_space")
async def create_space(
    name: str, color: str = "#6366f1", icon: SpaceIcon = "folder", confirm: bool = False
) -> dict[str, Any]:
    """Create a new Space. Set confirm=true to perform the write."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Creating a space")
    name = _validate_name(name, 120)
    _validate_color(color)
    try:
        return await database.create_space(chat_id=chat_id, name=name, color=color, icon=icon)
    except aiosqlite.IntegrityError:
        raise ToolError("Space name already exists")


@_tool(name="update_space")
async def update_space(
    space_id: str,
    name: str,
    color: str | None = None,
    icon: SpaceIcon | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Rename/recolor/re-icon a Space. Omit color/icon to leave them unchanged. Set confirm=true."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Updating a space")
    await _owned_space(space_id, chat_id)
    name = _validate_name(name, 120)
    if color is not None:
        _validate_color(color)
    try:
        updated = await database.update_space(
            chat_id=chat_id, space_id=space_id, name=name, color=color, icon=icon
        )
    except aiosqlite.IntegrityError:
        raise ToolError("Space name already exists")
    if not updated:
        raise ToolError("Space not found")
    return await database.get_space(space_id)


@_tool(name="delete_space")
async def delete_space(space_id: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a Space — unpins jobs and cascades to context blobs. Set confirm=true."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Deletion")
    await _owned_space(space_id, chat_id)
    await database.delete_space(chat_id=chat_id, space_id=space_id)
    return {"deleted": True, "id": space_id}


@_tool(name="add_space_url")
async def add_space_url(space_id: str, job_id: str, confirm: bool = False) -> dict[str, Any]:
    """Pin an existing job into a Space. Set confirm=true. Never creates a new job — see ADR-0063."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Adding a URL")
    await _owned_space(space_id, chat_id)
    job = await database.get_job(job_id)
    if job is None or job["chat_id"] != chat_id:
        raise ToolError("Job not found")
    await database.add_space_url(space_id=space_id, job_id=job_id)
    return {"space_id": space_id, "job_id": job_id}


@_tool(name="remove_space_url")
async def remove_space_url(space_id: str, job_id: str, confirm: bool = False) -> dict[str, Any]:
    """Unpin a job from a Space. Set confirm=true."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Removing a URL")
    await _owned_space(space_id, chat_id)
    if not await database.remove_space_url(space_id=space_id, job_id=job_id):
        raise ToolError("URL not in space")
    return {"space_id": space_id, "job_id": job_id, "removed": True}


@_tool(name="reorder_space_url")
async def reorder_space_url(space_id: str, job_id: str, new_sort_order: int) -> dict[str, Any]:
    """Reorder a pinned job within a Space. Not confirm-gated — reordering is reversible."""
    chat_id = _chat_id()
    await _owned_space(space_id, chat_id)
    if not await database.reorder_space_url(
        space_id=space_id, job_id=job_id, new_sort_order=new_sort_order
    ):
        raise ToolError("URL not in space")
    return {"space_id": space_id, "job_id": job_id, "sort_order": new_sort_order}


@_tool(name="create_context_blob")
async def create_context_blob(
    space_id: str, name: str, content: str = "", confirm: bool = False
) -> dict[str, Any]:
    """Create a context blob (editorial note) in a Space. Set confirm=true."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Creating a context blob")
    await _owned_space(space_id, chat_id)
    name = _validate_name(name, 200)
    _validate_content(content)
    return await database.create_context_blob(space_id=space_id, name=name, content=content)


@_tool(name="update_context_blob")
async def update_context_blob(
    space_id: str, blob_id: str, name: str, content: str, confirm: bool = False
) -> dict[str, Any]:
    """Edit a context blob's name/content. Set confirm=true. Last write wins — see ADR-0063."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Editing a context blob")
    await _owned_space(space_id, chat_id)
    await _owned_blob(blob_id, space_id)
    name = _validate_name(name, 200)
    _validate_content(content)
    if not await database.update_context_blob(blob_id=blob_id, name=name, content=content):
        raise ToolError("Blob not found")
    return await database.get_context_blob(blob_id)


@_tool(name="delete_context_blob")
async def delete_context_blob(
    space_id: str, blob_id: str, confirm: bool = False
) -> dict[str, Any]:
    """Delete a context blob. Set confirm=true."""
    chat_id = _chat_id()
    _require_confirm(confirm, "Deletion")
    await _owned_space(space_id, chat_id)
    await _owned_blob(blob_id, space_id)
    await database.delete_context_blob(blob_id)
    return {"deleted": True, "id": blob_id}


@_tool(name="reorder_context_blob")
async def reorder_context_blob(space_id: str, blob_id: str, new_sort_order: int) -> dict[str, Any]:
    """Reorder a context blob within a Space. Not confirm-gated."""
    chat_id = _chat_id()
    await _owned_space(space_id, chat_id)
    await _owned_blob(blob_id, space_id)
    if not await database.reorder_context_blob(blob_id=blob_id, new_sort_order=new_sort_order):
        raise ToolError("Blob not found")
    return {"space_id": space_id, "blob_id": blob_id, "sort_order": new_sort_order}


mcp_asgi_app = McpIdentityMiddleware(mcp.streamable_http_app())

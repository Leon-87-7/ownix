"""In-process MCP Gardener server for tenant-owned Brain links (Phase 1)."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar, Token
from typing import Any
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from src import brain, database
from src.config import settings
from src.intake import rate_limit
from src.services.link_health import check_link

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
    "Ownix Gardener",
    instructions="Inspect and deliberately delete links in the caller's private Index.",
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(allowed_hosts=_allowed_hosts()),
)


@mcp.tool(name="list_items")
async def list_items(
    limit: int = 50, offset: int = 0, q: str = "", order: str = "desc"
) -> dict[str, Any]:
    """List the caller's Brain links, with a fresh reachability signal for each."""
    chat_id = _chat_id()
    rate_limit.enforce(f"mcp_tools:{chat_id}", max_requests=60)
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


@mcp.tool(name="get_item_detail")
async def get_item_detail(link_id: str) -> dict[str, Any]:
    """Get one caller-owned Brain link and its fresh reachability signal."""
    chat_id = _chat_id()
    rate_limit.enforce(f"mcp_tools:{chat_id}", max_requests=60)
    item = await brain.get_owned_link_detail(link_id, chat_id)
    if item is None:
        raise ToolError("Link not found")
    return await _with_health(item)


@mcp.tool(name="delete_item")
async def delete_item(link_id: str, confirm: bool = False) -> dict[str, Any]:
    """Hard-delete exactly one link. Set confirm=true to perform the irreversible delete."""
    chat_id = _chat_id()
    rate_limit.enforce(f"mcp_tools:{chat_id}", max_requests=60)
    if confirm is not True:
        raise ToolError("Deletion requires confirm=true")
    if not await database.delete_link(link_id, chat_id):
        raise ToolError("Link not found")
    return {"deleted": True, "id": link_id}


mcp_asgi_app = McpIdentityMiddleware(mcp.streamable_http_app())

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException
from mcp.server.fastmcp.exceptions import ToolError

from src import mcp_server
from src.intake import rate_limit


@pytest.fixture(autouse=True)
def reset_rate_limit() -> None:
    rate_limit.reset()


@pytest.mark.asyncio
async def test_list_items_passes_tenant_scope_and_preserves_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_list_links(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {
            "items": [{"id": "a", "url": "https://ok"}, {"id": "b", "url": "https://slow"}],
            "total": 2,
            "limit": 2,
            "offset": 0,
        }

    async def fake_health(url: str) -> dict[str, Any]:
        status = "reachable" if url.endswith("ok") else "transient_failure"
        return {
            "status": status,
            "http_status": 200 if status == "reachable" else None,
            "reason": None if status == "reachable" else "timeout",
        }

    monkeypatch.setattr(mcp_server.brain, "list_links", fake_list_links)
    monkeypatch.setattr(mcp_server, "check_link", fake_health)
    token = mcp_server._current_chat_id.set(10)
    try:
        result = await mcp_server.list_items(limit=2)
    finally:
        mcp_server._current_chat_id.reset(token)

    assert seen["owner_chat_id"] == 10
    assert seen["viewer_chat_id"] == 10
    assert [item["health"]["status"] for item in result["items"]] == [
        "reachable",
        "transient_failure",
    ]


@pytest.mark.asyncio
async def test_detail_foreign_and_missing_are_same_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing(link_id: str, owner_chat_id: int) -> None:
        return None

    monkeypatch.setattr(mcp_server.brain, "get_owned_link_detail", missing)
    token = mcp_server._current_chat_id.set(20)
    try:
        with pytest.raises(ToolError, match="Link not found"):
            await mcp_server.get_item_detail("foreign-or-missing")
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_find_related_passes_tenant_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake_find_related(link_id: str, owner_chat_id: int) -> list[dict[str, Any]]:
        seen["link_id"] = link_id
        seen["owner_chat_id"] = owner_chat_id
        return [{"id": "b", "url": "https://b", "title": "B", "topic": "x", "score": 0.9}]

    monkeypatch.setattr(mcp_server.brain, "find_related_links", fake_find_related)
    token = mcp_server._current_chat_id.set(50)
    try:
        result = await mcp_server.find_related("a")
    finally:
        mcp_server._current_chat_id.reset(token)

    assert seen == {"link_id": "a", "owner_chat_id": 50}
    assert result == {"items": [{"id": "b", "url": "https://b", "title": "B", "topic": "x", "score": 0.9}]}


@pytest.mark.asyncio
async def test_find_related_foreign_and_missing_are_same_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing(link_id: str, owner_chat_id: int) -> None:
        return None

    monkeypatch.setattr(mcp_server.brain, "find_related_links", missing)
    token = mcp_server._current_chat_id.set(20)
    try:
        with pytest.raises(ToolError, match="Link not found"):
            await mcp_server.find_related("foreign-or-missing")
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_delete_requires_confirmation_and_deletes_only_explicit_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    async def delete(link_id: str, chat_id: int) -> bool:
        calls.append((link_id, chat_id))
        return True

    monkeypatch.setattr(mcp_server.database, "delete_link", delete)
    token = mcp_server._current_chat_id.set(30)
    try:
        with pytest.raises(ToolError, match="confirm=true"):
            await mcp_server.delete_item("only-this-one")
        assert calls == []
        assert await mcp_server.delete_item("only-this-one", confirm=True) == {
            "deleted": True,
            "id": "only-this-one",
        }
    finally:
        mcp_server._current_chat_id.reset(token)
    assert calls == [("only-this-one", 30)]


@pytest.mark.asyncio
async def test_auth_and_rate_limit_happen_before_data_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_list_links(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"items": [], "total": 0, "limit": 1, "offset": 0}

    monkeypatch.setattr(mcp_server.brain, "list_links", fake_list_links)
    with pytest.raises(ToolError, match="Not authenticated"):
        await mcp_server.list_items(limit=1)
    assert called is False

    token = mcp_server._current_chat_id.set(40)
    try:
        for _ in range(60):
            await mcp_server.list_items(limit=1)
        with pytest.raises(HTTPException) as exc:
            await mcp_server.list_items(limit=1)
        assert exc.value.status_code == 429
    finally:
        mcp_server._current_chat_id.reset(token)

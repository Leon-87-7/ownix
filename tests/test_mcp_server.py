from __future__ import annotations

from typing import Any

import aiosqlite
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
async def test_scout_passes_tenant_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake_search_links(query: str, owner_chat_id: int, top_k: int = 5) -> list[dict[str, Any]]:
        seen["links_query"] = query
        seen["links_owner_chat_id"] = owner_chat_id
        seen["links_top_k"] = top_k
        return [{"id": "a", "url": "https://a", "title": "A", "topic": "x", "score": 0.7}]

    async def fake_search_jobs(query: str, owner_chat_id: int, top_k: int = 5) -> list[dict[str, Any]]:
        seen["jobs_query"] = query
        seen["jobs_owner_chat_id"] = owner_chat_id
        seen["jobs_top_k"] = top_k
        return [{"id": "j1", "url": "https://b", "title": "B", "content_type": "link", "status": "done"}]

    monkeypatch.setattr(mcp_server.brain, "search_links_scoped", fake_search_links)
    monkeypatch.setattr(mcp_server.brain, "search_jobs_scoped", fake_search_jobs)
    token = mcp_server._current_chat_id.set(60)
    try:
        result = await mcp_server.scout("some task", top_k=3)
    finally:
        mcp_server._current_chat_id.reset(token)

    assert seen == {
        "links_query": "some task",
        "links_owner_chat_id": 60,
        "links_top_k": 3,
        "jobs_query": "some task",
        "jobs_owner_chat_id": 60,
        "jobs_top_k": 3,
    }
    assert result == {
        "items": [{"id": "a", "url": "https://a", "title": "A", "topic": "x", "score": 0.7}],
        "jobs": [{"id": "j1", "url": "https://b", "title": "B", "content_type": "link", "status": "done"}],
    }


@pytest.mark.asyncio
async def test_scout_rejects_blank_query(monkeypatch: pytest.MonkeyPatch) -> None:
    token = mcp_server._current_chat_id.set(60)
    try:
        with pytest.raises(ToolError, match="Invalid query"):
            await mcp_server.scout("   ")
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_get_scout_settings_reads_account_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_enabled(chat_id: int) -> bool:
        assert chat_id == 70
        return True

    monkeypatch.setattr(mcp_server.database, "get_scout_autonomous_enabled", fake_enabled)
    token = mcp_server._current_chat_id.set(70)
    try:
        result = await mcp_server.get_scout_settings()
    finally:
        mcp_server._current_chat_id.reset(token)

    assert result == {"autonomous_enabled": True}


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


def _space(chat_id: int, space_id: str = "sp1") -> dict[str, Any]:
    return {"id": space_id, "chat_id": chat_id, "name": "Reading", "color": "#6366f1", "icon": "folder"}


@pytest.mark.asyncio
async def test_list_spaces_scopes_by_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake_list_spaces(chat_id: int) -> list[dict[str, Any]]:
        seen["chat_id"] = chat_id
        return [_space(chat_id)]

    monkeypatch.setattr(mcp_server.database, "list_spaces", fake_list_spaces)
    token = mcp_server._current_chat_id.set(10)
    try:
        result = await mcp_server.list_spaces()
    finally:
        mcp_server._current_chat_id.reset(token)

    assert seen == {"chat_id": 10}
    assert result == {"items": [_space(10)]}


@pytest.mark.asyncio
async def test_get_space_detail_foreign_space_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=99, space_id=space_id)

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="Space not found"):
            await mcp_server.get_space_detail("sp1")
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_create_space_requires_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def fake_create(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return _space(10)

    monkeypatch.setattr(mcp_server.database, "create_space", fake_create)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="confirm=true"):
            await mcp_server.create_space(name="Reading")
        assert called is False
        result = await mcp_server.create_space(name="Reading", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert called is True
    assert result == _space(10)


@pytest.mark.asyncio
async def test_create_space_rejects_bad_name_and_color(monkeypatch: pytest.MonkeyPatch) -> None:
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="Name must be"):
            await mcp_server.create_space(name="   ", confirm=True)
        with pytest.raises(ToolError, match="hex string"):
            await mcp_server.create_space(name="Reading", color="not-a-color", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_create_space_duplicate_name_raises_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_create(**kwargs: Any) -> dict[str, Any]:
        raise aiosqlite.IntegrityError()

    monkeypatch.setattr(mcp_server.database, "create_space", fake_create)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="already exists"):
            await mcp_server.create_space(name="Reading", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_update_space_omitted_color_preserves_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_update(**kwargs: Any) -> bool:
        seen.update(kwargs)
        return True

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "update_space", fake_update)
    token = mcp_server._current_chat_id.set(10)
    try:
        await mcp_server.update_space("sp1", name="Renamed", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert seen["color"] is None
    assert seen["icon"] is None


@pytest.mark.asyncio
async def test_update_space_duplicate_name_raises_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_update(**kwargs: Any) -> bool:
        raise aiosqlite.IntegrityError()

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "update_space", fake_update)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="already exists"):
            await mcp_server.update_space("sp1", name="Taken", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_delete_space_requires_ownership_and_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted = False

    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=99, space_id=space_id)

    async def fake_delete(**kwargs: Any) -> bool:
        nonlocal deleted
        deleted = True
        return True

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "delete_space", fake_delete)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="confirm=true"):
            await mcp_server.delete_space("sp1")
        with pytest.raises(ToolError, match="Space not found"):
            await mcp_server.delete_space("sp1", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert deleted is False


@pytest.mark.asyncio
async def test_add_space_url_only_pins_existing_owned_job(monkeypatch: pytest.MonkeyPatch) -> None:
    pinned: list[tuple[str, str]] = []

    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_get_job(job_id: str) -> dict[str, Any] | None:
        return {"id": job_id, "chat_id": 99} if job_id == "foreign" else {"id": job_id, "chat_id": 10}

    async def fake_add(*, space_id: str, job_id: str) -> bool:
        pinned.append((space_id, job_id))
        return True

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "get_job", fake_get_job)
    monkeypatch.setattr(mcp_server.database, "add_space_url", fake_add)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="Job not found"):
            await mcp_server.add_space_url("sp1", "foreign", confirm=True)
        result = await mcp_server.add_space_url("sp1", "mine", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert pinned == [("sp1", "mine")]
    assert result == {"space_id": "sp1", "job_id": "mine"}


@pytest.mark.asyncio
async def test_reorder_space_url_is_not_confirm_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_reorder(**kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "reorder_space_url", fake_reorder)
    token = mcp_server._current_chat_id.set(10)
    try:
        result = await mcp_server.reorder_space_url("sp1", "job1", 2)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert result == {"space_id": "sp1", "job_id": "job1", "sort_order": 2}


@pytest.mark.asyncio
async def test_create_context_blob_rejects_oversize_content(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="at most 20000"):
            await mcp_server.create_context_blob("sp1", "Notes", content="x" * 20_001, confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_update_context_blob_requires_blob_belongs_to_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_get_blob(blob_id: str) -> dict[str, Any]:
        return {"id": blob_id, "space_id": "other-space", "name": "Old", "content": ""}

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "get_context_blob", fake_get_blob)
    token = mcp_server._current_chat_id.set(10)
    try:
        with pytest.raises(ToolError, match="Blob not found"):
            await mcp_server.update_context_blob("sp1", "blob1", "New", "content", confirm=True)
    finally:
        mcp_server._current_chat_id.reset(token)


@pytest.mark.asyncio
async def test_reorder_context_blob_is_not_confirm_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_space(space_id: str) -> dict[str, Any]:
        return _space(chat_id=10, space_id=space_id)

    async def fake_get_blob(blob_id: str) -> dict[str, Any]:
        return {"id": blob_id, "space_id": "sp1", "name": "Notes", "content": ""}

    async def fake_reorder(**kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(mcp_server.database, "get_space", fake_get_space)
    monkeypatch.setattr(mcp_server.database, "get_context_blob", fake_get_blob)
    monkeypatch.setattr(mcp_server.database, "reorder_context_blob", fake_reorder)
    token = mcp_server._current_chat_id.set(10)
    try:
        result = await mcp_server.reorder_context_blob("sp1", "blob1", 3)
    finally:
        mcp_server._current_chat_id.reset(token)
    assert result == {"space_id": "sp1", "blob_id": "blob1", "sort_order": 3}


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

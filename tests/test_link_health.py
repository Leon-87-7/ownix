from __future__ import annotations

import socket

import httpx
import pytest

from src.services.link_health import check_link


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 204, 403])
async def test_reachable_statuses(status: int) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await check_link("https://example.com", client=client))["status"] == "reachable"


@pytest.mark.asyncio
async def test_404_is_confirmed_dead() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await check_link("https://example.com/missing", client=client)
    assert result == {"status": "confirmed_dead", "http_status": 404, "reason": "not_found"}


@pytest.mark.asyncio
async def test_dns_failure_is_confirmed_dead() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        error = socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        raise httpx.ConnectError("dns", request=request) from error

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        result = await check_link("https://missing.invalid", client=client)
    assert result["status"] == "confirmed_dead"
    assert result["reason"] == "dns_failure"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "reason"),
    [("timeout", "timeout"), (429, "rate_limited"), (500, "server_error"), (503, "server_error")],
)
async def test_transient_failures_remain_distinct(outcome: str | int, reason: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if outcome == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(outcome, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await check_link("https://example.com", client=client)
    assert result["status"] == "transient_failure"
    assert result["reason"] == reason

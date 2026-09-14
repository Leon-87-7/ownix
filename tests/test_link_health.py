from __future__ import annotations

import httpx
import pytest

from src.services import link_health
from src.services.link_health import check_link

_PUBLIC_IP = "93.184.216.34"


def _mock_public_dns(monkeypatch: pytest.MonkeyPatch, ip: str = _PUBLIC_IP) -> None:
    """Stub `resolve_public_host` so tests exercise the mocked transport instead
    of real DNS — a blackholed resolver would otherwise cost seconds per case."""

    async def fake_resolve(_hostname: str) -> list:
        return [(2, 1, 6, "", (ip, 0))]

    monkeypatch.setattr(link_health, "resolve_public_host", fake_resolve)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 204, 403])
async def test_reachable_statuses(status: int, monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_public_dns(monkeypatch)
    transport = httpx.MockTransport(lambda request: httpx.Response(status, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await check_link("https://example.com", client=client))["status"] == "reachable"


@pytest.mark.asyncio
async def test_404_is_confirmed_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_public_dns(monkeypatch)
    transport = httpx.MockTransport(lambda request: httpx.Response(404, request=request))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await check_link("https://example.com/missing", client=client)
    assert result == {"status": "confirmed_dead", "http_status": 404, "reason": "not_found"}


@pytest.mark.asyncio
async def test_dns_failure_is_confirmed_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_resolve(_hostname: str) -> None:
        return None

    monkeypatch.setattr(link_health, "resolve_public_host", fake_resolve)
    result = await check_link("https://missing.invalid")
    assert result["status"] == "confirmed_dead"
    assert result["reason"] == "dns_failure"


@pytest.mark.asyncio
async def test_blocked_host_is_confirmed_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_public_dns(monkeypatch, ip="127.0.0.1")
    result = await check_link("https://localhost.example")
    assert result == {"status": "confirmed_dead", "http_status": None, "reason": "blocked_host"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "reason"),
    [("timeout", "timeout"), (429, "rate_limited"), (500, "server_error"), (503, "server_error")],
)
async def test_transient_failures_remain_distinct(
    outcome: str | int, reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_public_dns(monkeypatch)

    def respond(request: httpx.Request) -> httpx.Response:
        if outcome == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(outcome, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await check_link("https://example.com", client=client)
    assert result["status"] == "transient_failure"
    assert result["reason"] == reason

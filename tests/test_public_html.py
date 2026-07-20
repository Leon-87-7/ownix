"""Behavior tests for the hardened public-HTML fetch module."""

from __future__ import annotations

import pytest
import httpx

from src.utils.public_html import fetch_public_html


@pytest.mark.asyncio
async def test_fetch_public_html_blocks_redirect_to_loopback() -> None:
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(
            status_code=302,
            headers={"location": "http://127.0.0.1/admin"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_html("https://1.1.1.1/start", client=client)

    assert result is None
    assert requests == ["https://1.1.1.1/start"]


@pytest.mark.asyncio
async def test_fetch_public_html_caps_the_returned_document() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"x" * 200_000,
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_html("https://1.1.1.1/page", client=client)

    assert result is not None
    assert len(result.html.encode()) == 128_000


@pytest.mark.asyncio
async def test_fetch_public_html_rejects_declared_non_html_content() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.7",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_html("https://1.1.1.1/file", client=client)

    assert result is None

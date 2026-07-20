"""Behavior tests for the hardened public-HTML fetch module."""

from __future__ import annotations

import pytest
import httpx

from src.utils import public_html
from src.utils.public_html import fetch_public_html, fetch_public_image


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


@pytest.mark.asyncio
async def test_fetch_public_html_passes_sni_hostname_as_a_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_sni_hostname: object | None = None

    async def resolve(_url: str) -> tuple[str, str]:
        return "1.1.1.1", "example.com"

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal seen_sni_hostname
        seen_sni_hostname = request.extensions["sni_hostname"]
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html"},
            content=b"<html></html>",
            request=request,
        )

    monkeypatch.setattr(public_html, "_resolve_safe_public_url", resolve)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_html("https://example.com/page", client=client)

    assert result is not None
    assert seen_sni_hostname == "example.com"


@pytest.mark.asyncio
async def test_fetch_public_html_resolves_relative_redirects_from_the_original_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_urls: list[str] = []

    async def resolve(url: str) -> tuple[str, str]:
        resolved_urls.append(url)
        return "1.1.1.1", "example.com"

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(
                status_code=302,
                headers={"location": "/final"},
                request=request,
            )
        return httpx.Response(
            status_code=200,
            headers={"content-type": "text/html"},
            content=b"<html></html>",
            request=request,
        )

    monkeypatch.setattr(public_html, "_resolve_safe_public_url", resolve)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_html("https://example.com/start", client=client)

    assert result is not None
    assert resolved_urls == ["https://example.com/start", "https://example.com/final"]


@pytest.mark.asyncio
async def test_fetch_public_image_returns_allowed_image_bytes() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "image/png"},
            content=b"\x89PNG\r\n\x1a\nimage-bytes",
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await fetch_public_image("https://1.1.1.1/preview.png", client=client)

    assert result is not None
    assert result.content_type == "image/png"
    assert result.content == b"\x89PNG\r\n\x1a\nimage-bytes"

"""Unit tests for src/services/jina.py — Jina Reader markdown fetch."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

_FULL_PREAMBLE_RESPONSE = """Title: Building Scalable Web Apps

URL Source: https://example.com/article

Published Time: 2026-04-01T10:00:00Z

Markdown Content:
# Building Scalable Web Apps

Some real body content here.

More paragraphs of body.
"""


_NO_PUBLISHED_TIME_RESPONSE = """Title: Quick Note

URL Source: https://example.com/note

Markdown Content:
This is the article body without a Published Time line.
"""


_MARKDOWN_BODY_ONLY = """Markdown Content:
Body only — no title preamble line.
"""


_NO_PREAMBLE_RESPONSE = """# Bare Markdown

Body content with no Jina preamble at all.
"""


def _mock_response(status_code: int, text: str) -> httpx.Response:
    request = httpx.Request("GET", "https://r.jina.ai/test")
    return httpx.Response(status_code=status_code, text=text, request=request)


@pytest.mark.asyncio
async def test_fetch_markdown_strips_full_preamble():
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(200, _FULL_PREAMBLE_RESPONSE)),
    ):
        title, body = await jina.fetch_markdown("https://example.com/article")

    assert title == "Building Scalable Web Apps"
    # Body must not contain any preamble keys
    assert "Title:" not in body
    assert "URL Source:" not in body
    assert "Published Time:" not in body
    assert "Markdown Content:" not in body
    # Real body content is preserved
    assert "Some real body content here." in body
    assert "# Building Scalable Web Apps" in body


@pytest.mark.asyncio
async def test_fetch_markdown_handles_missing_published_time():
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(200, _NO_PUBLISHED_TIME_RESPONSE)),
    ):
        title, body = await jina.fetch_markdown("https://example.com/note")

    assert title == "Quick Note"
    assert "URL Source:" not in body
    assert "Markdown Content:" not in body
    assert "This is the article body" in body


@pytest.mark.asyncio
async def test_fetch_markdown_empty_title_when_no_title_line():
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(200, _MARKDOWN_BODY_ONLY)),
    ):
        title, body = await jina.fetch_markdown("https://example.com/whatever")

    assert title == ""
    assert "Body only" in body
    assert "Markdown Content:" not in body


@pytest.mark.asyncio
async def test_fetch_markdown_passthrough_when_no_preamble():
    """A response with no Jina preamble lines should be returned essentially unchanged."""
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(200, _NO_PREAMBLE_RESPONSE)),
    ):
        title, body = await jina.fetch_markdown("https://example.com/raw")

    assert title == ""
    assert "# Bare Markdown" in body
    assert "Body content with no Jina preamble" in body


@pytest.mark.asyncio
async def test_fetch_markdown_raises_typed_error_on_non_200():
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(500, "Internal Server Error")),
    ):
        with pytest.raises(jina.JinaFetchError) as exc_info:
            await jina.fetch_markdown("https://example.com/broken")

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_fetch_markdown_raises_typed_error_on_404():
    from src.services import jina

    with patch.object(
        httpx.AsyncClient,
        "get",
        new=AsyncMock(return_value=_mock_response(404, "Not Found")),
    ):
        with pytest.raises(jina.JinaFetchError) as exc_info:
            await jina.fetch_markdown("https://example.com/missing")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_markdown_sends_bearer_header_when_key_set(monkeypatch):
    """When settings.JINA_API_KEY is set, an Authorization Bearer header must be attached."""
    from src.services import jina

    monkeypatch.setattr("src.services.jina.settings.JINA_API_KEY", "test-key-123")
    captured_kwargs: dict = {}

    async def _fake_get(self, url, **kwargs):
        captured_kwargs.update(kwargs)
        captured_kwargs["url"] = url
        return _mock_response(200, _FULL_PREAMBLE_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", new=_fake_get):
        await jina.fetch_markdown("https://example.com/article")

    headers = captured_kwargs.get("headers") or {}
    assert headers.get("Authorization") == "Bearer test-key-123"
    assert headers.get("Accept") == "text/plain"
    # URL must be Jina Reader proxy + quoted target URL
    assert captured_kwargs["url"].startswith("https://r.jina.ai/")


@pytest.mark.asyncio
async def test_fetch_markdown_omits_bearer_header_when_key_absent(monkeypatch):
    from src.services import jina

    monkeypatch.setattr("src.services.jina.settings.JINA_API_KEY", "")
    captured_kwargs: dict = {}

    async def _fake_get(self, url, **kwargs):
        captured_kwargs.update(kwargs)
        return _mock_response(200, _FULL_PREAMBLE_RESPONSE)

    with patch.object(httpx.AsyncClient, "get", new=_fake_get):
        await jina.fetch_markdown("https://example.com/article")

    headers = captured_kwargs.get("headers") or {}
    assert "Authorization" not in headers
    assert headers.get("Accept") == "text/plain"


@pytest.mark.asyncio
async def test_fetch_markdown_uses_explicit_timeout(monkeypatch):
    """Jina Reader fetches can be slow, so use a timeout above httpx's 5s default."""
    from src.services import jina

    captured: dict = {}
    real_init = httpx.AsyncClient.__init__

    def spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        return real_init(self, *args, **kwargs)

    async def fake_get(self, url, headers=None):
        return _mock_response(200, "Title: T\n\nMarkdown Content:\nBody")

    monkeypatch.setattr(httpx.AsyncClient, "__init__", spy_init)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    await jina.fetch_markdown("https://example.com")

    assert captured.get("timeout") == 30

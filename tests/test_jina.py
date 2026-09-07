"""Unit tests for src/services/jina.py — Jina Reader streaming fetch."""

from __future__ import annotations

import pytest
import httpx

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


def _mock_client(respond) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(respond))


def _text_responder(status_code: int, text: str):
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, text=text, request=request)

    return respond


@pytest.mark.asyncio
async def test_fetch_markdown_strips_full_preamble():
    from src.services import jina

    async with _mock_client(_text_responder(200, _FULL_PREAMBLE_RESPONSE)) as client:
        title, body = await jina.fetch_markdown("https://example.com/article", client=client)

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

    async with _mock_client(_text_responder(200, _NO_PUBLISHED_TIME_RESPONSE)) as client:
        title, body = await jina.fetch_markdown("https://example.com/note", client=client)

    assert title == "Quick Note"
    assert "URL Source:" not in body
    assert "Markdown Content:" not in body
    assert "This is the article body" in body


@pytest.mark.asyncio
async def test_fetch_markdown_empty_title_when_no_title_line():
    from src.services import jina

    async with _mock_client(_text_responder(200, _MARKDOWN_BODY_ONLY)) as client:
        title, body = await jina.fetch_markdown("https://example.com/whatever", client=client)

    assert title == ""
    assert "Body only" in body
    assert "Markdown Content:" not in body


@pytest.mark.asyncio
async def test_fetch_markdown_passthrough_when_no_preamble():
    """A response with no Jina preamble lines should be returned essentially unchanged."""
    from src.services import jina

    async with _mock_client(_text_responder(200, _NO_PREAMBLE_RESPONSE)) as client:
        title, body = await jina.fetch_markdown("https://example.com/raw", client=client)

    assert title == ""
    assert "# Bare Markdown" in body
    assert "Body content with no Jina preamble" in body


@pytest.mark.asyncio
async def test_fetch_markdown_raises_typed_error_on_non_200():
    from src.services import jina

    async with _mock_client(_text_responder(500, "Internal Server Error")) as client:
        with pytest.raises(jina.JinaFetchError) as exc_info:
            await jina.fetch_markdown("https://example.com/broken", client=client)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_fetch_markdown_raises_typed_error_on_404():
    from src.services import jina

    async with _mock_client(_text_responder(404, "Not Found")) as client:
        with pytest.raises(jina.JinaFetchError) as exc_info:
            await jina.fetch_markdown("https://example.com/missing", client=client)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_markdown_sends_bearer_header_when_key_set(monkeypatch):
    """When settings.JINA_API_KEY is set, an Authorization Bearer header must be attached."""
    from src.services import jina

    monkeypatch.setattr("src.services.jina.settings.JINA_API_KEY", "test-key-123")
    captured: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, text=_FULL_PREAMBLE_RESPONSE, request=request)

    async with _mock_client(respond) as client:
        await jina.fetch_markdown("https://example.com/article", client=client)

    assert captured["headers"].get("authorization") == "Bearer test-key-123"
    assert captured["headers"].get("accept") == "text/plain"
    # URL must be Jina Reader proxy + quoted target URL
    assert captured["url"].startswith("https://r.jina.ai/")


@pytest.mark.asyncio
async def test_fetch_markdown_omits_bearer_header_when_key_absent(monkeypatch):
    from src.services import jina

    monkeypatch.setattr("src.services.jina.settings.JINA_API_KEY", "")
    captured: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, text=_FULL_PREAMBLE_RESPONSE, request=request)

    async with _mock_client(respond) as client:
        await jina.fetch_markdown("https://example.com/article", client=client)

    assert "authorization" not in captured["headers"]
    assert captured["headers"].get("accept") == "text/plain"


@pytest.mark.asyncio
async def test_fetch_markdown_uses_explicit_timeout(monkeypatch):
    """Jina Reader fetches can be slow, so use a timeout above httpx's 5s default."""
    from src.services import jina

    captured: dict = {}
    real_init = httpx.AsyncClient.__init__

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="Title: T\n\nMarkdown Content:\nBody", request=request)

    def spy_init(self, *args, **kwargs):
        captured.update(kwargs)
        kwargs["transport"] = httpx.MockTransport(respond)
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", spy_init)

    await jina.fetch_markdown("https://example.com")

    assert captured.get("timeout") == 30


@pytest.mark.asyncio
async def test_fetch_html_sends_return_format_header():
    from src.services import jina

    captured: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, text="<html><body>hi</body></html>", request=request)

    async with _mock_client(respond) as client:
        html = await jina.fetch_html("https://example.com/archive", client=client)

    assert html == "<html><body>hi</body></html>"
    assert captured["headers"].get("x-return-format") == "html"


@pytest.mark.asyncio
async def test_fetch_html_raises_typed_error_on_non_200():
    from src.services import jina

    async with _mock_client(_text_responder(404, "")) as client:
        with pytest.raises(jina.JinaFetchError) as exc_info:
            await jina.fetch_html("https://example.com/missing", client=client)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_raw_omits_return_format_header_by_default():
    from src.services import jina

    captured: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, text="body", request=request)

    async with _mock_client(respond) as client:
        await jina.fetch_raw("https://example.com/plain", client=client)

    assert "x-return-format" not in captured["headers"]


@pytest.mark.asyncio
async def test_fetch_raw_aborts_before_materialising_full_body(monkeypatch):
    """Streaming abort at 4 MB + 1: the helper must stop pulling chunks the
    moment the running total crosses the cap, rather than draining the whole
    (much larger) stream first."""
    from src.services import jina

    pulled = 0
    chunk = b"a" * 1000
    available_chunks = 5000  # 5 MB worth — comfortably more than the 4 MB cap

    class _FakeResponse:
        status_code = 200

        async def aiter_bytes(self):
            nonlocal pulled
            for _ in range(available_chunks):
                pulled += 1
                yield chunk

    class _FakeStreamCM:
        async def __aenter__(self):
            return _FakeResponse()

        async def __aexit__(self, *exc_info):
            return False

    def fake_stream(self, method, url, **kwargs):
        return _FakeStreamCM()

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    with pytest.raises(jina.JinaOversizeError) as exc_info:
        await jina.fetch_raw("https://example.com/huge")

    assert exc_info.value.url == "https://example.com/huge"
    assert exc_info.value.max_bytes == jina._MAX_JINA_BYTES
    # Must have stopped well short of draining the whole fake stream.
    assert pulled < available_chunks
    # The cap (4 MiB) is crossed after ~4195 1000-byte chunks; the abort must
    # fire at that boundary, not thousands of chunks later.
    expected_pull_count = jina._MAX_JINA_BYTES // len(chunk) + 1
    assert pulled == expected_pull_count


@pytest.mark.asyncio
async def test_fetch_raw_allows_body_exactly_at_cap():
    from src.services import jina

    body = b"x" * jina._MAX_JINA_BYTES

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, request=request)

    async with _mock_client(respond) as client:
        status_code, text = await jina.fetch_raw(
            "https://example.com/exact", client=client, max_bytes=jina._MAX_JINA_BYTES
        )

    assert status_code == 200
    assert len(text.encode("utf-8")) == jina._MAX_JINA_BYTES


@pytest.mark.asyncio
async def test_fetch_raw_does_not_read_body_on_non_200(monkeypatch):
    from src.services import jina

    read_called = False

    class _FakeResponse:
        status_code = 404

        async def aiter_bytes(self):
            nonlocal read_called
            read_called = True
            yield b"should never be read"

    class _FakeStreamCM:
        async def __aenter__(self):
            return _FakeResponse()

        async def __aexit__(self, *exc_info):
            return False

    def fake_stream(self, method, url, **kwargs):
        return _FakeStreamCM()

    monkeypatch.setattr(httpx.AsyncClient, "stream", fake_stream)

    status_code, text = await jina.fetch_raw("https://example.com/missing")

    assert status_code == 404
    assert text == ""
    assert read_called is False

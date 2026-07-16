"""Unit tests for src/telegram/sender.py -- no real network calls."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from src.telegram import sender


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict) -> None:
        self.status_code = status_code
        self._json = json_body
        self.is_error = status_code >= 400

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.is_error:
            request = httpx.Request("POST", "https://api.telegram.org/botX/sendMessage")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.posted: list[dict] = []

    async def post(self, url: str, **kwargs):  # noqa: ANN003
        self.posted.append(kwargs)
        return self._response


class _FakeGetResponse:
    def __init__(self, *, body: dict | None = None, content: bytes = b"") -> None:
        self.status_code = 200
        self._body = body or {"ok": True}
        self.content = content

    def json(self) -> dict:
        return self._body

    def raise_for_status(self) -> None:
        raise AssertionError("raise_for_status should not be called for 200 responses")


class _FakeGetClient:
    def __init__(self) -> None:
        self.get_calls: list[tuple[str, dict | None]] = []

    async def get(self, url: str, params: dict | None = None) -> _FakeGetResponse:
        self.get_calls.append((url, params))
        if len(self.get_calls) == 1:
            return _FakeGetResponse(body={"ok": True, "result": {"file_path": "photos/pic.png"}})
        return _FakeGetResponse(content=b"image-bytes")


@pytest.mark.asyncio
async def test_send_message_logs_telegram_error_description(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 400 must surface Telegram's `description` in the error log, then raise."""
    body = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: can't parse entities: can't find end of the entity starting at byte offset 3",
    }
    fake_resp = _FakeResponse(400, body)
    monkeypatch.setattr(sender, "_http", lambda: _FakeClient(fake_resp))
    fake_log = MagicMock()
    monkeypatch.setattr(sender, "log", fake_log)

    with pytest.raises(httpx.HTTPStatusError):
        await sender.send_message(123, "boom", parse_mode="HTML")

    assert fake_log.error.called, "expected an error log on HTTP failure"
    # The Telegram description must appear somewhere in the logged kwargs.
    logged = " ".join(repr(c.kwargs) for c in fake_log.error.call_args_list)
    assert "can't parse entities" in logged
    assert "400" in logged


@pytest.mark.asyncio
async def test_send_message_success_returns_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path is unchanged: returns the `result` field."""
    body = {"ok": True, "result": {"message_id": 42}}
    monkeypatch.setattr(sender, "_http", lambda: _FakeClient(_FakeResponse(200, body)))
    monkeypatch.setattr(sender, "log", MagicMock())

    result = await sender.send_message(123, "hi")
    assert result == {"message_id": 42}


@pytest.mark.asyncio
async def test_send_document_marks_markdown_as_utf8_and_normalizes_dashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Markdown uploads include a UTF-8 BOM and avoid Gemini typographic dashes."""
    body = {"ok": True, "result": {"document": {"file_name": "brief.md"}}}
    fake_client = _FakeClient(_FakeResponse(200, body))
    monkeypatch.setattr(sender, "_http", lambda: fake_client)
    monkeypatch.setattr(sender, "log", MagicMock())

    result = await sender.send_document(123, "A — B – C".encode("utf-8"), "brief.md")

    assert result == {"document": {"file_name": "brief.md"}}
    files = fake_client.posted[0]["files"]
    filename, payload, mime = files["document"]
    assert filename == "brief.md"
    assert mime == "text/markdown; charset=utf-8"
    assert payload.startswith(b"\xef\xbb\xbf")
    assert payload.decode("utf-8-sig") == "A - B - C"


@pytest.mark.asyncio
async def test_send_document_leaves_non_markdown_payloads_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Telegram encoding workaround is scoped to Markdown documents only."""
    body = {"ok": True, "result": {"document": {"file_name": "brief.txt"}}}
    fake_client = _FakeClient(_FakeResponse(200, body))
    monkeypatch.setattr(sender, "_http", lambda: fake_client)
    monkeypatch.setattr(sender, "log", MagicMock())

    await sender.send_document(123, "A — B".encode("utf-8"), "brief.txt")

    filename, payload, mime = fake_client.posted[0]["files"]["document"]
    assert filename == "brief.txt"
    assert payload == "A — B".encode("utf-8")
    assert mime == "text/plain"


@pytest.mark.asyncio
async def test_download_photo_uses_supplied_bot_token_for_getfile_and_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeGetClient()
    monkeypatch.setattr(sender, "_client", fake)

    content, mime_type = await sender.download_photo("FILE_ID", bot_token="ops-token")

    assert content == b"image-bytes"
    assert mime_type == "image/png"
    assert fake.get_calls == [
        ("https://api.telegram.org/botops-token/getFile", {"file_id": "FILE_ID"}),
        ("https://api.telegram.org/file/botops-token/photos/pic.png", None),
    ]


@pytest.mark.asyncio
async def test_download_file_uses_supplied_bot_token_for_getfile_and_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeGetClient()
    monkeypatch.setattr(sender, "_client", fake)

    content = await sender.download_file("FILE_ID", bot_token="ops-token")

    assert content == b"image-bytes"
    assert fake.get_calls == [
        ("https://api.telegram.org/botops-token/getFile", {"file_id": "FILE_ID"}),
        ("https://api.telegram.org/file/botops-token/photos/pic.png", None),
    ]

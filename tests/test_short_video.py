"""Tests for the short-video pipeline (issue #2)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# URL routing
# ---------------------------------------------------------------------------

from src.utils.validators import detect_pipeline


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/shorts/abc123",
        "https://instagram.com/reel/DVNolBNE6vV/",
        "https://tiktok.com/@user/video/1234567890",
    ],
)
def test_detect_pipeline_short_urls(url: str) -> None:
    assert detect_pipeline(url) == "short"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/video",
        "https://instagram.com/p/abc/",
        "mmmm.nnn",
        "",
    ],
)
def test_detect_pipeline_rejected(url: str) -> None:
    assert detect_pipeline(url) == "rejected"


# ---------------------------------------------------------------------------
# Brave Search
# ---------------------------------------------------------------------------

from src.services import brave


@pytest.mark.asyncio
async def test_brave_fallback_disabled(monkeypatch) -> None:
    monkeypatch.setattr("src.services.brave.settings.ENABLE_BRAVE_SEARCH", False)
    links = [{"url": "https://example.com", "label": "example", "description": ""}]
    result = await brave.verify_links(links)
    assert result == links


@pytest.mark.asyncio
async def test_brave_fallback_no_api_key(monkeypatch) -> None:
    monkeypatch.setattr("src.services.brave.settings.ENABLE_BRAVE_SEARCH", True)
    monkeypatch.setattr("src.services.brave.settings.BRAVE_API_KEY", "")
    links = [{"url": "https://example.com", "label": "x", "description": ""}]
    result = await brave.verify_links(links)
    assert result == links


@pytest.mark.asyncio
async def test_brave_fallback_rate_limited(monkeypatch) -> None:
    """Non-200 response → links returned unchanged (graceful degrade)."""
    monkeypatch.setattr("src.services.brave.settings.ENABLE_BRAVE_SEARCH", True)
    monkeypatch.setattr("src.services.brave.settings.BRAVE_API_KEY", "dummy-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        links = [{"url": "https://example.com", "label": "x", "description": ""}]
        result = await brave.verify_links(links)

    assert result[0]["url"] == "https://example.com"


# ---------------------------------------------------------------------------
# Google Drive upload helper
# ---------------------------------------------------------------------------

from src.services import drive as drive_svc


@pytest.mark.asyncio
async def test_drive_upload_helper(monkeypatch) -> None:
    """upload_file returns (file_id, web_view_link) from the mocked API."""
    fake_result = {"id": "fake-file-id", "webViewLink": "https://drive.google.com/fake"}

    mock_files = MagicMock()
    mock_files.create.return_value.execute.return_value = fake_result
    mock_service = MagicMock()
    mock_service.files.return_value = mock_files

    with patch("src.services.drive._build_service", return_value=mock_service):
        file_id, link = await drive_svc.upload_file("content", "test.md", "folder-id")

    assert file_id == "fake-file-id"
    assert "drive.google.com" in link


# ---------------------------------------------------------------------------
# Google Sheets append helper
# ---------------------------------------------------------------------------

from src.services import sheets as sheets_svc


@pytest.mark.asyncio
async def test_sheets_append_short_row(monkeypatch) -> None:
    """append_short_row calls the correct sheet ID."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID_SHORT", "short-sheet-id")

    mock_values = MagicMock()
    mock_values.append.return_value.execute.return_value = {}
    mock_spreadsheets = MagicMock()
    mock_spreadsheets.values.return_value = mock_values
    mock_service = MagicMock()
    mock_service.spreadsheets.return_value = mock_spreadsheets

    with patch("src.services.sheets._build_service", return_value=mock_service):
        await sheets_svc.append_short_row({
            "id": "job1", "chat_id": 123, "url": "https://youtube.com/shorts/x",
            "title": "Test", "platform": "youtube_shorts",
            "drive_url": "https://drive.google.com/x",
            "processing_time_ms": 1000, "created_at": "2026-01-01T00:00:00",
        })

    mock_values.append.assert_called_once()
    call_kwargs = mock_values.append.call_args.kwargs
    assert call_kwargs["spreadsheetId"] == "short-sheet-id"


# ---------------------------------------------------------------------------
# Processor: too_long error surfaces to user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_too_long_error_surfaces(monkeypatch) -> None:
    """Frame service returning too_long sends the correct message and raises."""
    from src.processors import short_video

    too_long_response = {"error": {"type": "too_long", "message": "Video duration 200s exceeds 180s limit"}}

    with (
        patch("src.processors.short_video.database.update_job_status", new_callable=AsyncMock),
        patch("src.processors.short_video.send_message", new_callable=AsyncMock) as mock_send,
        patch("src.processors.short_video.frames.fetch_frames", new_callable=AsyncMock, return_value=too_long_response),
    ):
        job = {"id": "job1", "chat_id": 42, "url": "https://youtube.com/shorts/x"}
        with pytest.raises(RuntimeError):
            await short_video.run(job)

    # Confirm the user-facing message was sent
    calls = [str(c) for c in mock_send.call_args_list]
    assert any("max 3 minutes" in c or "too long" in c.lower() for c in calls)

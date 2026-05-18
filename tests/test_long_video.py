"""Tests for the long-video Phase 1 pipeline (issue #3)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.validators import detect_pipeline


# ---------------------------------------------------------------------------
# URL routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=abc123",
        "https://www.youtube.com/watch?v=qZkX_gIlwsY",
        "https://youtu.be/qZkX_gIlwsY",
        "https://youtu.be/4bfKyZ7hbsU?si=xyz",
    ],
)
def test_detect_pipeline_long_urls(url: str) -> None:
    assert detect_pipeline(url) == "long"


# ---------------------------------------------------------------------------
# Google Drive upload helper
# ---------------------------------------------------------------------------

from src.services import drive as drive_svc


@pytest.mark.asyncio
async def test_drive_upload_helper() -> None:
    """upload_file returns (file_id, web_view_link) from the mocked API."""
    fake_result = {"id": "file-id-long", "webViewLink": "https://drive.google.com/long-file"}

    mock_files = MagicMock()
    mock_files.create.return_value.execute.return_value = fake_result
    mock_service = MagicMock()
    mock_service.files.return_value = mock_files

    with patch("src.services.drive._build_service", return_value=mock_service):
        file_id, link = await drive_svc.upload_file("transcript text", "slug.md", "folder-id")

    assert file_id == "file-id-long"
    assert "drive.google.com" in link


# ---------------------------------------------------------------------------
# Google Sheets append helper
# ---------------------------------------------------------------------------

from src.services import sheets as sheets_svc


@pytest.mark.asyncio
async def test_append_long_row(monkeypatch) -> None:
    """append_long_row calls the correct sheet ID with the right column order."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID_LONG", "long-sheet-id")

    captured: list = []

    def fake_append_sync(spreadsheet_id, values):
        captured.append((spreadsheet_id, values))

    with patch("src.services.sheets._append_sync", side_effect=fake_append_sync):
        await sheets_svc.append_long_row(
            {"id": "job1", "url": "https://youtube.com/watch?v=x", "title": "Test Video", "drive_url": "https://drive.google.com/x"},
            video_id="vid123",
            channel="Test Channel",
            views="1000",
            description_links_raw="https://example.com",
            char_count=5000,
            drive_file_id="file-abc",
        )

    assert len(captured) == 1
    sheet_id, row = captured[0]
    assert sheet_id == "long-sheet-id"
    # Verify column order: url, video_id, title, channel, ...
    assert row[0] == "https://youtube.com/watch?v=x"
    assert row[1] == "vid123"
    assert row[2] == "Test Video"
    assert row[3] == "Test Channel"
    assert row[5] == 5000  # char_count
    assert row[6] == "file-abc"  # drive_file_id
    assert row[9] == "ok"  # status


# ---------------------------------------------------------------------------
# Pipeline resilience
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_description_link_failure_does_not_block() -> None:
    """If extract_description_links raises, the pipeline continues with empty list."""
    from src.processors import long_video

    with (
        patch("src.processors.long_video.database.update_job_status", new_callable=AsyncMock),
        patch("src.processors.long_video.send_message", new_callable=AsyncMock),
        patch("src.processors.long_video.send_document", new_callable=AsyncMock),
        patch("src.processors.long_video.send_inline_keyboard", new_callable=AsyncMock),
        patch("src.processors.long_video.transcript_svc.fetch_transcript", new_callable=AsyncMock,
              return_value={"videoId": "v1", "text": "transcript text"}),
        patch("src.processors.long_video.transcript_svc.fetch_metadata", new_callable=AsyncMock,
              return_value={"title": "T", "channel": "C", "views": "100", "description": "desc"}),
        patch("src.processors.long_video.extract_description_links", side_effect=RuntimeError("boom")),
        patch("src.processors.long_video.upload_file", new_callable=AsyncMock,
              return_value=("fid", "https://drive.google.com/x")),
        patch("src.processors.long_video.sheets.append_long_row", new_callable=AsyncMock),
        patch("src.processors.long_video.database.get_job", new_callable=AsyncMock,
              return_value={"id": "job1", "url": "https://youtube.com/watch?v=x", "chat_id": 42}),
    ):
        # Should NOT raise even though extract_description_links fails
        job = {"id": "job1", "chat_id": 42, "url": "https://youtube.com/watch?v=x"}
        await long_video.run(job)


@pytest.mark.asyncio
async def test_transcript_error_continues() -> None:
    """If transcript response has 'error' key, pipeline continues with empty transcript."""
    from src.processors import long_video

    with (
        patch("src.processors.long_video.database.update_job_status", new_callable=AsyncMock),
        patch("src.processors.long_video.send_message", new_callable=AsyncMock),
        patch("src.processors.long_video.send_document", new_callable=AsyncMock),
        patch("src.processors.long_video.send_inline_keyboard", new_callable=AsyncMock),
        patch("src.processors.long_video.transcript_svc.fetch_transcript", new_callable=AsyncMock,
              return_value={"error": {"type": "TranscriptsDisabled", "message": "no captions"}}),
        patch("src.processors.long_video.transcript_svc.fetch_metadata", new_callable=AsyncMock,
              return_value={"title": "T", "channel": "C", "views": "100", "description": ""}),
        patch("src.processors.long_video.upload_file", new_callable=AsyncMock,
              return_value=("fid", "https://drive.google.com/x")),
        patch("src.processors.long_video.sheets.append_long_row", new_callable=AsyncMock),
        patch("src.processors.long_video.database.get_job", new_callable=AsyncMock,
              return_value={"id": "job1", "url": "https://youtube.com/watch?v=x", "chat_id": 42}),
    ):
        job = {"id": "job1", "chat_id": 42, "url": "https://youtube.com/watch?v=x"}
        await long_video.run(job)  # must not raise

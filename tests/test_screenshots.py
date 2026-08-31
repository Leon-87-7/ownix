from unittest.mock import AsyncMock

import pytest

from src.processors import screenshots


@pytest.mark.asyncio
async def test_trigger_rejects_known_over_limit_without_lock(monkeypatch) -> None:
    connection = AsyncMock()
    monkeypatch.setattr(screenshots.database, "connection", connection)
    outcome = await screenshots.trigger({
        "id": "job1",
        "content_type": "long",
        "status": "done",
        "video_duration_seconds": 5_401,
    })
    assert outcome == "too_long"
    connection.assert_not_called()


@pytest.mark.asyncio
async def test_run_uploads_only_gemini_selections(monkeypatch) -> None:
    frames = [{"data": "aGVsbG8="}, {"data": "d29ybGQ="}]
    monkeypatch.setattr(
        screenshots.transcript,
        "fetch_metadata",
        AsyncMock(return_value={"duration": 120, "title": "Useful Video"}),
    )
    monkeypatch.setattr(
        screenshots.transcript,
        "fetch_screenshot_candidates",
        AsyncMock(return_value={"frames": frames}),
    )
    monkeypatch.setattr(
        screenshots.gemini,
        "select_informative_screenshots",
        AsyncMock(return_value=[{"index": 1, "caption": "Architecture diagram"}]),
    )
    monkeypatch.setattr(
        screenshots.drive,
        "create_subfolder",
        AsyncMock(return_value=("folder", "https://drive/folder")),
    )
    upload = AsyncMock(return_value=("file", "https://drive/file"))
    monkeypatch.setattr(screenshots.drive, "upload_file", upload)
    monkeypatch.setattr(screenshots.database, "update_job_fields", AsyncMock())
    monkeypatch.setattr(screenshots, "send_message", AsyncMock())

    await screenshots.run({
        "id": "job1", "chat_id": 7, "url": "https://video", "title": "Video"
    })

    assert upload.await_count == 1
    assert upload.await_args.args[:3] == (b"world", "01_architecture_diagram.jpg", "folder")

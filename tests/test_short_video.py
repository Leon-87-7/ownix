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
    """append_short_row writes to the consolidated workbook and Short Video Analysis tab."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID", "consolidated-sheet-id")

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
    assert call_kwargs["spreadsheetId"] == "consolidated-sheet-id"
    assert call_kwargs["range"] == "Short Video Analysis!A1"


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


# ---------------------------------------------------------------------------
# Template path — audio fallback routing (issue #32)
# ---------------------------------------------------------------------------

import contextlib

_FRAME_RESP = {
    "frames": [{"base64": "eA==", "mime_type": "image/jpeg"}],  # base64 of b"x"
    "platform": "instagram_reels",
    "video_id": "reel1",
    "title": "Test Reel",
    "duration": 30,
}
_VISION = {"main_frame_index": 0, "summary": "a short clip", "links": []}


_TEMPLATE_JOB = {"id": "job1", "chat_id": 42, "url": "u", "template": "method", "title": "Test Reel"}
_PLAIN_JOB = {"id": "job1", "chat_id": 42, "url": "https://instagram.com/reel/x", "title": "Test Reel"}


@contextlib.contextmanager
def _patch_pipeline(transcript_resp: dict, *, job: dict | None = None):
    """Patch the whole short-video pipeline so run() reaches the transcript/template branches."""
    from src.processors import short_video
    from src.processors.enrichment import Enrichment

    with contextlib.ExitStack() as stack:
        p = lambda target, **kw: stack.enter_context(patch(target, **kw))  # noqa: E731
        mocks = {
            "update_job_status": p("src.processors.short_video.database.update_job_status", new_callable=AsyncMock),
            "get_job": p("src.processors.short_video.database.get_job", new_callable=AsyncMock),
            "save_thumbnail": p("src.processors.short_video.database.save_thumbnail", new_callable=AsyncMock),
            "send_message": p("src.processors.short_video.send_message", new_callable=AsyncMock,
                              return_value={"message_id": 1}),
            "send_photo": p("src.processors.short_video.send_photo", new_callable=AsyncMock,
                            return_value={"message_id": 2}),
            "send_document": p("src.processors.short_video.send_document", new_callable=AsyncMock),
            "edit_message_text": p("src.processors.short_video.edit_message_text", new_callable=AsyncMock),
            "fetch_frames": p("src.processors.short_video.frames.fetch_frames", new_callable=AsyncMock, return_value=_FRAME_RESP),
            "vision": p("src.processors.short_video.gemini.call_gemini_vision", new_callable=AsyncMock, return_value=_VISION),
            "upload_file": p("src.processors.short_video.upload_file", new_callable=AsyncMock, return_value=("fid", "https://drive/x")),
            "append_short_row": p("src.processors.short_video.sheets.append_short_row", new_callable=AsyncMock),
            "fetch_transcript": p("src.processors.short_video.transcript_svc.fetch_transcript", new_callable=AsyncMock, return_value=transcript_resp),
            "enrich_audio": p("src.processors.enrichment.enrich_audio", new_callable=AsyncMock),
            "transcribe_audio": p("src.processors.enrichment.transcribe_audio", new_callable=AsyncMock),
            "enrich": p("src.processors.enrichment.enrich", new_callable=AsyncMock),
            "get_ignored_domains": p("src.processors.short_video.database.get_ignored_domains", new_callable=AsyncMock, return_value=set()),
        }
        resolved_job = job if job is not None else _TEMPLATE_JOB
        mocks["get_job"].return_value = resolved_job
        yield short_video, mocks


def _final_update_kwargs(mocks: dict) -> dict:
    """Return kwargs from the final rich done update in short_video.run()."""
    for call in mocks["update_job_status"].await_args_list:
        kwargs = call.kwargs
        if kwargs.get("drive_url") and "title" in kwargs:
            return kwargs
    raise AssertionError("final update_job_status call not found")


@pytest.mark.asyncio
async def test_instagram_best_frame_thumbnail_is_persisted() -> None:
    """Instagram/TikTok short jobs store the selected frame for dashboard thumbnails."""
    transcript_resp = {"text": ""}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    mocks["save_thumbnail"].assert_awaited_once()
    args = mocks["save_thumbnail"].await_args.args
    kwargs = mocks["save_thumbnail"].await_args.kwargs
    assert args[0] == "job1"
    assert args[1] == b"x"
    assert kwargs["mime"] == "image/jpeg"

    done_calls = [str(call) for call in mocks["update_job_status"].call_args_list]
    assert any("best_frame_index" in call and "instagram_reels" in call for call in done_calls)


@pytest.mark.asyncio
async def test_short_video_vision_title_wins_over_sidecar_title() -> None:
    """Gemini Vision title is stored when both Vision and sidecar provide titles."""
    transcript_resp = {"text": ""}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["vision"].return_value = {
            **_VISION,
            "title": "Gemini Python Tools",
        }
        await short_video.run(_PLAIN_JOB)

    assert _final_update_kwargs(mocks)["title"] == "Gemini Python Tools"
    mocks["vision"].assert_awaited_once()


@pytest.mark.asyncio
async def test_short_video_sidecar_title_fallback_when_vision_title_missing() -> None:
    """Sidecar title is stored when Gemini Vision omits title."""
    transcript_resp = {"text": ""}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["vision"].return_value = {**_VISION}
        await short_video.run(_PLAIN_JOB)

    assert _final_update_kwargs(mocks)["title"] == "Test Reel"
    mocks["vision"].assert_awaited_once()


@pytest.mark.asyncio
async def test_template_audio_fallback_routes_to_enrich_audio() -> None:
    """A fallback=='audio' transcript response goes through enrich_audio, not the text path."""
    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}
    template_analysis = {
        "steps": [{"action": "Open terminal", "details": "Run CLI", "result": "ok"}],
        "common_mistakes": "",
        "pro_tips": "",
    }

    with _patch_pipeline(transcript_resp) as (short_video, mocks):
        mocks["enrich_audio"].return_value = (template_analysis, "spoken words here")
        job = {"id": "job1", "chat_id": 42, "url": "https://instagram.com/reel/x", "template": "method"}
        await short_video.run(job)

    mocks["enrich_audio"].assert_awaited_once()
    await_args = mocks["enrich_audio"].await_args.args
    assert await_args[1] == "YXVkaW8="
    assert await_args[2] == "audio/mp4"
    mocks["enrich"].assert_not_awaited()
    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "Method Analysis" in sent


@pytest.mark.asyncio
async def test_template_caption_path_unchanged() -> None:
    """A text transcript still routes through the caption enrich() path, not enrich_audio."""
    from src.processors.enrichment import Enrichment

    transcript_resp = {"text": "hello world this is a transcript about python and fastapi"}

    with _patch_pipeline(transcript_resp) as (short_video, mocks):
        mocks["enrich"].return_value = (
            Enrichment("Tech", "fastapi", "obj", "ap", "ts", [], ""),
            {"steps": [{"action": "a", "details": "d", "result": "r"}], "common_mistakes": "", "pro_tips": ""},
            None,
        )
        job = {"id": "job1", "chat_id": 42, "url": "https://instagram.com/reel/x", "template": "method"}
        await short_video.run(job)

    mocks["enrich"].assert_awaited_once()
    mocks["enrich_audio"].assert_not_awaited()


@pytest.mark.asyncio
async def test_template_audio_gemini_unavailable_surfaces_message() -> None:
    """Both Gemini keys failing in the audio path surfaces the unavailable message."""
    from src.processors.enrichment import EnrichmentUnavailableError

    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp) as (short_video, mocks):
        mocks["enrich_audio"].side_effect = EnrichmentUnavailableError("both keys failed")
        job = {"id": "job1", "chat_id": 42, "url": "https://instagram.com/reel/x", "template": "method"}
        await short_video.run(job)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "Transcription failed — Gemini unavailable" in sent


# ---------------------------------------------------------------------------
# ADR-0020 issue #102: guaranteed transcript acquisition on all short jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plain_url_job_always_fetches_transcript() -> None:
    """A plain URL job (no template) still calls fetch_transcript after ADR-0020."""
    transcript_resp = {"text": "some spoken content"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    mocks["fetch_transcript"].assert_awaited_once()


@pytest.mark.asyncio
async def test_plain_caption_less_job_calls_transcribe_audio() -> None:
    """A plain URL caption-less job calls transcribe_audio (not enrich_audio)."""
    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["transcribe_audio"].return_value = "spoken words"
        await short_video.run(_PLAIN_JOB)

    mocks["transcribe_audio"].assert_awaited_once()
    mocks["enrich_audio"].assert_not_awaited()


@pytest.mark.asyncio
async def test_plain_job_transcript_svc_error_sends_warning_job_stays_done() -> None:
    """A transcript service HTTP error sends a warning but does not change job status from done."""
    with _patch_pipeline({}, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["fetch_transcript"].side_effect = Exception("HTTP 503")
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "Transcript service error" in sent
    # Job status was set to 'done' from Vision; never regressed to 'error'
    status_calls = [str(c) for c in mocks["update_job_status"].call_args_list]
    assert not any("error" in c for c in status_calls)


@pytest.mark.asyncio
async def test_plain_job_wordless_transcript_sends_wordless_warning() -> None:
    """A transcript that returns empty text sends the ADR-0020 wordless warning."""
    transcript_resp = {"text": ""}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "I'm wordless" in sent


@pytest.mark.asyncio
async def test_transcript_persisted_on_all_short_jobs() -> None:
    """Every short job with a transcript persists it without computing key phrases."""
    transcript_resp = {"text": "python fastapi tutorial step by step guide"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    update_calls = mocks["update_job_status"].call_args_list
    persisted = any(
        "transcript" in str(c) and "python fastapi" in str(c)
        for c in update_calls
    )
    assert persisted, "jobs.transcript was never persisted"


# ---------------------------------------------------------------------------
# ADR-0020 issue #103: Drive upload + Telegram document delivery tail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plain_job_with_transcript_uploads_transcript_to_drive() -> None:
    """A short job that produces a transcript uploads {job_id}_transcript.md to Drive."""
    transcript_resp = {"text": "hello world content here"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    upload_calls = mocks["upload_file"].call_args_list
    filenames = [str(c) for c in upload_calls]
    assert any("_transcript.md" in f for f in filenames), "transcript.md not uploaded to Drive"


@pytest.mark.asyncio
async def test_plain_job_with_transcript_sends_document_to_telegram() -> None:
    """A short job that produces a transcript sends it as a Telegram document."""
    transcript_resp = {"text": "some spoken content for document delivery"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    mocks["send_document"].assert_awaited_once()
    call_kwargs = mocks["send_document"].call_args
    assert "_transcript.md" in str(call_kwargs)


@pytest.mark.asyncio
async def test_no_transcript_skips_document_delivery() -> None:
    """When no transcript text is produced, send_document is never called."""
    transcript_resp = {"text": ""}  # wordless

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    mocks["send_document"].assert_not_awaited()


# ---------------------------------------------------------------------------
# Issue #97: caption-based skeleton — no-template path end-to-end coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caption_based_no_template_gemini_budget_is_one_call() -> None:
    """Caption-based plain job: only Vision is called (captions = free, no Gemini audio)."""
    transcript_resp = {"text": "step by step python tutorial"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    # transcribe_audio and enrich_audio must NOT be called — budget: Vision + free captions = 1 call
    mocks["transcribe_audio"].assert_not_awaited()
    mocks["enrich_audio"].assert_not_awaited()


# ---------------------------------------------------------------------------
# Issue #98: caption-less plain job — transcribe_audio path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plain_caption_less_transcript_tail_runs() -> None:
    """Caption-less plain job: transcribe_audio result drives persist + Drive + Telegram doc."""
    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["transcribe_audio"].return_value = "spoken content from audio"
        await short_video.run(_PLAIN_JOB)

    upload_calls = [str(c) for c in mocks["upload_file"].call_args_list]
    assert any("_transcript.md" in f for f in upload_calls), "transcript.md not uploaded to Drive"
    mocks["send_document"].assert_awaited_once()


@pytest.mark.asyncio
async def test_plain_caption_less_transcribe_audio_unavailable_surfaces_message() -> None:
    """EnrichmentUnavailableError from transcribe_audio (plain path) surfaces the right message."""
    from src.processors.enrichment import EnrichmentUnavailableError

    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["transcribe_audio"].side_effect = EnrichmentUnavailableError("both keys failed")
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "Transcription failed — Gemini unavailable" in sent
    status_calls = [str(c) for c in mocks["update_job_status"].call_args_list]
    assert not any("'error'" in c for c in status_calls)


@pytest.mark.asyncio
async def test_plain_caption_less_empty_audio_transcript_is_wordless() -> None:
    """transcribe_audio returning empty string signals a silent/wordless clip."""
    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["transcribe_audio"].return_value = ""
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "I'm wordless" in sent
    mocks["send_document"].assert_not_awaited()


# ---------------------------------------------------------------------------
# Issue #99: caption-less template path — enrich_audio tail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_template_audio_transcript_persisted_and_tail_runs() -> None:
    """caption-less + template: enrich_audio transcript is persisted, Drive-uploaded, and doc-sent."""
    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}
    template_analysis = {
        "steps": [{"action": "Run", "details": "CLI", "result": "ok"}],
        "common_mistakes": "",
        "pro_tips": "",
    }

    with _patch_pipeline(transcript_resp) as (short_video, mocks):
        mocks["enrich_audio"].return_value = (template_analysis, "verbatim spoken content")
        job = {"id": "job1", "chat_id": 42, "url": "https://instagram.com/reel/x", "template": "method"}
        await short_video.run(job)

    update_calls = mocks["update_job_status"].call_args_list
    assert any("verbatim spoken content" in str(c) for c in update_calls), "transcript not persisted"
    upload_calls = [str(c) for c in mocks["upload_file"].call_args_list]
    assert any("_transcript.md" in f for f in upload_calls), "transcript.md not uploaded to Drive"
    mocks["send_document"].assert_awaited_once()


# ---------------------------------------------------------------------------
# Issue #100: explicit failure taxonomy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sidecar_error_dict_surfaces_message_text() -> None:
    """Sidecar returning {"error": {"message": "..."}} sends the specific message text."""
    transcript_resp = {"error": {"type": "http_error", "message": "503 Service Unavailable"}}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "Transcript service error" in sent
    assert "503 Service Unavailable" in sent


@pytest.mark.asyncio
async def test_sidecar_error_dict_job_stays_done() -> None:
    """Sidecar error dict: job status never regresses from done."""
    transcript_resp = {"error": {"type": "timeout", "message": "request timed out"}}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    status_calls = [str(c) for c in mocks["update_job_status"].call_args_list]
    assert not any("'error'" in c for c in status_calls)


@pytest.mark.asyncio
async def test_whitespace_only_transcript_is_wordless() -> None:
    """A transcript response containing only whitespace is treated as wordless (issue #100)."""
    transcript_resp = {"text": "   \n\t  "}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        await short_video.run(_PLAIN_JOB)

    sent = " ".join(str(c) for c in mocks["send_message"].call_args_list)
    assert "I'm wordless" in sent
    mocks["send_document"].assert_not_awaited()


@pytest.mark.asyncio
async def test_gemini_unavailable_plain_job_stays_done() -> None:
    """EnrichmentUnavailableError on plain caption-less path: job status stays done."""
    from src.processors.enrichment import EnrichmentUnavailableError

    transcript_resp = {"fallback": "audio", "audio_b64": "YXVkaW8=", "mime_type": "audio/mp4"}

    with _patch_pipeline(transcript_resp, job=_PLAIN_JOB) as (short_video, mocks):
        mocks["transcribe_audio"].side_effect = EnrichmentUnavailableError("both keys failed")
        await short_video.run(_PLAIN_JOB)

    status_calls = [str(c) for c in mocks["update_job_status"].call_args_list]
    assert not any("'error'" in c for c in status_calls)

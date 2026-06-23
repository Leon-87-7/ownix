"""Tests for issues #164/#213: short-pipeline job detail pages.

Covers:
- _DETAIL_FIELDS_SHORT / _detail_fields_for API selector
- GET /api/jobs/{id} returns short fields for short jobs and long fields for long jobs
- short_video.run() persists the vision summary and enriched links to DB columns
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# API: _detail_fields_for selects the right schema
# ---------------------------------------------------------------------------

from src.api.jobs import (
    _detail_fields_for,
    _DETAIL_FIELDS_COMMON,
    _DETAIL_FIELDS_SHORT,
    _DETAIL_FIELDS_LONG,
)


def test_detail_fields_short_includes_summary_transcript_links() -> None:
    fields = _detail_fields_for("short")
    assert "summary" in fields
    assert "transcript" in fields
    assert "links" in fields
    assert "key_phrases" not in fields


def test_detail_fields_short_excludes_long_enrichment() -> None:
    fields = _detail_fields_for("short")
    assert "ai_topic" not in fields
    assert "ai_objective" not in fields
    assert "ai_action_points" not in fields
    assert "promise_gap" not in fields
    assert "template_analysis" not in fields


def test_detail_fields_long_includes_enrichment() -> None:
    fields = _detail_fields_for("long")
    assert "ai_topic" in fields
    assert "ai_objective" in fields
    assert "promise_gap" in fields
    assert "template_analysis" in fields


def test_detail_fields_long_excludes_short_fields() -> None:
    fields = _detail_fields_for("long")
    assert "summary" not in fields
    assert "transcript" not in fields
    assert "links" not in fields
    assert "key_phrases" not in fields


def test_detail_fields_article_matches_long() -> None:
    assert _detail_fields_for("article") == _detail_fields_for("long")


def test_detail_fields_common_always_present() -> None:
    for ct in ("short", "long", "article", "repo"):
        fields = _detail_fields_for(ct)
        for common in _DETAIL_FIELDS_COMMON:
            assert common in fields, f"{common!r} missing from {ct!r} fields"


# ---------------------------------------------------------------------------
# API: get_job returns correct field set depending on content_type
# ---------------------------------------------------------------------------

from src.api import jobs as jobs_module


def _make_job(**extra) -> dict:
    base = {
        "id": "job1",
        "url": "https://youtube.com/shorts/abc",
        "content_type": "short",
        "status": "done",
        "title": "Test Short",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:01:00Z",
        "completed_at": "2026-01-01T00:01:00Z",
        "error_msg": None,
        "drive_url": "https://drive.google.com/x",
        # short fields
        "summary": "A short clip about Python.",
        "transcript": "Hello world.",
        "links": '[{"url":"https://python.org","label":"Python","description":"Official site"}]',
        "key_phrases": '["python", "hello world"]',
        # long fields that must NOT appear for a short job
        "ai_topic": "topic",
        "ai_objective": "obj",
        "ai_action_points": "ap",
        "ai_tools": "tools",
        "ai_market_data": "md",
        "promise_gap": "pg",
        "template": None,
        "template_analysis": None,
    }
    return {**base, **extra}


@pytest.mark.asyncio
async def test_get_job_short_returns_short_fields(monkeypatch) -> None:
    job = _make_job()

    async def _get_owned_job(job_id, request):
        return job

    monkeypatch.setattr(jobs_module, "get_owned_job", _get_owned_job)

    response = await jobs_module.get_job(
        "job1",
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
    )

    assert response["summary"] == "A short clip about Python."
    assert response["transcript"] == "Hello world."
    assert response["links"] == '[{"url":"https://python.org","label":"Python","description":"Official site"}]'
    assert "key_phrases" not in response
    assert "ai_topic" not in response
    assert "ai_objective" not in response
    assert "promise_gap" not in response


@pytest.mark.asyncio
async def test_get_job_long_returns_long_fields(monkeypatch) -> None:
    job = _make_job(
        content_type="long",
        url="https://youtube.com/watch?v=abc",
    )

    async def _get_owned_job(job_id, request):
        return job

    monkeypatch.setattr(jobs_module, "get_owned_job", _get_owned_job)

    response = await jobs_module.get_job(
        "job1",
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
    )

    assert response["ai_topic"] == "topic"
    assert response["promise_gap"] == "pg"
    assert "summary" not in response
    assert "transcript" not in response
    assert "links" not in response
    assert "key_phrases" not in response


# ---------------------------------------------------------------------------
# Pipeline: short_video.run() persists summary to the DB
# ---------------------------------------------------------------------------

import contextlib

_FRAME_RESP = {
    "frames": [{"base64": "eA==", "mime_type": "image/jpeg"}],
    "platform": "youtube_shorts",
    "video_id": "abc",
    "title": "Test Short",
    "duration": 30,
}
_VISION = {"main_frame_index": 0, "summary": "A short clip about Python.", "links": []}
_PLAIN_SHORT_JOB = {
    "id": "job1",
    "chat_id": 42,
    "url": "https://youtube.com/shorts/abc",
    "title": "Test Short",
}


@contextlib.contextmanager
def _patch_short_pipeline(transcript_resp: dict, *, job: dict | None = None):
    """Patch the short pipeline so run() executes fully with minimal I/O."""
    from src.processors import short_video

    resolved_job = job if job is not None else _PLAIN_SHORT_JOB
    with (
        patch("src.processors.short_video.database.update_job_status", new_callable=AsyncMock) as mock_update,
        patch("src.processors.short_video.database.get_job", new_callable=AsyncMock, return_value=resolved_job),
        patch("src.processors.short_video.database.save_thumbnail", new_callable=AsyncMock),
        patch("src.processors.short_video.database.get_ignored_domains", new_callable=AsyncMock, return_value=set()),
        patch("src.processors.short_video.send_message", new_callable=AsyncMock, return_value={"message_id": 1}),
        patch("src.processors.short_video.send_photo", new_callable=AsyncMock, return_value={"message_id": 2}),
        patch("src.processors.short_video.send_document", new_callable=AsyncMock),
        patch("src.processors.short_video.edit_message_text", new_callable=AsyncMock),
        patch("src.processors.short_video.frames.fetch_frames", new_callable=AsyncMock, return_value=_FRAME_RESP),
        patch("src.processors.short_video.gemini.call_gemini_vision", new_callable=AsyncMock, return_value=_VISION),
        patch("src.processors.short_video.upload_file", new_callable=AsyncMock, return_value=("fid", "https://drive/x")),
        patch("src.processors.short_video.sheets.append_short_row", new_callable=AsyncMock),
        patch("src.processors.short_video.transcript_svc.fetch_transcript", new_callable=AsyncMock, return_value=transcript_resp),
        patch("src.processors.enrichment.enrich_audio", new_callable=AsyncMock),
        patch("src.processors.enrichment.transcribe_audio", new_callable=AsyncMock),
        patch("src.processors.enrichment.enrich", new_callable=AsyncMock),
    ):
        yield short_video, mock_update


@pytest.mark.asyncio
async def test_short_pipeline_persists_summary() -> None:
    """short_video.run() must persist the vision summary to the DB at step 5."""
    transcript_resp = {"text": ""}

    with _patch_short_pipeline(transcript_resp, job=_PLAIN_SHORT_JOB) as (short_video, mock_update):
        await short_video.run(_PLAIN_SHORT_JOB)

    # Find the update_job_status call that includes the drive_url (step 5 call)
    all_calls = mock_update.call_args_list
    step5_calls = [c for c in all_calls if c.kwargs.get("drive_url") is not None]
    assert step5_calls, "No update_job_status call with drive_url found (step 5)"
    step5 = step5_calls[0]
    assert step5.kwargs.get("summary") == "A short clip about Python.", (
        f"summary not persisted in step 5 update; got kwargs: {step5.kwargs}"
    )


@pytest.mark.asyncio
async def test_short_pipeline_persists_summary_with_non_empty_vision() -> None:
    """Summary from Gemini Vision is passed through correctly, even with links."""
    from src.processors import short_video

    vision_with_links = {
        "main_frame_index": 0,
        "summary": "Detailed Python tutorial covering decorators.",
        "links": [{"url": "https://python.org", "label": "Python", "description": "Official site"}],
    }
    transcript_resp = {"text": ""}

    with _patch_short_pipeline(transcript_resp, job=_PLAIN_SHORT_JOB) as (_, mock_update):
        with patch("src.processors.short_video.gemini.call_gemini_vision", new_callable=AsyncMock, return_value=vision_with_links):
            # brave.verify_links returns links unchanged when disabled
            with patch("src.processors.short_video.brave.verify_links", new_callable=AsyncMock, return_value=vision_with_links["links"]):
                with patch("src.processors.short_video.enrich_github_links", new_callable=AsyncMock, return_value=vision_with_links["links"]):
                    await short_video.run(_PLAIN_SHORT_JOB)

    step5_calls = [c for c in mock_update.call_args_list if c.kwargs.get("drive_url") is not None]
    assert step5_calls
    assert step5_calls[0].kwargs.get("summary") == "Detailed Python tutorial covering decorators."

    links_calls = [c for c in mock_update.call_args_list if c.kwargs.get("links") is not None]
    assert links_calls
    assert links_calls[-1].kwargs.get("links") == json.dumps(vision_with_links["links"])


@pytest.mark.asyncio
async def test_short_pipeline_omits_links_when_none_found() -> None:
    """Link-free videos must not persist links='[]' (would render literal [] in UI)."""
    from src.processors import short_video

    vision_no_links = {
        "main_frame_index": 0,
        "summary": "A short clip about Python.",
        "links": [],
    }
    transcript_resp = {"text": ""}

    with _patch_short_pipeline(transcript_resp, job=_PLAIN_SHORT_JOB) as (_, mock_update):
        with patch("src.processors.short_video.gemini.call_gemini_vision", new_callable=AsyncMock, return_value=vision_no_links):
            with patch("src.processors.short_video.brave.verify_links", new_callable=AsyncMock, return_value=[]):
                with patch("src.processors.short_video.enrich_github_links", new_callable=AsyncMock, return_value=[]):
                    await short_video.run(_PLAIN_SHORT_JOB)

    assert not any("links" in c.kwargs for c in mock_update.call_args_list)

"""Unit tests for src/processors/checklists.py"""
from __future__ import annotations

from src.processors.checklists import (
    CHECKLISTS_JSON_SCHEMA,
    build_checklists_markdown,
    build_checklists_prompt,
)


# ---------------------------------------------------------------------------
# build_checklists_prompt
# ---------------------------------------------------------------------------

def test_prompt_includes_transcript_and_title():
    job = {"title": "5 things your AI-built app forgot", "transcript": "rate limiting matters"}
    prompt = build_checklists_prompt(job)
    assert "rate limiting matters" in prompt
    assert "5 things your AI-built app forgot" in prompt


def test_prompt_never_hardcodes_a_project_name():
    job = {"title": "t", "transcript": "some engineering advice"}
    prompt = build_checklists_prompt(job)
    assert "Ownix" not in prompt


def test_prompt_includes_long_video_enrichment_when_present():
    job = {
        "title": "t",
        "transcript": "x",
        "ai_topic": "Rate limiting",
        "ai_objective": "Avoid runaway AWS bills",
    }
    prompt = build_checklists_prompt(job)
    assert "Rate limiting" in prompt
    assert "Avoid runaway AWS bills" in prompt


def test_prompt_omits_enrichment_fields_for_short_jobs():
    job = {"title": "t", "transcript": "x", "summary": "quick tips video"}
    prompt = build_checklists_prompt(job)
    assert "quick tips video" in prompt
    assert "Objective:" not in prompt


# ---------------------------------------------------------------------------
# build_checklists_markdown
# ---------------------------------------------------------------------------

def test_markdown_not_applicable_renders_no_actionable_message():
    data = {"applicable": False, "topics": []}
    md = build_checklists_markdown(data)
    assert "No actionable engineering recommendations" in md


def test_markdown_applicable_with_empty_topics_also_renders_no_actionable_message():
    data = {"applicable": True, "topics": []}
    md = build_checklists_markdown(data)
    assert "No actionable engineering recommendations" in md


def test_markdown_renders_each_topic_as_a_section():
    data = {
        "applicable": True,
        "topics": [
            {"name": "Rate limiting", "directive": "Check for per-user rate limits."},
            {"name": "Audit logging", "directive": "Check for an audit trail."},
        ],
    }
    md = build_checklists_markdown(data)
    assert "## Rate limiting" in md
    assert "Check for per-user rate limits." in md
    assert "## Audit logging" in md
    assert "Check for an audit trail." in md


def test_markdown_includes_title_when_given():
    data = {"applicable": True, "topics": [{"name": "X", "directive": "Y"}]}
    md = build_checklists_markdown(data, title="5 things your AI forgot")
    assert md.startswith("# Checklist: 5 things your AI forgot")


# ---------------------------------------------------------------------------
# CHECKLISTS_JSON_SCHEMA
# ---------------------------------------------------------------------------

def test_schema_requires_applicable_and_topics():
    assert CHECKLISTS_JSON_SCHEMA["required"] == ["applicable", "topics"]
    topic_schema = CHECKLISTS_JSON_SCHEMA["properties"]["topics"]["items"]
    assert topic_schema["required"] == ["name", "directive"]


# ---------------------------------------------------------------------------
# run_checklists
# ---------------------------------------------------------------------------

import pytest
from unittest.mock import AsyncMock

from src.processors.checklists import run_checklists


@pytest.mark.asyncio
async def test_run_checklists_returns_data_and_markdown(monkeypatch):
    fake_generate = AsyncMock(
        return_value='{"applicable": true, "topics": [{"name": "Rate limiting", "directive": "Check it."}]}'
    )
    monkeypatch.setattr("src.services.gemini.generate", fake_generate)

    job = {"title": "t", "transcript": "some transcript text"}
    data, md = await run_checklists(job)

    assert data["applicable"] is True
    assert data["topics"][0]["name"] == "Rate limiting"
    assert "## Rate limiting" in md
    fake_generate.assert_awaited_once()
    _, kwargs = fake_generate.await_args
    assert kwargs["model"] == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_run_checklists_propagates_gemini_unavailable(monkeypatch):
    from src.services.gemini import GeminiUnavailableError

    async def _fail(*args, **kwargs):
        raise GeminiUnavailableError("both keys failed")

    monkeypatch.setattr("src.services.gemini.generate", _fail)

    with pytest.raises(GeminiUnavailableError):
        await run_checklists({"title": "t", "transcript": "x"})

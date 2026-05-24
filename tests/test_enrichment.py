"""Unit tests for src/processors/enrichment.py — no network calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.processors.enrichment import (
    Enrichment,
    EnrichmentUnavailableError,
    _build_audio_prompt,
    _build_enrichment_message,
    _build_prompt,
    _extract_json,
    _parse_enrichment,
    enrich,
    enrich_audio,
)
from src.services.gemini_client import GeminiClient


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

def test_extract_json_strips_fences() -> None:
    raw = '```json\n{"category": "A", "topic": "foo"}\n```'
    result = _extract_json(raw)
    assert result == {"category": "A", "topic": "foo"}


def test_extract_json_bare_object() -> None:
    raw = '{"category": "B", "topic": "bar"}'
    result = _extract_json(raw)
    assert result == {"category": "B", "topic": "bar"}


# ---------------------------------------------------------------------------
# _parse_enrichment
# ---------------------------------------------------------------------------

def test_parse_enrichment_pipe_joins() -> None:
    data = {
        "category": "Technical Tutorial",
        "topic": "FastAPI setup",
        "objective": "Learn FastAPI",
        "action_points": ["Point one", "Point two", "Point three"],
        "tools": [
            {"name": "FastAPI", "type": "library", "url": "https://fastapi.tiangolo.com", "description": "Web framework"},
        ],
        "market_data": "",
    }
    result = _parse_enrichment(data)
    assert result.action_points_str == "Point one | Point two | Point three"
    assert "[library] FastAPI" in result.tools_str
    assert "https://fastapi.tiangolo.com" in result.tools_str
    assert "Web framework" in result.tools_str


def test_parse_enrichment_symbol_prefix() -> None:
    data = {
        "category": "Market Analysis",
        "topic": "AAPL breakout",
        "objective": "Analyze AAPL",
        "action_points": [],
        "tools": [
            {"name": "AAPL", "type": "symbol", "url": "https://finance.yahoo.com/quote/AAPL", "description": "Apple stock"},
        ],
        "market_data": "AAPL bullish above 200",
    }
    result = _parse_enrichment(data)
    assert result.tools_str.startswith("$AAPL")


# ---------------------------------------------------------------------------
# URL resolution helpers (via _parse_enrichment tools_str)
# ---------------------------------------------------------------------------

def test_url_resolution_known_tools() -> None:
    data = {
        "category": "Technical Tutorial",
        "topic": "n8n automation",
        "objective": "Automate with n8n",
        "action_points": [],
        "tools": [
            {"name": "n8n", "type": "service", "url": "https://n8n.io", "description": "Workflow automation"},
        ],
        "market_data": "",
    }
    result = _parse_enrichment(data)
    assert "https://n8n.io" in result.tools_str


def test_url_resolution_concept_no_url() -> None:
    data = {
        "category": "Technical Tutorial",
        "topic": "HTTP basics",
        "objective": "Understand HTTP",
        "action_points": [],
        "tools": [
            {"name": "HTTP Request", "type": "tool", "url": "", "description": "Generic HTTP concept"},
        ],
        "market_data": "",
    }
    result = _parse_enrichment(data)
    # No URL should appear in parentheses for this tool
    assert "HTTP Request: Generic HTTP concept" in result.tools_str
    assert "HTTP Request ()" not in result.tools_str


# ---------------------------------------------------------------------------
# enrich() — mock _call_gemini_sync so no real Gemini calls are made
# ---------------------------------------------------------------------------

_SAMPLE_GEMINI_JSON = json.dumps({
    "category": "Technical Tutorial",
    "topic": "claude code + n8n",
    "objective": "Show how to integrate Claude Code with n8n workflows.",
    "action_points": ["Use Claude API", "Set up n8n webhook", "Test the flow"],
    "tools": [
        {"name": "n8n", "type": "service", "url": "https://n8n.io", "description": "Workflow automation platform"},
        {"name": "Claude", "type": "service", "url": "https://claude.ai", "description": "AI assistant"},
    ],
    "market_data": "",
    "promise_gap": {
        "gaps": ["Advanced deployment never covered"],
        "hidden_value": ["Practical n8n error handling tips"],
    },
})


@pytest.mark.asyncio
async def test_enrich_both_keys_failed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both Gemini keys fail, enrich() raises EnrichmentUnavailableError."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    def _boom(prompt: str, api_key: str, model: str, schema: type | dict | None) -> str:
        raise RuntimeError("network error")

    with patch.object(GeminiClient, "_call_sync", side_effect=_boom):
        with pytest.raises(EnrichmentUnavailableError):
            await enrich({"title": "Test Video", "transcript": "some transcript"})


@pytest.mark.asyncio
async def test_enrich_returns_enrichment_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a key succeeds, enrich() returns a populated Enrichment dataclass."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch.object(GeminiClient, "_call_sync", return_value=_SAMPLE_GEMINI_JSON):
        result, template_analysis, promise_gap = await enrich({"title": "Test Video", "transcript": "some transcript"})

    assert isinstance(result, Enrichment)
    assert result.category == "Technical Tutorial"
    assert result.topic == "claude code + n8n"
    assert "Use Claude API" in result.action_points_str
    assert template_analysis is None
    assert promise_gap == {
        "gaps": ["Advanced deployment never covered"],
        "hidden_value": ["Practical n8n error handling tips"],
    }


@pytest.mark.asyncio
async def test_enrich_pops_and_returns_promise_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich() must pop promise_gap from parsed JSON and return it as 3rd element."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch.object(GeminiClient, "_call_sync", return_value=_SAMPLE_GEMINI_JSON):
        result, template_analysis, promise_gap = await enrich(
            {"title": "Test Video", "transcript": "some transcript"}
        )

    assert promise_gap == {
        "gaps": ["Advanced deployment never covered"],
        "hidden_value": ["Practical n8n error handling tips"],
    }
    assert template_analysis is None
    assert isinstance(result, Enrichment)


# ---------------------------------------------------------------------------
# Audio enrichment — issue #32 (caption-less Reels)
# ---------------------------------------------------------------------------

def test_build_audio_prompt_includes_title_and_template_instructions() -> None:
    prompt = _build_audio_prompt("My Reel", "method")
    assert "My Reel" in prompt
    assert "template_analysis" in prompt
    # The chosen template's extra instructions are appended verbatim.
    assert "ADDITIONAL EXTRACTION — method template" in prompt


def test_build_audio_prompt_unknown_template_falls_back_to_summary() -> None:
    # summary has empty extra_instructions, so this must not raise.
    prompt = _build_audio_prompt("Untitled", "does-not-exist")
    assert "Untitled" in prompt
    assert "template_analysis" in prompt


_SAMPLE_AUDIO_JSON = json.dumps({
    "template_analysis": {
        "steps": [{"action": "Open terminal", "details": "Run the CLI", "result": "ready"}],
        "common_mistakes": "",
        "pro_tips": "",
    }
})


@pytest.mark.asyncio
async def test_enrich_audio_returns_template_analysis_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch(
        "src.processors.enrichment._call_gemini_audio_sync",
        return_value=_SAMPLE_AUDIO_JSON,
    ):
        result = await enrich_audio(
            {"title": "Test Reel", "template": "method"}, "YXVkaW8=", "audio/mp4"
        )

    assert result == {
        "steps": [{"action": "Open terminal", "details": "Run the CLI", "result": "ready"}],
        "common_mistakes": "",
        "pro_tips": "",
    }


@pytest.mark.asyncio
async def test_enrich_audio_returns_none_when_no_template_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch(
        "src.processors.enrichment._call_gemini_audio_sync",
        return_value='{"something_else": 1}',
    ):
        result = await enrich_audio(
            {"title": "Test Reel", "template": "method"}, "YXVkaW8=", "audio/mp4"
        )

    assert result is None


@pytest.mark.asyncio
async def test_enrich_audio_both_keys_failed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    def _boom(audio_b64: str, mime_type: str, prompt: str, api_key: str) -> str:
        raise RuntimeError("network error")

    with patch("src.processors.enrichment._call_gemini_audio_sync", side_effect=_boom):
        with pytest.raises(EnrichmentUnavailableError):
            await enrich_audio(
                {"title": "Test Reel", "template": "method"}, "YXVkaW8=", "audio/mp4"
            )


# ---------------------------------------------------------------------------
# _build_enrichment_message
# ---------------------------------------------------------------------------

def _make_enrichment() -> Enrichment:
    return Enrichment(
        category="Technical Tutorial",
        topic="claude code + n8n",
        objective="Show integration of Claude Code with n8n.",
        action_points_str="Use Claude API | Set up n8n webhook | Test the flow",
        tools_str="[service] n8n (https://n8n.io): Workflow automation",
        tools_raw=[
            {"name": "n8n", "type": "service", "url": "https://n8n.io", "description": "Workflow automation"},
        ],
        market_data="",
    )


def test_build_enrichment_message_contains_tag() -> None:
    job = {"id": "20260519_120000_ABCD", "title": "Test Video", "chat_id": 1, "drive_url": ""}
    enrichment = _make_enrichment()
    msg = _build_enrichment_message(job, enrichment)
    assert msg.startswith("job_ABCD:")


def test_build_enrichment_message_contains_title() -> None:
    job = {"id": "20260519_120000_ABCD", "title": "Test Video Title", "chat_id": 1, "drive_url": ""}
    enrichment = _make_enrichment()
    msg = _build_enrichment_message(job, enrichment)
    assert "Test Video Title" in msg


# ---------------------------------------------------------------------------
# Promise-gap analysis (issue #33)
# ---------------------------------------------------------------------------

def test_build_prompt_contains_promise_gap_instruction() -> None:
    prompt = _build_prompt("My Title", "some transcript content")
    assert "promise_gap" in prompt
    assert "gaps" in prompt
    assert "hidden_value" in prompt

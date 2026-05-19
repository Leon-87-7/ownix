"""Unit tests for src/processors/enrichment.py — no network calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.processors.enrichment import (
    Enrichment,
    EnrichmentUnavailableError,
    _build_enrichment_message,
    _extract_json,
    _parse_enrichment,
    enrich,
)


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
})


@pytest.mark.asyncio
async def test_enrich_both_keys_failed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both Gemini keys fail, enrich() raises EnrichmentUnavailableError."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")

    def _boom(prompt: str, api_key: str) -> str:
        raise RuntimeError("network error")

    with patch("src.processors.enrichment._call_gemini_sync", side_effect=_boom):
        with pytest.raises(EnrichmentUnavailableError):
            await enrich({"title": "Test Video", "transcript": "some transcript"})


@pytest.mark.asyncio
async def test_enrich_returns_enrichment_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a key succeeds, enrich() returns a populated Enrichment dataclass."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch("src.processors.enrichment._call_gemini_sync", return_value=_SAMPLE_GEMINI_JSON):
        result = await enrich({"title": "Test Video", "transcript": "some transcript"})

    assert isinstance(result, Enrichment)
    assert result.category == "Technical Tutorial"
    assert result.topic == "claude code + n8n"
    assert "Use Claude API" in result.action_points_str


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

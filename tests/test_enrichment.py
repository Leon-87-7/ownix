"""Unit tests for src/processors/enrichment.py — no network calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.processors.enrichment import (
    Enrichment,
    EnrichmentUnavailableError,
    _build_audio_prompt,
    _build_enrichment_message,
    _build_prompt,
    _extract_json,
    _parse_enrichment,
    _split_message,
    enrich,
    enrich_audio,
)


def _utf16_units(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _make_response(text: str) -> MagicMock:
    r = MagicMock()
    r.text = text
    return r


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

    def _boom(parts, *, api_key: str, model: str, schema=None):
        raise RuntimeError("network error")

    with patch("src.services.gemini._call_sync", side_effect=_boom):
        with pytest.raises(EnrichmentUnavailableError):
            await enrich({"title": "Test Video", "transcript": "some transcript"})


@pytest.mark.asyncio
async def test_enrich_returns_enrichment_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When a key succeeds, enrich() returns a populated Enrichment dataclass."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    with patch("src.services.gemini._call_sync", return_value=_make_response(_SAMPLE_GEMINI_JSON)):
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

    with patch("src.services.gemini._call_sync", return_value=_make_response(_SAMPLE_GEMINI_JSON)):
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


# ---------------------------------------------------------------------------
# Freestyle prompt substitution (issue #52 / ADR-0012)
# ---------------------------------------------------------------------------

def test_build_prompt_freestyle_overrides_template_extra_instructions() -> None:
    """When freestyle_prompt is set it replaces the template's extra_instructions."""
    freestyle = "Focus only on the risk factors mentioned."
    prompt = _build_prompt("My Title", "transcript", template="method", freestyle_prompt=freestyle)
    assert "FREESTYLE INSTRUCTIONS" in prompt
    assert freestyle in prompt
    # Template's own extra instructions must NOT appear
    assert "ADDITIONAL EXTRACTION — method template" not in prompt


def test_build_prompt_no_freestyle_uses_template_extra_instructions() -> None:
    """Without freestyle_prompt the template's extra_instructions are used unchanged."""
    prompt = _build_prompt("My Title", "transcript", template="method")
    assert "ADDITIONAL EXTRACTION — method template" in prompt
    assert "FREESTYLE INSTRUCTIONS" not in prompt


@pytest.mark.asyncio
async def test_enrich_passes_freestyle_prompt_to_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich() must include freestyle_prompt in the Gemini call when set."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    captured: list[str] = []

    def _capture(parts, *, api_key: str, model: str, schema=None):
        captured.append(parts)
        return _make_response(_SAMPLE_GEMINI_JSON)

    with patch("src.services.gemini._call_sync", side_effect=_capture):
        await enrich({
            "title": "Test",
            "transcript": "some content",
            "freestyle_prompt": "Summarise the key risks mentioned.",
        })

    assert captured, "Gemini was not called"
    prompt_text = captured[0]
    assert "FREESTYLE INSTRUCTIONS" in prompt_text
    assert "Summarise the key risks mentioned." in prompt_text


@pytest.mark.asyncio
async def test_enrich_without_freestyle_prompt_uses_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """enrich() without freestyle_prompt falls back to template extra_instructions."""
    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "")

    captured: list[str] = []

    def _capture(parts, *, api_key: str, model: str, schema=None):
        captured.append(parts)
        return _make_response(_SAMPLE_GEMINI_JSON)

    with patch("src.services.gemini._call_sync", side_effect=_capture):
        await enrich({
            "title": "Test",
            "transcript": "some content",
            "template": "method",
        })

    assert captured
    assert "ADDITIONAL EXTRACTION — method template" in captured[0]
    assert "FREESTYLE INSTRUCTIONS" not in captured[0]


def test_build_enrichment_message_with_promise_gap() -> None:
    """Message includes separator + gaps + hidden_value when promise_gap is present."""
    job = {"id": "20260519_120000_ABCD", "title": "Test Video", "chat_id": 1, "drive_url": ""}
    enrichment = _make_enrichment()
    promise_gap = {
        "gaps": ["Advanced deployment never covered"],
        "hidden_value": ["Practical n8n error handling tips"],
    }
    msg = _build_enrichment_message(job, enrichment, promise_gap=promise_gap)
    assert "=====PROMISE=GAP=====" in msg
    assert "Advanced deployment never covered" in msg
    assert "Practical n8n error handling tips" in msg


def test_build_enrichment_message_no_promise_gap_omits_separator() -> None:
    """Separator absent when promise_gap is None."""
    job = {"id": "20260519_120000_ABCD", "title": "Test Video", "chat_id": 1, "drive_url": ""}
    enrichment = _make_enrichment()
    msg = _build_enrichment_message(job, enrichment)
    assert "=====PROMISE=GAP=====" not in msg


def test_build_enrichment_message_empty_promise_gap_omits_separator() -> None:
    """Separator absent when both arrays are empty."""
    job = {"id": "20260519_120000_ABCD", "title": "Test Video", "chat_id": 1, "drive_url": ""}
    enrichment = _make_enrichment()
    promise_gap = {"gaps": [], "hidden_value": []}
    msg = _build_enrichment_message(job, enrichment, promise_gap=promise_gap)
    assert "=====PROMISE=GAP=====" not in msg


# ---------------------------------------------------------------------------
# HTML rendering — the message is sent with parse_mode="HTML" so that
# arbitrary AI-generated text can never break Telegram entity parsing.
# (Replaces the fragile Markdown-V1 path that 400'd on an odd '_'/'*' count.)
# ---------------------------------------------------------------------------

def test_build_enrichment_message_escapes_html_special_chars() -> None:
    """&, <, > in AI text are HTML-escaped; raw tags never leak through."""
    job = {"id": "20260519_120000_ABCD", "title": "Tips & Tricks <live>", "chat_id": 1, "drive_url": ""}
    enrichment = Enrichment(
        category="A) Tutorial",
        topic="b<a>r & baz",
        objective="Use <script> & co.",
        action_points_str="",
        tools_str="",
        tools_raw=[],
        market_data="",
    )
    msg = _build_enrichment_message(job, enrichment)
    assert "&lt;script&gt;" in msg
    assert "&amp;" in msg
    assert "<script>" not in msg  # never emitted raw


def test_build_enrichment_message_transcript_is_html_anchor() -> None:
    """Transcript link is an <a href> — the URL lives in the attribute, so
    underscores/dots in it can never break parsing."""
    job = {
        "id": "20260519_120000_ABCD",
        "title": "T",
        "chat_id": 1,
        "drive_url": "https://drive.google.com/file/d/abc_def/view",
    }
    msg = _build_enrichment_message(job, _make_enrichment())
    assert '<a href="https://drive.google.com/file/d/abc_def/view">Transcript</a>' in msg


def test_build_enrichment_message_tool_is_html_anchor() -> None:
    """Tool URL goes in href (safe even with underscores); name is the label."""
    job = {"id": "20260519_120000_ABCD", "title": "T", "chat_id": 1, "drive_url": ""}
    enrichment = Enrichment(
        category="A",
        topic="t",
        objective="o",
        action_points_str="",
        tools_str="",
        tools_raw=[
            {"name": "some_tool", "type": "repo", "url": "https://github.com/foo/some_repo", "description": "d"}
        ],
        market_data="",
    )
    msg = _build_enrichment_message(job, enrichment)
    assert '<a href="https://github.com/foo/some_repo">some_tool</a>' in msg


def test_build_enrichment_message_no_markdown_backslash_escapes() -> None:
    """The old Markdown-V1 backslash hack is gone; special chars survive literally."""
    job = {"id": "20260519_120000_ABCD", "title": "a_b*c`d[e", "chat_id": 1, "drive_url": ""}
    msg = _build_enrichment_message(job, _make_enrichment())
    assert "\\_" not in msg
    assert "\\*" not in msg
    assert "\\[" not in msg
    assert "a_b*c`d[e" in msg  # title passes through untouched (no &<>)


# ---------------------------------------------------------------------------
# _split_message — Telegram caps sendMessage text at 4096 chars (long videos
# produce longer enrichment messages → "Bad Request: message is too long").
# ---------------------------------------------------------------------------

def test_split_message_short_returns_single_chunk() -> None:
    text = "line one\nline two"
    assert _split_message(text) == [text]


def test_split_message_long_respects_limit_and_is_lossless() -> None:
    # 400 lines of ~30 chars ≈ 12k chars, well over Telegram's 4096 cap.
    text = "\n".join(f"line number {i} with some words" for i in range(400))
    chunks = _split_message(text, limit=4096)
    assert len(chunks) > 1
    for chunk in chunks:
        assert _utf16_units(chunk) <= 4096
    # Rejoining on newlines reproduces the original exactly (no content lost).
    assert "\n".join(chunks) == text


def test_split_message_never_cuts_an_anchor_tag() -> None:
    # Each line holds a complete <a>…</a>; splitting on line boundaries must
    # keep every anchor whole within a single chunk.
    line = '• [repo] <a href="https://github.com/foo/bar_baz">bar_baz</a>: a tool'
    text = "\n".join(line for _ in range(300))
    chunks = _split_message(text, limit=4096)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.count("<a ") == chunk.count("</a>")

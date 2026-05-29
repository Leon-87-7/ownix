"""Tests for the repo pipeline processor (issue #67)."""
from __future__ import annotations

import json as _json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from src.processors.repo import _format_bundle_message, _days_ago, _parse_owner_repo, REPO_ANALYSIS_SCHEMA, _build_repo_prompt

_BUNDLE = {
    "owner": "anthropics",
    "repo": "claude-code",
    "metadata": {
        "stars": 12_345, "forks": 678, "language": "TypeScript",
        "pushed_at": "2026-01-01T00:00:00Z", "description": "AI tool",
        "archived": False,
    },
    "default_branch": "main",
    "readme": "x" * 200,
    "readme_raw_bytes": 5_000,
    "tree": ["a.py", "b.py", "c.py"],
    "manifests": {"pyproject.toml": "[tool]", "package.json": "{}"},
    "no_readme": False,
}


# ---------------------------------------------------------------------------
# _parse_owner_repo
# ---------------------------------------------------------------------------

def test_parse_owner_repo_bare() -> None:
    assert _parse_owner_repo("https://github.com/owner/repo") == ("owner", "repo")


def test_parse_owner_repo_subpath() -> None:
    assert _parse_owner_repo("https://github.com/owner/repo/blob/main/README.md") == ("owner", "repo")


# ---------------------------------------------------------------------------
# _days_ago
# ---------------------------------------------------------------------------

def test_days_ago_none_returns_zero() -> None:
    assert _days_ago(None) == 0


def test_days_ago_invalid_returns_zero() -> None:
    assert _days_ago("not-a-date") == 0


def test_days_ago_past_date_positive() -> None:
    days = _days_ago("2020-01-01T00:00:00Z")
    assert days > 0


# ---------------------------------------------------------------------------
# _format_bundle_message
# ---------------------------------------------------------------------------

def test_bundle_message_has_stats() -> None:
    msg = _format_bundle_message("anthropics", "claude-code", _BUNDLE)
    assert "12,345" in msg
    assert "678" in msg
    assert "TypeScript" in msg


def test_bundle_message_has_readme_stats() -> None:
    msg = _format_bundle_message("anthropics", "claude-code", _BUNDLE)
    assert "200 bytes" in msg
    assert "4.9 KB" in msg


def test_bundle_message_has_tree_count() -> None:
    msg = _format_bundle_message("anthropics", "claude-code", _BUNDLE)
    assert "3 files" in msg


def test_bundle_message_has_manifest_list() -> None:
    msg = _format_bundle_message("anthropics", "claude-code", _BUNDLE)
    assert "pyproject.toml" in msg
    assert "package.json" in msg


def test_bundle_message_no_manifests_shows_none() -> None:
    bundle = {**_BUNDLE, "manifests": {}}
    msg = _format_bundle_message("anthropics", "claude-code", bundle)
    assert "none" in msg.lower()


# ---------------------------------------------------------------------------
# run() integration — mocked DB, sender, fetch_repo_bundle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_calls_fetch_repo_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_calls: list[tuple] = []

    async def fake_bundle(owner, repo, token):
        bundle_calls.append((owner, repo))
        return _BUNDLE

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", fake_bundle)
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert ("anthropics", "claude-code") in bundle_calls


# ---------------------------------------------------------------------------
# REPO_ANALYSIS_SCHEMA + _build_repo_prompt (#68)
# ---------------------------------------------------------------------------

def test_repo_analysis_schema_has_all_top_level_keys() -> None:
    props = REPO_ANALYSIS_SCHEMA.get("properties", {})
    for key in ("title", "tagline", "tech_stack", "for_developers", "for_education"):
        assert key in props, f"missing key: {key}"


def test_repo_analysis_schema_curriculum_hooks_fields() -> None:
    hooks = (
        REPO_ANALYSIS_SCHEMA["properties"]["for_education"]["properties"]
        ["curriculum_hooks"]["items"]["properties"]
    )
    assert "concept" in hooks
    assert "file_pointer" in hooks
    assert "why" in hooks


def test_build_repo_prompt_contains_metadata() -> None:
    prompt = _build_repo_prompt(_BUNDLE)
    assert "anthropics" in prompt or "claude-code" in prompt
    assert "12,345" in prompt or "TypeScript" in prompt


def test_build_repo_prompt_contains_tree_and_manifests() -> None:
    prompt = _build_repo_prompt(_BUNDLE)
    assert "pyproject.toml" in prompt
    assert "a.py" in prompt or "file tree" in prompt.lower()


def test_build_repo_prompt_freestyle_substitutes_focus() -> None:
    prompt = _build_repo_prompt(_BUNDLE, freestyle_prompt="explain for a Rust developer")
    assert "Rust developer" in prompt


def test_build_repo_prompt_no_readme_flag_adjusts_instructions() -> None:
    bundle = {**_BUNDLE, "no_readme": True, "readme": ""}
    prompt = _build_repo_prompt(bundle, flags={"no_readme": True})
    lower = prompt.lower()
    assert "no readme" in lower or "tree" in lower or "manifest" in lower


# ---------------------------------------------------------------------------
# Task 7 — Gemini call + DB persistence + summary + Freestyle button (#68)
# ---------------------------------------------------------------------------

_ANALYSIS = {
    "title": "anthropics/claude-code",
    "tagline": "AI coding assistant for the terminal",
    "tech_stack": ["TypeScript", "Node.js"],
    "for_developers": {
        "project_ideas": ["Build custom AI workflows", "Extend with plugins"],
        "when_to_use": "When you need AI assistance in the terminal",
        "avoid_when": "When you need a GUI IDE",
    },
    "for_education": {
        "concepts_taught": ["LLM tool use", "CLI design"],
        "prerequisites": ["TypeScript basics"],
        "curriculum_hooks": [
            {"concept": "Tool calling", "file_pointer": "src/tools/", "why": "Demonstrates LLM tool patterns"},
        ],
    },
}


@pytest.mark.asyncio
async def test_run_calls_gemini_flash_with_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    gemini_calls: list[dict] = []

    async def spy_generate(prompt, *, model, schema=None):
        gemini_calls.append({"model": model, "schema": schema})
        return _json.dumps(_ANALYSIS)

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", spy_generate)
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert len(gemini_calls) == 1
    assert gemini_calls[0]["model"] == "gemini-2.5-flash"
    assert gemini_calls[0]["schema"] is not None


@pytest.mark.asyncio
async def test_run_persists_template_analysis_and_ai_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    updated_kwargs: dict = {}

    async def spy_update(job_id, status, **kwargs):
        updated_kwargs.update(kwargs)

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", spy_update)
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert "template_analysis" in updated_kwargs
    assert updated_kwargs.get("ai_topic") == "AI coding assistant for the terminal"
    assert "ai_objective" in updated_kwargs
    assert "ai_action_points" in updated_kwargs
    assert "ai_tools" in updated_kwargs


@pytest.mark.asyncio
async def test_run_sends_summary_with_freestyle_button(monkeypatch: pytest.MonkeyPatch) -> None:
    keyboard_calls: list[dict] = []

    async def spy_keyboard(chat_id, text, buttons, **kwargs):
        keyboard_calls.append({"text": text, "buttons": buttons})

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", spy_keyboard)
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert len(keyboard_calls) == 1
    text = keyboard_calls[0]["text"]
    assert "AI coding assistant for the terminal" in text
    assert "🛠 For developers" in text
    assert "🎓 For teaching" in text
    btns = keyboard_calls[0]["buttons"]
    flat = [btn for row in btns for btn in row]
    assert any("Freestyle" in b.get("text", "") for b in flat)

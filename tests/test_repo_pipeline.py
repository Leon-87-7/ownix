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
    assert any(b.get("callback_data", "").startswith("template_freestyle:") for b in flat)


# ---------------------------------------------------------------------------
# Task 8 — render_repo_markdown + _sanitize_filename + document delivery (#69)
# ---------------------------------------------------------------------------

from src.processors.repo import render_repo_markdown, _sanitize_filename


def test_render_has_all_section_headings() -> None:
    md = render_repo_markdown(_ANALYSIS, _BUNDLE)
    for heading in ("## Tech Stack", "## 🛠 For Developers", "## 🎓 For Education", "### Curriculum Hooks"):
        assert heading in md, f"missing: {heading}"


def test_render_includes_tagline() -> None:
    md = render_repo_markdown(_ANALYSIS, _BUNDLE)
    assert "AI coding assistant for the terminal" in md


def test_render_archived_includes_warning_h2() -> None:
    bundle = {**_BUNDLE, "metadata": {**_BUNDLE["metadata"], "archived": True}}
    assert "## ⚠️ Archived" in render_repo_markdown(_ANALYSIS, bundle)


def test_render_no_readme_includes_info_h2() -> None:
    bundle = {**_BUNDLE, "no_readme": True}
    assert "## ℹ️ No README" in render_repo_markdown(_ANALYSIS, bundle)


def test_render_hook_with_file_pointer_includes_backtick_path() -> None:
    md = render_repo_markdown(_ANALYSIS, _BUNDLE)
    assert "`src/tools/`" in md


def test_render_hook_without_file_pointer_omits_suffix() -> None:
    analysis = {
        **_ANALYSIS,
        "for_education": {**_ANALYSIS["for_education"],
                          "curriculum_hooks": [{"concept": "Async", "file_pointer": None, "why": "Core"}]},
    }
    md = render_repo_markdown(analysis, _BUNDLE)
    assert "Async" in md
    assert "`None`" not in md


def test_render_empty_tech_stack_shows_none_placeholder() -> None:
    analysis = {**_ANALYSIS, "tech_stack": []}
    md = render_repo_markdown(analysis, _BUNDLE)
    assert "_(none)_" in md


def test_sanitize_filename_basic() -> None:
    assert _sanitize_filename("anthropics", "claude-code") == "anthropics-claude-code.md"


def test_sanitize_filename_dot_in_owner() -> None:
    result = _sanitize_filename("golang.org", "go")
    assert result.endswith(".md")
    assert "golang" in result


def test_sanitize_filename_fallback_on_empty() -> None:
    result = _sanitize_filename("", "", job_id="20260101_120000_ABCD")
    assert result == "20260101_120000_ABCD.md"


@pytest.mark.asyncio
async def test_run_sends_document_before_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    call_order: list[str] = []

    async def spy_doc(chat_id, file_bytes, filename, **kw):
        call_order.append("doc")

    async def spy_kbd(chat_id, text, buttons, **kw):
        call_order.append("kbd")

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", spy_doc)
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", spy_kbd)
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert call_order.index("doc") < call_order.index("kbd")


@pytest.mark.asyncio
async def test_run_document_failure_does_not_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    kbd_calls: list = []

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock(side_effect=RuntimeError("blip")))
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard",
                        AsyncMock(side_effect=lambda *a, **kw: kbd_calls.append(1)))
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)   # must not raise

    assert kbd_calls


# ---------------------------------------------------------------------------
# Task 10 — Second Brain ingest (#71)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_ingests_normalized_repo_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """brain.ingest_links called with exactly the root repo URL (no subpaths)."""
    import asyncio as _asyncio
    ingest_calls: list[dict] = []

    async def fake_ingest(links, topic, source_job_id):
        ingest_calls.append({"links": links, "topic": topic, "source_job_id": source_job_id})

    def eager_create_task(coro):
        return _asyncio.ensure_future(coro)

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")
    monkeypatch.setattr("src.brain.ingest_links", fake_ingest)
    monkeypatch.setattr("asyncio.create_task", eager_create_task)

    # URL with subpath — should be normalized
    job = {"id": "abc", "chat_id": 1,
           "url": "https://github.com/anthropics/claude-code/blob/main/README.md",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)
    await _asyncio.sleep(0)  # yield so fire-and-forget tasks execute

    brain_calls = [c for c in ingest_calls]
    assert len(brain_calls) == 1
    assert brain_calls[0]["links"][0]["url"] == "https://github.com/anthropics/claude-code"
    assert brain_calls[0]["topic"] == _ANALYSIS["tagline"]
    assert brain_calls[0]["source_job_id"] == "abc"


@pytest.mark.asyncio
async def test_run_brain_failure_leaves_job_done(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio as _asyncio
    statuses: list[str] = []

    async def failing_ingest(links, topic, source_job_id):
        raise RuntimeError("embed failed")

    def eager_create_task(coro):
        return _asyncio.ensure_future(coro)

    async def track_status(job_id, status, **kwargs):
        statuses.append(status)

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", track_status)
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")
    monkeypatch.setattr("src.brain.ingest_links", failing_ingest)
    monkeypatch.setattr("asyncio.create_task", eager_create_task)

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)
    await _asyncio.sleep(0)  # yield so fire-and-forget tasks execute

    assert "done" in statuses
    assert "error" not in statuses


# ---------------------------------------------------------------------------
# Task 11 — Edge cases: archived, no-README, GitHub API failures, GeminiUnavailableError (#72)
# ---------------------------------------------------------------------------

from src.services.gemini import GeminiUnavailableError


@pytest.mark.asyncio
async def test_run_archived_repo_warning_in_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    archived_bundle = {**_BUNDLE, "metadata": {**_BUNDLE["metadata"], "archived": True}}
    texts: list[str] = []

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=archived_bundle))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard",
                        AsyncMock(side_effect=lambda c, t, b, **kw: texts.append(t)))
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)
    assert any("⚠️ Archived" in t for t in texts)


@pytest.mark.asyncio
async def test_run_no_readme_warning_in_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    no_readme_bundle = {**_BUNDLE, "no_readme": True, "readme": ""}
    texts: list[str] = []

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=no_readme_bundle))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard",
                        AsyncMock(side_effect=lambda c, t, b, **kw: texts.append(t)))
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)
    assert any("ℹ️ No README" in t for t in texts)


@pytest.mark.asyncio
async def test_run_github_404_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []
    user_messages: list[str] = []

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle",
                        AsyncMock(side_effect=FileNotFoundError("not found")))
    monkeypatch.setattr("src.processors.repo.database.update_job_status",
                        AsyncMock(side_effect=lambda jid, s, **kw: statuses.append(s)))
    monkeypatch.setattr("src.processors.repo.send_message",
                        AsyncMock(side_effect=lambda c, t, **kw: user_messages.append(t)))
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert "error" in statuses
    assert any("check the URL" in m or "not found" in m.lower() for m in user_messages)


@pytest.mark.asyncio
async def test_run_gemini_unavailable_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses: list[str] = []
    user_messages: list[str] = []

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate",
                        AsyncMock(side_effect=GeminiUnavailableError("both keys failed")))
    monkeypatch.setattr("src.processors.repo.database.update_job_status",
                        AsyncMock(side_effect=lambda jid, s, **kw: statuses.append(s)))
    monkeypatch.setattr("src.processors.repo.send_message",
                        AsyncMock(side_effect=lambda c, t, **kw: user_messages.append(t)))
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert "error" in statuses
    assert any("Gemini" in m or "/force" in m for m in user_messages)


@pytest.mark.asyncio
async def test_run_rate_limit_403_shows_rate_limit_message(monkeypatch: pytest.MonkeyPatch) -> None:
    user_messages: list[str] = []

    class FakeHTTPError(Exception):
        class response:
            status_code = 403
            headers = {"X-RateLimit-Remaining": "0"}

    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle",
                        AsyncMock(side_effect=FakeHTTPError()))
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_message",
                        AsyncMock(side_effect=lambda c, t, **kw: user_messages.append(t)))
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert any("limit" in m.lower() or "hour" in m.lower() for m in user_messages)


# ---------------------------------------------------------------------------
# Task 12 — Freestyle re-run verification (#73)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_freestyle_prompt_passed_to_build_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """freestyle_prompt is forwarded to _build_repo_prompt."""
    prompts_seen: list[str | None] = []

    import src.processors.repo as repo_mod
    original = repo_mod._build_repo_prompt

    def spy_build(bundle, freestyle_prompt=None, flags=None):
        prompts_seen.append(freestyle_prompt)
        return original(bundle, freestyle_prompt=freestyle_prompt, flags=flags)

    monkeypatch.setattr("src.processors.repo._build_repo_prompt", spy_build)
    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": "explain for a Rust developer",
           "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)

    assert prompts_seen and prompts_seen[0] == "explain for a Rust developer"


@pytest.mark.asyncio
async def test_freestyle_with_sheets_row_id_calls_update_not_append(monkeypatch: pytest.MonkeyPatch) -> None:
    """With sheets_row_id set, _sheets_update_safe is called; _sheets_append_safe is not."""
    import asyncio as _asyncio
    update_calls: list = []
    append_calls: list = []

    async def fake_update_safe(row_idx, job, analysis, bundle):
        update_calls.append(row_idx)

    async def fake_append_safe(job_id, job, analysis, bundle):
        append_calls.append(job_id)

    def eager_create_task(coro):
        return _asyncio.ensure_future(coro)

    import src.processors.repo as repo_mod
    monkeypatch.setattr(repo_mod, "_sheets_update_safe", fake_update_safe)
    monkeypatch.setattr(repo_mod, "_sheets_append_safe", fake_append_safe)
    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")
    monkeypatch.setattr(repo_mod.asyncio, "create_task", eager_create_task)

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": "explain for a Rust developer",
           "template_analysis": _json.dumps(_ANALYSIS), "sheets_row_id": "5"}
    from src.processors.repo import run
    await run(job)
    await _asyncio.sleep(0)  # yield so fire-and-forget tasks execute

    assert update_calls == [5]
    assert not append_calls


@pytest.mark.asyncio
async def test_fresh_job_calls_append_not_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without sheets_row_id, _sheets_append_safe is called; _sheets_update_safe is not."""
    import asyncio as _asyncio
    update_calls: list = []
    append_calls: list = []

    async def fake_update_safe(row_idx, job, analysis, bundle):
        update_calls.append(row_idx)

    async def fake_append_safe(job_id, job, analysis, bundle):
        append_calls.append(job_id)

    def eager_create_task(coro):
        return _asyncio.ensure_future(coro)

    import src.processors.repo as repo_mod
    monkeypatch.setattr(repo_mod, "_sheets_update_safe", fake_update_safe)
    monkeypatch.setattr(repo_mod, "_sheets_append_safe", fake_append_safe)
    monkeypatch.setattr("src.processors.repo.fetch_repo_bundle", AsyncMock(return_value=_BUNDLE))
    monkeypatch.setattr("src.processors.repo.gemini.generate", AsyncMock(return_value=_json.dumps(_ANALYSIS)))
    monkeypatch.setattr("src.processors.repo.send_document", AsyncMock())
    monkeypatch.setattr("src.processors.repo.send_inline_keyboard", AsyncMock())
    monkeypatch.setattr("src.processors.repo.database.update_job_status", AsyncMock())
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "tok")
    monkeypatch.setattr(repo_mod.asyncio, "create_task", eager_create_task)

    job = {"id": "abc", "chat_id": 1, "url": "https://github.com/anthropics/claude-code",
           "freestyle_prompt": None, "template_analysis": None, "sheets_row_id": None}
    from src.processors.repo import run
    await run(job)
    await _asyncio.sleep(0)  # yield so fire-and-forget tasks execute

    assert append_calls == ["abc"]
    assert not update_calls

"""Tests for the repo pipeline stub processor (issue #66)."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")

from src.processors.repo import _format_stub_message, _days_ago, _parse_owner_repo


# ---------------------------------------------------------------------------
# _parse_owner_repo
# ---------------------------------------------------------------------------

def test_parse_owner_repo_bare() -> None:
    assert _parse_owner_repo("https://github.com/owner/repo") == ("owner", "repo")


def test_parse_owner_repo_subpath() -> None:
    assert _parse_owner_repo("https://github.com/owner/repo/blob/main/README.md") == ("owner", "repo")


# ---------------------------------------------------------------------------
# _format_stub_message — with metadata
# ---------------------------------------------------------------------------

_META = {
    "stars": 1234,
    "forks": 56,
    "language": "Python",
    "pushed_at": "2026-01-01T00:00:00Z",
}


def test_stub_message_contains_owner_repo() -> None:
    msg = _format_stub_message("anthropics", "claude-code", _META)
    assert "anthropics/claude-code" in msg


def test_stub_message_contains_stats() -> None:
    msg = _format_stub_message("anthropics", "claude-code", _META)
    assert "1,234" in msg   # stars formatted with comma
    assert "56" in msg      # forks
    assert "Python" in msg


def test_stub_message_contains_placeholder_text() -> None:
    msg = _format_stub_message("anthropics", "claude-code", _META)
    assert "placeholder" in msg.lower()


def test_stub_message_contains_link() -> None:
    msg = _format_stub_message("anthropics", "claude-code", _META)
    assert "https://github.com/anthropics/claude-code" in msg


# ---------------------------------------------------------------------------
# _format_stub_message — without metadata (API unavailable)
# ---------------------------------------------------------------------------

def test_stub_message_no_meta_shows_dashes() -> None:
    msg = _format_stub_message("owner", "repo", None)
    assert "—" in msg
    assert "owner/repo" in msg
    assert "https://github.com/owner/repo" in msg


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
# run() integration — mocked DB, sender, enrich_repo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_sends_message_and_marks_done(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    async def fake_send(chat_id, text):
        sent.append(text)

    async def fake_update_status(job_id, status, **_kwargs):
        pass

    async def fake_enrich(owner, repo, token):
        return _META

    monkeypatch.setattr("src.processors.repo.send_message", fake_send)
    monkeypatch.setattr("src.processors.repo.database.update_job_status", fake_update_status)
    monkeypatch.setattr("src.processors.repo.settings.GITHUB_TOKEN", "test-token")

    with patch("src.services.github.enrich_repo", new=AsyncMock(return_value=_META)):
        import src.processors.repo as repo_mod
        monkeypatch.setattr(repo_mod, "send_message", fake_send)

        # Patch enrich_repo inside the module's lazy import path
        import src.services.github as gh_mod
        monkeypatch.setattr(gh_mod, "enrich_repo", AsyncMock(return_value=_META))

        job = {
            "id": "abc123",
            "chat_id": 999,
            "url": "https://github.com/anthropics/claude-code",
        }
        import src.database as db_mod
        monkeypatch.setattr(db_mod, "update_job_status", fake_update_status)

        from src.processors.repo import run
        await run(job)

    assert len(sent) == 1
    assert "anthropics/claude-code" in sent[0]

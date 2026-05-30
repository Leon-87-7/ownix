"""Unit tests for src/services/sheets.py — consolidated workbook + named-tab routing.

See ADR-0013 (`docs/adr/0013-consolidate-sheets-into-tabs.md`).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services import sheets as sheets_svc


# ---------------------------------------------------------------------------
# Settings shape — the three old env vars are gone, one consolidated var exists
# ---------------------------------------------------------------------------


def test_settings_exposes_single_sheets_id() -> None:
    """settings.GOOGLE_SHEETS_ID is the canonical, single spreadsheet identifier."""
    from src.config import settings

    assert hasattr(settings, "GOOGLE_SHEETS_ID")


def test_settings_drops_legacy_short_var() -> None:
    """The legacy per-domain env var must be removed (ADR-0013)."""
    from src.config import settings

    with pytest.raises(AttributeError):
        _ = settings.GOOGLE_SHEETS_ID_SHORT  # type: ignore[attr-defined]


def test_settings_drops_legacy_long_var() -> None:
    """The legacy per-domain env var must be removed (ADR-0013)."""
    from src.config import settings

    with pytest.raises(AttributeError):
        _ = settings.GOOGLE_SHEETS_ID_LONG  # type: ignore[attr-defined]


def test_settings_drops_legacy_prd_var() -> None:
    """The legacy per-domain env var must be removed (ADR-0013)."""
    from src.config import settings

    with pytest.raises(AttributeError):
        _ = settings.GOOGLE_SHEETS_ID_PRD  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _append_sync — accepts tab_name, builds tab-qualified A1 range
# ---------------------------------------------------------------------------


def test_append_sync_builds_tab_qualified_range(monkeypatch) -> None:
    """_append_sync must construct range=f'{tab_name}!A1' against GOOGLE_SHEETS_ID."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID", "wb-123")

    mock_values = MagicMock()
    mock_values.append.return_value.execute.return_value = {}
    mock_spreadsheets = MagicMock()
    mock_spreadsheets.values.return_value = mock_values
    mock_service = MagicMock()
    mock_service.spreadsheets.return_value = mock_spreadsheets

    with patch("src.services.sheets._build_service", return_value=mock_service):
        sheets_svc._append_sync("My Tab", ["a", "b", "c"])

    mock_values.append.assert_called_once()
    call_kwargs = mock_values.append.call_args.kwargs
    assert call_kwargs["spreadsheetId"] == "wb-123"
    assert call_kwargs["range"] == "My Tab!A1"
    assert call_kwargs["body"] == {"values": [["a", "b", "c"]]}


# ---------------------------------------------------------------------------
# Per-domain helpers — each routes to its fixed tab name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_prd_row_routes_to_mini_prd_tab(monkeypatch) -> None:
    """append_prd_row must write to the 'mini PRD' tab."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID", "wb-123")

    mock_values = MagicMock()
    mock_values.append.return_value.execute.return_value = {}
    mock_spreadsheets = MagicMock()
    mock_spreadsheets.values.return_value = mock_values
    mock_service = MagicMock()
    mock_service.spreadsheets.return_value = mock_spreadsheets

    with patch("src.services.sheets._build_service", return_value=mock_service):
        await sheets_svc.append_prd_row(
            job_id="job_prd_1",
            video_url="https://youtube.com/watch?v=x",
            title="PRD title",
            drive_url="https://drive/x",
            slot="auto",
            intent_text=None,
        )

    mock_values.append.assert_called_once()
    call_kwargs = mock_values.append.call_args.kwargs
    assert call_kwargs["spreadsheetId"] == "wb-123"
    assert call_kwargs["range"] == "mini PRD!A1"


@pytest.mark.asyncio
async def test_append_short_row_routes_to_short_tab(monkeypatch) -> None:
    """append_short_row must write to the 'Short Video Analysis' tab."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID", "wb-123")

    captured: list = []

    def fake_append_sync(tab_name, values):
        captured.append((tab_name, values))

    with patch("src.services.sheets._append_sync", side_effect=fake_append_sync):
        await sheets_svc.append_short_row({"id": "j", "url": "https://x", "links": []})

    assert len(captured) == 1
    tab_name, _ = captured[0]
    assert tab_name == "Short Video Analysis"


@pytest.mark.asyncio
async def test_append_long_row_routes_to_long_tab(monkeypatch) -> None:
    """append_long_row must write to the 'YouTube Transcript Index' tab."""
    monkeypatch.setattr("src.services.sheets.settings.GOOGLE_SHEETS_ID", "wb-123")

    captured: list = []

    def fake_append_sync(tab_name, values):
        captured.append((tab_name, values))

    with patch("src.services.sheets._append_sync", side_effect=fake_append_sync):
        await sheets_svc.append_long_row(
            {"id": "j", "url": "https://yt/x", "title": "T", "drive_url": "https://d/x"},
            video_id="vid",
            channel="C",
            views="1",
            description_links_raw="",
            char_count=1,
            drive_file_id="fid",
        )

    assert len(captured) == 1
    tab_name, _ = captured[0]
    assert tab_name == "YouTube Transcript Index"


# ---------------------------------------------------------------------------
# Repo Analysis tab — TAB_REPO, append_repo_row, update_repo_row
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import patch as _patch

from src.services.sheets import TAB_REPO, append_repo_row, update_repo_row

_SHEETS_JOB = {
    "id": "20260101_120000_ABCD",
    "url": "https://github.com/anthropics/claude-code",
    "sheets_row_id": None,
    "created_at": "2026-01-01T12:00:00Z",
    "status": "done",
}
_SHEETS_ANALYSIS = {
    "title": "anthropics/claude-code",
    "tagline": "AI coding tool",
    "tech_stack": ["TypeScript", "Node.js"],
    "for_developers": {
        "project_ideas": ["Build workflows", "Extend"],
        "when_to_use": "In terminal",
        "avoid_when": "GUI needed",
    },
    "for_education": {
        "concepts_taught": ["LLM tool use"],
        "prerequisites": ["TypeScript"],
        "curriculum_hooks": [
            {"concept": "Tool calling", "file_pointer": "src/", "why": "Patterns"},
            {"concept": "Async", "file_pointer": None, "why": "Core"},
        ],
    },
}
_SHEETS_BUNDLE = {
    "owner": "anthropics", "repo": "claude-code",
    "metadata": {"stars": 100, "forks": 10, "language": "TypeScript",
                 "pushed_at": "2026-01-01T00:00:00Z", "description": "AI", "archived": False},
}


def test_tab_repo_constant() -> None:
    assert TAB_REPO == "Repo Analysis"


@pytest.mark.asyncio
async def test_append_repo_row_produces_20_columns() -> None:
    rows: list[list] = []

    async def patched_to_thread(fn, *args):
        return fn(*args)

    with _patch("src.services.sheets._append_sync", lambda t, v: (rows.append(v), 5)[1]), \
         _patch("asyncio.to_thread", patched_to_thread):
        await append_repo_row(_SHEETS_JOB, _SHEETS_ANALYSIS, _SHEETS_BUNDLE)

    assert rows, "no row appended"
    assert len(rows[0]) == 20


@pytest.mark.asyncio
async def test_append_repo_row_tech_stack_newline_joined() -> None:
    rows: list[list] = []

    async def patched_to_thread(fn, *args):
        return fn(*args)

    with _patch("src.services.sheets._append_sync", lambda t, v: (rows.append(v), 5)[1]), \
         _patch("asyncio.to_thread", patched_to_thread):
        await append_repo_row(_SHEETS_JOB, _SHEETS_ANALYSIS, _SHEETS_BUNDLE)

    tech_col = rows[0][6]  # column index 6
    assert "TypeScript" in tech_col
    assert "Node.js" in tech_col
    assert "\n" in tech_col


@pytest.mark.asyncio
async def test_append_repo_row_curriculum_hooks_serialization() -> None:
    rows: list[list] = []

    async def patched_to_thread(fn, *args):
        return fn(*args)

    with _patch("src.services.sheets._append_sync", lambda t, v: (rows.append(v), 5)[1]), \
         _patch("asyncio.to_thread", patched_to_thread):
        await append_repo_row(_SHEETS_JOB, _SHEETS_ANALYSIS, _SHEETS_BUNDLE)

    hooks_col = rows[0][17]  # column index 17
    assert "Tool calling — src/: Patterns" in hooks_col
    assert "Async: Core" in hooks_col
    assert "file_pointer" not in hooks_col


@pytest.mark.asyncio
async def test_append_repo_row_archived_is_TRUE_FALSE_string() -> None:
    rows: list[list] = []
    bundle = {**_SHEETS_BUNDLE, "metadata": {**_SHEETS_BUNDLE["metadata"], "archived": True}}

    async def patched_to_thread(fn, *args):
        return fn(*args)

    with _patch("src.services.sheets._append_sync", lambda t, v: (rows.append(v), 5)[1]), \
         _patch("asyncio.to_thread", patched_to_thread):
        await append_repo_row(_SHEETS_JOB, _SHEETS_ANALYSIS, bundle)

    assert rows[0][11] == "TRUE"  # archived column


@pytest.mark.asyncio
async def test_append_repo_row_failure_does_not_raise() -> None:
    async def patched_to_thread(fn, *args):
        raise RuntimeError("403 Forbidden")

    with _patch("asyncio.to_thread", patched_to_thread):
        await append_repo_row(_SHEETS_JOB, _SHEETS_ANALYSIS, _SHEETS_BUNDLE)  # must not raise

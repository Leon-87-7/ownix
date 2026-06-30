"""Operator-only export gate — per-user isolation, the #201 'now' fix (#202).

A non-operator job must complete end-to-end (GCS+DB+Telegram) without writing a
single row/file into the operator's shared Drive/Sheets. The gate lives at the
service boundary (drive.py upload helpers, sheets.py append_*/update_* fns) so a
new processor can't accidentally leak. See ADR-0027 / ADR-0022.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.config import settings
from src.services import drive as drive_svc
from src.services import sheets as sheets_svc

OPERATOR = 100
INTRUDER = 999


@pytest.fixture
def operator_set(monkeypatch):
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)


# --- the predicate ---------------------------------------------------------

def test_export_blocked_truth_table(monkeypatch):
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)
    assert settings.export_blocked(INTRUDER) is True
    assert settings.export_blocked(OPERATOR) is False
    # System/operator-internal calls (no chat_id, e.g. brain rebuild) never blocked.
    assert settings.export_blocked(None) is False


def test_export_never_blocked_when_operator_unset(monkeypatch):
    """Backward-compat: an unconfigured deployment exports for everyone."""
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)
    assert settings.export_blocked(INTRUDER) is False
    assert settings.export_blocked(OPERATOR) is False


# --- Drive helpers ---------------------------------------------------------

@pytest.mark.asyncio
async def test_drive_upload_skips_for_non_operator(operator_set):
    with patch("src.services.drive._upload_sync") as sync:
        file_id, link = await drive_svc.upload_file("body", "f.md", "folder", chat_id=INTRUDER)
    sync.assert_not_called()
    assert (file_id, link) == ("", "")


@pytest.mark.asyncio
async def test_drive_upload_runs_for_operator(operator_set):
    with patch("src.services.drive._upload_sync", return_value=("id1", "http://x")) as sync:
        await drive_svc.upload_file("body", "f.md", "folder", chat_id=OPERATOR)
    sync.assert_called_once()


@pytest.mark.asyncio
async def test_drive_upload_runs_for_system_call(operator_set):
    """No chat_id (brain rebuild, preflight) still exports — operator-owned aggregate."""
    with patch("src.services.drive._upload_sync", return_value=("id1", "http://x")) as sync:
        await drive_svc.upload_file("body", "f.md", "folder")
    sync.assert_called_once()


@pytest.mark.asyncio
async def test_drive_update_and_gdoc_skip_for_non_operator(operator_set):
    with patch("src.services.drive._update_sync") as up, \
         patch("src.services.drive._gdoc_sync") as gd:
        link = await drive_svc.update_file("fid", "body", chat_id=INTRUDER)
        glink = await drive_svc.export_to_gdoc("# md", "name", "folder", chat_id=INTRUDER)
    up.assert_not_called()
    gd.assert_not_called()
    assert link == "" and glink == ""


# --- Sheets helpers --------------------------------------------------------

@pytest.mark.asyncio
async def test_sheets_skip_for_non_operator(operator_set):
    job = {"id": "j1", "chat_id": INTRUDER, "url": "u"}
    with patch("src.services.sheets._append_sync") as ap, \
         patch("src.services.sheets._update_sync") as up:
        await sheets_svc.append_short_row(job)
        await sheets_svc.append_long_row(job, video_id="v", channel="c", views="0",
                                         description_links_raw="", char_count=0, drive_file_id="")
        await sheets_svc.append_article_row(job, domain="x.com")
        await sheets_svc.update_article_row(2, job, domain="x.com")
        await sheets_svc.append_repo_row(job, {}, {})
        await sheets_svc.update_repo_row(2, job, {}, {})
        await sheets_svc.append_prd_row(job_id="j1", video_url="u", title="t",
                                        drive_url="", chat_id=INTRUDER)
    ap.assert_not_called()
    up.assert_not_called()


@pytest.mark.asyncio
async def test_sheets_runs_for_operator(operator_set):
    job = {"id": "j1", "chat_id": OPERATOR, "url": "u"}
    with patch("src.services.sheets._append_sync", return_value=1) as ap:
        await sheets_svc.append_repo_row(job, {}, {})
    ap.assert_called_once()


# --- API call site ---------------------------------------------------------

def _export_request(chat_id):
    return SimpleNamespace(state=SimpleNamespace(user={"id": chat_id}))


@pytest.mark.asyncio
async def test_spaces_export_forwards_chat_id(operator_set, monkeypatch):
    """The operator's export must thread chat_id into export_to_gdoc."""
    from src.api import spaces

    monkeypatch.setattr("src.config.settings.GOOGLE_DRIVE_FOLDER_EXPORTS", "folder")
    request = _export_request(OPERATOR)

    with patch.object(spaces, "_get_owned_space", AsyncMock(return_value={"name": "S"})), \
         patch.object(spaces.database, "list_context_blobs", AsyncMock(return_value=[])), \
         patch.object(spaces.database, "list_space_urls", AsyncMock(return_value=[])), \
         patch.object(spaces.database, "list_tags", AsyncMock(return_value=[])), \
         patch.object(spaces, "_enrich_space_jobs", AsyncMock(return_value=[])), \
         patch("src.services.space_export.compose_space_export", return_value="# md"), \
         patch("src.services.drive.export_to_gdoc", AsyncMock(return_value="http://x")) as gdoc:
        out = await spaces.export_space("sp1", spaces.ExportIn(), request)  # type: ignore[arg-type]

    assert gdoc.await_args.kwargs["chat_id"] == OPERATOR
    assert out == {"url": "http://x"}


@pytest.mark.asyncio
async def test_spaces_export_blocked_returns_error(operator_set, monkeypatch):
    """A non-operator gets an error-shaped response, not a silent {"url": ""}."""
    from src.api import spaces

    monkeypatch.setattr("src.config.settings.GOOGLE_DRIVE_FOLDER_EXPORTS", "folder")
    request = _export_request(INTRUDER)

    with patch.object(spaces, "_get_owned_space", AsyncMock(return_value={"name": "S"})), \
         patch("src.services.drive.export_to_gdoc", AsyncMock()) as gdoc:
        out = await spaces.export_space("sp1", spaces.ExportIn(), request)  # type: ignore[arg-type]

    assert out == {"error": "export_blocked"}
    gdoc.assert_not_called()

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


@pytest.mark.asyncio
async def test_drive_invalid_grant_deletes_token_notifies_once_and_completes(monkeypatch):
    from google.auth.exceptions import RefreshError

    calls = {"handled": 0}

    def boom(*args, **kwargs):
        raise RefreshError("invalid_grant")

    async def handle_revoked(chat_id):
        calls["handled"] += 1
        assert chat_id == OPERATOR

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)
    monkeypatch.setattr(drive_svc, "_gdoc_sync", boom)
    monkeypatch.setattr(drive_svc, "handle_google_refresh_error", handle_revoked)

    assert await drive_svc.export_to_gdoc("# md", "n", "folder", chat_id=OPERATOR) == ""
    assert calls == {"handled": 1}


@pytest.mark.asyncio
async def test_google_connect_forces_consent(monkeypatch):
    from src.api import google_oauth

    class Url:
        def __init__(self, value):
            self.value = value
        def __str__(self):
            return self.value

    request = SimpleNamespace(
        state=SimpleNamespace(user={"id": OPERATOR}),
        url_for=lambda name: Url("https://api.example.com/api/google/callback"),
    )
    monkeypatch.setattr("src.config.settings.GOOGLE_OAUTH_CLIENT_ID", "client")

    response = await google_oauth.connect_google(request)  # type: ignore[arg-type]
    location = response.headers["location"]
    assert "prompt=consent" in location
    assert "access_type=offline" in location


@pytest.mark.asyncio
async def test_google_refresh_handler_deletes_token_and_notifies_once(monkeypatch):
    from src.services import google_auth

    calls = {"deleted": 0, "marked": 0, "sent": 0}

    async def mark_once(chat_id):
        calls["marked"] += 1
        return calls["marked"] == 1

    async def delete_token(chat_id):
        calls["deleted"] += 1

    async def send_message(chat_id, text, **kwargs):
        calls["sent"] += 1
        assert chat_id == OPERATOR
        assert "/connect" in text

    monkeypatch.setattr(google_auth, "mark_reconnect_notified_once", mark_once)
    monkeypatch.setattr(google_auth, "delete_google_token", delete_token)
    monkeypatch.setattr(google_auth.sender, "send_message", send_message)

    assert await google_auth.handle_google_refresh_error(OPERATOR) is True
    assert await google_auth.handle_google_refresh_error(OPERATOR) is False
    assert calls == {"deleted": 2, "marked": 2, "sent": 1}

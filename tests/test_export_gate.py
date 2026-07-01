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
        await sheets_svc.append_document_row(job)
        await sheets_svc.update_document_row(2, job)
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
    stored_state: dict[str, object] = {}

    async def store_state(state: str, chat_id: int) -> None:
        stored_state.update({"state": state, "chat_id": chat_id})

    monkeypatch.setattr("src.config.settings.GOOGLE_OAUTH_CLIENT_ID", "client")
    monkeypatch.setattr("src.config.settings.GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setattr("src.config.settings.GOOGLE_TOKEN_ENCRYPTION_KEY", "test-google-token-key")
    monkeypatch.setattr(google_oauth, "store_google_oauth_state", store_state)

    response = await google_oauth.connect_google(request)  # type: ignore[arg-type]
    location = response.headers["location"]
    assert "prompt=consent" in location
    assert "access_type=offline" in location
    assert stored_state["chat_id"] == OPERATOR
    assert f"state={stored_state['state']}" in location


@pytest.mark.asyncio
async def test_google_callback_denied_consent_redirects_without_crashing(monkeypatch):
    """A user clicking Cancel sends ?error=access_denied with no `code` — must not 422/500."""
    from src.api import google_oauth

    request = SimpleNamespace(url_for=lambda name: "https://api.example.com/api/google/callback")

    monkeypatch.setattr("src.config.settings.GOOGLE_OAUTH_CLIENT_ID", "client")
    monkeypatch.setattr("src.config.settings.GOOGLE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setattr("src.config.settings.GOOGLE_TOKEN_ENCRYPTION_KEY", "test-google-token-key")

    async def consume_state(state: str):
        return OPERATOR

    monkeypatch.setattr(google_oauth, "consume_google_oauth_state", consume_state)

    response = await google_oauth.google_oauth_callback(
        request, state="state-1", code=None, error="access_denied"
    )  # type: ignore[arg-type]
    assert response.status_code == 303
    assert "denied" in response.headers["location"]


@pytest.mark.asyncio
async def test_append_prd_row_reraises_on_refresh_error(monkeypatch):
    """append_prd_row must re-raise after handling a revoked token, matching its documented
    'let caller decide' contract — prd.py relies on the exception to warn the user."""
    from google.auth.exceptions import RefreshError

    calls = {"handled": 0}

    def boom(*args, **kwargs):
        raise RefreshError("invalid_grant")

    async def handle_revoked(chat_id):
        calls["handled"] += 1

    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)
    monkeypatch.setattr(sheets_svc, "_append_sync", boom)
    monkeypatch.setattr(sheets_svc, "handle_google_refresh_error", handle_revoked)

    with pytest.raises(RefreshError):
        await sheets_svc.append_prd_row(
            job_id="j1", video_url="u", title="t", drive_url="", chat_id=OPERATOR
        )
    assert calls == {"handled": 1}


@pytest.mark.asyncio
async def test_google_refresh_handler_deletes_token_and_notifies_once(monkeypatch):
    from src.services import google_auth

    calls = {"deleted": 0, "sent": 0}

    async def delete_token(chat_id):
        calls["deleted"] += 1
        return calls["deleted"] == 1

    async def send_message(chat_id, text, **kwargs):
        calls["sent"] += 1
        assert chat_id == OPERATOR
        assert "/connect" in text

    monkeypatch.setattr(google_auth, "delete_google_token", delete_token)
    monkeypatch.setattr(google_auth.sender, "send_message", send_message)

    assert await google_auth.handle_google_refresh_error(OPERATOR) is True
    assert await google_auth.handle_google_refresh_error(OPERATOR) is False
    assert calls == {"deleted": 2, "sent": 1}


@pytest.mark.asyncio
async def test_google_oauth_state_consumes_once(tmp_path, monkeypatch):
    from src import database
    from src.services.google_tokens import consume_google_oauth_state, store_google_oauth_state

    db_file = tmp_path / "oauth_state.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

    await database.init_db()
    await store_google_oauth_state("state-1", OPERATOR)

    assert await consume_google_oauth_state("state-1") == OPERATOR
    assert await consume_google_oauth_state("state-1") is None

    await store_google_oauth_state("expired", OPERATOR, ttl_seconds=-1)
    assert await consume_google_oauth_state("expired") is None

@pytest.mark.asyncio
async def test_export_blocked_allows_user_with_readable_google_token(tmp_path, monkeypatch):
    from src import database
    from src.services.google_tokens import store_google_token

    db_file = tmp_path / "export_gate_token.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.GOOGLE_TOKEN_ENCRYPTION_KEY", "test-google-token-key")
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", OPERATOR)

    await database.init_db()

    assert settings.export_blocked(INTRUDER) is True
    await store_google_token(INTRUDER, {"refresh_token": "refresh", "scopes": []})
    assert settings.export_blocked(INTRUDER) is False

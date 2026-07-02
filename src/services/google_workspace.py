"""Per-user Google Drive workspace helpers (/vig folder + workbook)."""
from __future__ import annotations

import sqlite3
import threading

from src.config import settings
from src.services.google_tokens import has_google_connection_sync

FOLDER_KEY = "google_workspace:folder_id"
SHEET_KEY = "google_workspace:sheet_id"
_LOCKS_GUARD = threading.Lock()
# ponytail: in-process lock only guards single-worker deploys (current prod is
# one process); move to a DB-level advisory lock if we ever run multi-worker.
_WORKSPACE_LOCKS: dict[tuple[int, str], threading.Lock] = {}


def _workspace_lock(chat_id: int, key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _WORKSPACE_LOCKS.setdefault((chat_id, key), threading.Lock())


def _get(chat_id: int, key: str) -> str | None:
    with sqlite3.connect(settings.DB_PATH) as conn:
        row = conn.execute("SELECT value FROM user_settings WHERE chat_id = ? AND key = ?", (chat_id, key)).fetchone()
    return str(row[0]) if row else None


def _set(chat_id: int, key: str, value: str) -> None:
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (chat_id, key, value, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id, key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, key, value),
        )
        conn.commit()


def user_folder_id(chat_id: int | None) -> str | None:
    if chat_id is None or not has_google_connection_sync(chat_id):
        return None
    with _workspace_lock(chat_id, FOLDER_KEY):
        existing = _get(chat_id, FOLDER_KEY)
        if existing:
            return existing
        from src.services.google_auth import build_google_service

        service = build_google_service("drive", "v3", ["https://www.googleapis.com/auth/drive.file"], chat_id=chat_id)
        result = service.files().create(
            body={"name": "vig", "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
            supportsAllDrives=True,
        ).execute()
        folder_id = result["id"]
        _set(chat_id, FOLDER_KEY, folder_id)
        return folder_id


def user_sheet_id(chat_id: int | None) -> str | None:
    if chat_id is None or not has_google_connection_sync(chat_id):
        return None
    with _workspace_lock(chat_id, SHEET_KEY):
        existing = _get(chat_id, SHEET_KEY)
        if existing:
            return existing
        from src.services.google_auth import build_google_service

        sheets = build_google_service("sheets", "v4", ["https://www.googleapis.com/auth/spreadsheets"], chat_id=chat_id)
        sheet = sheets.spreadsheets().create(body={"properties": {"title": "vig exports"}}, fields="spreadsheetId").execute()
        sheet_id = sheet["spreadsheetId"]
        # Record the sheet before attempting the folder move: if that call fails
        # (quota, permission, transient network), the sheet is still tracked instead
        # of being orphaned and re-created on every subsequent retry.
        _set(chat_id, SHEET_KEY, sheet_id)
        folder_id = user_folder_id(chat_id)
        if folder_id:
            drive = build_google_service("drive", "v3", ["https://www.googleapis.com/auth/drive.file"], chat_id=chat_id)
            drive.files().update(fileId=sheet_id, addParents=folder_id, fields="id", supportsAllDrives=True).execute()
        return sheet_id
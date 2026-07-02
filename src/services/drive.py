from __future__ import annotations

import asyncio
from typing import Any

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

from src.config import settings
from src.services.google_auth import build_google_service, handle_google_refresh_error
from src.services.google_workspace import user_folder_id
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service(chat_id: int | None = None) -> Any:
    return build_google_service("drive", "v3", _SCOPES, chat_id=chat_id)


async def _handle_refresh_error(chat_id: int | None, exc: RefreshError) -> str:
    if chat_id is None:
        raise exc
    await handle_google_refresh_error(chat_id)
    return ""


def _degrade_or_raise(chat_id: int | None, exc: HttpError, event: str, **fields: object) -> None:
    """Preserve the operator path's existing failure semantics (raise); degrade a
    per-user job to an empty result instead of crashing it (matches the RefreshError
    contract this PR already established for user_folder_id's live Drive calls)."""
    if chat_id is None:
        raise exc
    log.exception(event, chat_id=chat_id, **fields)


def _upload_sync(
    content: str | bytes,
    filename: str,
    folder_id: str,
    mime_type: str,
    chat_id: int | None = None,
) -> tuple[str, str]:
    if isinstance(content, str):
        content = content.encode("utf-8")
    service = _build_service(chat_id)
    media = MediaInMemoryUpload(content, mimetype=mime_type, resumable=False)
    file_meta = {"name": filename, "parents": [folder_id]}
    result = (
        service.files()
        .create(body=file_meta, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
        .execute()
    )
    return result["id"], result["webViewLink"]


async def upload_file(
    content: str | bytes,
    filename: str,
    folder_id: str,
    mime_type: str = "text/markdown",
    *,
    chat_id: int | None = None,
) -> tuple[str, str]:
    """Upload to Google Drive. Returns (file_id, web_view_link).

    Non-operator jobs are gated out (#202, ADR-0027): they get ("", "") and the
    file never lands in the operator's Drive. System calls (no chat_id) pass.
    """
    if settings.export_blocked(chat_id):
        log.info("drive_export_gated", filename=filename, chat_id=chat_id)
        return "", ""
    try:
        target_folder = await asyncio.to_thread(lambda: user_folder_id(chat_id) or folder_id)
        file_id, link = await asyncio.to_thread(
            _upload_sync, content, filename, target_folder, mime_type, chat_id
        )
    except RefreshError as exc:
        await _handle_refresh_error(chat_id, exc)
        return "", ""
    except HttpError as exc:
        _degrade_or_raise(chat_id, exc, "drive_upload_failed", filename=filename)
        return "", ""
    log.info("drive_uploaded", filename=filename, file_id=file_id)
    return file_id, link


def _update_sync(
    file_id: str, content: str | bytes, mime_type: str, chat_id: int | None = None
) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    service = _build_service(chat_id)
    media = MediaInMemoryUpload(content, mimetype=mime_type, resumable=False)
    result = (
        service.files()
        .update(fileId=file_id, media_body=media, fields="webViewLink", supportsAllDrives=True)
        .execute()
    )
    return result["webViewLink"]


async def update_file(
    file_id: str,
    content: str | bytes,
    mime_type: str = "text/markdown",
    *,
    chat_id: int | None = None,
) -> str:
    """In-place update of a Drive file. Returns the (unchanged) webViewLink.

    Gated for non-operator jobs (#202) — returns "" without touching Drive.
    """
    if settings.export_blocked(chat_id):
        log.info("drive_update_gated", file_id=file_id, chat_id=chat_id)
        return ""
    try:
        link = await asyncio.to_thread(_update_sync, file_id, content, mime_type, chat_id)
    except RefreshError as exc:
        return await _handle_refresh_error(chat_id, exc)
    except HttpError as exc:
        _degrade_or_raise(chat_id, exc, "drive_update_failed", file_id=file_id)
        return ""
    log.info("drive_updated", file_id=file_id)
    return link


def _gdoc_sync(markdown: str, name: str, folder_id: str, chat_id: int | None = None) -> str:
    """Upload *markdown* as a real Google Doc (Drive converts text/plain → Doc).
    Returns the webViewLink of the created document.
    """
    service = _build_service(chat_id)
    content_bytes = markdown.encode("utf-8")
    media = MediaInMemoryUpload(content_bytes, mimetype="text/plain", resumable=False)
    file_meta = {
        "name": name,
        "parents": [folder_id],
        "mimeType": "application/vnd.google-apps.document",
    }
    result = (
        service.files()
        .create(body=file_meta, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
        .execute()
    )
    return result["webViewLink"]


async def export_to_gdoc(
    markdown: str, name: str, folder_id: str, *, chat_id: int | None = None
) -> str:
    """Create a real, editable Google Doc in *folder_id* from *markdown*.
    Returns the Doc's webViewLink.

    Gated for non-operator jobs (#202) — returns "" without creating a Doc.
    """
    if settings.export_blocked(chat_id):
        log.info("gdoc_export_gated", name=name, chat_id=chat_id)
        return ""
    try:
        target_folder = await asyncio.to_thread(lambda: user_folder_id(chat_id) or folder_id)
        link = await asyncio.to_thread(_gdoc_sync, markdown, name, target_folder, chat_id)
    except RefreshError as exc:
        return await _handle_refresh_error(chat_id, exc)
    except HttpError as exc:
        _degrade_or_raise(chat_id, exc, "gdoc_export_failed", name=name)
        return ""
    log.info("gdoc_exported", name=name)
    return link

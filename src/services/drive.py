from __future__ import annotations

import asyncio
from typing import Any

from googleapiclient.http import MediaInMemoryUpload

from src.config import settings
from src.services.google_auth import build_google_service
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service() -> Any:
    return build_google_service("drive", "v3", _SCOPES)


def _upload_sync(content: str | bytes, filename: str, folder_id: str, mime_type: str) -> tuple[str, str]:
    if isinstance(content, str):
        content = content.encode("utf-8")
    service = _build_service()
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
    file_id, link = await asyncio.to_thread(_upload_sync, content, filename, folder_id, mime_type)
    log.info("drive_uploaded", filename=filename, file_id=file_id)
    return file_id, link


def _update_sync(file_id: str, content: str | bytes, mime_type: str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    service = _build_service()
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
    link = await asyncio.to_thread(_update_sync, file_id, content, mime_type)
    log.info("drive_updated", file_id=file_id)
    return link


def _gdoc_sync(markdown: str, name: str, folder_id: str) -> str:
    """Upload *markdown* as a real Google Doc (Drive converts text/plain → Doc).
    Returns the webViewLink of the created document.
    """
    service = _build_service()
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
    link = await asyncio.to_thread(_gdoc_sync, markdown, name, folder_id)
    log.info("gdoc_exported", name=name)
    return link

from __future__ import annotations

import asyncio
from typing import Any

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service() -> Any:
    # Prefer OAuth refresh token (required for personal Google accounts).
    # Fall back to service account (works with Shared Drives / Workspace).
    if settings.GOOGLE_OAUTH_REFRESH_TOKEN:
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=_SCOPES,
        )
        creds.refresh(Request())
    else:
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=_SCOPES
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


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
) -> tuple[str, str]:
    """Upload to Google Drive. Returns (file_id, web_view_link)."""
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
) -> str:
    """In-place update of a Drive file. Returns the (unchanged) webViewLink."""
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


async def export_to_gdoc(markdown: str, name: str, folder_id: str) -> str:
    """Create a real, editable Google Doc in *folder_id* from *markdown*.
    Returns the Doc's webViewLink.
    """
    link = await asyncio.to_thread(_gdoc_sync, markdown, name, folder_id)
    log.info("gdoc_exported", name=name)
    return link

from __future__ import annotations

import asyncio
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service() -> Any:
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
        .create(body=file_meta, media_body=media, fields="id,webViewLink")
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

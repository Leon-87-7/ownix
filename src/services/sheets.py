from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _build_service() -> Any:
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=_SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _append_sync(spreadsheet_id: str, values: list) -> None:
    service = _build_service()
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()


async def append_short_row(job: dict) -> None:
    """Append one row to GOOGLE_SHEETS_ID_SHORT. Columns: id, chat_id, url, title, platform, drive_url, processing_time_ms, created_at."""
    row = [
        job.get("id", ""),
        job.get("chat_id", ""),
        job.get("url", ""),
        job.get("title", ""),
        job.get("platform", ""),
        job.get("drive_url", ""),
        job.get("processing_time_ms", ""),
        job.get("created_at", ""),
    ]
    try:
        await asyncio.to_thread(_append_sync, settings.GOOGLE_SHEETS_ID_SHORT, row)
        log.info("sheets_short_appended", job_id=job.get("id"))
    except Exception:
        log.exception("sheets_short_failed", job_id=job.get("id"))


async def append_long_row(
    job: dict,
    *,
    video_id: str,
    channel: str,
    views: str,
    description_links_raw: str,
    char_count: int,
    drive_file_id: str,
) -> None:
    """
    Append one row to GOOGLE_SHEETS_ID_LONG.
    Columns (§13.15 verified shape):
      url, video_id, title, channel, description_links_raw, char_count,
      drive_file_id, drive_url, fetched_at, status,
      ai_objective, ai_action_points, ai_tools, ai_category, ai_topic, ai_market_data
    """
    fetched_at = datetime.now(timezone.utc).isoformat()
    row = [
        job.get("url", ""),
        video_id,
        job.get("title", ""),
        channel,
        description_links_raw,
        char_count,
        drive_file_id,
        job.get("drive_url", ""),
        fetched_at,
        "ok",
        "",  # ai_objective — filled by Phase 2
        "",  # ai_action_points
        "",  # ai_tools
        "",  # ai_category
        "",  # ai_topic
        "",  # ai_market_data
    ]
    try:
        await asyncio.to_thread(_append_sync, settings.GOOGLE_SHEETS_ID_LONG, row)
        log.info("sheets_long_appended", job_id=job.get("id"))
    except Exception:
        log.exception("sheets_long_failed", job_id=job.get("id"))

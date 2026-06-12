from __future__ import annotations

import asyncio
import re as _re
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.services.google_auth import build_google_service
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Tab names inside the consolidated workbook (ADR-0013).
# Each per-domain helper writes to a fixed tab; routing is enforced in code, not config.
TAB_LONG = "YouTube Transcript Index"
TAB_SHORT = "Short Video Analysis"
TAB_PRD = "mini PRD"
TAB_ARTICLE = "Article Analysis"
TAB_REPO = "Repo Analysis"


def _repo_row(job: dict, analysis: dict, bundle: dict) -> list:
    owner = bundle.get("owner", "")
    repo = bundle.get("repo", "")
    meta = bundle.get("metadata") or {}
    for_dev = analysis.get("for_developers") or {}
    for_edu = analysis.get("for_education") or {}

    def join_list(items: list) -> str:
        return "\n".join(str(x) for x in items) if items else ""

    def hooks_str(hooks: list) -> str:
        parts = []
        for h in hooks:
            fp = h.get("file_pointer")
            fp_part = f" — {fp}" if fp else ""
            parts.append(f"{h.get('concept', '')}{fp_part}: {h.get('why', '')}")
        return "\n".join(parts)

    return [
        job.get("id", ""),
        job.get("url", ""),
        owner,
        repo,
        analysis.get("title", f"{owner}/{repo}"),
        analysis.get("tagline", ""),
        join_list(analysis.get("tech_stack") or []),
        meta.get("stars", ""),
        meta.get("forks", ""),
        meta.get("language") or "",
        meta.get("pushed_at") or "",
        "TRUE" if meta.get("archived") else "FALSE",
        join_list(for_dev.get("project_ideas") or []),
        for_dev.get("when_to_use", ""),
        for_dev.get("avoid_when", ""),
        join_list(for_edu.get("concepts_taught") or []),
        join_list(for_edu.get("prerequisites") or []),
        hooks_str(for_edu.get("curriculum_hooks") or []),
        job.get("created_at", ""),
        job.get("status", ""),
    ]


async def _append_row_logged(tab: str, row: list, event_prefix: str, job_id) -> int | None:
    """Append *row* to *tab*; log `<prefix>_appended` / `<prefix>_failed`; never raise."""
    try:
        row_idx = await asyncio.to_thread(_append_sync, tab, row)
        log.info(f"{event_prefix}_appended", job_id=job_id, row_idx=row_idx)
        return row_idx
    except Exception:
        log.exception(f"{event_prefix}_failed", job_id=job_id)
        return None


async def _update_row_logged(tab: str, row_idx: int, row: list, event_prefix: str, job_id) -> None:
    """Overwrite *row_idx* in *tab*; log `<prefix>_updated` / `<prefix>_update_failed`."""
    try:
        await asyncio.to_thread(_update_sync, tab, row_idx, row)
        log.info(f"{event_prefix}_updated", job_id=job_id, row_idx=row_idx)
    except Exception:
        log.exception(f"{event_prefix}_update_failed", job_id=job_id)


async def append_repo_row(job: dict, analysis: dict, bundle: dict) -> int | None:
    """Append one row to 'Repo Analysis' tab and return the 1-based row index."""
    row = _repo_row(job, analysis, bundle)
    return await _append_row_logged(TAB_REPO, row, "sheets_repo", job.get("id"))


async def update_repo_row(row_idx: int, job: dict, analysis: dict, bundle: dict) -> None:
    """Overwrite the Repo Analysis row at row_idx (1-based) in-place."""
    row = _repo_row(job, analysis, bundle)
    await _update_row_logged(TAB_REPO, row_idx, row, "sheets_repo", job.get("id"))


def _build_service() -> Any:
    return build_google_service("sheets", "v4", _SCOPES)


def _append_sync(tab_name: str, values: list) -> int | None:
    """Append `values` to the consolidated workbook's `tab_name` tab.

    Range is tab-qualified A1 notation (`"<tab_name>!A1"`) — the Sheets v4 API
    routes the write to the named tab. With a bare `"A1"` range the API
    silently lands the row in the first tab regardless of intent (ADR-0013).

    Returns the 1-based row index written (parsed from the API's updatedRange),
    or None when the API response doesn't include that information.
    """
    service = _build_service()
    result = service.spreadsheets().values().append(
        spreadsheetId=settings.GOOGLE_SHEETS_ID,
        range=f"{tab_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [values]},
    ).execute()
    updated_range = result.get("updates", {}).get("updatedRange", "")
    m = _re.search(r"!A(\d+)", updated_range)
    return int(m.group(1)) if m else None


def _update_sync(tab_name: str, row_idx: int, values: list) -> None:
    """Overwrite a single row at 1-based *row_idx* in *tab_name*."""
    service = _build_service()
    service.spreadsheets().values().update(
        spreadsheetId=settings.GOOGLE_SHEETS_ID,
        range=f"{tab_name}!A{row_idx}",
        valueInputOption="USER_ENTERED",
        body={"values": [values]},
    ).execute()


async def append_short_row(job: dict) -> None:
    """Append one row to the 'Short Video Analysis' tab of GOOGLE_SHEETS_ID.

    Expected columns (must match sheet header order):
    job_id, url, chat_id, status, platform, title, duration_s, frame_count,
    best_frame_index, tools_message, links, tools_count, submitted_at,
    processed_at, error_message
    """
    links_raw = job.get("links", [])
    links_str = (
        ", ".join(lnk.get("url", "") for lnk in links_raw)
        if isinstance(links_raw, list)
        else str(links_raw)
    )
    row = [
        job.get("id", ""),
        job.get("url", ""),
        job.get("chat_id", ""),
        job.get("status", ""),
        job.get("platform", ""),
        job.get("title", ""),
        job.get("duration_s", ""),
        job.get("frame_count", ""),
        job.get("best_frame_index", ""),
        job.get("tools_message", ""),
        links_str,
        job.get("tools_count", ""),
        job.get("created_at", ""),
        job.get("completed_at", "") or job.get("updated_at", ""),
        job.get("error_msg", ""),
    ]
    try:
        await asyncio.to_thread(_append_sync, TAB_SHORT, row)
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
    """Append one row to the 'YouTube Transcript Index' tab of GOOGLE_SHEETS_ID.

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
        await asyncio.to_thread(_append_sync, TAB_LONG, row)
        log.info("sheets_long_appended", job_id=job.get("id"))
    except Exception:
        log.exception("sheets_long_failed", job_id=job.get("id"))


def _article_row(job: dict, *, domain: str) -> list:
    """Build the 11-column Article Analysis row from a completed job dict."""
    action_points = job.get("ai_action_points") or ""
    tools = job.get("ai_tools") or ""
    promise_gap_raw = job.get("promise_gap")
    try:
        import json as _json
        pg = _json.loads(promise_gap_raw) if promise_gap_raw else {}
        gaps = pg.get("gaps", [])
        hidden = pg.get("hidden_value", [])
        promise_gap_str = " | ".join(gaps + hidden)
    except Exception:
        promise_gap_str = promise_gap_raw or ""
    return [
        job.get("id", ""),
        job.get("url", ""),
        domain,
        job.get("title", ""),
        job.get("ai_topic", ""),
        job.get("ai_objective", ""),
        action_points,
        tools,
        promise_gap_str,
        job.get("created_at", ""),
        job.get("status", ""),
    ]


async def append_article_row(job: dict, *, domain: str) -> int | None:
    """Append one row to the 'Article Analysis' tab and return the 1-based row index.

    Columns: job_id, url, domain, title, topic, objective, action_points, tools,
             promise_gap, submitted_at, status
    """
    row = _article_row(job, domain=domain)
    return await _append_row_logged(TAB_ARTICLE, row, "sheets_article", job.get("id"))


async def update_article_row(row_idx: int, job: dict, *, domain: str) -> None:
    """Overwrite the existing Article Analysis row at *row_idx* (1-based) in-place."""
    row = _article_row(job, domain=domain)
    await _update_row_logged(TAB_ARTICLE, row_idx, row, "sheets_article", job.get("id"))


async def append_prd_row(
    *,
    job_id: str,
    video_url: str,
    title: str,
    drive_url: str,
    slot: str = "auto",
    intent_text: str | None = None,
) -> None:
    """Append one row to the 'mini PRD' tab of GOOGLE_SHEETS_ID.

    Columns: job_id, video_url, title, slot, intent_text, drive_url, created_at
    """
    row = [
        job_id,
        video_url,
        title,
        slot,
        intent_text,
        drive_url,
        datetime.now(timezone.utc).isoformat(),
    ]
    try:
        await asyncio.to_thread(_append_sync, TAB_PRD, row)
        log.info("sheets_prd_appended", job_id=job_id, slot=slot)
    except Exception:
        log.exception("sheets_prd_failed", job_id=job_id, slot=slot)
        raise  # let caller decide

"""Bookmark import processor — one job card, N standalone Brain links (#492,
#495, ADR-0048). content_type stays 'link'; the worker dispatches on the task
envelope's discriminator, not on content_type (see worker.py's docstring).

Sliced so links are usable before they are enriched (CONTEXT.md "Deferred
link enrichment"): this module inserts url + title + topic and commits —
description and embedding stay NULL, resolved later by a scoped pass (#496).
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

from src import database
from src.brain import _clean_title, _fallback_title_hint
from src.database import generate_id
from src.utils.bookmarks_html import parse_bookmarks_html
from src.utils.validators import coerce_url


def _add_date_to_iso(add_date: str | None) -> str | None:
    """Netscape ADD_DATE is a Unix epoch string; None on missing/malformed."""
    if not add_date:
        return None
    try:
        return datetime.fromtimestamp(int(add_date), tz=timezone.utc).isoformat()
    except (ValueError, OSError, OverflowError):
        return None


async def run(job: dict, *, html_b64: str = "") -> None:
    """Parse the bookmark HTML and insert one standalone link per URL.

    Snapshot ingest (ADR-0048): a URL that already exists as a link is
    skipped outright — no seen_count bump, no touch. A bookmark export is a
    snapshot of state, not a stream of events, so re-importing an unchanged
    export writes nothing.
    """
    job_id = job["id"]
    chat_id = job["chat_id"]
    await database.update_job_status(job_id, "processing")

    html = base64.b64decode(html_b64).decode("utf-8", errors="replace")
    raw_entries = parse_bookmarks_html(html)

    # Dedup by coerced URL, first occurrence wins — same rule as batch link
    # paste (#494). coerce_url also drops chrome://, file://, javascript:
    # entries for free.
    deduped: dict[str, dict] = {}
    for entry in raw_entries:
        url = coerce_url(entry.get("href", ""))
        if url is not None and url not in deduped:
            deduped[url] = entry

    now_iso = datetime.now(timezone.utc).isoformat()
    async with database.connection() as conn:
        for url, entry in deduped.items():
            cursor = await conn.execute(
                "SELECT 1 FROM links WHERE chat_id = ? AND url = ?", (chat_id, url)
            )
            if await cursor.fetchone() is not None:
                continue  # Snapshot ingest: already a link, leave it untouched.

            title = _clean_title(entry.get("title")) or _fallback_title_hint(url)
            topic = (entry.get("folder") or "").strip() or None
            created_at = _add_date_to_iso(entry.get("add_date")) or now_iso

            await conn.execute(
                """
                INSERT INTO links
                    (id, chat_id, url, title, topic, source_job, seen_count,
                     last_seen_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (generate_id(), chat_id, url, title, topic, job_id, now_iso, created_at, now_iso),
            )
        await conn.commit()

    await database.update_job_status(job_id, "done")

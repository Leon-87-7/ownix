"""Markdown cache (Jina Reader — issue #60 / ADR-0013).
"""

from __future__ import annotations



from src.db import core
from src.db.core import log, _execute, _execute_rowcount

# ---------------------------------------------------------------------------
# Markdown cache (Jina Reader — issue #60 / ADR-0013)
# ---------------------------------------------------------------------------


async def get_markdown_cache(url: str) -> dict | None:
    """Return the markdown_cache row for *url*, or None if absent."""
    async with core.connection() as conn:
        cursor = await conn.execute(
            "SELECT url, content, fetched_at FROM markdown_cache WHERE url = ?",
            (url,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def insert_markdown_cache(url: str, content: str) -> None:
    """Insert or replace a markdown_cache row for *url*."""
    await _execute(
        "INSERT OR REPLACE INTO markdown_cache (url, content, fetched_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP)",
        (url, content),
    )
    log.info("markdown_cache.inserted", url=url, content_len=len(content))


async def delete_markdown_cache(url: str) -> bool:
    """Delete the markdown_cache row for *url*. Returns True if a row was deleted."""
    return await _execute_rowcount("DELETE FROM markdown_cache WHERE url = ?", (url,)) > 0

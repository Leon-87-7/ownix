"""Spaces, the jobs pinned into them, and their context blobs.
"""

from __future__ import annotations

import json
from typing import Any


from src.db import core
from src.db.core import (
    _execute,
    _execute_rowcount,
    _fetch_all,
    _fetch_dicts,
    _fetch_one,
    _insert_returning,
    generate_id,
)

# ---------------------------------------------------------------------------
# Spaces (issue #89 / S6)
# ---------------------------------------------------------------------------


async def create_space(*, chat_id: int, name: str, color: str, icon: str = "folder") -> dict:
    """INSERT a new space row and return it as a dict."""
    space_id = generate_id()
    return await _insert_returning(
        "INSERT INTO spaces (id, chat_id, name, color, icon) VALUES (?, ?, ?, ?, ?)",
        (space_id, chat_id, name, color, icon),
        "SELECT id, chat_id, name, color, icon, created_at, updated_at FROM spaces WHERE id = ?",
        (space_id,),
    )


async def list_spaces(chat_id: int) -> list[dict]:
    """Return all spaces for chat_id ordered newest-first."""
    return await _fetch_dicts(
        "SELECT s.id, s.chat_id, s.name, s.color, s.icon, s.created_at, s.updated_at, "
        "(SELECT name FROM context_blobs WHERE space_id = s.id "
        " ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_name, "
        "(SELECT SUBSTR(content, 1, 140) FROM context_blobs WHERE space_id = s.id "
        " ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_snippet, "
        "(SELECT updated_at FROM context_blobs WHERE space_id = s.id "
        " ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_updated_at, "
        "(SELECT LENGTH(content) > 140 FROM context_blobs WHERE space_id = s.id "
        " ORDER BY sort_order ASC, id ASC LIMIT 1) AS note_truncated "
        "FROM spaces s WHERE s.chat_id = ? ORDER BY s.created_at DESC",
        (chat_id,),
    )


async def get_space(space_id: str) -> dict | None:
    """Return a single space by PK, or None."""
    row = await _fetch_one(
        "SELECT id, chat_id, name, color, icon, created_at, updated_at FROM spaces WHERE id = ?",
        (space_id,),
    )
    return dict(row) if row else None


async def update_space(
    *, chat_id: int, space_id: str, name: str, color: str, icon: str | None = None
) -> bool:
    """UPDATE name/color for a space owned by chat_id; icon only when provided. Returns True if updated."""
    return (
        await _execute_rowcount(
            "UPDATE spaces SET name = ?, color = ?, icon = COALESCE(?, icon), updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND chat_id = ?",
            (name, color, icon, space_id, chat_id),
        )
        > 0
    )


async def delete_space(*, chat_id: int, space_id: str) -> bool:
    """DELETE a space owned by chat_id. Returns True if deleted."""
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(
                """UPDATE email_digest_payloads
                      SET context_md = NULL
                    WHERE watch_id IN (
                        SELECT id FROM newsletter_watches
                         WHERE space_id = ? AND chat_id = ?
                    )""",
                (space_id, chat_id),
            )
            cur = await conn.execute(
                "DELETE FROM spaces WHERE id = ? AND chat_id = ?",
                (space_id, chat_id),
            )
            await conn.commit()
            return cur.rowcount > 0
        except Exception:
            await conn.rollback()
            raise
async def add_space_url(*, space_id: str, job_id: str) -> bool:
    """Pin a job into a space. sort_order = max+1. Idempotent (INSERT OR IGNORE)."""
    await _execute(
        """INSERT OR IGNORE INTO space_urls (space_id, job_id, sort_order)
           VALUES (?, ?, COALESCE(
               (SELECT MAX(sort_order) FROM space_urls WHERE space_id = ?), 0
           ) + 1)""",
        (space_id, job_id, space_id),
    )
    return True


async def remove_space_url(*, space_id: str, job_id: str) -> bool:
    """Unpin a job from a space. Returns True if the row existed."""
    return (
        await _execute_rowcount(
            "DELETE FROM space_urls WHERE space_id = ? AND job_id = ?",
            (space_id, job_id),
        )
        > 0
    )


async def list_pending_purge_tasks() -> list[dict[str, Any]]:
    """Return all purge tasks that have not yet been enqueued to Redis."""
    rows = await _fetch_all("SELECT id, task_payload FROM purge_tasks WHERE enqueued_at IS NULL ORDER BY created_at")
    return [{"id": row["id"], "task_payload": json.loads(row["task_payload"])} for row in rows]


async def mark_purge_task_enqueued(task_id: int) -> None:
    """Mark a purge task as successfully enqueued to Redis."""
    await _execute(
        "UPDATE purge_tasks SET enqueued_at = CURRENT_TIMESTAMP WHERE id = ?",
        (task_id,),
    )


async def reorder_space_url(*, space_id: str, job_id: str, new_sort_order: int) -> bool:
    """Update sort_order for a pinned job. Returns True if the row existed."""
    return (
        await _execute_rowcount(
            "UPDATE space_urls SET sort_order = ? WHERE space_id = ? AND job_id = ?",
            (new_sort_order, space_id, job_id),
        )
        > 0
    )


async def list_space_urls(space_id: str, chat_id: int) -> list[dict]:
    """Return jobs pinned to a space, joined with key job fields, ordered by sort_order."""
    return await _fetch_dicts(
        """SELECT j.id, j.title, j.url, j.content_type, j.status,
                  su.sort_order, su.added_at
           FROM space_urls su
           JOIN jobs j ON j.id = su.job_id AND j.chat_id = ?
           WHERE su.space_id = ?
           ORDER BY su.sort_order ASC""",
        (chat_id, space_id),
    )
# ---------------------------------------------------------------------------
# Context blobs (issue #93 / S7)
# ---------------------------------------------------------------------------


async def create_context_blob(
    *, space_id: str, name: str, content: str = "", source_url: str | None = None
) -> dict:
    """INSERT a context blob; auto-assigns sort_order = max+1. Returns the row."""
    blob_id = generate_id()
    return await _insert_returning(
        """INSERT INTO context_blobs (id, space_id, name, content, source_url, sort_order)
           VALUES (?, ?, ?, ?, ?, COALESCE(
               (SELECT MAX(sort_order) FROM context_blobs WHERE space_id = ?), 0
           ) + 1)""",
        (blob_id, space_id, name, content, source_url, space_id),
        "SELECT id, space_id, name, content, source_url, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE id = ?",
        (blob_id,),
    )


async def list_context_blobs(space_id: str) -> list[dict]:
    """Return all context blobs for a space ordered by sort_order."""
    return await _fetch_dicts(
        "SELECT id, space_id, name, content, source_url, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE space_id = ? ORDER BY sort_order ASC",
        (space_id,),
    )


# Ownership note: none of the four functions below take chat_id — the caller
# (src/api/spaces.py's route handlers) is responsible for verifying the blob's
# parent space is owned by request.state.user["id"] BEFORE calling any of these.
# If you add a new caller, verify ownership first; these functions trust the caller.
async def get_context_blob(blob_id: str) -> dict | None:
    """Return a single context blob by PK, or None."""
    row = await _fetch_one(
        "SELECT id, space_id, name, content, source_url, sort_order, created_at, updated_at "
        "FROM context_blobs WHERE id = ?",
        (blob_id,),
    )
    return dict(row) if row else None


async def update_context_blob(*, blob_id: str, name: str, content: str) -> bool:
    """UPDATE name and content; sets updated_at. Returns True if the row existed."""
    return (
        await _execute_rowcount(
            "UPDATE context_blobs SET name = ?, content = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (name, content, blob_id),
        )
        > 0
    )


async def delete_context_blob(blob_id: str) -> bool:
    """DELETE a context blob. Returns True if the row existed."""
    return await _execute_rowcount("DELETE FROM context_blobs WHERE id = ?", (blob_id,)) > 0


async def reorder_context_blob(*, blob_id: str, new_sort_order: int) -> bool:
    """UPDATE sort_order for a blob. Returns True if the row existed."""
    return (
        await _execute_rowcount(
            "UPDATE context_blobs SET sort_order = ? WHERE id = ?",
            (new_sort_order, blob_id),
        )
        > 0
    )

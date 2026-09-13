"""User-applied metadata on jobs and links: tags, tag links and annotations.
"""

from __future__ import annotations

import json


from src.config import settings
from src.db import core
from src.db.core import (
    _execute,
    _execute_rowcount,
    _fetch_dicts,
    _fetch_in,
    _fetch_one,
    _insert_returning,
    generate_id,
)

# ---------------------------------------------------------------------------
# Tags (web dashboard — issue #87 / S4)
# ---------------------------------------------------------------------------


async def list_tags(chat_id: int) -> list[dict]:
    rows = await _fetch_dicts(
        "SELECT id, name, meaning, color, icon, pinned, created_at FROM tags WHERE chat_id = ? ORDER BY name",
        (chat_id,),
    )
    for row in rows:
        row["pinned"] = bool(row["pinned"])
    return rows


async def get_tag(chat_id: int, tag_id: str) -> dict | None:
    row = await _fetch_one(
        "SELECT id, name, meaning, color, icon, pinned FROM tags WHERE id = ? AND chat_id = ?",
        (tag_id, chat_id),
    )
    if row is None:
        return None
    result = dict(row)
    result["pinned"] = bool(result["pinned"])
    return result


class TagTokenCollisionError(ValueError):
    """A create/rename would introduce a canonical token collision."""


async def _reject_tag_token_collision(chat_id: int, name: str, *, exclude_id: str | None = None) -> None:
    from src.intake.tag_tokens import normalize

    wanted = normalize(name)
    for tag in await list_tags(chat_id):
        if tag["id"] != exclude_id and normalize(tag["name"]) == wanted:
            raise TagTokenCollisionError(f"Tag token #{wanted} already belongs to {tag['name']!r}")


async def create_tag(*, chat_id: int, name: str, meaning: str, color: str, icon: str | None = None) -> dict:
    tag_id = generate_id()
    async with core.connection() as conn:
        # Serialize the canonical check with the write. SQLite's exact-name
        # UNIQUE constraint cannot protect alternate spellings of one token.
        await conn.execute("BEGIN IMMEDIATE")
        from src.intake.tag_tokens import normalize
        rows = await (await conn.execute("SELECT id, name FROM tags WHERE chat_id = ?", (chat_id,))).fetchall()
        wanted = normalize(name)
        for row in rows:
            if normalize(row["name"]) == wanted:
                raise TagTokenCollisionError(
                    f"Tag token #{wanted} already belongs to {row['name']!r}"
                )
        await conn.execute(
            "INSERT INTO tags (id, chat_id, name, meaning, color, icon) VALUES (?, ?, ?, ?, ?, ?)",
            (tag_id, chat_id, name, meaning, color, icon),
        )
        await conn.commit()
    return {"id": tag_id, "name": name, "meaning": meaning, "color": color, "icon": icon, "pinned": False}


async def update_tag(*, chat_id: int, tag_id: str, name: str, meaning: str, color: str, icon: str | None = None) -> bool:
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        from src.intake.tag_tokens import normalize
        rows = await (await conn.execute("SELECT id, name FROM tags WHERE chat_id = ?", (chat_id,))).fetchall()
        wanted = normalize(name)
        for row in rows:
            if row["id"] != tag_id and normalize(row["name"]) == wanted:
                raise TagTokenCollisionError(
                    f"Tag token #{wanted} already belongs to {row['name']!r}"
                )
        cursor = await conn.execute(
            "UPDATE tags SET name = ?, meaning = ?, color = ?, icon = ? WHERE id = ? AND chat_id = ?",
            (name, meaning, color, icon, tag_id, chat_id),
        )
        await conn.commit()
        return cursor.rowcount > 0


async def delete_tag(*, chat_id: int, tag_id: str) -> bool:
    return (
        await _execute_rowcount("DELETE FROM tags WHERE id = ? AND chat_id = ?", (tag_id, chat_id))
        > 0
    )


async def set_tag_pinned(*, chat_id: int, tag_id: str, pinned: bool) -> dict | None:
    """Toggle a tag's GoTo-pin. Any number of a chat's tags may be pinned at once."""
    row = await _fetch_one(
        "SELECT id, name, meaning, color, icon FROM tags WHERE id = ? AND chat_id = ?",
        (tag_id, chat_id),
    )
    if row is None:
        return None
    await _execute_rowcount(
        "UPDATE tags SET pinned = ? WHERE id = ? AND chat_id = ?",
        (1 if pinned else 0, tag_id, chat_id),
    )
    result = dict(row)
    result["pinned"] = pinned
    return result
# ---------------------------------------------------------------------------
# Job annotations + job-tag links (issue #88 / S5)
# ---------------------------------------------------------------------------


async def get_job_annotation(job_id: str) -> dict | None:
    """Return the job_annotations row for *job_id*, or None if absent."""
    row = await _fetch_one(
        "SELECT job_id, notes, updated_at FROM job_annotations WHERE job_id = ?",
        (job_id,),
    )
    return dict(row) if row else None


async def upsert_job_annotation(job_id: str, notes: str) -> dict:
    """Insert or replace the annotation for *job_id*. Returns the saved row."""
    return await _insert_returning(
        """INSERT INTO job_annotations (job_id, notes, updated_at)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(job_id) DO UPDATE SET
               notes      = excluded.notes,
               updated_at = excluded.updated_at""",
        (job_id, notes),
        "SELECT job_id, notes, updated_at FROM job_annotations WHERE job_id = ?",
        (job_id,),
    )


async def list_link_tags(link_id: str, chat_id: int | None = None) -> list[dict]:
    """Return tags attached to *link_id* ordered by name.

    Tags are viewer-private (CONTEXT.md "Link tag") — pass ``chat_id`` to
    constrain to the viewer's own vocabulary. The statement is static; the
    scope is the null-tolerant ``(? IS NULL OR t.chat_id = ?)`` form.
    """
    return await _fetch_dicts(
        """SELECT t.id, t.name, t.color, t.meaning, t.icon
           FROM link_tags lt
           JOIN tags t ON t.id = lt.tag_id
           WHERE lt.link_id = ? AND (? IS NULL OR t.chat_id = ?)
           ORDER BY t.name""",
        (link_id, chat_id, chat_id),
    )


async def attach_link_tag(link_id: str, tag_id: str) -> bool:
    await _execute(
        "INSERT OR IGNORE INTO link_tags (link_id, tag_id) VALUES (?, ?)", (link_id, tag_id)
    )
    return True


async def detach_link_tag(link_id: str, tag_id: str) -> bool:
    return (
        await _execute_rowcount(
            "DELETE FROM link_tags WHERE link_id = ? AND tag_id = ?",
            (link_id, tag_id),
        )
        > 0
    )


async def resolve_link_ids(chat_id: int, urls: list[str]) -> dict[str, str]:
    """Return normalized URL -> link ID for one user's URLs in one query."""
    unique_urls = list(dict.fromkeys(urls))
    if not unique_urls:
        return {}
    rows = await _fetch_in(
        "SELECT url, id FROM links WHERE chat_id = ? AND url IN ({placeholders})",
        unique_urls,
        chat_id,
    )
    return {row["url"]: row["id"] for row in rows}


async def delete_link(link_id: str, chat_id: int) -> bool:
    """Delete a Brain link owned by *chat_id*; its link_tags cascade.

    Ownership is persisted on ``links.chat_id`` so retained links stay deletable
    after their source job is removed. Legacy rows without a stored owner fall
    back through ``source_job`` and then the Operator.

    If the link owns a Drive ``.md`` node, a purge task is recorded in the same
    transaction (the outbox job deletion already uses — src/processors/purge.py)
    so it doesn't outlive the link the way it used to.
    """
    async with core.connection() as conn:
        row = await (
            await conn.execute(
                """SELECT drive_file_id,
                       COALESCE(
                           links.chat_id,
                           (SELECT j.chat_id FROM jobs j WHERE j.id = links.source_job),
                           ?
                       ) AS owner_chat_id
                   FROM links WHERE id = ?""",
                (settings.OPERATOR_CHAT_ID, link_id),
            )
        ).fetchone()
        if row is None or row["owner_chat_id"] != chat_id:
            return False
        cursor = await conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
        if cursor.rowcount > 0 and row["drive_file_id"]:
            purge_payload = {
                "task": "job_purge",
                "job_id": link_id,
                "chat_id": chat_id,
                "drive_file_ids": [row["drive_file_id"]],
            }
            await conn.execute(
                "INSERT INTO purge_tasks (job_id, chat_id, task_payload) VALUES (?, ?, ?)",
                (link_id, chat_id, json.dumps(purge_payload)),
            )
        await conn.commit()
        return cursor.rowcount > 0


async def list_job_tags(job_id: str) -> list[dict]:
    """Return tags attached to *job_id* ordered by name."""
    return await _fetch_dicts(
        """SELECT t.id, t.name, t.color, t.meaning, t.icon
           FROM job_tags jt
           JOIN tags t ON t.id = jt.tag_id
           WHERE jt.job_id = ?
           ORDER BY t.name""",
        (job_id,),
    )
async def batch_get_job_annotations(job_ids: list[str]) -> dict[str, str]:
    """Return {job_id: notes} for jobs that have saved annotations."""
    rows = await _fetch_in(
        "SELECT job_id, notes FROM job_annotations WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"]: row["notes"] for row in rows}


async def batch_list_job_tags(job_ids: list[str]) -> dict[str, list[dict]]:
    """Return {job_id: [tag_dicts]} for all given job IDs (absent job = empty list)."""
    if not job_ids:
        return {}
    rows = await _fetch_in(
        """SELECT jt.job_id, t.id, t.name, t.color, t.meaning, t.icon
           FROM job_tags jt
           JOIN tags t ON t.id = jt.tag_id
           WHERE jt.job_id IN ({placeholders})
           ORDER BY t.name""",
        job_ids,
    )
    result: dict[str, list[dict]] = {jid: [] for jid in job_ids}
    for row in rows:
        jid = row.pop("job_id")
        result[jid].append(row)
    return result


async def batch_list_link_tags(link_ids: list[str]) -> dict[str, list[dict]]:
    """Return {link_id: [tag_dicts]} for all given link IDs (absent link = empty list)."""
    if not link_ids:
        return {}
    rows = await _fetch_in(
        """SELECT lt.link_id, t.id, t.name, t.color, t.meaning, t.icon
           FROM link_tags lt
           JOIN tags t ON t.id = lt.tag_id
           WHERE lt.link_id IN ({placeholders})
           ORDER BY t.name""",
        link_ids,
    )
    result: dict[str, list[dict]] = {lid: [] for lid in link_ids}
    for row in rows:
        lid = row.pop("link_id")
        result[lid].append(row)
    return result


async def batch_list_effective_job_tags(items: list[dict]) -> dict[str, list[dict]]:
    """Return {job_id: [tag_dicts]}, unioning job_tags with link_tags via item["link_id"].

    Mirrors the frontend's useMergedTags: sweep_job_tags_to_link empties a linked
    job's job_tags, so the union never double-counts once a job has resolved to
    a link. Callers must resolve link_id (e.g. via _add_link_ids) first.
    """
    job_ids = [item["id"] for item in items]
    link_ids = [item["link_id"] for item in items if item.get("link_id")]
    job_tag_map = await batch_list_job_tags(job_ids)
    link_tag_map = await batch_list_link_tags(link_ids)
    result: dict[str, list[dict]] = {}
    for item in items:
        tags = job_tag_map.get(item["id"], [])
        if item.get("link_id"):
            tags = tags + link_tag_map.get(item["link_id"], [])
        result[item["id"]] = tags
    return result


async def attach_job_tag(job_id: str, tag_id: str) -> bool:
    """Attach *tag_id* to *job_id*. Idempotent. Returns True."""
    await _execute(
        "INSERT OR IGNORE INTO job_tags (job_id, tag_id) VALUES (?, ?)", (job_id, tag_id)
    )
    return True


async def detach_job_tag(job_id: str, tag_id: str) -> bool:
    """Remove *tag_id* from *job_id*. Returns True if a row was deleted."""
    return (
        await _execute_rowcount(
            "DELETE FROM job_tags WHERE job_id = ? AND tag_id = ?",
            (job_id, tag_id),
        )
        > 0
    )


async def job_ids_with_tags(job_ids: list[str]) -> set[str]:
    """Return the subset of *job_ids* that still have job_tags rows.

    Lets callers skip a per-job sweep query for jobs already swept — most
    requests, once a job has been swept once.
    """
    if not job_ids:
        return set()
    rows = await _fetch_in(
        "SELECT DISTINCT job_id FROM job_tags WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"] for row in rows}


async def sweep_job_tags_to_link(job_id: str, link_id: str) -> None:
    """Union a job's tag attachments onto a link, then remove the job copies."""
    for tag in await list_job_tags(job_id):
        await attach_link_tag(link_id, tag["id"])
        await detach_job_tag(job_id, tag["id"])
async def count_jobs_by_tag(chat_id: int) -> dict[str, int]:
    """Return {tag id: how many of this user's jobs carry it}.

    The server-mode counterpart to the frontend's deriveTagCounts, which can
    only count the jobs the browser is holding. Unions job_tags with link_tags
    the same way `batch_list_effective_job_tags` does, and counts each job once
    per tag even when both sides carry it.
    """
    async with core.connection() as conn:
        cur = await conn.execute(
            """SELECT tag_id, COUNT(DISTINCT job_id) AS cnt FROM (
                   SELECT jt.tag_id AS tag_id, j.id AS job_id
                   FROM job_tags jt JOIN jobs j ON j.id = jt.job_id
                   WHERE j.chat_id = ? AND j.status != 'cancelled'
                     AND j.url NOT LIKE 'email_digest:%'
                   UNION
                   SELECT lt.tag_id AS tag_id, j.id AS job_id
                   FROM link_tags lt JOIN jobs j ON j.link_id = lt.link_id
                   WHERE j.chat_id = ? AND j.status != 'cancelled'
                     AND j.url NOT LIKE 'email_digest:%'
               ) GROUP BY tag_id""",
            (chat_id, chat_id),
        )
        return {row["tag_id"]: row["cnt"] for row in await cur.fetchall()}

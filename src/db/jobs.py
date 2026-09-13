"""The jobs table: lifecycle, thumbnails, chat state and document outputs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal


from src.db import core
from src.db.core import (
    log,
    _execute,
    _execute_rowcount,
    _fetch_dicts,
    _fetch_in,
    _fetch_one,
    generate_id,
)

async def create_job(
    *,
    chat_id: int,
    url: str,
    content_type: str,
    source_url: str | None = None,
    message_id: int | None = None,
    template: str | None = None,
    freestyle_prompt: str | None = None,
    status: str = "pending",
) -> str:
    """Insert a new job row with the requested initial status and return its ID."""
    job_id = generate_id()
    async with core.connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                id, chat_id, message_id, url, source_url, content_type,
                status, template, freestyle_prompt
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id, chat_id, message_id, url, source_url, content_type,
                status, template, freestyle_prompt,
            ),
        )
        await conn.commit()
    log.info("job_created", job_id=job_id, chat_id=chat_id, content_type=content_type)
    return job_id


async def create_held_job_unless_recent(
    *,
    chat_id: int,
    url: str,
    content_type: str,
    message_id: int | None = None,
) -> dict[str, Any]:
    """Atomically deduplicate and insert a held pre-approval job."""
    job_id = generate_id()
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        cur = await conn.execute(
            "SELECT * FROM jobs "
            "WHERE chat_id = ? AND url = ? AND status NOT IN ('error', 'cancelled') "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (chat_id, url),
        )
        row = await cur.fetchone()
        if row:
            await conn.commit()
            return {**dict(row), "_deduped": True}

        await conn.execute(
            """
            INSERT INTO jobs (id, chat_id, message_id, url, content_type, status)
            VALUES (?, ?, ?, ?, ?, 'held')
            """,
            (job_id, chat_id, message_id, url, content_type),
        )
        cur = await conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        created = await cur.fetchone()
        await conn.commit()

    log.info("held_job_created", job_id=job_id, chat_id=chat_id, content_type=content_type)
    return {**dict(created), "_deduped": False}  # type: ignore[arg-type]


async def reset_job(job_id: str) -> None:
    """Reset a job back to pending, clearing all result fields. Increments attempt."""
    async with core.connection() as conn:
        await conn.execute(
            """
            UPDATE jobs SET
                status = 'pending',
                attempt = attempt + 1,
                error_msg = NULL,
                drive_url = NULL,
                transcript_drive_url = NULL,
                title = NULL,
                transcript = NULL,
                bot_message_id = NULL,
                key_phrases = NULL,
                template_analysis = NULL,
                ai_category = NULL,
                ai_topic = NULL,
                ai_objective = NULL,
                ai_action_points = NULL,
                ai_tools = NULL,
                ai_market_data = NULL,
                processing_time_ms = NULL,
                best_frame_index = NULL,
                platform = NULL,
                video_id = NULL,
                og_image_url = NULL,
                summary = NULL,
                links = NULL,
                promise_gap = NULL,
                completed_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
        await conn.execute("DELETE FROM job_thumbnails WHERE job_id = ?", (job_id,))
        await conn.commit()
    log.info("job_reset", job_id=job_id)


async def get_job(job_id: str) -> dict[str, Any] | None:
    row = await _fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return dict(row) if row else None


async def update_job_status(job_id: str, status: str, **fields: Any) -> None:
    """Update status + updated_at, plus any additional columns passed as kwargs."""
    set_parts = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = [status]
    for col, val in fields.items():
        set_parts.append(f"{col} = ?")
        params.append(val)
    params.append(job_id)
    async with core.connection() as conn:
        # Interpolated text is only `<col> = ?`, and `col` is a **fields key, so
        # Python has already constrained it to an identifier. Values bind as `?`.
        await conn.execute(  # nosemgrep
            f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",  # nosec B608
            params,
        )
        await conn.commit()
    log.info("job_status_updated", job_id=job_id, status=status)


async def clear_job_checklists(job_id: str, expected_generated_at: str | None) -> bool:
    """Clear a job's checklist only if it is still the one the caller saw.

    The match happens inside the UPDATE, so a generation landing between the
    caller's read and this write loses the race instead of being erased. Returns
    False when the stored checklist has moved on; True when the row was cleared
    or was already empty (nothing to erase, so the caller's intent holds).
    """
    async with core.connection() as conn:
        cursor = await conn.execute(
            "UPDATE jobs SET checklists_md = NULL, checklists_generated_at = NULL, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND checklists_generated_at IS ?",
            (job_id, expected_generated_at),
        )
        cleared = cursor.rowcount > 0
        await conn.commit()
        if cleared:
            log.info("job_checklists_cleared", job_id=job_id)
            return True
        # No row matched: either the checklist moved on (conflict) or there was
        # never one to clear (idempotent no-op).
        async with conn.execute(
            "SELECT checklists_generated_at FROM jobs WHERE id = ?", (job_id,)
        ) as check:
            row = await check.fetchone()
    return row is not None and row[0] is None


async def update_job_fields(job_id: str, **fields: Any) -> None:
    """Update job fields without changing its workflow status."""
    if not fields:
        return
    set_parts = ["updated_at = CURRENT_TIMESTAMP"]
    params: list[Any] = []
    for col, val in fields.items():
        set_parts.append(f"{col} = ?")
        params.append(val)
    params.append(job_id)
    async with core.connection() as conn:
        # Same as update_job_status: only `<col> = ?` is interpolated, and `col`
        # is a **fields key. Values bind as `?`.
        await conn.execute(  # nosemgrep
            f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?",  # nosec B608
            params,
        )
        await conn.commit()
    log.info("job_fields_updated", job_id=job_id, fields=list(fields))


async def backfill_og_image_url(job_id: str, og_image_url: str) -> bool:
    """Set og_image_url for a still-completed article without touching status.

    Idempotent and race-safe: only writes when the job is still ``done`` and the
    column is still empty, so a job reset to pending between scan and write is
    never forced back to ``done``. Returns True iff a row was updated.
    """
    rowcount = await _execute_rowcount(
        """
        UPDATE jobs
        SET og_image_url = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'done' AND og_image_url IS NULL
        """,
        (og_image_url, job_id),
    )
    return rowcount > 0


async def claim_job_enrichment(
    job_id: str, template: str | None, freestyle_prompt: str | None
) -> bool:
    """Atomically claim a transcript-complete job for queued enrichment."""
    rowcount = await _execute_rowcount(
        """
        UPDATE jobs
        SET status = 'enriching', template = ?, freestyle_prompt = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'transcript_done'
        """,
        (template, freestyle_prompt, job_id),
    )
    return rowcount > 0


async def release_job_enrichment_claim(job_id: str) -> bool:
    """Best-effort release when enqueueing a freshly claimed job fails."""
    return await _execute_rowcount(
        """
        UPDATE jobs SET status = 'transcript_done', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'enriching'
        """,
        (job_id,),
    ) > 0


# Image MIME types we are willing to persist and later serve to browsers.
# Anything else (e.g. a stray ``text/html`` from the vision model) is coerced
# to ``image/jpeg`` so stored bytes can never be interpreted as active content.
ALLOWED_THUMBNAIL_MIMES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


async def save_thumbnail(
    job_id: str,
    thumbnail_bytes: bytes,
    *,
    mime: str = "image/jpeg",
    width: int | None = None,
    height: int | None = None,
) -> str:
    """Persist a job thumbnail and return its API URL."""
    safe_mime = mime if mime in ALLOWED_THUMBNAIL_MIMES else "image/jpeg"
    async with core.connection() as conn:
        await conn.execute(
            """
            INSERT INTO job_thumbnails (job_id, bytes, mime, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_id) DO UPDATE SET
                bytes = excluded.bytes,
                mime = excluded.mime,
                width = excluded.width,
                height = excluded.height
            """,
            (job_id, thumbnail_bytes, safe_mime, width, height),
        )
        await conn.commit()
    log.info("job_thumbnail_saved", job_id=job_id, mime=safe_mime, bytes=len(thumbnail_bytes))
    return f"/api/jobs/{job_id}/thumbnail"


async def get_thumbnail(job_id: str) -> dict[str, Any] | None:
    row = await _fetch_one(
        "SELECT job_id, bytes, mime, width, height, created_at FROM job_thumbnails WHERE job_id = ?",
        (job_id,),
    )
    return dict(row) if row else None


async def has_thumbnail(job_id: str) -> bool:
    row = await _fetch_one("SELECT 1 FROM job_thumbnails WHERE job_id = ?", (job_id,))
    return row is not None


async def get_thumbnail_job_ids(job_ids: list[str]) -> set[str]:
    """Return the subset of *job_ids* that have a stored thumbnail (single query)."""
    rows = await _fetch_in(
        "SELECT job_id FROM job_thumbnails WHERE job_id IN ({placeholders})", job_ids
    )
    return {row["job_id"] for row in rows}


async def set_prd_slot_status(job_id: str, slot: Literal["auto", "intent"], status: str) -> None:
    """Set prd_auto_status or prd_intent_status without leaking column names to callers."""
    col = "prd_auto_status" if slot == "auto" else "prd_intent_status"
    sql = f"UPDATE jobs SET {col} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"  # nosec B608
    async with core.connection() as conn:
        await conn.execute(sql, (status, job_id))
        await conn.commit()
    log.info("prd_slot_status_set", job_id=job_id, slot=slot, status=status)


_REAPABLE_STATUSES = ("processing", "enriching")


async def fetch_and_mark_stale_jobs(
    stale_minutes: int = 10,
    *,
    chat_id: int | None = None,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """Recover jobs orphaned by a worker crash and return the affected rows.

    Selects jobs stuck in ``processing``/``enriching`` whose ``updated_at`` is older
    than ``stale_minutes``, flips them to ``error``, and increments ``attempt`` — all
    in one transaction. Returns ``[{"id", "chat_id", "status", "url"}, ...]`` where
    ``status`` is the value BEFORE the reset, so callers can route per-state
    notifications — ``url`` lets a caller identify synthetic receipt jobs (e.g.
    ``email_digest:%``) that need different notification handling than a real job.

    Deliberately still reaps ``email_digest`` receipt jobs to ``error`` — skipping
    them here would leave a crashed digest stuck ``processing`` forever, since the
    dashboard's dedicated per-feature retry only looks for ``error`` rows. Callers
    that special-case receipt jobs (see ``job_recovery.retry_error``) do so on top
    of this reap, not by excluding them from it.

    Run once at worker startup (see ``worker.reap_stale_jobs``). ADR-0010.
    """
    modifier = f"-{stale_minutes} minutes"
    placeholders = ",".join("?" for _ in _REAPABLE_STATUSES)
    conditions = [f"status IN ({placeholders})", "updated_at < datetime('now', ?)"]
    params: list[Any] = [*_REAPABLE_STATUSES, modifier]
    if chat_id is not None:
        conditions.append("chat_id = ?")
        params.append(chat_id)
    if content_type is not None:
        conditions.append("content_type = ?")
        params.append(content_type)
    where = " AND ".join(conditions)
    # `where` is built only from the static clause literals above; every actual
    # value is bound through `params` as a `?` placeholder. The suppressions have
    # to sit on the flagged lines themselves, which is why they read so tersely.
    async with core.connection() as conn:
        cursor = await conn.execute(  # nosemgrep
            f"SELECT id, chat_id, status, url FROM jobs WHERE {where}",  # nosec B608
            tuple(params),
        )
        rows = [dict(row) for row in await cursor.fetchall()]
        if rows:
            await conn.execute(
                f"UPDATE jobs SET status='error', attempt = attempt + 1, "  # nosec B608
                f"updated_at=CURRENT_TIMESTAMP WHERE {where}",
                tuple(params),
            )
            await conn.commit()
    if rows:
        log.info("jobs_reaped", count=len(rows))
    return rows


async def get_chat_state(chat_id: int) -> dict | None:
    """Return the chat_state row for chat_id, or None if absent."""
    row = await _fetch_one(
        "SELECT chat_id, mode, job_id, created_at, expires_at FROM chat_state WHERE chat_id = ?",
        (chat_id,),
    )
    return dict(row) if row else None


async def set_chat_state(chat_id: int, mode: str, job_id: str, expires_minutes: int = 10) -> None:
    """Insert or replace a chat_state row (PK chat_id gives upsert semantics).

    Logs ``prd.chat_state.replaced_other_job`` when overwriting a row for a different job_id.
    """
    existing = await get_chat_state(chat_id)
    if existing and existing["job_id"] != job_id:
        log.info(
            "prd.chat_state.replaced_other_job",
            chat_id=chat_id,
            old_job_id=existing["job_id"],
            new_job_id=job_id,
        )
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=expires_minutes)
    async with core.connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO chat_state (chat_id, mode, job_id, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, mode, job_id, now.isoformat(), expires.isoformat()),
        )
        await conn.commit()


async def clear_chat_state(chat_id: int) -> None:
    """Remove the chat_state row for chat_id, if any. Idempotent."""
    await _execute("DELETE FROM chat_state WHERE chat_id = ?", (chat_id,))


async def find_jobs_by_suffix(chat_id: int, suffix: str) -> list[dict]:
    """Return all jobs in chat_id whose id ends with suffix. Ordered by created_at DESC.

    Returns all content_types and statuses. Caller filters as needed
    (see webhook /spec handler).
    """
    return await _fetch_dicts(
        "SELECT * FROM jobs WHERE chat_id = ? AND id LIKE '%' || ? ORDER BY created_at DESC, id DESC",
        (chat_id, suffix),
    )


async def get_recent_jobs(chat_id: int, limit: int = 5) -> list[dict]:
    """Return the most-recent jobs in chat_id, capped at limit."""
    return await _fetch_dicts(
        "SELECT id, title, content_type, status FROM jobs "
        "WHERE chat_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (chat_id, limit),
    )


async def find_recent_job_by_url(chat_id: int, url: str) -> dict | None:
    """Return the most recent non-failed job for this chat_id + url, or None.

    Covers pending/processing (still running) and completed (cached result).
    Failed and stale jobs are excluded so the user can retry after a failure.
    """
    row = await _fetch_one(
        "SELECT id, title, drive_url, content_type, status, bot_message_id FROM jobs "
        "WHERE chat_id = ? AND (url = ? OR source_url = ?) "
        "AND status NOT IN ('error', 'cancelled') "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (chat_id, url, url),
    )
    return dict(row) if row else None


async def set_job_telegram_delivery(job_id: str, state: str) -> dict | None:
    # 'retroactive' is a request-only action resolved at the API boundary (send
    # existing outputs, then persist 'on'); only 'off'/'on' are storable (#231).
    if state not in {"off", "on"}:
        raise ValueError("telegram_delivery must be off or on")
    await _execute(
        "UPDATE jobs SET telegram_delivery = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (state, job_id),
    )
    return await get_job(job_id)


async def add_document_output(job_id: str, kind: str, gcs_key: str, title: str = "") -> dict:
    # Singular kinds (raw_txt/raw_md/summary/clean) upsert in place so re-runs
    # (a freestyle re-process, a repeated Clean) refresh the one card instead of
    # duplicating it; freestyle has no unique index, so it accumulates as history.
    output_id = generate_id()
    async with core.connection() as conn:
        cur = await conn.execute(
            """INSERT INTO document_outputs (id, job_id, kind, gcs_key, title)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_id, kind) WHERE kind <> 'freestyle'
            DO UPDATE SET gcs_key = excluded.gcs_key, title = excluded.title
            RETURNING id, job_id, kind, gcs_key, title""",
            (output_id, job_id, kind, gcs_key, title),
        )
        row = await cur.fetchone()
        await conn.commit()
    return dict(row)


async def list_document_outputs(job_id: str) -> list[dict]:
    return await _fetch_dicts(
        "SELECT id, job_id, kind, gcs_key, title, created_at FROM document_outputs WHERE job_id = ? ORDER BY created_at ASC, id ASC",
        (job_id,),
    )
async def batch_get_jobs(job_ids: list[str]) -> dict[str, dict]:
    """Return {job_id: job_dict} for the given IDs. Missing IDs are omitted."""
    rows = await _fetch_in("SELECT * FROM jobs WHERE id IN ({placeholders})", job_ids)
    return {row["id"]: row for row in rows}
async def count_job_links(job_id: str) -> int:
    """Links a job would take with it under `delete_job(with_links=True)` — the
    count the delete-confirm checkbox names."""
    row = await _fetch_one("SELECT COUNT(*) AS n FROM links WHERE source_job = ?", (job_id,))
    return row["n"] if row else 0


async def list_job_link_topics(job_id: str) -> list[dict]:
    """Distinct folder/topic groups among one job's links (#497 — the
    folder-to-tag opt-in form). Grouped in Python, not SQL GROUP_CONCAT: the
    row count per job is small (hundreds at most) and avoids parsing a
    delimited string back into an id list."""
    rows = await _fetch_dicts(
        "SELECT id, topic FROM links WHERE source_job = ? AND topic IS NOT NULL AND topic != ''",
        (job_id,),
    )
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(row["topic"], []).append(row["id"])
    return [
        {"topic": topic, "link_ids": ids, "count": len(ids)}
        for topic, ids in sorted(groups.items())
    ]


async def delete_job(
    job_id: str, purge_payload: dict[str, Any] | None = None, *, with_links: bool = False
) -> bool:
    """Hard-delete a job. Its Brain links survive unless *with_links* is set.

    A job is a work record; the links it produced are knowledge that outlives it
    (ADR-0046). `source_job` is left dangling as pure provenance — `chat_id`
    carries ownership (ADR-0043), and `list_links` LEFT JOINs `jobs`, so a
    dangling reference never hides a link. Removing links is a separate,
    explicit act: `DELETE /api/brain/links/{id}`, or this flag for all of a
    job's at once.

    If purge_payload is provided, it is written to the purge_tasks outbox in the same
    transaction, ensuring durable purge acceptance before the delete commits. When
    with_links also removes the job's links, their Drive .md nodes (if any) are
    folded into that same purge task so with_links can't orphan them.
    """
    async with core.connection() as conn:
        cursor = await conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        if with_links:
            if purge_payload is not None:
                link_rows = await conn.execute(
                    "SELECT drive_file_id FROM links WHERE source_job = ? AND drive_file_id IS NOT NULL",
                    (job_id,),
                )
                link_drive_file_ids = [r["drive_file_id"] for r in await link_rows.fetchall()]
                if link_drive_file_ids:
                    purge_payload = {
                        **purge_payload,
                        "drive_file_ids": [
                            *purge_payload.get("drive_file_ids", []),
                            *link_drive_file_ids,
                        ],
                    }
            await conn.execute("DELETE FROM links WHERE source_job = ?", (job_id,))
        if purge_payload and cursor.rowcount > 0:
            await conn.execute(
                "INSERT INTO purge_tasks (job_id, chat_id, task_payload) VALUES (?, ?, ?)",
                (purge_payload["job_id"], purge_payload["chat_id"], json.dumps(purge_payload)),
            )
        await conn.commit()
        return cursor.rowcount > 0
async def persist_job_link_ids(by_job: dict[str, str]) -> None:
    """Store resolved job→link keys so tag filtering can JOIN instead of scan.

    Called from the jobs read path, which makes this self-backfilling: the
    migration catches what SQL could match, and everything else is written the
    first time its job is listed. Reads what's already stored first and writes
    only what changed — the common case (an already-persisted page, on every
    read after the first) then opens no write transaction at all, instead of
    committing a no-op UPDATE per job on every single list/adjacent call.
    """
    if not by_job:
        return
    existing = await _fetch_in(
        "SELECT id, link_id FROM jobs WHERE id IN ({placeholders})", list(by_job)
    )
    current = {row["id"]: row["link_id"] for row in existing}
    changed = {
        job_id: link_id for job_id, link_id in by_job.items() if current.get(job_id) != link_id
    }
    if not changed:
        return
    async with core.connection() as conn:
        await conn.executemany(
            "UPDATE jobs SET link_id = ? WHERE id = ?",
            [(link_id, job_id) for job_id, link_id in changed.items()],
        )
        await conn.commit()


async def jobs_missing_link_id(chat_id: int) -> list[tuple[str, str]]:
    """(id, url) for this chat's link-backed jobs jobs.link_id hasn't caught up to.

    Feeds the tag-filter backfill in src/api/jobs.py: tag-scoped SQL JOINs
    through jobs.link_id, but SQL can't call normalize_url() to resolve it
    (same reason _migrate_jobs_link_id resolves in Python) — this just returns
    the raw candidates for that Python-side resolution.
    """
    async with core.connection() as conn:
        cur = await conn.execute(
            "SELECT id, url FROM jobs WHERE chat_id = ? AND link_id IS NULL "
            "AND content_type IN ('link', 'article', 'repo')",
            (chat_id,),
        )
        return [(row["id"], row["url"]) for row in await cur.fetchall()]

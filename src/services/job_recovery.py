"""Dashboard-triggered job recovery orchestration."""

from __future__ import annotations

from typing import Any, Literal

from src import database, queue
from src.utils.logger import get_logger

ContentType = Literal["short", "long", "article", "repo"]

STALE_MINUTES = 10
_CONTENT_TYPES = {"short", "long", "article", "repo"}

log = get_logger(__name__)


def _validate_content_type(content_type: str | None) -> str | None:
    if content_type in (None, ""):
        return None
    if content_type not in _CONTENT_TYPES:
        raise ValueError("content_type must be one of short, long, article, repo")
    return content_type


def _task_for(content_type: str) -> str | None:
    if content_type in {"short", "long"}:
        return "video"
    if content_type in {"article", "repo"}:
        return content_type
    return None


def _scope_where(chat_id: int, content_type: str | None) -> tuple[str, list[Any]]:
    conditions = ["chat_id = ?"]
    params: list[Any] = [chat_id]
    if content_type:
        conditions.append("content_type = ?")
        params.append(content_type)
    return " AND ".join(conditions), params


async def recovery_summary(chat_id: int, content_type: str | None = None) -> dict[str, int]:
    content_type = _validate_content_type(content_type)
    where, params = _scope_where(chat_id, content_type)
    modifier = f"-{STALE_MINUTES} minutes"
    async with database.connection() as conn:
        cur = await conn.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN status = 'pending'
                    AND updated_at < datetime('now', ?) THEN 1 ELSE 0 END), 0) AS stale_pending,
                COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) AS error_jobs,
                COALESCE(SUM(CASE WHEN status IN ('processing', 'enriching')
                    AND updated_at < datetime('now', ?) THEN 1 ELSE 0 END), 0) AS stale_in_flight
            FROM jobs
            WHERE {where}
            """,
            (modifier, modifier, *params),
        )
        row = await cur.fetchone()
    return {
        "stale_pending": int(row["stale_pending"] if row else 0),
        "error_jobs": int(row["error_jobs"] if row else 0),
        "stale_in_flight": int(row["stale_in_flight"] if row else 0),
    }


async def retry_pending(chat_id: int, content_type: str | None = None) -> dict[str, int]:
    content_type = _validate_content_type(content_type)
    where, params = _scope_where(chat_id, content_type)
    modifier = f"-{STALE_MINUTES} minutes"
    async with database.connection() as conn:
        # Snapshot the stale pending rows (with their pre-claim updated_at) so a failed
        # enqueue can be rolled back to its original still-stale state rather than left
        # invisible to recovery for the stale window.
        snapshot_cur = await conn.execute(
            f"""
            SELECT id, content_type, updated_at
            FROM jobs
            WHERE {where} AND status = 'pending' AND updated_at < datetime('now', ?)
            """,
            (*params, modifier),
        )
        candidates = {row["id"]: dict(row) for row in await snapshot_cur.fetchall()}
        # Count fresh pending rows (left untouched) for reporting parity.
        fresh_cur = await conn.execute(
            f"""
            SELECT COUNT(*) AS fresh
            FROM jobs
            WHERE {where} AND status = 'pending' AND updated_at >= datetime('now', ?)
            """,
            (*params, modifier),
        )
        fresh_row = await fresh_cur.fetchone()
        skipped_fresh = int(fresh_row["fresh"] if fresh_row else 0)
        # Atomically claim stale pending rows by bumping updated_at. A concurrent
        # call — or the immediate summary refresh in useRecovery.act — then no longer
        # sees them as stale, so the same jobs can't be enqueued twice. Enqueue only
        # what this statement actually claimed (RETURNING), never a stale snapshot.
        claim_cur = await conn.execute(
            f"""
            UPDATE jobs
            SET updated_at = CURRENT_TIMESTAMP
            WHERE {where} AND status = 'pending' AND updated_at < datetime('now', ?)
            RETURNING id
            """,
            (*params, modifier),
        )
        claimed = [candidates[row["id"]] for row in await claim_cur.fetchall() if row["id"] in candidates]
        await conn.commit()

    enqueued = 0
    skipped_non_retryable = 0
    # Every claimed row carries a bumped updated_at. Until a row is enqueued (or found
    # non-retryable) it must be restorable, or a mid-loop queue failure would hide the
    # whole tail from recovery for the stale window.
    unprocessed = {row["id"]: row for row in claimed}
    try:
        for row in claimed:
            task = _task_for(row["content_type"])
            if task is None:
                skipped_non_retryable += 1
                del unprocessed[row["id"]]
                continue
            await queue.enqueue({"task": task, "job_id": row["id"]})
            enqueued += 1
            del unprocessed[row["id"]]
    except Exception:
        # Restore the pre-claim timestamp for the failed row and the untouched tail so
        # they stay stale-pending and the dashboard keeps offering them. Best-effort
        # per row: one restore failure must not strand the others.
        for leftover in unprocessed.values():
            try:
                await _restore_updated_at(leftover["id"], leftover["updated_at"])
            except Exception:
                log.exception("dashboard_recovery.restore_failed", job_id=leftover["id"])
        raise

    return {
        "scanned": skipped_fresh + len(claimed),
        "enqueued": enqueued,
        "skipped_fresh": skipped_fresh,
        "skipped_non_retryable": skipped_non_retryable,
    }


async def _restore_updated_at(job_id: str, updated_at: str) -> None:
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET updated_at = ? WHERE id = ?",
            (updated_at, job_id),
        )
        await conn.commit()


async def clear_failed(chat_id: int, content_type: str | None = None) -> dict[str, int]:
    content_type = _validate_content_type(content_type)
    where, params = _scope_where(chat_id, content_type)
    async with database.connection() as conn:
        cur = await conn.execute(
            f"""
            UPDATE jobs
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE {where} AND status = 'error'
            """,
            tuple(params),
        )
        await conn.commit()
        cancelled = cur.rowcount
    return {"cancelled": cancelled}


async def _notify_reaped_jobs(rows: list[dict[str, Any]], chat_id: int) -> int:
    """Inform the user that dashboard recovery reaped these stale in-flight jobs.

    Unlike the startup reaper (``worker.reap_stale_jobs``), ``retry_error`` re-queues
    every reaped row automatically within the same call, so these notifications carry
    no Retry button — a button here would point at a row this same request then
    cancels, leaving the user a dead control.
    """
    if not rows or not await database.get_recovery_telegram_notifications_enabled(chat_id):
        return 0

    from src.telegram.sender import send_message

    sent = 0
    for row in rows:
        job_id = row["id"]
        tag = f"job_{job_id[-4:]}:"
        stage = "Enrichment" if row["status"] == "enriching" else "Processing"
        try:
            await send_message(
                chat_id,
                f"{tag}\n⚠️ {stage} was interrupted by a restart — re-queued automatically.",
            )
            sent += 1
        except Exception:
            log.exception("dashboard_recovery.notify_failed", job_id=job_id)
    return sent


async def _claim_error_rows(chat_id: int, content_type: str | None) -> list[dict[str, Any]]:
    """Atomically claim scoped error rows by cancelling them, returning their data.

    Cancelling up front (rather than a plain SELECT the caller then mutates row by
    row) means a concurrent ``retry_error`` call sees zero error rows and can't
    reprocess the same jobs into duplicate workers. Same-job retries (article,
    long-with-transcript) move the row back to pending/enriching below; replacements
    leave the original cancelled; non-retryable rows are restored to 'error'.
    """
    where, params = _scope_where(chat_id, content_type)
    async with database.connection() as conn:
        cur = await conn.execute(
            f"""
            UPDATE jobs
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE {where} AND status = 'error'
            RETURNING id, chat_id, message_id, url, content_type, template, freestyle_prompt, transcript
            """,
            tuple(params),
        )
        rows = [dict(row) for row in await cur.fetchall()]
        await conn.commit()
    return rows


async def retry_error(chat_id: int, content_type: str | None = None) -> dict[str, int]:
    content_type = _validate_content_type(content_type)
    reaped = await database.fetch_and_mark_stale_jobs(
        STALE_MINUTES, chat_id=chat_id, content_type=content_type
    )
    notifications_sent = await _notify_reaped_jobs(reaped, chat_id)
    rows = await _claim_error_rows(chat_id, content_type)
    # Every claimed row is currently 'cancelled'. Track those not yet given a final
    # disposition so a mid-batch queue failure can restore the whole tail to 'error'
    # — otherwise rows after the failure point would be stranded in 'cancelled',
    # invisible to recovery with no self-healing path.
    unprocessed = {row["id"]: row for row in rows}

    retried_same = 0
    replaced = 0
    skipped = 0
    try:
        for row in rows:
            row_content_type = row["content_type"]
            if row_content_type == "article":
                await database.update_job_status(row["id"], "pending", error_msg=None)
                await queue.enqueue({"task": "article", "job_id": row["id"], "skip_document": True})
                retried_same += 1
                del unprocessed[row["id"]]
                continue
            if row_content_type == "long" and row.get("transcript"):
                await database.update_job_status(row["id"], "enriching", error_msg=None)
                await queue.enqueue({"task": "enrichment", "job_id": row["id"]})
                retried_same += 1
                del unprocessed[row["id"]]
                continue

            task = _task_for(row_content_type)
            if task is None:
                # Nothing to retry — leave it as a failed job the user still sees.
                await database.update_job_status(row["id"], "error")
                skipped += 1
                del unprocessed[row["id"]]
                continue
            new_job_id = await database.create_job(
                chat_id=chat_id,
                url=row["url"],
                content_type=row_content_type,
                message_id=row.get("message_id"),
                template=row.get("template"),
                freestyle_prompt=row.get("freestyle_prompt"),
            )
            try:
                await queue.enqueue({"task": task, "job_id": new_job_id})
            except Exception:
                # Cancel the orphan replacement before the batch rollback restores the
                # original (still in `unprocessed`) to 'error'.
                await database.update_job_status(new_job_id, "cancelled")
                raise
            replaced += 1
            del unprocessed[row["id"]]
    except Exception:
        # Best-effort restore per row: a DB failure on one row must not abort the
        # restore pass and strand the remaining rows in 'cancelled'.
        for leftover in unprocessed.values():
            try:
                await database.update_job_status(leftover["id"], "error")
            except Exception:
                log.exception("dashboard_recovery.restore_failed", job_id=leftover["id"])
        raise

    return {
        "reaped": len(reaped),
        "notifications_sent": notifications_sent,
        "retried_same": retried_same,
        "replaced": replaced,
        "skipped": skipped,
    }

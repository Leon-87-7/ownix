from __future__ import annotations

from pathlib import Path

import pytest

from src import database
from src.services import job_recovery


async def _init_tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "recovery.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    await database.init_db()


async def _insert_job(
    job_id: str,
    *,
    chat_id: int = 1,
    content_type: str = "short",
    status: str = "pending",
    age_minutes: int = 0,
    transcript: str | None = None,
    url: str | None = None,
) -> None:
    async with database.connection() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                id, chat_id, url, content_type, status, transcript, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?))
            """,
            (
                job_id,
                chat_id,
                url or f"https://example.com/{job_id}",
                content_type,
                status,
                transcript,
                f"-{age_minutes} minutes",
            ),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_recovery_summary_scopes_to_content_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_pending_stale", content_type="short", status="pending", age_minutes=20)
    await _insert_job("short_pending_fresh", content_type="short", status="pending", age_minutes=1)
    await _insert_job("short_error", content_type="short", status="error")
    await _insert_job("long_inflight", content_type="long", status="processing", age_minutes=20)
    await _insert_job("other_tenant", chat_id=2, content_type="short", status="error")

    assert await job_recovery.recovery_summary(1, "short") == {
        "stale_pending": 1,
        "error_jobs": 1,
        "stale_in_flight": 0,
    }
    assert await job_recovery.recovery_summary(1, None) == {
        "stale_pending": 1,
        "error_jobs": 1,
        "stale_in_flight": 1,
    }


@pytest.mark.asyncio
async def test_retry_pending_uses_cutoff_task_mapping_and_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_stale", content_type="short", status="pending", age_minutes=20)
    await _insert_job("article_stale", content_type="article", status="pending", age_minutes=20)
    await _insert_job("short_fresh", content_type="short", status="pending", age_minutes=1)

    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    monkeypatch.setattr(job_recovery.queue, "enqueue", fake_enqueue)

    result = await job_recovery.retry_pending(1, "short")

    assert result == {
        "scanned": 2,
        "enqueued": 1,
        "skipped_fresh": 1,
        "skipped_non_retryable": 0,
    }
    assert enqueued == [{"task": "video", "job_id": "short_stale"}]


@pytest.mark.asyncio
async def test_retry_pending_claims_rows_so_repeat_calls_do_not_double_enqueue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_stale", content_type="short", status="pending", age_minutes=20)

    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    monkeypatch.setattr(job_recovery.queue, "enqueue", fake_enqueue)

    first = await job_recovery.retry_pending(1, "short")
    assert first == {"scanned": 1, "enqueued": 1, "skipped_fresh": 0, "skipped_non_retryable": 0}

    # The claim bumped updated_at, so the row is no longer stale: a second call
    # (concurrent tab, retry-on-error) must not re-enqueue it.
    second = await job_recovery.retry_pending(1, "short")
    assert second == {"scanned": 1, "enqueued": 0, "skipped_fresh": 1, "skipped_non_retryable": 0}

    assert enqueued == [{"task": "video", "job_id": "short_stale"}]
    assert (await job_recovery.recovery_summary(1, "short"))["stale_pending"] == 0


@pytest.mark.asyncio
async def test_retry_pending_restores_whole_batch_when_enqueue_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_stale_1", content_type="short", status="pending", age_minutes=20)
    await _insert_job("short_stale_2", content_type="short", status="pending", age_minutes=20)

    async def boom(_task: dict) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(job_recovery.queue, "enqueue", boom)

    with pytest.raises(RuntimeError):
        await job_recovery.retry_pending(1, "short")

    # The claim bumped updated_at on both rows. A failure on the first enqueue must
    # restore the failed row AND the untouched tail, so neither is hidden from the
    # recovery panel for the stale window.
    assert (await job_recovery.recovery_summary(1, "short"))["stale_pending"] == 2


@pytest.mark.asyncio
async def test_retry_error_reaps_filters_retries_and_cancels_replacements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("article_error", content_type="article", status="error")
    await _insert_job("long_error", content_type="long", status="error", transcript="stored transcript")
    await _insert_job("short_error", content_type="short", status="error")
    await _insert_job("short_processing", content_type="short", status="processing", age_minutes=20)
    await _insert_job("long_processing", content_type="long", status="processing", age_minutes=20)

    enqueued: list[dict] = []
    notified: list[tuple[int, str, list]] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    async def fake_send_message(chat_id: int, text: str, **_kwargs) -> None:
        notified.append((chat_id, text, []))

    monkeypatch.setattr(job_recovery.queue, "enqueue", fake_enqueue)
    monkeypatch.setattr("src.telegram.sender.send_message", fake_send_message)

    result = await job_recovery.retry_error(1, "short")

    assert result["reaped"] == 1
    assert result["notifications_sent"] == 1
    assert result["replaced"] == 2
    assert result["retried_same"] == 0
    assert {task["task"] for task in enqueued} == {"video"}
    assert all("long" not in task["job_id"] for task in enqueued)
    assert len(notified) == 1

    assert (await database.get_job("short_error"))["status"] == "cancelled"
    assert (await database.get_job("short_processing"))["status"] == "cancelled"
    assert (await database.get_job("long_processing"))["status"] == "processing"

    enqueued.clear()
    result = await job_recovery.retry_error(1, "long")

    assert result["reaped"] == 1
    assert result["retried_same"] == 1
    assert result["replaced"] == 1
    assert {"task": "enrichment", "job_id": "long_error"} in enqueued
    assert (await database.get_job("long_error"))["status"] == "enriching"


@pytest.mark.asyncio
async def test_retry_error_claims_rows_so_repeat_calls_do_not_double_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_error", content_type="short", status="error")

    enqueued: list[dict] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    monkeypatch.setattr(job_recovery.queue, "enqueue", fake_enqueue)

    first = await job_recovery.retry_error(1, "short")
    assert first["replaced"] == 1
    assert (await database.get_job("short_error"))["status"] == "cancelled"

    # The atomic claim cancelled the original, so a second call finds no error rows
    # and must not create a second replacement for the same URL.
    second = await job_recovery.retry_error(1, "short")
    assert second["replaced"] == 0
    assert second["retried_same"] == 0
    assert len(enqueued) == 1


@pytest.mark.asyncio
async def test_retry_error_restores_whole_batch_when_enqueue_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_error_1", content_type="short", status="error")
    await _insert_job("short_error_2", content_type="short", status="error")

    async def boom(_task: dict) -> None:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(job_recovery.queue, "enqueue", boom)

    with pytest.raises(RuntimeError):
        await job_recovery.retry_error(1, "short")

    # The atomic claim cancelled both rows up front; a mid-batch queue failure must
    # restore every unprocessed row to 'error' rather than strand the tail in 'cancelled'.
    assert (await database.get_job("short_error_1"))["status"] == "error"
    assert (await database.get_job("short_error_2"))["status"] == "error"


@pytest.mark.asyncio
async def test_retry_error_respects_notification_preference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_processing", content_type="short", status="processing", age_minutes=20)
    await database.set_recovery_telegram_notifications_enabled(1, False)

    enqueued: list[dict] = []
    notified: list[str] = []

    async def fake_enqueue(task: dict) -> None:
        enqueued.append(task)

    async def fake_send_message(*_args, **_kwargs) -> None:
        notified.append("sent")

    monkeypatch.setattr(job_recovery.queue, "enqueue", fake_enqueue)
    monkeypatch.setattr("src.telegram.sender.send_message", fake_send_message)

    result = await job_recovery.retry_error(1, "short")

    assert result["reaped"] == 1
    assert result["notifications_sent"] == 0
    assert notified == []


@pytest.mark.asyncio
async def test_clear_failed_marks_cancelled_without_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init_tmp_db(tmp_path, monkeypatch)
    await _insert_job("short_error", content_type="short", status="error")
    await _insert_job("long_error", content_type="long", status="error")

    assert await job_recovery.clear_failed(1, "short") == {"cancelled": 1}
    assert (await database.get_job("short_error"))["status"] == "cancelled"
    assert (await database.get_job("long_error"))["status"] == "error"

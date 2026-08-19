import pytest
from unittest.mock import AsyncMock, MagicMock

from src import worker
from src.services.jobs import task_for_content_type


def test_unsized_enqueues_the_video_task():
    """Without this, an unsized job is enqueued as {"task": "unsized"} and _dispatch drops it."""
    assert task_for_content_type("unsized", default="unsized") == "video"
    assert worker._TASK_HANDLERS["video"] is worker._handle_video


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("duration", "expected"),
    [(19.201, "short"), (180.0, "short"), (180.001, "long")],
)
async def test_unsized_video_is_persisted_then_dispatched(monkeypatch, duration, expected):
    job = {
        "id": "job-1",
        "chat_id": 1,
        "url": "https://facebook.com/share/v/123",
        "content_type": "unsized",
        "status": "pending",
    }
    monkeypatch.setattr(worker.database, "get_job", AsyncMock(return_value=job))
    update = AsyncMock()
    monkeypatch.setattr(worker.database, "update_job_status", update)

    from src.services import transcript
    from src.processors import long_video, short_video

    monkeypatch.setattr(
        transcript,
        "fetch_metadata",
        AsyncMock(return_value={"duration": duration, "short_max_duration": 180}),
    )
    short_run = AsyncMock()
    long_run = AsyncMock()
    monkeypatch.setattr(short_video, "run", short_run)
    monkeypatch.setattr(long_video, "run", long_run)

    await worker._handle_video({"job_id": "job-1"})

    update.assert_awaited_once_with("job-1", "pending", content_type=expected)
    assert job["content_type"] == expected
    (short_run if expected == "short" else long_run).assert_awaited_once_with(job)


@pytest.mark.asyncio
async def test_unsized_duration_failure_defaults_short_and_logs(monkeypatch):
    job = {
        "id": "job-1",
        "chat_id": 1,
        "url": "https://x.com/user/status/123",
        "content_type": "unsized",
        "status": "pending",
    }
    monkeypatch.setattr(worker.database, "get_job", AsyncMock(return_value=job))
    monkeypatch.setattr(worker.database, "update_job_status", AsyncMock())
    from src.services import transcript
    from src.processors import short_video

    monkeypatch.setattr(
        transcript,
        "fetch_metadata",
        AsyncMock(return_value={"duration": 0, "error": "blocked"}),
    )
    monkeypatch.setattr(short_video, "run", AsyncMock())
    error = MagicMock()
    monkeypatch.setattr(worker.log, "error", error)

    await worker._handle_video({"job_id": "job-1"})

    assert job["content_type"] == "short"
    error.assert_called_once_with(
        "unsized_duration_resolution_failed",
        url=job["url"],
        host="x.com",
        sidecar_error="blocked",
    )


@pytest.mark.asyncio
async def test_dispatch_skips_envelope_when_job_is_gone(monkeypatch) -> None:
    called = False

    async def get_job(_job_id):
        return None

    async def handler(_task):
        nonlocal called
        called = True

    monkeypatch.setattr(worker.database, "get_job", get_job)
    monkeypatch.setitem(worker._TASK_HANDLERS, "video", handler)
    await worker._dispatch({"task": "video", "job_id": "gone"})
    assert not called


@pytest.mark.asyncio
async def test_enrichment_failure_resets_status_to_error(monkeypatch) -> None:
    """Regression: an unexpected (non-EnrichmentUnavailableError) failure must not
    leave the job stuck in 'enriching' forever — _handle_enrichment used to hand-roll
    its own except block and skip the status reset entirely (architecture review 2026-08-19)."""
    job = {"id": "job-1", "chat_id": 1, "status": "enriching"}
    monkeypatch.setattr(worker.database, "get_job", AsyncMock(return_value=job))
    update = AsyncMock()
    monkeypatch.setattr(worker.database, "update_job_status", update)
    monkeypatch.setattr(worker, "_notify_failure", AsyncMock())

    from src.processors import enrichment

    monkeypatch.setattr(enrichment, "run", AsyncMock(side_effect=RuntimeError("boom")))

    await worker._handle_enrichment({"job_id": "job-1"})

    update.assert_awaited_once_with("job-1", "error")


@pytest.mark.asyncio
async def test_dispatch_does_not_skip_rowless_job_purge(monkeypatch) -> None:
    called = False

    async def get_job(_job_id):
        raise AssertionError("rowless tasks must not query the deleted job")

    async def handler(_task):
        nonlocal called
        called = True

    monkeypatch.setattr(worker.database, "get_job", get_job)
    monkeypatch.setitem(worker._TASK_HANDLERS, "job_purge", handler)
    await worker._dispatch({"task": "job_purge", "job_id": "gone"})
    assert called

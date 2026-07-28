import pytest

from src import worker


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

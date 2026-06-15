from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import backfill_article_og_images as backfill


@pytest.mark.asyncio
async def test_backfill_dry_run_reports_without_writing(monkeypatch, capsys) -> None:
    class FakeCursor:
        async def fetchall(self):
            return [{"id": "job1", "url": "https://example.com/post"}]

    class FakeConn:
        async def execute(self, *_args, **_kwargs):
            return FakeCursor()

    class FakeConnection:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, *_args):
            return None

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url):
            return SimpleNamespace(
                text='<meta property="og:image" content="https://cdn.example.com/og.jpg">',
                url="https://example.com/post",
                raise_for_status=lambda: None,
            )

    update_job_status = AsyncMock()
    monkeypatch.setattr(backfill.database, "connection", lambda: FakeConnection())
    monkeypatch.setattr(backfill.database, "update_job_status", update_job_status)
    monkeypatch.setattr(backfill.httpx, "AsyncClient", lambda **_kwargs: FakeClient())

    summary = await backfill.backfill(dry_run=True)

    assert summary.scanned == 1
    assert summary.updated == 0
    assert summary.would_update == 1
    update_job_status.assert_not_awaited()
    assert "dry-run job1" in capsys.readouterr().out

from __future__ import annotations

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

    backfill_og_image_url = AsyncMock()
    monkeypatch.setattr(backfill.database, "connection", lambda: FakeConnection())
    monkeypatch.setattr(backfill.database, "backfill_og_image_url", backfill_og_image_url)
    monkeypatch.setattr(
        backfill, "fetch_og_image_url", AsyncMock(return_value="https://cdn.example.com/og.jpg")
    )

    summary = await backfill.backfill(dry_run=True)

    assert summary.scanned == 1
    assert summary.updated == 0
    assert summary.would_update == 1
    backfill_og_image_url.assert_not_awaited()
    assert "dry-run job1" in capsys.readouterr().out

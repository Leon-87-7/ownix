from types import SimpleNamespace

import pytest

from src.api import jobs
from src.api.jobs import _resolve_thumbnail


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtube_watch() -> None:
    assert await _resolve_thumbnail({"id": "j1", "url": "https://www.youtube.com/watch?v=abc123", "content_type": "long"}) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtu_be() -> None:
    assert await _resolve_thumbnail({"id": "j1", "url": "https://youtu.be/abc123", "content_type": "long"}) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_repo() -> None:
    assert await _resolve_thumbnail({"id": "j1", "url": "https://github.com/owner/repo/issues/1", "content_type": "repo"}) == (
        "https://opengraph.githubassets.com/0/owner/repo",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_youtube_short() -> None:
    assert await _resolve_thumbnail({"id": "j1", "url": "https://youtube.com/shorts/short123", "content_type": "short"}) == (
        "https://img.youtube.com/vi/short123/hqdefault.jpg",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_and_tiktok_short_placeholder(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return False

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)
    assert await _resolve_thumbnail({"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}) == (None, None)
    assert await _resolve_thumbnail({"id": "j2", "url": "https://www.tiktok.com/@user/video/1234567890", "content_type": "short"}) == (
        None,
        None,
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_short_uses_persisted_thumbnail(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return True

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)

    assert await _resolve_thumbnail({"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}) == (
        "/api/jobs/j1/thumbnail",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_og_image() -> None:
    assert await _resolve_thumbnail({
        "id": "j1",
        "url": "https://medium.com/example/post",
        "content_type": "article",
        "og_image_url": "https://cdn.example.com/og.jpg",
    }) == ("https://cdn.example.com/og.jpg", "landscape")


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_placeholder() -> None:
    assert await _resolve_thumbnail({"id": "j1", "url": "https://medium.com/example/post", "content_type": "article"}) == (None, None)


@pytest.mark.asyncio
async def test_list_jobs_includes_resolved_thumbnail_fields(monkeypatch) -> None:
    class FakeCursor:
        def __init__(self, payload):
            self.payload = payload

        async def fetchone(self):
            return self.payload

        async def fetchall(self):
            return self.payload

    class FakeConn:
        def __init__(self):
            self.calls = 0

        async def execute(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeCursor((1,))
            return FakeCursor([
                {
                    "id": "j1",
                    "title": "Example",
                    "content_type": "long",
                    "status": "done",
                    "url": "https://youtube.com/watch?v=abc123",
                    "created_at": "2026-01-01T00:00:00Z",
                    "og_image_url": None,
                }
            ])

    class FakeConnection:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(jobs.database, "connection", lambda: FakeConnection())

    response = await jobs.list_jobs(
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
        page=1,
        limit=20,
    )

    assert response["items"][0]["thumbnail_url"] == "https://img.youtube.com/vi/abc123/hqdefault.jpg"
    assert response["items"][0]["thumbnail_kind"] == "landscape"

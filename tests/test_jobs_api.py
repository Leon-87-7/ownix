import inspect
from types import SimpleNamespace

import pytest

from src.api import jobs
from src.api.jobs import resolve_thumbnail


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtube_watch() -> None:
    assert await resolve_thumbnail({"id": "j1", "url": "https://www.youtube.com/watch?v=abc123", "content_type": "long"}) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtu_be() -> None:
    assert await resolve_thumbnail({"id": "j1", "url": "https://youtu.be/abc123", "content_type": "long"}) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_repo() -> None:
    assert await resolve_thumbnail({"id": "j1", "url": "https://github.com/owner/repo/issues/1", "content_type": "repo"}) == (
        "https://opengraph.githubassets.com/0/owner/repo",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_youtube_short() -> None:
    assert await resolve_thumbnail({"id": "j1", "url": "https://youtube.com/shorts/short123", "content_type": "short"}) == (
        "https://img.youtube.com/vi/short123/hqdefault.jpg",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_and_tiktok_short_placeholder(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return False

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)
    assert await resolve_thumbnail({"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}) == (None, None)
    assert await resolve_thumbnail({"id": "j2", "url": "https://www.tiktok.com/@user/video/1234567890", "content_type": "short"}) == (
        None,
        None,
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_short_uses_persisted_thumbnail(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return True

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)

    assert await resolve_thumbnail({"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}) == (
        "/api/jobs/j1/thumbnail",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_og_image() -> None:
    assert await resolve_thumbnail({
        "id": "j1",
        "url": "https://medium.com/example/post",
        "content_type": "article",
        "og_image_url": "https://cdn.example.com/og.jpg",
    }) == ("https://cdn.example.com/og.jpg", "landscape")


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_placeholder() -> None:
    assert await resolve_thumbnail({"id": "j1", "url": "https://medium.com/example/post", "content_type": "article"}) == (None, None)


class _RecordingCursor:
    def __init__(self, payload):
        self.payload = payload

    async def fetchall(self):
        return self.payload


class _RecordingConn:
    """Records (sql, params) for each execute; returns canned rows per call."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls: list[tuple[str, object]] = []

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _RecordingCursor(self.payloads[len(self.calls) - 1])


class _RecordingConnection:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_get_job_stats_unscoped_omits_content_type_predicate(monkeypatch) -> None:
    conn = _RecordingConn(
        [
            [{"status": "done", "cnt": 3}, {"status": "error", "cnt": 5}],
            [{"content_type": "article", "cnt": 9}, {"content_type": "short", "cnt": 2}],
        ]
    )
    monkeypatch.setattr(jobs.database, "connection", lambda: _RecordingConnection(conn))

    response = await jobs.get_job_stats(
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
        content_type=None,
    )

    # Status query is global: chat_id only, no content_type predicate.
    status_sql, status_params = conn.calls[0]
    assert "content_type" not in status_sql
    assert status_params == [1]
    assert response["total"] == 8
    assert response["by_status"] == {"done": 3, "error": 5}
    # by_content_type stays global regardless.
    assert response["by_content_type"] == {"article": 9, "short": 2}


@pytest.mark.asyncio
async def test_get_job_stats_scopes_status_breakdown_to_content_type(monkeypatch) -> None:
    # Article tab: 9 jobs — 3 done, 1 pending, 5 error (0 processing).
    conn = _RecordingConn(
        [
            [
                {"status": "done", "cnt": 3},
                {"status": "pending", "cnt": 1},
                {"status": "error", "cnt": 5},
            ],
            [{"content_type": "article", "cnt": 9}, {"content_type": "short", "cnt": 2}],
        ]
    )
    monkeypatch.setattr(jobs.database, "connection", lambda: _RecordingConnection(conn))

    response = await jobs.get_job_stats(
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
        content_type="article",
    )

    # Status query is scoped: content_type predicate + param appended.
    status_sql, status_params = conn.calls[0]
    assert "content_type = ?" in status_sql
    assert status_params == [1, "article"]
    assert response["total"] == 9
    assert response["by_status"] == {"done": 3, "pending": 1, "error": 5}

    # Content-type breakdown query stays unfiltered (chat_id only) so tab chips are global.
    ct_sql, ct_params = conn.calls[1]
    assert "content_type = ?" not in ct_sql
    assert ct_params == (1,)
    assert response["by_content_type"] == {"article": 9, "short": 2}


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


# ---------------------------------------------------------------------------
# adjacent-jobs scope + ordering (issue #309)
# ---------------------------------------------------------------------------


def test_job_scope_where_defaults_exclude_cancelled() -> None:
    where, params = jobs._job_scope_where(1, None, None)
    assert where == "chat_id = ? AND status != 'cancelled'"
    assert params == [1]

    where, params = jobs._job_scope_where(1, "short", "error")
    assert where == "chat_id = ? AND content_type = ? AND status = ?"
    assert params == [1, "short", "error"]


class _FetchOneCursor:
    def __init__(self, payload):
        self.payload = payload

    async def fetchone(self):
        return self.payload


class _AdjacentConn:
    """Records (sql, params); returns one canned row per execute call."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls: list[tuple[str, object]] = []

    async def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _FetchOneCursor(self.payloads[len(self.calls) - 1])


@pytest.mark.asyncio
async def test_get_adjacent_jobs_queries_and_payload(monkeypatch) -> None:
    conn = _AdjacentConn([{"id": "older"}, None])
    monkeypatch.setattr(jobs.database, "connection", lambda: _RecordingConnection(conn))

    async def _fake_get_owned_job(job_id, _request):
        return {"id": job_id, "created_at": "2026-07-04 09:00:00"}

    monkeypatch.setattr(jobs, "get_owned_job", _fake_get_owned_job)

    response = await jobs.get_adjacent_jobs(
        "j2",
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
        content_type="short",
        status=None,
    )

    prev_sql, prev_params = conn.calls[0]
    next_sql, next_params = conn.calls[1]
    # Neighbor selection is created_at with an id tie-break, scoped like list_jobs.
    assert "created_at < ? OR (created_at = ? AND id < ?)" in prev_sql
    assert "ORDER BY created_at DESC, id DESC" in prev_sql
    assert "created_at > ? OR (created_at = ? AND id > ?)" in next_sql
    assert "status != 'cancelled'" in prev_sql
    assert prev_params == [1, "short", "2026-07-04 09:00:00", "2026-07-04 09:00:00", "j2"]
    assert next_params == prev_params
    assert response == {"previous_id": "older", "next_id": None}


def test_list_jobs_order_matches_adjacent_tiebreak() -> None:
    # The feed and /adjacent must sort identically or prev/next drifts from the
    # visible list for same-second jobs (created_at is second-precision).
    import inspect as _inspect

    assert "ORDER BY created_at DESC, id DESC" in _inspect.getsource(jobs.list_jobs)


# ---------------------------------------------------------------------------
# list_jobs limit cap tests (issue #175 — raised from 50 to 1000)
# ---------------------------------------------------------------------------

def _get_limit_query_metadata() -> list:
    """Return the metadata annotations attached to the ``limit`` Query param."""
    sig = inspect.signature(jobs.list_jobs)
    return sig.parameters["limit"].default.metadata


def test_list_jobs_limit_cap_is_1000() -> None:
    """The ``limit`` Query parameter must accept up to 1000 (the preload cap)."""
    metadata = _get_limit_query_metadata()
    le_constraints = [m for m in metadata if type(m).__name__ == "Le"]
    assert len(le_constraints) == 1, "Expected exactly one Le constraint on limit"
    assert le_constraints[0].le == 1000, (
        f"Expected limit cap to be 1000 (the client-mode preload ceiling), got {le_constraints[0].le}"
    )


def test_list_jobs_limit_ge_is_still_1() -> None:
    """The lower bound on ``limit`` must remain 1."""
    metadata = _get_limit_query_metadata()
    ge_constraints = [m for m in metadata if type(m).__name__ == "Ge"]
    assert len(ge_constraints) == 1
    assert ge_constraints[0].ge == 1


@pytest.mark.asyncio
async def test_list_jobs_accepts_limit_1000(monkeypatch) -> None:
    """Passing limit=1000 to list_jobs must not raise; it is now a valid value."""

    class FakeCursor:
        async def fetchone(self):
            return (0,)

        async def fetchall(self):
            return []

    class FakeConn:
        async def execute(self, *_args, **_kwargs):
            return FakeCursor()

    class FakeConnection:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr(jobs.database, "connection", lambda: FakeConnection())
    async def _fake_get_thumbnail_job_ids(_ids: list) -> set:
        return set()

    monkeypatch.setattr(
        jobs.database,
        "get_thumbnail_job_ids",
        _fake_get_thumbnail_job_ids,
    )

    # Must not raise; with no rows the response is an empty list.
    response = await jobs.list_jobs(
        SimpleNamespace(state=SimpleNamespace(user={"id": 1})),
        page=1,
        limit=1000,
    )
    assert response["items"] == []
    assert response["limit"] == 1000

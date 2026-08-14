import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import jobs
from src.api.jobs import is_persistable_short_platform, resolve_thumbnail


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtube_watch() -> None:
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://www.youtube.com/watch?v=abc123", "content_type": "long"}
    ) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_long_youtu_be() -> None:
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://youtu.be/abc123", "content_type": "long"}
    ) == (
        "https://img.youtube.com/vi/abc123/hqdefault.jpg",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_repo() -> None:
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://github.com/owner/repo/issues/1", "content_type": "repo"}
    ) == (
        "https://opengraph.githubassets.com/0/owner/repo",
        "landscape",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_youtube_short() -> None:
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://youtube.com/shorts/short123", "content_type": "short"}
    ) == (
        "https://img.youtube.com/vi/short123/hqdefault.jpg",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_and_tiktok_short_placeholder(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return False

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}
    ) == (None, None)
    assert await resolve_thumbnail(
        {
            "id": "j2",
            "url": "https://www.tiktok.com/@user/video/1234567890",
            "content_type": "short",
        }
    ) == (
        None,
        None,
    )
    assert await resolve_thumbnail(
        {"id": "j3", "url": "https://vt.tiktok.com/ZS2vJqL2Y/", "content_type": "short"}
    ) == (
        None,
        None,
    )


def test_is_persistable_short_platform() -> None:
    assert is_persistable_short_platform("https://instagram.com/reel/abc123")
    assert is_persistable_short_platform("https://www.tiktok.com/@user/video/123")
    assert is_persistable_short_platform("https://vt.tiktok.com/ZS2vJqL2Y/")
    assert is_persistable_short_platform("https://facebook.com/share/v/123")
    assert is_persistable_short_platform("https://x.com/user/status/123")
    assert is_persistable_short_platform("https://mobile.twitter.com/user/status/123")
    assert not is_persistable_short_platform("https://youtube.com/shorts/abc123")


@pytest.mark.asyncio
async def test_resolve_thumbnail_ig_short_uses_persisted_thumbnail(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return True

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)

    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://instagram.com/reel/abc123", "content_type": "short"}
    ) == (
        "/api/jobs/j1/thumbnail",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_unsized_short_uses_persisted_thumbnail(monkeypatch) -> None:
    async def _has_thumbnail(_job_id: str) -> bool:
        return True

    monkeypatch.setattr(jobs.database, "has_thumbnail", _has_thumbnail)

    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://x.com/user/status/123", "content_type": "short"}
    ) == (
        "/api/jobs/j1/thumbnail",
        "portrait",
    )


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_og_image() -> None:
    assert await resolve_thumbnail(
        {
            "id": "j1",
            "url": "https://medium.com/example/post",
            "content_type": "article",
            "og_image_url": "https://cdn.example.com/og.jpg",
        }
    ) == ("https://cdn.example.com/og.jpg", "landscape")


@pytest.mark.asyncio
async def test_resolve_thumbnail_article_placeholder() -> None:
    assert await resolve_thumbnail(
        {"id": "j1", "url": "https://medium.com/example/post", "content_type": "article"}
    ) == (None, None)


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
            return FakeCursor(
                [
                    {
                        "id": "j1",
                        "title": "Example",
                        "content_type": "long",
                        "status": "done",
                        "url": "https://youtube.com/watch?v=abc123",
                        "created_at": "2026-01-01T00:00:00Z",
                        "og_image_url": None,
                    }
                ]
            )

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

    assert (
        response["items"][0]["thumbnail_url"] == "https://img.youtube.com/vi/abc123/hqdefault.jpg"
    )
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


def test_post_jobs_routes_to_create_job() -> None:
    # Regression: the decorator once sat on _create_link_job, so POST /api/jobs
    # took chat_id/url as query params and never saw the body or the session.
    post = next(r for r in jobs.jobs_router.routes if r.path == "/api/jobs" and "POST" in r.methods)
    assert post.endpoint is jobs.create_job


@pytest.mark.asyncio
async def test_create_pipeline_job_accepts_unsized_host(monkeypatch) -> None:
    monkeypatch.setattr(jobs.database, "list_allowed_domains", AsyncMock(return_value=[]))
    create = AsyncMock(
        return_value={
            "id": "job-unsized",
            "url": "https://facebook.com/share/v/123",
            "content_type": "unsized",
            "status": "pending",
        }
    )
    monkeypatch.setattr(jobs, "create_and_enqueue_job", create)

    result = await jobs._create_pipeline_job(
        jobs.JobCreateRequest(url="https://facebook.com/share/v/123"),
        1,
        "https://facebook.com/share/v/123",
    )

    assert result["content_type"] == "unsized"


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/thumbnail — cache headers (issue #436)
# ---------------------------------------------------------------------------


USER_A = {"id": 1, "username": "alice"}
USER_B = {"id": 2, "username": "bob"}


@pytest.fixture
def jobs_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A FastAPI app with SessionMiddleware + jobs_router over a fresh file DB.

    Mints real sessions via src.auth.session.mint() (rather than hand-seeding a
    store) so the fixture works regardless of the local SESSION_BACKEND
    (memory vs redis) — hand-seeding a FakeRedis store, like
    tests/test_spaces.py does, silently no-ops when SESSION_BACKEND=memory
    since resolve() then reads an in-process dict instead.
    """
    db_file = tmp_path / "jobs_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))

    from src import database

    async def _setup() -> tuple[str, str]:
        await database.init_db()
        await database.set_user_status(USER_A["id"], "approved")
        await database.set_user_status(USER_B["id"], "approved")
        return await session_module.mint(USER_A), await session_module.mint(USER_B)

    from src.api.jobs import jobs_router
    from src.auth.middleware import SessionMiddleware
    from src.auth import session as session_module

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware)
    test_app.include_router(jobs_router)

    session_a, session_b = asyncio.run(_setup())

    client = TestClient(test_app, raise_server_exceptions=True)
    client.session_a = session_a  # type: ignore[attr-defined]
    client.session_b = session_b  # type: ignore[attr-defined]
    return client


def _insert_thumbnail_job(job_id: str, chat_id: int) -> None:
    async def run() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (id, chat_id, url, content_type, status, title, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    chat_id,
                    "https://www.instagram.com/reel/abc/",
                    "short",
                    "done",
                    f"title {job_id}",
                    "2026-01-01 00:00:00",
                ),
            )
            await conn.commit()
        await database.save_thumbnail(job_id, b"\xff\xd8fakejpeg", mime="image/jpeg")

    asyncio.run(run())


@pytest.mark.parametrize(
    ("content_type", "includes_transcript"),
    [("long", True), ("article", False), ("repo", False)],
)
def test_job_detail_exposes_transcript_only_for_long_jobs(
    jobs_client: TestClient, content_type: str, includes_transcript: bool
) -> None:
    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (id, chat_id, url, content_type, status, transcript)
                VALUES (?, ?, ?, ?, 'done', 'populated transcript')
                """,
                (f"detail-{content_type}", USER_A["id"], "https://example.com/item", content_type),
            )
            await conn.commit()

    asyncio.run(seed())
    jobs_client.cookies.set("vig_session", jobs_client.session_a)

    response = jobs_client.get(f"/api/jobs/detail-{content_type}")

    assert response.status_code == 200
    assert ("transcript" in response.json()) is includes_transcript


def test_delete_job_leaves_brain_links_standing_and_enqueues_refs(
    jobs_client: TestClient,
) -> None:
    """ADR-0046: a job is a work record, its links are knowledge that outlives it.

    Deleting the job leaves `source_job` dangling as pure provenance.
    """
    _insert_thumbnail_job("pending-delete", chat_id=1)

    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET status='pending', "
                "drive_url='https://drive.google.com/file/d/drive-1/view', "
                "prd_auto_drive_file_id='drive-2', url='https://example.com/job' WHERE id=?",
                ("pending-delete",),
            )
            await conn.execute(
                "INSERT INTO links (id, url, source_job, last_seen_at, created_at, updated_at) "
                "VALUES (?, ?, ?, '2026-01-01', '2026-01-01', '2026-01-01')",
                ("link-1", "https://example.com/link", "pending-delete"),
            )
            await conn.commit()
        await database.add_document_output("pending-delete", "raw_txt", "parsed/key.txt")

    asyncio.run(seed())
    jobs_client.cookies.set("vig_session", jobs_client.session_a)
    response = jobs_client.delete("/api/jobs/pending-delete")

    assert response.status_code == 204
    assert asyncio.run(jobs.database.get_job("pending-delete")) is None
    surviving = asyncio.run(
        jobs.database._fetch_one("SELECT id FROM links WHERE source_job = ?", ("pending-delete",))
    )
    assert surviving is not None and surviving["id"] == "link-1"
    pending = asyncio.run(jobs.database.list_pending_purge_tasks())
    assert [entry["task_payload"] for entry in pending] == [
        {
            "task": "job_purge",
            "job_id": "pending-delete",
            "chat_id": 1,
            "drive_file_ids": ["drive-1", "drive-2"],
            "gcs_keys": ["parsed/key.txt"],
            "url": "https://example.com/job",
        }
    ]


def test_delete_job_with_links_flag_removes_them(
    jobs_client: TestClient,
) -> None:
    """The old cascade survives as an opt-in — same SQL, opposite default."""
    _insert_thumbnail_job("delete-with-links", chat_id=1)

    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO links (id, url, source_job, last_seen_at, created_at, updated_at) "
                "VALUES (?, ?, ?, '2026-01-01', '2026-01-01', '2026-01-01')",
                ("link-2", "https://example.com/link-2", "delete-with-links"),
            )
            await conn.commit()

    asyncio.run(seed())
    jobs_client.cookies.set("vig_session", jobs_client.session_a)
    response = jobs_client.delete("/api/jobs/delete-with-links?with_links=1")

    assert response.status_code == 204
    assert (
        asyncio.run(
            jobs.database._fetch_one(
                "SELECT id FROM links WHERE source_job = ?", ("delete-with-links",)
            )
        )
        is None
    )


def test_delete_job_unknown_and_foreign_leave_rows_intact(
    jobs_client: TestClient,
) -> None:
    _insert_thumbnail_job("owned-by-a", chat_id=1)
    jobs_client.cookies.set("vig_session", jobs_client.session_b)
    assert jobs_client.delete("/api/jobs/owned-by-a").status_code == 403
    assert asyncio.run(jobs.database.get_job("owned-by-a")) is not None
    assert jobs_client.delete("/api/jobs/missing").status_code == 404
    assert asyncio.run(jobs.database.get_job("owned-by-a")) is not None


def test_get_job_link_topics_returns_owned_jobs_folders(
    jobs_client: TestClient,
) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)

    async def seed() -> None:
        from src import database

        async with database.connection() as conn:
            await conn.execute(
                """INSERT INTO links (id, url, topic, source_job, last_seen_at, created_at, updated_at)
                   VALUES ('l1', 'https://a.com', 'screeners', 'owner-job', 't', 't', 't')"""
            )
            await conn.commit()

    asyncio.run(seed())
    jobs_client.cookies.set("vig_session", jobs_client.session_a)

    resp = jobs_client.get("/api/jobs/owner-job/link-topics")

    assert resp.status_code == 200
    assert resp.json() == [{"topic": "screeners", "link_ids": ["l1"], "count": 1}]


def test_get_job_link_topics_forbidden_for_foreign_job(
    jobs_client: TestClient,
) -> None:
    _insert_thumbnail_job("owner-job", chat_id=1)
    jobs_client.cookies.set("vig_session", jobs_client.session_b)

    resp = jobs_client.get("/api/jobs/owner-job/link-topics")

    assert resp.status_code == 403


class TestJobThumbnailCaching:
    def test_first_request_sets_cache_control_and_etag(self, jobs_client: TestClient) -> None:
        _insert_thumbnail_job("s1", chat_id=1)

        jobs_client.cookies.set("vig_session", jobs_client.session_a)
        resp = jobs_client.get("/api/jobs/s1/thumbnail")

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/jpeg")
        assert resp.headers["cache-control"] == "private, max-age=2592000, must-revalidate"
        assert resp.headers["etag"]

    @pytest.mark.parametrize(
        "header_value",
        [
            "{etag}",
            "*",
            '"stale", {etag}',
            "W/{etag}",
        ],
    )
    def test_matching_if_none_match_returns_304(
        self, jobs_client: TestClient, header_value: str
    ) -> None:
        _insert_thumbnail_job("s1", chat_id=1)
        jobs_client.cookies.set("vig_session", jobs_client.session_a)

        first = jobs_client.get("/api/jobs/s1/thumbnail")
        etag = first.headers["etag"]

        second = jobs_client.get(
            "/api/jobs/s1/thumbnail",
            headers={"If-None-Match": header_value.format(etag=etag)},
        )
        assert second.status_code == 304
        assert second.content == b""
        assert second.headers["etag"] == etag

    def test_mismatched_if_none_match_returns_200(self, jobs_client: TestClient) -> None:
        _insert_thumbnail_job("s1", chat_id=1)
        jobs_client.cookies.set("vig_session", jobs_client.session_a)

        resp = jobs_client.get("/api/jobs/s1/thumbnail", headers={"If-None-Match": '"stale"'})
        assert resp.status_code == 200
        assert resp.content == b"\xff\xd8fakejpeg"

    def test_foreign_job_thumbnail_still_forbidden(self, jobs_client: TestClient) -> None:
        _insert_thumbnail_job("s1", chat_id=1)
        jobs_client.cookies.set("vig_session", jobs_client.session_b)

        resp = jobs_client.get("/api/jobs/s1/thumbnail")
        assert resp.status_code == 403

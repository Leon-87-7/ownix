"""Unit tests for src/brain.py — no network, no real Drive."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from src.brain import (
    EMBEDDING_DIM,
    _cosine_similarity,
    _load_embeddings,
    _rebuild_lock,
    _resolve_identity,
    rebuild_graph,
    get_graph,
    get_link_preview,
    ingest_links,
    list_links,
    normalize_url,
    refresh_stale_links,
    search_links,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_blob(vec: np.ndarray) -> bytes:
    """Serialize a float32 array to the expected BLOB format."""
    return vec.astype(np.float32).tobytes()


def _rand_vec() -> np.ndarray:
    v = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    return v / (np.linalg.norm(v) + 1e-10)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def test_cosine_similarity_self():
    v = _rand_vec()
    score = _cosine_similarity(v, v)
    assert abs(score - 1.0) < 1e-5


def test_cosine_similarity_orthogonal():
    a = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    b = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    a[0] = 1.0
    b[1] = 1.0
    score = _cosine_similarity(a, b)
    assert abs(score) < 1e-5


# ---------------------------------------------------------------------------
# _load_embeddings
# ---------------------------------------------------------------------------

def test_load_embeddings_valid():
    v1 = _rand_vec()
    v2 = _rand_vec()
    rows = [
        {"id": "row1", "embedding": _make_blob(v1)},
        {"id": "row2", "embedding": _make_blob(v2)},
    ]
    ids, matrix = _load_embeddings(rows)
    assert ids == ["row1", "row2"]
    assert matrix.shape == (2, EMBEDDING_DIM)
    np.testing.assert_allclose(matrix[0], v1, rtol=1e-5)
    np.testing.assert_allclose(matrix[1], v2, rtol=1e-5)


def test_load_embeddings_bad_length_skipped(caplog):

    v_good = _rand_vec()
    bad_blob = b"\x00" * 10  # wrong length

    rows = [
        {"id": "good", "embedding": _make_blob(v_good)},
        {"id": "bad", "embedding": bad_blob},
    ]

    with patch("src.brain.log") as mock_log:
        ids, matrix = _load_embeddings(rows)

    assert "bad" not in ids
    assert "good" in ids
    assert matrix.shape == (1, EMBEDDING_DIM)
    mock_log.warning.assert_called_once()
    call_kwargs = mock_log.warning.call_args
    assert "brain.embedding_invalid_length" in call_kwargs[0]


# ---------------------------------------------------------------------------
# _resolve_identity — (title, description) pair, tiered per docs/TASK.md task 32
# ---------------------------------------------------------------------------

GOOD_DESC = "A utility-first CSS framework for rapidly building modern user interfaces."


@pytest.mark.asyncio
async def test_resolve_identity_github_returns_pair():
    """GitHub URLs: title is owner/repo, description is the repo description — separate fields."""
    url = "https://github.com/vercel/next.js"

    with patch(
        "src.services.github.fetch_repo_description",
        new=AsyncMock(return_value="The React Framework for the Web"),
    ):
        title, description, resolved = await _resolve_identity(url)

    assert title == "vercel/next.js"
    assert description == "The React Framework for the Web"
    assert resolved is True


@pytest.mark.asyncio
async def test_resolve_identity_github_missing_description():
    url = "https://github.com/vercel/next.js"

    with patch("src.services.github.fetch_repo_description", new=AsyncMock(return_value=None)):
        title, description, resolved = await _resolve_identity(url)

    assert title == "vercel/next.js"
    assert description == ""
    # None is ambiguous (missing repo vs transport error) -> retryable.
    assert resolved is False


@pytest.mark.asyncio
async def test_resolve_identity_strong_meta_skips_jina():
    """A normal-length page title with a solid description never touches Jina."""
    url = "https://docs.tailwindcss.com/getting-started"
    jina = AsyncMock()

    with patch(
        "src.brain._fetch_meta",
        new=AsyncMock(return_value=("Installation - Tailwind CSS", GOOD_DESC, True)),
    ), patch("src.services.jina.fetch_markdown", new=jina):
        title, description, resolved = await _resolve_identity(url)

    assert title == "Installation - Tailwind CSS"
    assert description == GOOD_DESC
    assert resolved is True
    jina.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_identity_vague_description_escalates_to_jina():
    """Description under 40 chars escalates; Jina's first paragraph becomes the description."""
    url = "https://example.com/article"
    body = "First paragraph of the article, detailed enough to describe it.\n\nSecond paragraph."

    with patch(
        "src.brain._fetch_meta", new=AsyncMock(return_value=("A Fine Article", "Short.", True))
    ), patch(
        "src.services.jina.fetch_markdown",
        new=AsyncMock(return_value=("A Fine Article — Full Title", body)),
    ):
        title, description, resolved = await _resolve_identity(url)

    assert title == "A Fine Article — Full Title"
    assert description == "First paragraph of the article, detailed enough to describe it."
    assert resolved is True


@pytest.mark.asyncio
async def test_resolve_identity_falls_back_to_host_hint():
    """Total fetch failure yields the deterministic host hint and an empty description."""
    url = "https://docs.tailwindcss.com/getting-started"

    with patch("src.brain._fetch_meta", new=AsyncMock(return_value=("", "", False))), patch(
        "src.services.jina.fetch_markdown", new=AsyncMock(side_effect=Exception("down"))
    ):
        title, description, resolved = await _resolve_identity(url)

    assert title == "docs.tailwindcss"
    assert description == ""
    assert resolved is False


# ---------------------------------------------------------------------------
# Soft dedup (seen_count)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_dedup_seen_count():
    """Ingesting the same URL twice must yield one row with seen_count=2, updated_at unchanged."""
    import aiosqlite
    import tempfile
    import os
    from src.brain import ingest_links, SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Bootstrap schema
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            # Also need the jobs table for source-job lookup
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    url TEXT,
                    drive_url TEXT
                );
                INSERT INTO jobs (id, url, drive_url) VALUES ('job_001', 'https://yt.com/watch?v=1', NULL);
                """
            )
            await conn.commit()

        url = "https://example.com/tool"
        link = {"url": url, "title": "Example Tool"}

        with patch("src.brain.settings") as mock_settings, \
             patch("src.brain.upload_file", new_callable=AsyncMock) as mock_upload, \
             patch("src.brain._embed", new_callable=AsyncMock) as mock_embed, \
             patch(
                 "src.brain._resolve_identity",
                 new=AsyncMock(return_value=("Example Tool — Official Site", GOOD_DESC, True)),
             ):

            mock_settings.DB_PATH = db_path
            mock_settings.GOOGLE_DRIVE_FOLDER_BRAIN = "fake-folder-id"
            mock_settings.BRAIN_MIN_SCORE = 0.5
            mock_embed.return_value = _rand_vec()
            mock_upload.return_value = ("file-id-123", "https://drive.google.com/file/x")

            # First ingest
            await ingest_links([link], topic="tools", source_job_id="job_001")
            # Second ingest (same URL)
            await ingest_links([link], topic="tools", source_job_id="job_001")

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT COUNT(*) as cnt, MAX(seen_count) as max_seen, MAX(title) as title, "
                "MAX(description) as description FROM links WHERE url = ?",
                (url,),
            )
            row = await cursor.fetchone()

        assert row["cnt"] == 1, "Expected exactly one row per URL"
        assert row["max_seen"] == 2, "seen_count should be 2 after two ingests"
        # Standalone identity: the resolved page title beats the provided label,
        # and the per-URL description is persisted.
        assert row["title"] == "Example Tool — Official Site"
        assert row["description"] == GOOD_DESC

    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# Rebuild lock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebuild_lock_blocks_concurrent():
    """Calling rebuild_graph while lock is held must raise RuntimeError."""
    async with _rebuild_lock:
        with pytest.raises(RuntimeError, match="rebuild_in_progress"):
            await rebuild_graph()


# ---------------------------------------------------------------------------
# Refresh skips when lock held
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_skips_when_lock_held():
    """refresh_stale_links should return immediately without touching DB when lock is locked."""
    with patch("src.brain.log") as mock_log:
        async with _rebuild_lock:
            await refresh_stale_links()

    mock_log.info.assert_called_with(
        "brain.refresh_skipped", reason="rebuild_in_progress"
    )


# ---------------------------------------------------------------------------
# search_links returns [] when no corpus
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_returns_empty_on_no_corpus():
    """search_links should return [] when DB has no embeddings."""
    import tempfile
    import os
    import aiosqlite
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT)"
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings, \
             patch("src.brain._embed", new_callable=AsyncMock) as mock_embed:

            mock_settings.DB_PATH = db_path
            mock_settings.BRAIN_MIN_SCORE = 0.5
            mock_embed.return_value = _rand_vec()

            results = await search_links("some query", top_k=5)

        assert results == []

    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_normalized_url_dedup_variants():
    """Query strings, fragments, and trailing slashes collapse to one Brain node."""
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, url TEXT, drive_url TEXT);
                INSERT INTO jobs (id, url, drive_url) VALUES ('job_norm', 'https://yt.com/watch?v=1', NULL);
            """)
            await conn.commit()

        with patch("src.brain.settings") as mock_settings, \
             patch("src.brain.upload_file", new_callable=AsyncMock) as mock_upload, \
             patch("src.brain._embed", new_callable=AsyncMock) as mock_embed, \
             patch("src.brain._resolve_identity", new=AsyncMock(return_value=("Tool", "", True))):
            mock_settings.DB_PATH = db_path
            mock_settings.GOOGLE_DRIVE_FOLDER_BRAIN = "fake-folder-id"
            mock_settings.BRAIN_MIN_SCORE = 0.5
            mock_embed.return_value = _rand_vec()
            mock_upload.return_value = ("file-id", "drive-url")

            await ingest_links([{"url": "https://example.com/tool/?v=X&t=10#frag", "title": "Tool"}], "tools", "job_norm")
            await ingest_links([{"url": "https://example.com/tool/?v=X", "title": "Tool"}], "tools", "job_norm")
            await ingest_links([{"url": "https://example.com/tool/", "title": "Tool"}], "tools", "job_norm")

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT url, seen_count FROM links")
            rows = await cursor.fetchall()

        assert normalize_url("https://example.com/tool/?v=X#frag") == "https://example.com/tool"
        # Root-domain URLs collapse to one canonical form regardless of trailing slash.
        assert normalize_url("https://example.com/") == normalize_url("https://example.com") == "https://example.com"
        assert len(rows) == 1
        assert rows[0]["url"] == "https://example.com/tool"
        assert rows[0]["seen_count"] == 3
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_get_graph_empty_corpus():
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT)")
            await conn.commit()
        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            mock_settings.BRAIN_MIN_SCORE = 0.5
            assert await get_graph() == {"nodes": [], "edges": []}
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_list_links_orders_by_last_seen_paginates_and_filters_cancelled_but_keeps_photo_rows():
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT)")
            await conn.executemany(
                "INSERT INTO jobs (id, status) VALUES (?, ?)",
                [("job_done", "done"), ("job_cancelled", "cancelled")],
            )
            await conn.executemany(
                """INSERT INTO links
                   (id, url, title, topic, source_job, seen_count, last_seen_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        "old",
                        "https://example.com/old",
                        "Old",
                        "topic-a",
                        "job_done",
                        3,
                        "2026-06-29T09:00:00+00:00",
                        "2026-06-27T10:00:00+00:00",
                        "2026-06-29T09:00:00+00:00",
                    ),
                    (
                        "new",
                        "https://example.com/new",
                        "New",
                        "topic-b",
                        "job_done",
                        7,
                        "2026-06-28T10:00:00+00:00",
                        "2026-06-28T10:00:00+00:00",
                        "2026-06-28T10:00:00+00:00",
                    ),
                    (
                        "cancelled",
                        "https://example.com/cancelled",
                        "Cancelled",
                        "topic-c",
                        "job_cancelled",
                        1,
                        "2026-06-29T10:00:00+00:00",
                        "2026-06-29T10:00:00+00:00",
                        "2026-06-29T10:00:00+00:00",
                    ),
                    (
                        "photo",
                        "https://example.com/photo",
                        "Photo",
                        "topic-photo",
                        "photo_123",
                        2,
                        "2026-06-28T12:00:00+00:00",
                        "2026-06-28T12:00:00+00:00",
                        "2026-06-28T12:00:00+00:00",
                    ),
                ],
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            first_page = await list_links(limit=2, offset=0)
            second_page = await list_links(limit=2, offset=2)

        assert first_page["total"] == 3
        assert [item["url"] for item in first_page["items"]] == [
            "https://example.com/old",
            "https://example.com/photo",
        ]
        assert first_page["items"][0]["first_seen"] == "2026-06-27T10:00:00+00:00"
        assert first_page["items"][0]["last_seen"] == "2026-06-29T09:00:00+00:00"
        assert first_page["items"][0]["seen_count"] == 3
        assert [item["url"] for item in second_page["items"]] == [
            "https://example.com/new",
        ]
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_link_preview_keeps_transient_fetch_failure_retryable() -> None:
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute(
                """INSERT INTO links
                   (id, url, title, topic, source_job, seen_count,
                    last_seen_at, created_at, updated_at, og_image_url)
                   VALUES ('link-1', 'https://example.com/page', 'Title', 'Topic',
                           'job-1', 1, 't', 't', 't', NULL)"""
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings, patch(
            "src.brain.fetch_public_html", new=AsyncMock(return_value=None)
        ):
            mock_settings.DB_PATH = db_path
            result = await get_link_preview("link-1")

        async with aiosqlite.connect(db_path) as conn:
            stored = await (
                await conn.execute("SELECT og_image_url FROM links WHERE id = 'link-1'")
            ).fetchone()

        assert result == {"id": "link-1", "og_image_url": None}
        assert stored[0] is None
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_link_preview_caches_successful_page_without_an_image() -> None:
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL
    from src.utils.public_html import PublicHtmlResult

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute(
                """INSERT INTO links
                   (id, url, source_job, seen_count, last_seen_at, created_at, updated_at)
                   VALUES ('link-1', 'https://example.com/page', 'job-1', 1, 't', 't', 't')"""
            )
            await conn.commit()

        fetch = AsyncMock(
            return_value=PublicHtmlResult(
                html="<html><title>No image here</title></html>",
                final_url="https://example.com/page",
            )
        )
        with patch("src.brain.settings") as mock_settings, patch(
            "src.brain.fetch_public_html", new=fetch
        ):
            mock_settings.DB_PATH = db_path
            first = await get_link_preview("link-1")
            second = await get_link_preview("link-1")

        async with aiosqlite.connect(db_path) as conn:
            stored = await (
                await conn.execute("SELECT og_image_url FROM links WHERE id = 'link-1'")
            ).fetchone()

        assert first == second == {"id": "link-1", "og_image_url": None}
        assert fetch.await_count == 1
        assert stored[0] == ""
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_list_links_q_filters_by_substring_across_url_title_description():
    """Since #384, q matches url/title/description — never the shared video topic."""
    import aiosqlite
    import os
    import tempfile
    from unittest.mock import patch
    from src.brain import SCHEMA_SQL, list_links

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT)")
            await conn.execute("INSERT INTO jobs (id, status) VALUES ('j', 'done')")
            await conn.executemany(
                """INSERT INTO links
                   (id, url, title, topic, description, source_job, seen_count, last_seen_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 'j', 1, ?, ?, ?)""",
                [
                    ("a", "https://github.com/foo", "Repo", "code", None, "t", "t", "t"),
                    ("b", "https://news.com/x", "GitHub digest", "media", None, "t", "t", "t"),
                    ("c", "https://blog.io/y", "Other", "github-actions", None, "t", "t", "t"),
                    ("d", "https://example.com/z", "Nope", "misc", "A GitHub client.", "t", "t", "t"),
                ],
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            res = await list_links(q="github")  # case-insensitive; url/title/description
            empty = await list_links(q="   ")  # blank q is ignored, returns all

        # c matches only via its topic — excluded since #384; d matches via description.
        assert {item["url"] for item in res["items"]} == {
            "https://github.com/foo",
            "https://news.com/x",
            "https://example.com/z",
        }
        assert res["total"] == 3
        assert empty["total"] == 4
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_refresh_repo_metadata_skips_archived_and_updates_stale():
    import aiosqlite
    import os
    import tempfile
    from datetime import datetime, timedelta, timezone
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    old = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, url TEXT, drive_url TEXT, status TEXT)")
            await conn.execute("INSERT INTO jobs (id, status) VALUES ('job_repo', 'done')")
            await conn.execute("""
                INSERT INTO links (id, url, title, topic, source_job, embedding, drive_file_id, seen_count, last_seen_at, created_at, updated_at, archived)
                VALUES ('fresh', 'https://github.com/owner/fresh', 'Fresh', 'repo', 'job_repo', ?, 'drive', 1, ?, ?, ?, 0),
                       ('arch', 'https://github.com/owner/arch', 'Archived', 'repo', 'job_repo', ?, 'drive', 1, ?, ?, ?, 1)
            """, (_make_blob(_rand_vec()), old, old, old, _make_blob(_rand_vec()), old, old, old))
            await conn.commit()

        async def fake_bundle(owner, repo, token):
            return {"metadata": {"stars": 42, "pushed_at": "2026-06-01T00:00:00Z", "archived": False}}

        with patch("src.brain.settings") as mock_settings, \
             patch("src.brain.upload_file", new_callable=AsyncMock), \
             patch("src.services.github.fetch_repo_bundle", new=AsyncMock(side_effect=fake_bundle)) as mock_fetch:
            mock_settings.DB_PATH = db_path
            mock_settings.BRAIN_REFRESH_BATCH = 10
            mock_settings.BRAIN_MIN_SCORE = 0.0
            mock_settings.GOOGLE_DRIVE_FOLDER_BRAIN = "folder"
            mock_settings.GITHUB_TOKEN = "token"
            await refresh_stale_links()

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            rows = {r["id"]: r for r in await (await conn.execute("SELECT id, stars, pushed_at FROM links")).fetchall()}
        assert mock_fetch.await_count == 1
        assert rows["fresh"]["stars"] == 42
        assert rows["fresh"]["pushed_at"] == "2026-06-01T00:00:00Z"
        assert rows["arch"]["stars"] is None
    finally:
        os.unlink(db_path)

@pytest.mark.asyncio
async def test_list_links_sorts_by_last_seen_in_both_directions():
    import aiosqlite
    import os
    import tempfile
    from unittest.mock import patch
    from src.brain import SCHEMA_SQL, list_links

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT)")
            await conn.execute("INSERT INTO jobs (id, status) VALUES ('j', 'done')")
            await conn.executemany(
                """INSERT INTO links
                   (id, url, title, topic, source_job, seen_count, last_seen_at, created_at, updated_at)
                   VALUES (?, ?, ?, 'topic', 'j', ?, ?, ?, ?)""",
                [
                    ("a", "https://example.com/a", "A", 2, "2026-06-28T10:00:00+00:00", "t", "t"),
                    ("b", "https://example.com/b", "B", 9, "2026-06-27T10:00:00+00:00", "t", "t"),
                    ("c", "https://example.com/c", "C", 1, "2026-06-29T10:00:00+00:00", "t", "t"),
                ],
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            descending = await list_links(order="desc")
            ascending = await list_links(order="asc")
            fallback = await list_links(order="sideways")

        assert [item["url"] for item in descending["items"]] == [
            "https://example.com/c",
            "https://example.com/a",
            "https://example.com/b",
        ]
        assert [item["url"] for item in ascending["items"]] == [
            "https://example.com/b",
            "https://example.com/a",
            "https://example.com/c",
        ]
        assert [item["url"] for item in fallback["items"]] == [
            "https://example.com/c",
            "https://example.com/a",
            "https://example.com/b",
        ]
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# #384 / #387 — standalone search: no sibling-topic leakage, exact tag match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_links_search_is_standalone_and_matches_exact_tags():
    """Searching never matches the shared video topic; exact tag names match, substrings don't."""
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, status TEXT)")
            await conn.execute("INSERT INTO jobs (id, status) VALUES ('j', 'done')")
            # Three sibling links sharing one video topic mentioning svg.
            await conn.executemany(
                """INSERT INTO links
                   (id, url, title, topic, description, source_job, seen_count,
                    last_seen_at, created_at, updated_at)
                   VALUES (?, ?, ?, 'svg tips for devs', ?, 'j', 1, 't', 't', 't')""",
                [
                    ("a", "https://ora.studio", "ORA Studio", "Draw SVG shapes in the browser."),
                    ("b", "https://invoicegen.io", "Invoice Generator", "Privacy-first invoices."),
                    ("c", "https://iconfonts.dev", "Icon Fonts", "Icon font toolkit."),
                ],
            )
            await conn.executemany(
                "INSERT INTO tags (id, chat_id, name) VALUES (?, 1, ?)",
                [("t_svg", "svg"), ("t_svgicons", "svg-icons")],
            )
            await conn.executemany(
                "INSERT INTO link_tags (link_id, tag_id) VALUES (?, ?)",
                [("b", "t_svg"), ("c", "t_svgicons")],
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            result = await list_links(q="svg")

        urls = sorted(item["url"] for item in result["items"])
        # a: description hit; b: exact tag "svg"; c must NOT match — its topic
        # mentions svg (excluded, #384) and its tag is "svg-icons" (not exact, #387).
        assert urls == ["https://invoicegen.io", "https://ora.studio"]
        assert result["total"] == 2
        by_url = {item["url"]: item for item in result["items"]}
        assert [t["name"] for t in by_url["https://invoicegen.io"]["tags"]] == ["svg"]
        assert by_url["https://ora.studio"]["tags"] == []
    finally:
        os.unlink(db_path)


# ---------------------------------------------------------------------------
# #385 — refresh loop repairs description IS NULL and re-embeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_repairs_missing_description_and_reembeds():
    import aiosqlite
    import os
    import tempfile
    from src.brain import SCHEMA_SQL

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        old_vec = _rand_vec()
        async with aiosqlite.connect(db_path) as conn:
            await conn.executescript(SCHEMA_SQL)
            await conn.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, url TEXT, drive_url TEXT)")
            await conn.execute(
                """INSERT INTO links
                   (id, url, title, topic, description, source_job, embedding, drive_file_id,
                    seen_count, last_seen_at, created_at, updated_at)
                   VALUES ('l1', 'https://example.com/tool', 'Old Hint', 'video topic', NULL,
                           'j', ?, 'drive-1', 1, 't', 't', 't')""",
                (_make_blob(old_vec),),
            )
            await conn.commit()

        new_vec = _rand_vec()
        embed_calls: list[str] = []

        async def fake_embed(doc: str):
            embed_calls.append(doc)
            return new_vec

        with patch("src.brain.settings") as mock_settings, \
             patch(
                 "src.brain._resolve_identity",
                 new=AsyncMock(return_value=("Example Tool", GOOD_DESC, True)),
             ), \
             patch("src.brain._embed", new=fake_embed), \
             patch("src.brain.upload_file", new_callable=AsyncMock) as mock_upload:
            mock_settings.DB_PATH = db_path
            mock_settings.BRAIN_REFRESH_BATCH = 10
            mock_settings.GOOGLE_DRIVE_FOLDER_BRAIN = "folder"
            mock_settings.BRAIN_MIN_SCORE = 0.5
            mock_settings.GITHUB_TOKEN = ""
            mock_upload.return_value = ("file-id", "drive-url")
            await refresh_stale_links()

        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT title, description, embedding FROM links WHERE id = 'l1'"
            )
            row = await cursor.fetchone()

        assert row["description"] == GOOD_DESC
        assert row["title"] == "Example Tool"
        # Re-embedded with the link-own doc: description in, video topic out.
        assert embed_calls and GOOD_DESC in embed_calls[0]
        assert "video topic" not in embed_calls[0]
        np.testing.assert_allclose(
            np.frombuffer(row["embedding"], dtype=np.float32), new_vec, rtol=1e-5
        )
    finally:
        os.unlink(db_path)

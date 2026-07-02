"""Unit tests for src/brain.py — no network, no real Drive."""

from __future__ import annotations

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

from src.brain import (
    EMBEDDING_DIM,
    _cosine_similarity,
    _load_embeddings,
    _rebuild_lock,
    _resolve_title,
    rebuild_graph,
    get_graph,
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
    import logging

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
# _resolve_title
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_title_github():
    """GitHub URL should return the title from Gemini generate()."""
    url = "https://github.com/vercel/next.js"
    topic = "web dev"

    with patch("src.services.gemini.generate", new=AsyncMock(return_value="vercel/next.js")):
        result = await _resolve_title(url, topic)

    assert result == "vercel/next.js"


@pytest.mark.asyncio
async def test_resolve_title_strip_tld():
    """Non-GitHub URL falls back to hint when GeminiUnavailableError is raised."""
    from src.services.gemini import GeminiUnavailableError

    url = "https://docs.tailwindcss.com/getting-started"
    topic = "css"

    with patch("src.services.gemini.generate", new=AsyncMock(side_effect=GeminiUnavailableError("both failed"))):
        result = await _resolve_title(url, topic)

    assert result == "docs.tailwindcss"


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
             patch("src.brain._embed", new_callable=AsyncMock) as mock_embed:

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
                "SELECT COUNT(*) as cnt, MAX(seen_count) as max_seen FROM links WHERE url = ?",
                (url,),
            )
            row = await cursor.fetchone()

        assert row["cnt"] == 1, "Expected exactly one row per URL"
        assert row["max_seen"] == 2, "seen_count should be 2 after two ingests"

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
    from src.brain import ingest_links, SCHEMA_SQL

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
             patch("src.brain._embed", new_callable=AsyncMock) as mock_embed:
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
async def test_list_links_q_filters_by_substring_across_url_title_topic():
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
                   VALUES (?, ?, ?, ?, 'j', 1, ?, ?, ?)""",
                [
                    ("a", "https://github.com/foo", "Repo", "code", "t", "t", "t"),
                    ("b", "https://news.com/x", "GitHub digest", "media", "t", "t", "t"),
                    ("c", "https://blog.io/y", "Other", "github-actions", "t", "t", "t"),
                    ("d", "https://example.com/z", "Nope", "misc", "t", "t", "t"),
                ],
            )
            await conn.commit()

        with patch("src.brain.settings") as mock_settings:
            mock_settings.DB_PATH = db_path
            res = await list_links(q="github")  # case-insensitive; matches url/title/topic
            empty = await list_links(q="   ")  # blank q is ignored, returns all

        assert {item["url"] for item in res["items"]} == {
            "https://github.com/foo",
            "https://news.com/x",
            "https://blog.io/y",
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
async def test_list_links_sorts_by_appearances_and_falls_back_to_last_seen():
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
            by_appearances = await list_links(sort="appearances", order="desc")
            by_appearances_asc = await list_links(sort="appearances", order="asc")
            fallback = await list_links(sort="nonsense", order="sideways")

        assert [item["url"] for item in by_appearances["items"]] == [
            "https://example.com/b",
            "https://example.com/a",
            "https://example.com/c",
        ]
        assert [item["url"] for item in by_appearances_asc["items"]] == [
            "https://example.com/c",
            "https://example.com/a",
            "https://example.com/b",
        ]
        assert [item["url"] for item in fallback["items"]] == [
            "https://example.com/c",
            "https://example.com/a",
            "https://example.com/b",
        ]
    finally:
        os.unlink(db_path)

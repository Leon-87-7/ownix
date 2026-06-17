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
    """GitHub URL should return the title from gemini_client.generate."""
    url = "https://github.com/vercel/next.js"
    topic = "web dev"

    with patch("src.services.gemini.gemini_client") as mock_client:
        mock_client.generate = AsyncMock(return_value="vercel/next.js")
        result = await _resolve_title(url, topic)

    assert result == "vercel/next.js"


@pytest.mark.asyncio
async def test_resolve_title_strip_tld():
    """Non-GitHub URL falls back to hint when GeminiUnavailableError is raised."""
    from src.services.gemini import GeminiUnavailableError

    url = "https://docs.tailwindcss.com/getting-started"
    topic = "css"

    with patch("src.services.gemini.gemini_client") as mock_client:
        mock_client.generate = AsyncMock(side_effect=GeminiUnavailableError("both failed"))
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

"""#492: the bookmarks processor is deliberately hollow — it completes the
job and ingests zero links. Real parsing lands in #495."""

from __future__ import annotations

import base64
import os
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
async def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db

        await db.init_db()
        yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_run_marks_job_done_and_creates_no_links(temp_db):
    from src import database
    from src.processors import bookmarks

    job_id = await database.create_job(
        chat_id=1, url="bookmarks:deadbeefcafef00d", content_type="link"
    )
    await database.update_job_status(job_id, "pending", title="Bookmarks 8/6/26")
    job = await database.get_job(job_id)

    html_b64 = base64.b64encode(b"<!DOCTYPE NETSCAPE-Bookmark-file-1>\r\n").decode("ascii")
    await bookmarks.run(job, html_b64=html_b64)

    updated = await database.get_job(job_id)
    assert updated["status"] == "done"
    row = await database._fetch_one(
        "SELECT COUNT(*) AS n FROM links WHERE source_job = ?", (job_id,)
    )
    assert row["n"] == 0


@pytest.mark.asyncio
async def test_run_raises_on_corrupt_envelope(temp_db):
    """A decode failure surfaces as a real job error, not a hollow 'done'."""
    from src import database
    from src.processors import bookmarks

    job_id = await database.create_job(
        chat_id=1, url="bookmarks:deadbeefcafef00d", content_type="link"
    )
    job = await database.get_job(job_id)

    with pytest.raises(Exception):
        await bookmarks.run(job, html_b64="not valid base64 !!!")

    # Left mid-flight, not silently marked done — the worker's error path
    # (src/worker.py's _handle_bookmarks) is what sets status='error'.
    updated = await database.get_job(job_id)
    assert updated["status"] == "processing"

"""#495: the bookmarks processor parses the HTML and inserts one standalone
link per URL, skipping URLs that already exist (snapshot ingest, ADR-0048)."""

from __future__ import annotations

import base64
import binascii
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


def _b64(html: str) -> str:
    return base64.b64encode(html.encode("utf-8")).decode("ascii")


_TWO_LINK_HTML = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><H3 ADD_DATE="1600000000">Bookmarks bar</H3>
    <DL><p>
        <DT><A HREF="https://land-book.com" ADD_DATE="1621107450">Land-Book</A>
        <DT><H3 ADD_DATE="1600000001">screeners</H3>
        <DL><p>
            <DT><A HREF="https://finviz.com" ADD_DATE="1600000003">Finviz</A>
        </DL><p>
    </DL><p>
</DL><p>
"""


async def _make_job(chat_id: int = 1) -> dict:
    from src import database

    job_id = await database.create_job(
        chat_id=chat_id, url="bookmarks:deadbeefcafef00d", content_type="link"
    )
    await database.update_job_status(job_id, "pending", title="Bookmarks 8/6/26")
    return await database.get_job(job_id)


@pytest.mark.asyncio
async def test_run_marks_job_done_and_creates_no_links_for_an_empty_file(temp_db):
    from src import database
    from src.processors import bookmarks

    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64("<!DOCTYPE NETSCAPE-Bookmark-file-1>\r\n"))

    updated = await database.get_job(job["id"])
    assert updated["status"] == "done"
    row = await database._fetch_one(
        "SELECT COUNT(*) AS n FROM links WHERE source_job = ?", (job["id"],)
    )
    assert row["n"] == 0


@pytest.mark.asyncio
async def test_run_inserts_one_link_per_url_with_topic_and_created_at(temp_db):
    from src import database
    from src.processors import bookmarks

    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(_TWO_LINK_HTML))

    updated = await database.get_job(job["id"])
    assert updated["status"] == "done"

    rows = await database._fetch_dicts(
        "SELECT * FROM links WHERE source_job = ? ORDER BY url", (job["id"],)
    )
    assert [r["url"] for r in rows] == ["https://finviz.com", "https://land-book.com"]

    finviz = rows[0]
    assert finviz["topic"] == "screeners"
    assert finviz["description"] is None
    assert finviz["embedding"] is None
    assert finviz["seen_count"] == 1
    # ADD_DATE=1600000003 -> 2020-09-13T12:13:23+00:00
    assert finviz["created_at"].startswith("2020-09-13")

    landbook = rows[1]
    assert landbook["title"] == "Land-Book"
    assert landbook["topic"] == "Bookmarks bar"


@pytest.mark.asyncio
async def test_run_skips_urls_that_already_exist(temp_db):
    """Snapshot ingest: no seen_count bump, no touch, nothing rewritten."""
    from src import database, brain
    from src.processors import bookmarks

    async with database.connection() as conn:
        await conn.execute(
            """INSERT INTO links
               (id, chat_id, url, title, source_job, seen_count, last_seen_at, created_at, updated_at)
               VALUES ('existing', 1, 'https://land-book.com', 'Original title',
                       'other-job', 5, 't0', 't0', 't0')"""
        )
        await conn.commit()

    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(_TWO_LINK_HTML))

    row = await database._fetch_one(
        "SELECT * FROM links WHERE url = 'https://land-book.com'"
    )
    # Untouched: same title, same seen_count, same source_job as before import.
    assert row["title"] == "Original title"
    assert row["seen_count"] == 5
    assert row["source_job"] == "other-job"

    # The genuinely new URL still lands.
    finviz = await database._fetch_one("SELECT 1 FROM links WHERE url = 'https://finviz.com'")
    assert finviz is not None


@pytest.mark.asyncio
async def test_run_allows_same_url_for_different_chats(temp_db):
    from src import database
    from src.processors import bookmarks

    async with database.connection() as conn:
        await conn.execute(
            """INSERT INTO links
               (id, chat_id, url, title, source_job, seen_count, last_seen_at, created_at, updated_at)
               VALUES ('existing', 1, 'https://land-book.com', 'Original title',
                       'other-job', 5, 't0', 't0', 't0')"""
        )
        await conn.commit()

    job = await _make_job(chat_id=2)
    await bookmarks.run(job, html_b64=_b64(_TWO_LINK_HTML))

    rows = await database._fetch_dicts(
        "SELECT chat_id, url FROM links WHERE url = 'https://land-book.com' ORDER BY chat_id"
    )
    assert rows == [
        {"chat_id": 1, "url": "https://land-book.com"},
        {"chat_id": 2, "url": "https://land-book.com"},
    ]


@pytest.mark.asyncio
async def test_run_reimport_of_unchanged_export_writes_nothing(temp_db):
    from src import database
    from src.processors import bookmarks

    job1 = await _make_job()
    await bookmarks.run(job1, html_b64=_b64(_TWO_LINK_HTML))
    count_after_first = (
        await database._fetch_one("SELECT COUNT(*) AS n FROM links")
    )["n"]

    job2 = await _make_job()
    await bookmarks.run(job2, html_b64=_b64(_TWO_LINK_HTML))
    count_after_second = (
        await database._fetch_one("SELECT COUNT(*) AS n FROM links")
    )["n"]

    assert count_after_first == 2
    assert count_after_second == 2  # re-import added nothing


@pytest.mark.asyncio
async def test_run_falls_back_to_host_title_when_the_bookmark_has_none(temp_db):
    """The reference export's Bookmarks-bar-root entries are frequently
    titleless (ICON data with no inner text) — must not store an empty title."""
    from src import database
    from src.processors import bookmarks

    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p><DT><A HREF=\"https://example.com\" ADD_DATE=\"1600000000\">"
        "</A></DL><p>"
    )
    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(html))

    row = await database._fetch_one("SELECT title FROM links WHERE url = 'https://example.com'")
    assert row["title"] == "example"


@pytest.mark.asyncio
async def test_run_strips_trailing_whitespace_from_the_folder_name(temp_db):
    """The reference export has real folders like 'Trading ' / 'Value investing '
    with a trailing space — topic must not carry it into the DB."""
    from src import database
    from src.processors import bookmarks

    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p><DT><H3>Trading </H3>\n"
        '<DL><p><DT><A HREF="https://example.com" ADD_DATE="1600000000">x</A>'
        "</DL><p></DL><p>"
    )
    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(html))

    row = await database._fetch_one("SELECT topic FROM links WHERE url = 'https://example.com'")
    assert row["topic"] == "Trading"


@pytest.mark.asyncio
async def test_run_dedupes_repeated_urls_within_the_same_file(temp_db):
    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p>"
        '<DT><A HREF="https://x.com" ADD_DATE="1600000000">X first</A>'
        '<DT><A HREF="https://x.com" ADD_DATE="1600000001">X second</A>'
        "</DL><p>"
    )
    from src import database
    from src.processors import bookmarks

    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(html))

    rows = await database._fetch_dicts("SELECT * FROM links WHERE url = 'https://x.com'")
    assert len(rows) == 1
    assert rows[0]["title"] == "X first"  # first occurrence wins


@pytest.mark.asyncio
async def test_run_skips_non_http_hrefs(temp_db):
    html = (
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n"
        "<DL><p>"
        '<DT><A HREF="chrome://bookmarks/">Chrome</A>'
        '<DT><A HREF="javascript:alert(1)">JS</A>'
        '<DT><A HREF="https://ok.example">OK</A>'
        "</DL><p>"
    )
    from src import database
    from src.processors import bookmarks

    job = await _make_job()
    await bookmarks.run(job, html_b64=_b64(html))

    rows = await database._fetch_dicts("SELECT url FROM links WHERE source_job = ?", (job["id"],))
    assert [r["url"] for r in rows] == ["https://ok.example"]


@pytest.mark.asyncio
async def test_run_raises_on_corrupt_envelope(temp_db):
    """A decode failure surfaces as a real job error, not a hollow 'done'."""
    from src import database
    from src.processors import bookmarks

    job = await _make_job()

    with pytest.raises(binascii.Error):
        await bookmarks.run(job, html_b64="not valid base64 !!!")

    # Left mid-flight, not silently marked done — the worker's error path
    # (src/worker.py's _handle_bookmarks) is what sets status='error'.
    updated = await database.get_job(job["id"])
    assert updated["status"] == "processing"

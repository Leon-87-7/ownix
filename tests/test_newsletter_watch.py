"""Tests for the watch-a-newsletter schema and flow (ADR-0060, PLAN.md §1/§5/§6,
issue #609): the migration teardown, the shared publications/publication_issues
schema, `create_newsletter_watch`'s atomic create-or-reuse + explicit first
delivery, and the digest processor reading a persisted `context_md`.
"""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio


async def _init_db(tmp_path, monkeypatch) -> "object":
    db_file = tmp_path / "newsletter_watch.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    await database.init_db()
    return database


_ISSUES = [
    {"slug": "issue-b", "title": "Issue B", "url": "https://x.example/p/issue-b"},
    {"slug": "issue-a", "title": "Issue A", "url": "https://x.example/p/issue-a"},
]


async def _watch(database, *, chat_id: int = 1, archive_url: str = "https://x.example", **kw) -> dict:
    return await database.create_newsletter_watch(
        chat_id=chat_id,
        name=kw.pop("name", "Signals"),
        archive_url=archive_url,
        feed_url=kw.pop("feed_url", None),
        issue_path_prefix=kw.pop("issue_path_prefix", "/p/"),
        fetched_title=kw.pop("fetched_title", "X"),
        recent_issues=kw.pop("recent_issues", _ISSUES),
    )


# ---------------------------------------------------------------------------
# Migration: schema parity + teardown ordering
# ---------------------------------------------------------------------------


async def test_fresh_and_migrated_schema_match_for_newsletter_tables(tmp_path, monkeypatch) -> None:
    """A fresh SCHEMA_SQL install and a fully-migrated database must produce
    byte-identical sqlite_master rows for every table/index this migration
    owns — SCHEMA_SQL and the migration function share the same Python string
    constants for exactly this reason."""
    from src import database

    fresh_path = tmp_path / "fresh.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(fresh_path))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(fresh_path))
    await database.init_db()

    names = (
        "publications",
        "publication_issues",
        "newsletter_watches",
        "email_digest_payloads",
        "idx_newsletter_watches_publication_id",
        "idx_email_digest_payloads_watch_id",
        "idx_email_digest_payloads_publication_slug",
    )
    placeholders = ",".join("?" for _ in names)
    async with aiosqlite.connect(fresh_path) as conn:
        cur = await conn.execute(
            f"SELECT type, name, sql FROM sqlite_master WHERE name IN ({placeholders}) ORDER BY name",
            names,
        )
        fresh_rows = await cur.fetchall()

    migrated_path = tmp_path / "migrated.db"
    target_version = database._MIGRATIONS.index(database._migrate_newsletter_archive_polling)
    async with aiosqlite.connect(migrated_path) as conn:
        await conn.execute("PRAGMA foreign_keys=OFF")
        await conn.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, chat_id INTEGER, url TEXT, "
            "content_type TEXT, status TEXT, title TEXT, error_msg TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            "CREATE TABLE spaces (id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, "
            "name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#6366f1', "
            "icon TEXT NOT NULL DEFAULT 'folder', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(chat_id, name))"
        )
        await conn.execute(
            "CREATE TABLE space_urls (space_id TEXT NOT NULL REFERENCES spaces(id) "
            "ON DELETE CASCADE, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, "
            "sort_order INTEGER NOT NULL DEFAULT 0, "
            "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (space_id, job_id))"
        )
        await conn.execute(
            "CREATE TABLE context_blobs (id TEXT PRIMARY KEY, space_id TEXT NOT NULL "
            "REFERENCES spaces(id) ON DELETE CASCADE, name TEXT NOT NULL, "
            "content TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            """CREATE TABLE newsletter_subscriptions (
                id               TEXT PRIMARY KEY,
                chat_id          INTEGER NOT NULL,
                name             TEXT NOT NULL,
                sender_email     TEXT NOT NULL,
                alias_local_part TEXT NOT NULL UNIQUE,
                space_id         TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        await conn.execute(
            """CREATE TABLE digest_candidates (
                id            TEXT PRIMARY KEY,
                space_id      TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
                url           TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                title         TEXT,
                thumbnail_url TEXT,
                status        TEXT NOT NULL DEFAULT 'pending',
                job_id        TEXT REFERENCES jobs(id) ON DELETE SET NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(status IN ('pending','promoting','promoted','dismissed')),
                UNIQUE(space_id, canonical_url)
            )"""
        )
        await conn.execute(
            """CREATE TABLE email_digest_payloads (
                job_id          TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                receipt_key     TEXT NOT NULL,
                subscription_id TEXT REFERENCES newsletter_subscriptions(id) ON DELETE SET NULL,
                subject         TEXT,
                html            TEXT,
                text            TEXT,
                UNIQUE(subscription_id, receipt_key)
            )"""
        )
        await conn.execute(f"PRAGMA user_version = {target_version}")
        await conn.commit()
        await conn.execute("PRAGMA foreign_keys=ON")
        await database._run_migrations(conn)

        cur = await conn.execute(
            f"SELECT type, name, sql FROM sqlite_master WHERE name IN ({placeholders}) ORDER BY name",
            names,
        )
        migrated_rows = await cur.fetchall()

    assert fresh_rows == migrated_rows


async def test_migration_teardown_deletes_legacy_data_and_cascades(tmp_path, monkeypatch) -> None:
    """Teardown order (PLAN.md §1 / issue #609): legacy email_digest:% jobs and
    their payload rows go first, then each subscription's backing Space
    (cascading digest_candidates/space_urls/context_blobs/the subscription
    itself), then the now-empty newsletter_subscriptions table. An errored
    digest job must still be retryable afterwards is #611's concern; here we
    only assert nothing is orphaned."""
    from src import database

    db_path = tmp_path / "teardown.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA foreign_keys=OFF")
        await conn.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, chat_id INTEGER, url TEXT, "
            "content_type TEXT, status TEXT, title TEXT, error_msg TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            "CREATE TABLE spaces (id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, "
            "name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#6366f1', "
            "icon TEXT NOT NULL DEFAULT 'folder', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(chat_id, name))"
        )
        await conn.execute(
            "CREATE TABLE space_urls (space_id TEXT NOT NULL REFERENCES spaces(id) "
            "ON DELETE CASCADE, job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, "
            "sort_order INTEGER NOT NULL DEFAULT 0, "
            "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (space_id, job_id))"
        )
        await conn.execute(
            "CREATE TABLE context_blobs (id TEXT PRIMARY KEY, space_id TEXT NOT NULL "
            "REFERENCES spaces(id) ON DELETE CASCADE, name TEXT NOT NULL, "
            "content TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            """CREATE TABLE newsletter_subscriptions (
                id               TEXT PRIMARY KEY,
                chat_id          INTEGER NOT NULL,
                name             TEXT NOT NULL,
                sender_email     TEXT NOT NULL,
                alias_local_part TEXT NOT NULL UNIQUE,
                space_id         TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        await conn.execute(
            """CREATE TABLE digest_candidates (
                id            TEXT PRIMARY KEY,
                space_id      TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
                url           TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                title         TEXT,
                thumbnail_url TEXT,
                status        TEXT NOT NULL DEFAULT 'pending',
                job_id        TEXT REFERENCES jobs(id) ON DELETE SET NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(status IN ('pending','promoting','promoted','dismissed')),
                UNIQUE(space_id, canonical_url)
            )"""
        )
        await conn.execute(
            """CREATE TABLE email_digest_payloads (
                job_id          TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                receipt_key     TEXT NOT NULL,
                subscription_id TEXT REFERENCES newsletter_subscriptions(id) ON DELETE SET NULL,
                subject         TEXT,
                html            TEXT,
                text            TEXT,
                UNIQUE(subscription_id, receipt_key)
            )"""
        )
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, title) "
            "VALUES ('job_legacy', 1, 'email_digest:abc', 'link', 'error', 'x')"
        )
        await conn.execute(
            "INSERT INTO email_digest_payloads (job_id, receipt_key, subscription_id, "
            "subject, html, text) VALUES ('job_legacy', 'k1', NULL, 's', 'h', 't')"
        )
        await conn.execute("INSERT INTO spaces (id, chat_id, name) VALUES ('space1', 1, 'Old sub')")
        await conn.execute(
            "INSERT INTO newsletter_subscriptions (id, chat_id, name, sender_email, "
            "alias_local_part, space_id) VALUES ('sub1', 1, 'Old', 'e@x.com', 'u_x', 'space1')"
        )
        await conn.execute(
            "INSERT INTO digest_candidates (id, space_id, url, canonical_url) "
            "VALUES ('cand1', 'space1', 'https://x.com', 'https://x.com')"
        )
        target_version = database._MIGRATIONS.index(database._migrate_newsletter_archive_polling)
        await conn.execute(f"PRAGMA user_version = {target_version}")
        await conn.commit()
        await conn.execute("PRAGMA foreign_keys=ON")

        await database._run_migrations(conn)

        assert (
            await (
                await conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE name='newsletter_subscriptions'"
                )
            ).fetchone()
        )[0] == 0
        assert (await (await conn.execute("SELECT COUNT(*) FROM spaces WHERE id='space1'")).fetchone())[
            0
        ] == 0
        assert (
            await (await conn.execute("SELECT COUNT(*) FROM digest_candidates WHERE id='cand1'")).fetchone()
        )[0] == 0
        assert (await (await conn.execute("SELECT COUNT(*) FROM jobs WHERE id='job_legacy'")).fetchone())[
            0
        ] == 0


# ---------------------------------------------------------------------------
# Composite FK
# ---------------------------------------------------------------------------


async def test_composite_fk_rejects_payload_for_missing_issue(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)

    async with database.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, title) "
            "VALUES ('job_x', 1, 'email_digest:x:no-such-slug', 'link', 'pending', 't')"
        )
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO email_digest_payloads (job_id, watch_id, publication_id, slug) "
                "VALUES ('job_x', ?, ?, 'no-such-slug')",
                (watch["id"], watch["publication_id"]),
            )
        await conn.rollback()


# ---------------------------------------------------------------------------
# create_newsletter_watch: explicit first delivery, dedup, reconciliation
# ---------------------------------------------------------------------------


async def test_create_watch_delivers_newest_issue_explicitly(tmp_path, monkeypatch) -> None:
    """`recent_issues[0]` is newest (source_order 0); the explicit first
    delivery must pick it, not rely on watched_from < first_seen_at, which
    can collapse at clock precision since both are stamped in this same
    transaction (PLAN.md §6)."""
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)

    assert watch["watched_from"] is not None
    row = await database._fetch_one(
        "SELECT first_seen_at FROM publication_issues WHERE publication_id=? AND slug='issue-b'",
        (watch["publication_id"],),
    )
    # Both timestamps were written in the same transaction — they may well be
    # equal at second precision, which is exactly the case the explicit
    # delivery (not a watched_from filter) must survive.
    assert row["first_seen_at"] >= watch["watched_from"] or row["first_seen_at"] == watch["watched_from"]

    payload = await database.get_email_digest_payload(watch["delivery_job_id"])
    assert payload["slug"] == "issue-b"


async def test_create_watch_delivers_when_watched_from_equals_first_seen_at(
    tmp_path, monkeypatch
) -> None:
    """Pin both timestamps to the exact same value to force the clock-
    precision collapse PLAN.md §6 calls out: a `first_seen_at > watched_from`
    filter would then match *nothing*, yet the explicit first delivery must
    still exist and point at the newest issue."""
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)

    pinned = "2026-09-07 12:00:00"
    await database._execute_rowcount(
        "UPDATE newsletter_watches SET watched_from = ? WHERE id = ?", (pinned, watch["id"])
    )
    await database._execute_rowcount(
        "UPDATE publication_issues SET first_seen_at = ? WHERE publication_id = ?",
        (pinned, watch["publication_id"]),
    )

    # The naive filter the poller's missing-delivery scan uses for *later*
    # issues would match zero rows here — proving the explicit delivery
    # doesn't depend on it.
    naive_filter_matches = await database._fetch_one(
        "SELECT COUNT(*) AS n FROM publication_issues "
        "WHERE publication_id = ? AND first_seen_at > ?",
        (watch["publication_id"], pinned),
    )
    assert naive_filter_matches["n"] == 0

    assert watch["delivery_job_id"] is not None
    payload = await database.get_email_digest_payload(watch["delivery_job_id"])
    assert payload["slug"] == "issue-b"


async def test_create_watch_first_delivery_skips_skip_reason_issue(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    first = await _watch(database, chat_id=1, archive_url="https://skip.example")
    await database._execute_rowcount(
        "UPDATE publication_issues SET skip_reason='oversize' "
        "WHERE publication_id=? AND slug='issue-b'",
        (first["publication_id"],),
    )

    second = await _watch(database, chat_id=2, archive_url="https://skip.example")

    payload = await database.get_email_digest_payload(second["delivery_job_id"])
    assert payload["slug"] == "issue-a"


async def test_concurrent_create_watch_same_archive_url_yields_one_publication(
    tmp_path, monkeypatch
) -> None:
    database = await _init_db(tmp_path, monkeypatch)

    async def create(chat_id: int) -> dict:
        return await _watch(database, chat_id=chat_id, archive_url="https://race.example")

    results = await asyncio.gather(create(1), create(2))

    publication_ids = {r["publication_id"] for r in results}
    assert len(publication_ids) == 1
    row = await database._fetch_one("SELECT COUNT(*) AS n FROM publications")
    assert row["n"] == 1


async def test_publication_metadata_reconciliation_respects_cooldown(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    first = await _watch(
        database, chat_id=1, archive_url="https://meta.example", feed_url=None, fetched_title="Original"
    )

    # Within the cooldown: a missing field (feed_url) is still filled...
    await _watch(
        database,
        chat_id=2,
        archive_url="https://meta.example",
        feed_url="https://meta.example/feed.xml",
        fetched_title="Renamed",
    )
    pub = await database._fetch_one(
        "SELECT * FROM publications WHERE id=?", (first["publication_id"],)
    )
    assert pub["feed_url"] == "https://meta.example/feed.xml"
    # ...but an existing, populated field is not ping-ponged.
    assert pub["fetched_title"] == "Original"

    # Past the cooldown, a validated new value is allowed to replace it.
    await database._execute_rowcount(
        "UPDATE publications SET last_resolved_at = datetime('now', '-1 hour') WHERE id=?",
        (first["publication_id"],),
    )
    await _watch(
        database,
        chat_id=3,
        archive_url="https://meta.example",
        feed_url="https://meta.example/feed.xml",
        fetched_title="Renamed",
    )
    pub2 = await database._fetch_one(
        "SELECT * FROM publications WHERE id=?", (first["publication_id"],)
    )
    assert pub2["fetched_title"] == "Renamed"


# ---------------------------------------------------------------------------
# latest_retryable_email_digest_job (rewritten, not re-pointed)
# ---------------------------------------------------------------------------


async def test_latest_retryable_email_digest_job_keys_on_watch_and_error_status(
    tmp_path, monkeypatch
) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    assert await database.latest_retryable_email_digest_job(watch["id"]) is None

    await database.update_job_status(job_id, "error")
    job = await database.latest_retryable_email_digest_job(watch["id"])
    assert job is not None
    assert job["id"] == job_id


# ---------------------------------------------------------------------------
# Processor: context_md persistence / null-never-generates
# ---------------------------------------------------------------------------


async def test_run_inserts_persisted_context_without_gemini_call(tmp_path, monkeypatch) -> None:
    from src.processors import email_digest

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    await database._execute_rowcount(
        "UPDATE publication_issues SET body_html = ? WHERE publication_id=? AND slug='issue-b'",
        ("<p>no links here</p>", watch["publication_id"]),
    )
    await database._execute_rowcount(
        "UPDATE email_digest_payloads SET context_md = ? WHERE job_id = ?",
        ("Persisted editorial context.", job_id),
    )
    gemini_generate = AsyncMock(side_effect=AssertionError("must not call Gemini per job"))
    monkeypatch.setattr(email_digest.gemini, "generate", gemini_generate)

    job = await database.get_job(job_id)
    await email_digest.run(job)

    gemini_generate.assert_not_called()
    blobs = await database.list_context_blobs(watch["space_id"])
    assert len(blobs) == 1
    assert blobs[0]["content"] == "Persisted editorial context."
    assert (await database.get_job(job_id))["status"] == "done"
    payload = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE job_id=?", (job_id,)
    )
    assert payload["context_md"] is None


async def test_run_with_null_context_md_creates_no_context_blob(tmp_path, monkeypatch) -> None:
    """A null context_md must never trigger per-job generation — context is
    owned entirely by the poll worker (#610)."""
    from src.processors import email_digest

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    await database._execute_rowcount(
        "UPDATE publication_issues SET body_html = ? WHERE publication_id=? AND slug='issue-b'",
        ("<p>no links here</p>", watch["publication_id"]),
    )
    gemini_generate = AsyncMock(side_effect=AssertionError("must not call Gemini per job"))
    monkeypatch.setattr(email_digest.gemini, "generate", gemini_generate)

    job = await database.get_job(job_id)
    await email_digest.run(job)

    gemini_generate.assert_not_called()
    blobs = await database.list_context_blobs(watch["space_id"])
    assert blobs == []
    assert (await database.get_job(job_id))["status"] == "done"


async def test_first_delivery_fetches_the_missing_issue_body(tmp_path, monkeypatch) -> None:
    """A watch's explicit first delivery is created from resolver data, which
    never fetches bodies — so `run()` must fetch and persist the body on
    demand. Erroring instead would be terminal: the payload row already
    exists, so the missing-delivery scan would never revisit this pair and no
    poll would ever fetch it (council review, blocker)."""
    from src.processors import email_digest

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    issue = await database.get_publication_issue(watch["publication_id"], "issue-b")
    assert issue["body_html"] is None  # nothing has fetched a body yet

    fetch_html = AsyncMock(return_value="<p>fetched on demand</p>")
    monkeypatch.setattr(email_digest, "fetch_html", fetch_html)
    monkeypatch.setattr(email_digest, "is_public_url", AsyncMock(return_value=True))

    job = await database.get_job(job_id)
    await email_digest.run(job)

    fetch_html.assert_awaited_once_with(issue["url"])
    assert (await database.get_job(job_id))["status"] == "done"
    # Persisted on the shared row, so later watchers reuse it rather than refetching.
    refreshed = await database.get_publication_issue(watch["publication_id"], "issue-b")
    assert refreshed["body_html"] == "<p>fetched on demand</p>"


async def test_first_delivery_rejects_a_non_public_issue_url(tmp_path, monkeypatch) -> None:
    """The on-demand fetch goes through the same public-URL gate as every other
    Jina call — a stored issue URL must not become an unvalidated proxy fetch."""
    from src.processors import email_digest

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    fetch_html = AsyncMock(side_effect=AssertionError("must not fetch a non-public URL"))
    monkeypatch.setattr(email_digest, "fetch_html", fetch_html)
    monkeypatch.setattr(email_digest, "is_public_url", AsyncMock(return_value=False))

    job = await database.get_job(job_id)
    await email_digest.run(job)

    fetch_html.assert_not_called()
    assert (await database.get_job(job_id))["status"] == "error"


async def test_run_retains_context_md_on_error_for_retry(tmp_path, monkeypatch) -> None:
    """A fetch failure is an error, but the error row must keep context_md so a
    retry needs no regeneration (PLAN.md §1/§5)."""
    from src.processors import email_digest
    from src.services.jina import JinaFetchError

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    job_id = watch["delivery_job_id"]

    await database._execute_rowcount(
        "UPDATE email_digest_payloads SET context_md = ? WHERE job_id = ?",
        ("Keep me for retry.", job_id),
    )
    monkeypatch.setattr(email_digest, "is_public_url", AsyncMock(return_value=True))
    monkeypatch.setattr(email_digest, "fetch_html", AsyncMock(side_effect=JinaFetchError(503)))

    job = await database.get_job(job_id)
    await email_digest.run(job)

    assert (await database.get_job(job_id))["status"] == "error"
    payload = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE job_id=?", (job_id,)
    )
    assert payload["context_md"] == "Keep me for retry."

"""Unit tests for src/database.py helpers added in slice #7."""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import aiosqlite
import pytest


@pytest.fixture
async def temp_db():
    """Create a fresh SQLite file with the full schema applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Patch settings.DB_PATH for the duration of the test
    with patch("src.config.settings.DB_PATH", path):
        from src import database as db
        await db.init_db()
        yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_set_and_get_chat_state_round_trip(temp_db):
    from src import database as db
    await db.set_chat_state(chat_id=42, mode="awaiting_intent", job_id="20260521_120000_AAAA")
    state = await db.get_chat_state(42)
    assert state is not None
    assert state["chat_id"] == 42
    assert state["mode"] == "awaiting_intent"
    assert state["job_id"] == "20260521_120000_AAAA"
    assert state["expires_at"] > datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_get_chat_state_missing_returns_none(temp_db):
    from src import database as db
    assert await db.get_chat_state(999) is None


@pytest.mark.asyncio
async def test_clear_chat_state_removes_row(temp_db):
    from src import database as db
    await db.set_chat_state(chat_id=1, mode="awaiting_intent", job_id="J1")
    await db.clear_chat_state(1)
    assert await db.get_chat_state(1) is None


@pytest.mark.asyncio
async def test_clear_chat_state_idempotent(temp_db):
    from src import database as db
    await db.clear_chat_state(999)  # no-op, must not raise


@pytest.mark.asyncio
async def test_set_chat_state_pk_replace(temp_db):
    """Second set overwrites the first (PK on chat_id)."""
    from src import database as db
    await db.set_chat_state(chat_id=7, mode="awaiting_intent", job_id="J_OLD")
    await db.set_chat_state(chat_id=7, mode="awaiting_intent", job_id="J_NEW")
    state = await db.get_chat_state(7)
    assert state["job_id"] == "J_NEW"


async def _insert_job(path: str, job_id: str, chat_id: int, content_type: str, status: str, title: str = "") -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status, title) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, chat_id, f"https://x.test/{job_id}", content_type, status, title),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_find_jobs_by_suffix_returns_all_content_types(temp_db):
    from src import database as db
    await _insert_job(temp_db, "20260521_120000_AAAA", 1, "long", "done", "Long video A")
    await _insert_job(temp_db, "20260521_120100_AAAA", 1, "short", "done", "Short video A")
    await _insert_job(temp_db, "20260521_120200_BBBB", 1, "long", "done", "Long video B")
    rows = await db.find_jobs_by_suffix(1, "AAAA")
    assert len(rows) == 2
    # Ordered by created_at DESC; the short was inserted second
    assert rows[0]["content_type"] == "short"
    assert rows[1]["content_type"] == "long"


@pytest.mark.asyncio
async def test_find_jobs_by_suffix_chat_scoped(temp_db):
    from src import database as db
    await _insert_job(temp_db, "20260521_120000_AAAA", 1, "long", "done")
    await _insert_job(temp_db, "20260521_120000_BBBB", 2, "long", "done")
    rows = await db.find_jobs_by_suffix(1, "BBBB")
    assert rows == []


@pytest.mark.asyncio
async def test_get_recent_jobs_orders_desc_and_limits(temp_db):
    from src import database as db
    for i in range(7):
        await _insert_job(temp_db, f"2026052{i}_120000_J{i:03d}1", 1, "long", "done", f"job {i}")
    rows = await db.get_recent_jobs(1, limit=5)
    assert len(rows) == 5
    assert rows[0]["title"] == "job 6"  # most recent first


@pytest.mark.asyncio
async def test_create_job_with_template_writes_column(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test",
        content_type="long",
        template="method",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["template"] == "method"


@pytest.mark.asyncio
async def test_create_job_without_template_defaults_none(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test2",
        content_type="long",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["template"] is None


@pytest.mark.asyncio
async def test_update_job_status_writes_template_detection_method(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test3",
        content_type="long",
    )
    await db.update_job_status(job_id, "pending", template_detection_method="explicit_command")
    job = await db.get_job(job_id)
    assert job["template_detection_method"] == "explicit_command"


@pytest.mark.asyncio
async def test_update_job_status_writes_key_phrases(temp_db):
    import json
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=test4",
        content_type="long",
    )
    await db.update_job_status(job_id, "transcript_done", key_phrases=json.dumps(["stripe", "nextjs"]))
    job = await db.get_job(job_id)
    assert json.loads(job["key_phrases"]) == ["stripe", "nextjs"]


@pytest.mark.asyncio
async def test_set_prd_slot_status_auto(temp_db):
    from src import database as db
    job_id = await db.create_job(chat_id=1, url="https://youtube.com/watch?v=prd1", content_type="long")
    await db.set_prd_slot_status(job_id, "auto", "generating")
    job = await db.get_job(job_id)
    assert job["prd_auto_status"] == "generating"
    assert job["prd_intent_status"] is None


@pytest.mark.asyncio
async def test_set_prd_slot_status_intent(temp_db):
    from src import database as db
    job_id = await db.create_job(chat_id=1, url="https://youtube.com/watch?v=prd2", content_type="long")
    await db.set_prd_slot_status(job_id, "intent", "done")
    job = await db.get_job(job_id)
    assert job["prd_intent_status"] == "done"
    assert job["prd_auto_status"] is None


@pytest.mark.asyncio
async def test_promise_gap_column_exists(tmp_path, monkeypatch) -> None:
    """promise_gap column must exist after init_db()."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cursor = await conn.execute("PRAGMA table_info(jobs)")
        cols = {row[1] async for row in cursor}
    assert "promise_gap" in cols


@pytest.mark.asyncio
async def test_fresh_install_sets_user_version(tmp_path, monkeypatch) -> None:
    """Fresh init_db() must stamp user_version = len(_MIGRATIONS), skipping migrations."""
    db_file = str(tmp_path / "fresh.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA user_version")
        row = await cur.fetchone()
    assert row[0] == len(database._MIGRATIONS)


@pytest.mark.asyncio
async def test_migration_from_version_zero_adds_columns(tmp_path, monkeypatch) -> None:
    """A DB at user_version=0 with an existing jobs table must have new columns added."""
    db_file = str(tmp_path / "old.db")
    # Simulate an old DB: jobs table without the post-launch columns.
    async with aiosqlite.connect(db_file) as conn:
        await conn.execute(
            "CREATE TABLE jobs ("
            "id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, url TEXT NOT NULL,"
            " content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
            " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        await conn.commit()
        # user_version stays 0 (SQLite default)

    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA table_info(jobs)")
        cols = {row[1] async for row in cur}
        cur2 = await conn.execute("PRAGMA user_version")
        version = (await cur2.fetchone())[0]

    migration_cols = {
        "template", "template_analysis", "key_phrases",
        "validation_warning_sent", "template_detection_method",
        "promise_gap", "bot_message_id",
    }
    assert migration_cols <= cols
    assert version == len(database._MIGRATIONS)


@pytest.mark.asyncio
async def test_freestyle_prompt_column_exists(tmp_path, monkeypatch) -> None:
    """freestyle_prompt column must exist after init_db()."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cursor = await conn.execute("PRAGMA table_info(jobs)")
        cols = {row[1] async for row in cursor}
    assert "freestyle_prompt" in cols


@pytest.mark.asyncio
async def test_create_job_with_freestyle_prompt(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=fp1",
        content_type="long",
        freestyle_prompt="Summarise the key risks mentioned.",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["freestyle_prompt"] == "Summarise the key risks mentioned."


@pytest.mark.asyncio
async def test_create_job_without_freestyle_prompt_defaults_none(temp_db):
    from src import database as db
    job_id = await db.create_job(
        chat_id=99,
        url="https://youtube.com/watch?v=fp2",
        content_type="long",
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["freestyle_prompt"] is None


# ---------------------------------------------------------------------------
# allowed_domains CRUD (issue #61) — per-chat article allowlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_domains_table_exists(temp_db) -> None:
    """allowed_domains table is created with the documented schema."""
    async with aiosqlite.connect(temp_db) as conn:
        cur = await conn.execute("PRAGMA table_info(allowed_domains)")
        cols = {row[1] for row in await cur.fetchall()}
    assert {"chat_id", "domain", "added_at"} <= cols


@pytest.mark.asyncio
async def test_allowed_domains_composite_primary_key(temp_db) -> None:
    """PRIMARY KEY is (chat_id, domain) — same domain in two chats is allowed."""
    async with aiosqlite.connect(temp_db) as conn:
        await conn.execute(
            "INSERT INTO allowed_domains (chat_id, domain) VALUES (?, ?)", (1, "substack.com")
        )
        await conn.execute(
            "INSERT INTO allowed_domains (chat_id, domain) VALUES (?, ?)", (2, "substack.com")
        )
        await conn.commit()
        cur = await conn.execute("SELECT COUNT(*) FROM allowed_domains")
        count = (await cur.fetchone())[0]
    assert count == 2


@pytest.mark.asyncio
async def test_add_and_list_allowed_domain_round_trip(temp_db) -> None:
    from src import database as db
    await db.add_allowed_domain(chat_id=42, domain="substack.com")
    domains = await db.list_allowed_domains(chat_id=42)
    assert "substack.com" in domains


@pytest.mark.asyncio
async def test_list_allowed_domains_is_chat_scoped(temp_db) -> None:
    from src import database as db
    await db.add_allowed_domain(chat_id=1, domain="medium.com")
    await db.add_allowed_domain(chat_id=2, domain="dev.to")
    assert await db.list_allowed_domains(chat_id=1) == {"medium.com"}
    assert await db.list_allowed_domains(chat_id=2) == {"dev.to"}


@pytest.mark.asyncio
async def test_add_allowed_domain_idempotent(temp_db) -> None:
    """Duplicate insert for the same (chat_id, domain) must not raise."""
    from src import database as db
    await db.add_allowed_domain(chat_id=1, domain="ghost.org")
    await db.add_allowed_domain(chat_id=1, domain="ghost.org")
    domains = await db.list_allowed_domains(chat_id=1)
    assert domains == {"ghost.org"}


@pytest.mark.asyncio
async def test_remove_allowed_domain_returns_true_when_present(temp_db) -> None:
    from src import database as db
    await db.add_allowed_domain(chat_id=5, domain="hashnode.com")
    assert await db.remove_allowed_domain(chat_id=5, domain="hashnode.com") is True
    assert await db.list_allowed_domains(chat_id=5) == set()


@pytest.mark.asyncio
async def test_remove_allowed_domain_returns_false_when_missing(temp_db) -> None:
    from src import database as db
    assert await db.remove_allowed_domain(chat_id=5, domain="missing.com") is False


@pytest.mark.asyncio
async def test_allowed_domains_migration_idempotent(tmp_path, monkeypatch) -> None:
    """Running init_db() twice must not raise — the migration is idempotent."""
    db_file = str(tmp_path / "twice.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    # second run must be a no-op
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA table_info(allowed_domains)")
        cols = {row[1] for row in await cur.fetchall()}
    assert {"chat_id", "domain", "added_at"} <= cols


@pytest.mark.asyncio
async def test_migration_adds_allowed_domains_to_existing_db(tmp_path, monkeypatch) -> None:
    """A DB at the previous user_version must gain allowed_domains after migration."""
    db_file = str(tmp_path / "pre_allow.db")
    # Build a DB pinned at user_version = N-1 (the version just before this migration).
    from src import database
    target_version = len(database._MIGRATIONS) - 1
    async with aiosqlite.connect(db_file) as conn:
        await conn.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, "
            "url TEXT NOT NULL, content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(f"PRAGMA user_version = {target_version}")
        await conn.commit()
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA table_info(allowed_domains)")
        cols = {row[1] for row in await cur.fetchall()}
        cur2 = await conn.execute("PRAGMA user_version")
        version = (await cur2.fetchone())[0]
    assert {"chat_id", "domain", "added_at"} <= cols
    assert version == len(database._MIGRATIONS)


@pytest.mark.asyncio
async def test_migration_v1_to_v2_adds_freestyle_prompt(tmp_path, monkeypatch) -> None:
    """A DB at user_version=1 must gain freestyle_prompt after running migrations."""
    db_file = str(tmp_path / "v1.db")
    # Simulate a v1 DB: jobs table with template columns but no freestyle_prompt.
    async with aiosqlite.connect(db_file) as conn:
        await conn.execute(
            "CREATE TABLE jobs ("
            "id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, url TEXT NOT NULL,"
            " content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
            " template TEXT, template_analysis TEXT, key_phrases TEXT,"
            " validation_warning_sent INTEGER DEFAULT 0, template_detection_method TEXT,"
            " promise_gap TEXT, bot_message_id INTEGER,"
            " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        await conn.execute("PRAGMA user_version = 1")
        await conn.commit()

    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA table_info(jobs)")
        cols = {row[1] async for row in cur}
        cur2 = await conn.execute("PRAGMA user_version")
        version = (await cur2.fetchone())[0]

    assert "freestyle_prompt" in cols
    assert version == len(database._MIGRATIONS)


# ---------------------------------------------------------------------------
# markdown_cache CRUD + migration tests (issue #60)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_markdown_cache_insert_and_get_round_trip(temp_db) -> None:
    from src import database as db

    url = "https://example.com/article"
    content = "# Hello\n\nSome content."
    await db.insert_markdown_cache(url, content)
    row = await db.get_markdown_cache(url)
    assert row is not None
    assert row["url"] == url
    assert row["content"] == content
    assert row["fetched_at"] is not None


@pytest.mark.asyncio
async def test_markdown_cache_get_missing_returns_none(temp_db) -> None:
    from src import database as db

    assert await db.get_markdown_cache("https://example.com/not-there") is None


@pytest.mark.asyncio
async def test_markdown_cache_delete_existing_returns_true(temp_db) -> None:
    from src import database as db

    url = "https://example.com/del"
    await db.insert_markdown_cache(url, "content")
    deleted = await db.delete_markdown_cache(url)
    assert deleted is True
    assert await db.get_markdown_cache(url) is None


@pytest.mark.asyncio
async def test_markdown_cache_delete_missing_returns_false(temp_db) -> None:
    from src import database as db

    deleted = await db.delete_markdown_cache("https://example.com/gone")
    assert deleted is False


@pytest.mark.asyncio
async def test_markdown_cache_insert_is_idempotent(temp_db) -> None:
    """Second insert with same URL overwrites content (INSERT OR REPLACE)."""
    from src import database as db

    url = "https://example.com/idem"
    await db.insert_markdown_cache(url, "first")
    await db.insert_markdown_cache(url, "second")
    row = await db.get_markdown_cache(url)
    assert row is not None
    assert row["content"] == "second"


@pytest.mark.asyncio
async def test_markdown_cache_table_exists_after_init(tmp_path, monkeypatch) -> None:
    """markdown_cache table must exist on fresh init_db()."""
    db_file = str(tmp_path / "fresh.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()
    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='markdown_cache'"
        )
        row = await cur.fetchone()
    assert row is not None


@pytest.mark.asyncio
async def test_migration_v3_to_v4_creates_markdown_cache(tmp_path, monkeypatch) -> None:
    """A DB at user_version=3 must gain markdown_cache after running migrations."""
    db_file = str(tmp_path / "v3.db")
    # Create the tables that would exist at v3 (no markdown_cache yet).
    async with aiosqlite.connect(db_file) as conn:
        await conn.execute(
            "CREATE TABLE jobs ("
            "id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, url TEXT NOT NULL,"
            " content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',"
            " template TEXT, template_analysis TEXT, key_phrases TEXT,"
            " validation_warning_sent INTEGER DEFAULT 0, template_detection_method TEXT,"
            " promise_gap TEXT, bot_message_id INTEGER, freestyle_prompt TEXT,"
            " created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS chat_state ("
            "chat_id INTEGER PRIMARY KEY, mode TEXT NOT NULL, job_id TEXT NOT NULL,"
            " created_at TEXT NOT NULL, expires_at TEXT NOT NULL,"
            " CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle'))"
            ")"
        )
        await conn.execute("PRAGMA user_version = 3")
        await conn.commit()

    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    from src import database
    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='markdown_cache'"
        )
        row = await cur.fetchone()
        cur2 = await conn.execute("PRAGMA user_version")
        version = (await cur2.fetchone())[0]

    assert row is not None, "markdown_cache table must exist after v3→v4 migration"
    assert version == len(database._MIGRATIONS)

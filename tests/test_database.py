"""Unit tests for src/database.py helpers added in slice #7."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
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


async def _insert_job(
    path: str, job_id: str, chat_id: int, content_type: str, status: str, title: str = ""
) -> None:
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
async def test_add_document_output_dedups_singular_keeps_freestyle_history(temp_db):
    """Singular kinds upsert one row per (job, kind); freestyle accumulates (ADR-0029)."""
    from src import database as db

    await _insert_job(temp_db, "20260618_000000_DOC1", 1, "document", "done")
    job_id = "20260618_000000_DOC1"

    a = await db.add_document_output(job_id, "summary", "enriched/s1.md", "Structured summary")
    b = await db.add_document_output(job_id, "summary", "enriched/s2.md", "Structured summary")
    assert a["id"] == b["id"]  # same row reused, not duplicated
    assert b["gcs_key"] == "enriched/s2.md"  # upsert refreshed the key

    await db.add_document_output(job_id, "freestyle", "enriched/f1.md", "Freestyle")
    await db.add_document_output(job_id, "freestyle", "enriched/f2.md", "Freestyle")

    kinds = [r["kind"] for r in await db.list_document_outputs(job_id)]
    assert kinds.count("summary") == 1
    assert kinds.count("freestyle") == 2


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
    await db.update_job_status(
        job_id, "transcript_done", key_phrases=json.dumps(["stripe", "nextjs"])
    )
    job = await db.get_job(job_id)
    assert json.loads(job["key_phrases"]) == ["stripe", "nextjs"]


@pytest.mark.asyncio
async def test_set_prd_slot_status_auto(temp_db):
    from src import database as db

    job_id = await db.create_job(
        chat_id=1, url="https://youtube.com/watch?v=prd1", content_type="long"
    )
    await db.set_prd_slot_status(job_id, "auto", "generating")
    job = await db.get_job(job_id)
    assert job["prd_auto_status"] == "generating"
    assert job["prd_intent_status"] is None


@pytest.mark.asyncio
async def test_set_prd_slot_status_intent(temp_db):
    from src import database as db

    job_id = await db.create_job(
        chat_id=1, url="https://youtube.com/watch?v=prd2", content_type="long"
    )
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
        "template",
        "template_analysis",
        "key_phrases",
        "validation_warning_sent",
        "template_detection_method",
        "promise_gap",
        "bot_message_id",
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
async def test_get_tag_round_trip_and_chat_scoped(temp_db) -> None:
    """get_tag (used by attach/detach handlers) must find a tag only for its owner."""
    from src import database as db

    created = await db.create_tag(chat_id=1, name="skills", meaning="", color="#fff")
    found = await db.get_tag(1, created["id"])
    assert found is not None and found["name"] == "skills"
    assert await db.get_tag(2, created["id"]) is None  # wrong owner
    assert await db.get_tag(1, "nope") is None  # missing id


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


@pytest.mark.asyncio
async def test_create_repo_job(temp_db) -> None:
    """content_type='repo' must be accepted by the jobs CHECK constraint."""
    from src import database as db

    job_id = await db.create_job(
        chat_id=1, url="https://github.com/owner/repo", content_type="repo"
    )
    job = await db.get_job(job_id)
    assert job is not None
    assert job["content_type"] == "repo"


# ---------------------------------------------------------------------------
# users invite-gate status and awaiting_email chat state (#254).
# ---------------------------------------------------------------------------


async def _build_pre_invite_gate_db(path: str, *, status_exists: bool = False) -> None:
    """A DB pinned one version before users.email/status + awaiting_email."""
    from src import database

    target_version = len(database._MIGRATIONS) - 1
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, "
            "url TEXT NOT NULL, content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        status_col = (
            ", status TEXT NOT NULL DEFAULT 'pending' "
            "CHECK(status IN ('pending','approved','blocked'))"
            if status_exists
            else ""
        )
        await conn.execute(
            "CREATE TABLE users ("
            "tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT NOT NULL, "
            "last_name TEXT, photo_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            f"updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP{status_col})"
        )
        if status_exists:
            await conn.execute(
                "INSERT INTO users (tg_id, username, first_name, status) VALUES (?,?,?,?)",
                (111, "existing", "Existing", "pending"),
            )
        else:
            await conn.execute(
                "INSERT INTO users (tg_id, username, first_name) VALUES (?,?,?)",
                (111, "existing", "Existing"),
            )
        await conn.execute(
            "CREATE TABLE chat_state ("
            "chat_id INTEGER PRIMARY KEY, mode TEXT NOT NULL, job_id TEXT NOT NULL, "
            "created_at TEXT NOT NULL, expires_at TEXT NOT NULL, "
            "CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle')))"
        )
        await conn.execute(f"PRAGMA user_version = {target_version}")
        await conn.commit()


@pytest.mark.asyncio
async def test_invite_gate_migration_adds_columns_chat_state_and_is_idempotent(
    tmp_path, monkeypatch
) -> None:
    from src import database

    db_file = str(tmp_path / "pre_invite_gate.db")
    await _build_pre_invite_gate_db(db_file)
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)

    await database.init_db()
    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in await cur.fetchall()}
        assert {"email", "status"} <= cols

        cur = await conn.execute("SELECT status, email FROM users WHERE tg_id = 111")
        row = await cur.fetchone()
        assert row == ("approved", None)

        await conn.execute(
            "INSERT INTO chat_state (chat_id, mode, job_id, created_at, expires_at) "
            "VALUES (1, 'awaiting_email', 'J1', 'now', 'later')"
        )

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO users (tg_id, first_name, status) VALUES (999, 'Bad', 'other')"
            )

        cur = await conn.execute("PRAGMA user_version")
        assert (await cur.fetchone())[0] == len(database._MIGRATIONS)


@pytest.mark.asyncio
async def test_invite_gate_migration_backfills_when_status_column_preexists(
    tmp_path, monkeypatch
) -> None:
    """Crash-retry shape: status DDL exists but user_version has not advanced yet."""
    from src import database

    db_file = str(tmp_path / "pre_invite_gate_partial.db")
    await _build_pre_invite_gate_db(db_file, status_exists=True)
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", None)

    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("SELECT status FROM users WHERE tg_id = 111")
        assert await cur.fetchone() == ("approved",)


@pytest.mark.asyncio
async def test_user_status_truth_table_and_helpers(tmp_path, monkeypatch) -> None:
    from src import database

    db_file = str(tmp_path / "invite_gate_truth.db")
    await _build_pre_invite_gate_db(db_file)
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 222)

    await database.init_db()

    assert await database.get_user_status(999) == "pending"
    assert await database.get_user_status(111) == "approved"
    assert await database.get_user_status(222) == "approved"
    async with aiosqlite.connect(db_file) as conn:
        cur = await conn.execute("SELECT status FROM users WHERE tg_id = ?", (222,))
        assert await cur.fetchone() == ("approved",)

    await database.set_user_email(999, "pending@example.com")
    pending = await database.list_pending_users()
    assert [row["tg_id"] for row in pending] == [999]
    assert pending[0]["email"] == "pending@example.com"

    await database.set_user_status(999, "approved")
    assert await database.get_user_status(999) == "approved"
    assert await database.list_pending_users() == []


# ---------------------------------------------------------------------------
# telegram_delivery is a stored domain of {'off','on'} only (#231).
# 'retroactive' is a request-only action resolved at the API boundary.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_telegram_delivery_rejects_retroactive(temp_db) -> None:
    """'retroactive' is a request action, never a storable state — the setter rejects it."""
    from src import database as db

    job_id = await db.create_job(chat_id=1, url="documents/abc.pdf", content_type="document")
    with pytest.raises(ValueError):
        await db.set_job_telegram_delivery(job_id, "retroactive")


@pytest.mark.asyncio
async def test_set_telegram_delivery_accepts_off_and_on(temp_db) -> None:
    from src import database as db

    job_id = await db.create_job(chat_id=1, url="documents/abc.pdf", content_type="document")
    off = await db.set_job_telegram_delivery(job_id, "off")
    assert off["telegram_delivery"] == "off"
    on = await db.set_job_telegram_delivery(job_id, "on")
    assert on["telegram_delivery"] == "on"


async def _build_pre_v23_db(path: str, *, job_delivery: str) -> None:
    """A DB pinned one version before the telegram_delivery-tighten migration:
    jobs carries telegram_delivery with no CHECK (it was added by ALTER), plus a
    document_outputs child row to prove the FK-CASCADE survives the rebuild."""
    from src import database

    target_version = len(database._MIGRATIONS) - 2
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, "
            "url TEXT NOT NULL, content_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', "
            "telegram_delivery TEXT NOT NULL DEFAULT 'on', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            "CREATE TABLE document_outputs (id TEXT PRIMARY KEY, "
            "job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, "
            "kind TEXT NOT NULL, gcs_key TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, telegram_delivery) VALUES (?,?,?,?,?)",
            ("20260625_000000_DOC1", 1, "documents/abc.pdf", "document", job_delivery),
        )
        await conn.execute(
            "INSERT INTO document_outputs (id, job_id, kind, gcs_key) VALUES (?,?,?,?)",
            ("OUT1", "20260625_000000_DOC1", "summary", "enriched/s1.md"),
        )
        await conn.execute(f"PRAGMA user_version = {target_version}")
        await conn.commit()


@pytest.mark.asyncio
async def test_migration_tightens_telegram_delivery_and_preserves_children(
    tmp_path, monkeypatch
) -> None:
    """v22→v23 adds CHECK(telegram_delivery IN ('off','on')) without wiping FK children."""
    from src import database

    db_file = str(tmp_path / "pre_td.db")
    await _build_pre_v23_db(db_file, job_delivery="on")

    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    await database.init_db()

    async with aiosqlite.connect(db_file) as conn:
        await conn.execute("PRAGMA foreign_keys=ON")
        # FK-CASCADE child row survived the table rebuild.
        cur = await conn.execute("SELECT COUNT(*) FROM document_outputs")
        assert (await cur.fetchone())[0] == 1
        # The CHECK is now enforced: 'retroactive' is no longer storable.
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, telegram_delivery) VALUES (?,?,?,?,?)",
                ("20260625_000001_DOC2", 1, "documents/x.pdf", "document", "retroactive"),
            )
        # 'off'/'on' still accepted.
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, telegram_delivery) VALUES (?,?,?,?,?)",
            ("20260625_000002_DOC3", 1, "documents/y.pdf", "document", "off"),
        )
        cur2 = await conn.execute("PRAGMA user_version")
        assert (await cur2.fetchone())[0] == len(database._MIGRATIONS)


@pytest.mark.asyncio
async def test_migration_fails_loudly_on_stored_retroactive(tmp_path, monkeypatch) -> None:
    """A pre-existing stored 'retroactive' is a defect — the migration refuses to coerce it silently."""
    from src import database

    db_file = str(tmp_path / "pre_td_bad.db")
    await _build_pre_v23_db(db_file, job_delivery="retroactive")

    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    with pytest.raises(RuntimeError, match="retroactive"):
        await database.init_db()


@pytest.mark.asyncio
async def test_brain_links_view_roundtrip_and_normalizes_invalid_values(tmp_path, monkeypatch):
    from src import database

    db_path = tmp_path / "settings.db"
    monkeypatch.setattr(database.settings, "DB_PATH", str(db_path))
    await database.init_db()

    assert await database.get_brain_links_view(42) == {
        "sort": "last_seen",
        "order": "desc",
        "size": 25,
    }

    saved = await database.set_brain_links_view(42, sort="appearances", order="asc", size=100)
    assert saved == {"sort": "appearances", "order": "asc", "size": 100}
    assert await database.get_brain_links_view(42) == saved

    await database.set_user_setting(
        42, "brain_links_view", '{"sort":"bad","order":"bad","size":999}'
    )
    assert await database.get_brain_links_view(42) == {
        "sort": "last_seen",
        "order": "desc",
        "size": 25,
    }

    await database.set_user_setting(42, "brain_links_view", "{not-json")
    assert await database.get_brain_links_view(42) == {
        "sort": "last_seen",
        "order": "desc",
        "size": 25,
    }


# ---------------------------------------------------------------------------
# link_tags (#382) + tag icon (#386) + palette remap (#383)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_link_tags_attach_detach_round_trip(temp_db):
    from src import database as db

    async with aiosqlite.connect(temp_db) as conn:
        await conn.execute(
            """INSERT INTO links (id, url, source_job, last_seen_at, created_at, updated_at)
               VALUES ('l1', 'https://example.com', 'j1', 't', 't', 't')"""
        )
        await conn.commit()

    tag = await db.create_tag(chat_id=1, name="svg", meaning="vector art", color="#f87171", icon="Code2")
    assert tag["icon"] == "Code2"

    await db.attach_link_tag("l1", tag["id"])
    await db.attach_link_tag("l1", tag["id"])  # idempotent (INSERT OR IGNORE)
    tags = await db.list_link_tags("l1")
    assert [(t["name"], t["icon"]) for t in tags] == [("svg", "Code2")]

    assert await db.detach_link_tag("l1", tag["id"]) is True
    assert await db.detach_link_tag("l1", tag["id"]) is False  # already gone
    assert await db.list_link_tags("l1") == []


@pytest.mark.asyncio
async def test_update_tag_preserves_and_clears_icon(temp_db):
    from src import database as db

    tag = await db.create_tag(chat_id=1, name="ui", meaning="", color="#60a5fa", icon="Brain")
    ok = await db.update_tag(
        chat_id=1, tag_id=tag["id"], name="ui", meaning="interface", color="#60a5fa", icon="Brain"
    )
    assert ok
    stored = await db.get_tag(1, tag["id"])
    assert stored is not None and stored["icon"] == "Brain"

    await db.update_tag(chat_id=1, tag_id=tag["id"], name="ui", meaning="", color="#60a5fa", icon=None)
    stored = await db.get_tag(1, tag["id"])
    assert stored is not None and stored["icon"] is None


@pytest.mark.asyncio
async def test_banned_palette_colors_remap_on_migration(temp_db):
    """v29 remaps orange/yellow-band tag colors to the nearest allowed hue."""
    from src import database as db

    async with aiosqlite.connect(temp_db) as conn:
        await conn.execute(
            "INSERT INTO tags (id, chat_id, name, color) VALUES ('t_old', 2, 'legacy', '#eab308')"
        )
        await conn.execute("PRAGMA user_version = 28")
        await conn.commit()

    await db.init_db()  # re-runs migrations from v28

    stored = await db.get_tag(2, "t_old")
    assert stored is not None and stored["color"] == "#f87171"

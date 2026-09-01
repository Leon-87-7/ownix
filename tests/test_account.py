import asyncio
from pathlib import Path

import pytest

CHAT_ID = 424242


@pytest.fixture
def account_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A fresh file DB with SESSION_BACKEND=memory, seeded with one user who
    owns a job, a standalone Brain link, and Controls settings rows."""
    db_file = tmp_path / "account_test.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.config.settings.SESSION_BACKEND", "memory")

    from src import database

    async def _setup() -> None:
        await database.init_db()
        await database.upsert_user(tg_id=CHAT_ID, username="u", first_name="U", last_name=None, photo_url=None)
        await database.set_user_email(CHAT_ID, "u@example.com")
        await database.set_user_status(CHAT_ID, "approved")
        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, created_at, "
                "drive_url, transcript_drive_url) "
                "VALUES ('job_1', ?, 'https://example.com/a', 'article', 'done', '2026-01-01', "
                "'https://drive.google.com/file/d/enrich1/view', "
                "'https://drive.google.com/file/d/transcript1/view')",
                (CHAT_ID,),
            )
            # source_job points at a job that no longer exists (ADR-0046: a link
            # outlives the job that produced it) - exercises the standalone-link
            # cleanup pass, not the with_links=True pass off job_1.
            await conn.execute(
                "INSERT INTO links (id, chat_id, url, source_job, seen_count, last_seen_at, created_at, updated_at) "
                "VALUES ('link_1', ?, 'https://example.com/standalone', 'job_deleted_earlier', 1, '2026-01-01', '2026-01-01', '2026-01-01')",
                (CHAT_ID,),
            )
            await conn.commit()
        await database.create_tag(chat_id=CHAT_ID, name="t", meaning="", color="#8b5cf6", icon=None)
        await database.add_allowed_domain(CHAT_ID, "example.com")
        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO spaces (id, chat_id, name) VALUES ('space_1', ?, 'Space')",
                (CHAT_ID,),
            )
            await conn.execute(
                "INSERT INTO context_blobs (id, space_id, name, content) "
                "VALUES ('blob_1', 'space_1', 'Notes', 'hi')"
            )
            await conn.execute(
                "INSERT INTO google_oauth_states (state, chat_id, expires_at) "
                "VALUES ('state_1', ?, '2026-01-01')",
                (CHAT_ID,),
            )
            await conn.commit()

    asyncio.run(_setup())
    return database


def test_delete_account_removes_every_owned_row(account_db) -> None:
    from src.services.account import delete_account

    database = account_db
    asyncio.run(delete_account(CHAT_ID))

    assert asyncio.run(database.get_user(CHAT_ID)) is None
    assert asyncio.run(database._fetch_one("SELECT 1 FROM jobs WHERE chat_id = ?", (CHAT_ID,))) is None
    assert asyncio.run(database._fetch_one("SELECT 1 FROM links WHERE chat_id = ?", (CHAT_ID,))) is None
    assert asyncio.run(database.list_tags(CHAT_ID)) == []
    assert asyncio.run(database.list_allowed_domains(CHAT_ID)) == set()
    assert asyncio.run(database._fetch_one("SELECT 1 FROM spaces WHERE chat_id = ?", (CHAT_ID,))) is None
    # context_blobs has no chat_id of its own — cascades from the spaces delete (FK ON DELETE CASCADE).
    assert asyncio.run(database._fetch_one("SELECT 1 FROM context_blobs WHERE id = 'blob_1'")) is None
    assert (
        asyncio.run(database._fetch_one("SELECT 1 FROM google_oauth_states WHERE chat_id = ?", (CHAT_ID,)))
        is None
    )
    # The delete is recorded as a durable purge task even though nothing external was ever attached.
    row = asyncio.run(database._fetch_one("SELECT 1 FROM purge_tasks WHERE job_id = 'job_1'"))
    assert row is not None


def test_delete_account_purges_both_job_drive_docs(account_db) -> None:
    """ADR-0057: a job can carry two independently-tracked Drive links
    (drive_url = enrichment, transcript_drive_url = transcript). The bulk
    SELECT account deletion uses to build purge tasks must fetch both, or
    the transcript file silently never gets queued for purge."""
    from src.services.account import delete_account

    database = account_db
    asyncio.run(delete_account(CHAT_ID))

    pending = asyncio.run(database.list_pending_purge_tasks())
    assert set(pending[0]["task_payload"]["drive_file_ids"]) == {"enrich1", "transcript1"}


def test_delete_account_is_scoped_to_the_caller(account_db) -> None:
    """A second user's job must survive another user's account deletion."""
    from src.services.account import delete_account

    database = account_db

    async def _seed_other() -> None:
        await database.upsert_user(tg_id=999, username="v", first_name="V", last_name=None, photo_url=None)
        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, created_at) "
                "VALUES ('job_other', 999, 'https://example.com/b', 'article', 'done', '2026-01-01')"
            )
            await conn.commit()

    asyncio.run(_seed_other())
    asyncio.run(delete_account(CHAT_ID))

    assert asyncio.run(database.get_job("job_other")) is not None
    assert asyncio.run(database.get_user(999)) is not None


def test_delete_account_does_not_refetch_each_job_individually(account_db, monkeypatch) -> None:
    """The purge-task loop must build its payload from the initial bulk
    query, not re-fetch each job row with database.get_job() (an extra
    round trip per job that matters at "hundreds of jobs" scale)."""
    from src.services import account as account_module

    database = account_db
    calls: list[str] = []
    real_get_job = database.get_job

    async def spy_get_job(job_id: str):
        calls.append(job_id)
        return await real_get_job(job_id)

    monkeypatch.setattr(account_module.database, "get_job", spy_get_job)

    asyncio.run(account_module.delete_account(CHAT_ID))

    assert calls == []
    assert asyncio.run(database.get_user(CHAT_ID)) is None
    row = asyncio.run(database._fetch_one("SELECT 1 FROM purge_tasks WHERE job_id = 'job_1'"))
    assert row is not None

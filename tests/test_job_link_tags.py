"""Regression coverage for the job/link tag read-model unification."""

import asyncio

import pytest

from src import database
from src.api.jobs import _add_link_ids


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tag_db(tmp_path, monkeypatch):
    path = tmp_path / "job-link-tags.db"
    monkeypatch.setattr(database.settings, "DB_PATH", str(path))
    _run(database.init_db())
    return path


async def _seed(content_type: str, *, with_link: bool = True) -> tuple[dict, str]:
    job_id = f"job-{content_type}"
    url = "https://example.com/resource/?tracking=ignored#fragment"
    normalized_url = "https://example.com/resource"
    stored_content_type = "short" if content_type == "photo" else content_type
    async with database.connection() as conn:
        await conn.execute(
            "INSERT INTO jobs (id, chat_id, url, content_type, status) VALUES (?, 7, ?, ?, 'done')",
            (job_id, url, stored_content_type),
        )
        await conn.execute(
            "INSERT INTO tags (id, chat_id, name) VALUES ('tag-job', 7, 'Job tag')"
        )
        await conn.execute(
            "INSERT INTO tags (id, chat_id, name) VALUES ('tag-link', 7, 'Link tag')"
        )
        await conn.execute("INSERT INTO job_tags VALUES (?, 'tag-job')", (job_id,))
        if with_link:
            await conn.execute(
                """INSERT INTO links
                   (id, chat_id, url, source_job, last_seen_at, created_at, updated_at)
                   VALUES ('link-existing', 7, ?, 'unrelated-job', '', '', '')""",
                (normalized_url,),
            )
            await conn.execute("INSERT INTO link_tags VALUES ('link-existing', 'tag-link')")
        await conn.commit()
    return {"id": job_id, "url": url, "content_type": content_type}, normalized_url


@pytest.mark.parametrize("content_type", ["link", "article", "repo"])
def test_link_backed_jobs_resolve_by_url_and_sweep_without_removing_link_tags(
    tag_db, content_type
):
    item, _ = _run(_seed(content_type))

    _run(_add_link_ids([item], 7))

    assert item["link_id"] == "link-existing"
    assert _run(database.list_job_tags(item["id"])) == []
    assert {tag["id"] for tag in _run(database.list_link_tags("link-existing"))} == {
        "tag-job",
        "tag-link",
    }


@pytest.mark.parametrize("content_type", ["article", "repo"])
def test_not_yet_linked_jobs_keep_editable_job_tags_until_link_resolves(tag_db, content_type):
    item, normalized_url = _run(_seed(content_type, with_link=False))

    _run(_add_link_ids([item], 7))

    assert "link_id" not in item
    assert [tag["id"] for tag in _run(database.list_job_tags(item["id"]))] == ["tag-job"]

    async def add_cross_pipeline_link():
        async with database.connection() as conn:
            await conn.execute(
                """INSERT INTO links
                   (id, chat_id, url, source_job, last_seen_at, created_at, updated_at)
                   VALUES ('link-later', 7, ?, 'different-pipeline-job', '', '', '')""",
                (normalized_url,),
            )
            await conn.commit()

    _run(add_cross_pipeline_link())
    _run(_add_link_ids([item], 7))

    assert item["link_id"] == "link-later"
    assert _run(database.list_job_tags(item["id"])) == []
    assert [tag["id"] for tag in _run(database.list_link_tags("link-later"))] == ["tag-job"]


@pytest.mark.parametrize("content_type", ["short", "long", "photo", "document"])
def test_carrier_jobs_never_receive_link_ids_or_sweep_tags(tag_db, content_type):
    item, _ = _run(_seed(content_type))

    _run(_add_link_ids([item], 7))

    assert "link_id" not in item
    assert [tag["id"] for tag in _run(database.list_job_tags(item["id"]))] == ["tag-job"]
    assert [tag["id"] for tag in _run(database.list_link_tags("link-existing"))] == [
        "tag-link"
    ]


@pytest.mark.parametrize("content_type", ["article", "repo"])
def test_batch_effective_job_tags_unions_swept_link_tags(tag_db, content_type):
    """Once a link-backed job sweeps to link_tags, the feed's tag filter must
    still see both tags (its own + the link's) or it silently loses coverage
    on the exact content types builders tag most."""
    item, _ = _run(_seed(content_type))
    _run(_add_link_ids([item], 7))

    result = _run(database.batch_list_effective_job_tags([item]))

    assert {tag["id"] for tag in result[item["id"]]} == {"tag-job", "tag-link"}


@pytest.mark.parametrize("content_type", ["short", "long", "photo", "document"])
def test_batch_effective_job_tags_reads_job_tags_for_carrier_types(tag_db, content_type):
    item, _ = _run(_seed(content_type))
    _run(_add_link_ids([item], 7))

    result = _run(database.batch_list_effective_job_tags([item]))

    assert [tag["id"] for tag in result[item["id"]]] == ["tag-job"]


def test_add_link_ids_persists_the_resolved_link_id(tag_db):
    """The read path is the backfill: a job becomes SQL-joinable once listed.

    normalize_url() runs in Python, so the job->link key can't be derived in a
    query — storing what _add_link_ids already resolved is what lets the feed
    filter by tag past the client-mode cap.
    """
    item, _ = _run(_seed("article"))

    async def read_stored() -> str | None:
        async with database.connection() as conn:
            cur = await conn.execute("SELECT link_id FROM jobs WHERE id = ?", (item["id"],))
            row = await cur.fetchone()
            return row["link_id"]

    assert _run(read_stored()) is None
    _run(_add_link_ids([item], 7))
    assert _run(read_stored()) == "link-existing"


def test_tag_scope_where_matches_job_tags_and_link_tags(tag_db):
    """A tag narrows identically whether it sits on the job or on its link."""
    from src.api.jobs import _job_scope_where

    item, _ = _run(_seed("article"))
    _run(_add_link_ids([item], 7))  # sweeps tag-job onto the link, stores link_id

    async def ids_for(tag_ids: list[str]) -> list[str]:
        where, params = _run_where(tag_ids)
        async with database.connection() as conn:
            cur = await conn.execute(f"SELECT id FROM jobs WHERE {where}", params)
            return [row["id"] for row in await cur.fetchall()]

    def _run_where(tag_ids: list[str]):
        return _job_scope_where(7, None, None, None, tag_ids)

    # Both tags now live on the link; the job must still match either one.
    assert _run(ids_for(["tag-link"])) == [item["id"]]
    assert _run(ids_for(["tag-job"])) == [item["id"]]
    # OR semantics across a selection, and a miss stays a miss.
    assert _run(ids_for(["tag-link", "nope"])) == [item["id"]]
    assert _run(ids_for(["nope"])) == []


def test_count_jobs_by_tag_counts_each_job_once(tag_db):
    """Union job_tags with link_tags without double-counting a job per tag."""
    item, _ = _run(_seed("article"))
    _run(_add_link_ids([item], 7))

    counts = _run(database.count_jobs_by_tag(7))

    assert counts == {"tag-job": 1, "tag-link": 1}


def test_persist_job_link_ids_opens_no_write_when_already_current(tag_db, monkeypatch):
    """CodeRabbit (PR #626): the read path calls this on every list/adjacent
    request. Once a job's link_id is already correct, re-persisting it must
    not open a write transaction — a naive unconditional UPDATE+commit would
    contend with other writers on every single read, for nothing."""
    item, _ = _run(_seed("article"))
    _run(_add_link_ids([item], 7))  # first call: real write, sets link_id

    real_connection = database.connection
    call_count = 0

    def _counting_connection():
        nonlocal call_count
        call_count += 1
        return real_connection()

    monkeypatch.setattr(database, "connection", _counting_connection)
    _run(database.persist_job_link_ids({item["id"]: "link-existing"}))

    # Only the read (_fetch_in's SELECT) should open a connection -- an
    # unchanged mapping must not also open one for a write.
    assert call_count == 1


def test_backfill_pending_link_ids_lets_a_brand_new_job_join_tag_scoped_results(tag_db):
    """CodeRabbit (PR #626): tag-scoped SQL joins on jobs.link_id, which only
    the read path sets -- and only for jobs an *unfiltered* read has already
    seen. Without a backfill pass, a job created since the last unfiltered
    read is invisible to every tag-scoped query forever, since the very query
    that would surface it (and let it get backfilled) is the one excluding it."""
    from src.api.jobs import _backfill_pending_link_ids, _job_scope_where

    item, _ = _run(_seed("article"))  # never passed through _add_link_ids: link_id is NULL

    async def ids_for(tag_ids: list[str]) -> list[str]:
        where, params = _job_scope_where(7, None, None, None, tag_ids)
        async with database.connection() as conn:
            cur = await conn.execute(f"SELECT id FROM jobs WHERE {where}", params)
            return [row["id"] for row in await cur.fetchall()]

    # Before backfill: the job's own tag lives in job_tags, so it's still
    # found via that half of the OR -- seed a link-only tag scenario instead
    # by checking the job is invisible on the link's tag until link_id is set.
    assert _run(ids_for(["tag-link"])) == []

    _run(_backfill_pending_link_ids(7))

    assert _run(ids_for(["tag-link"])) == [item["id"]]


def test_migration_backfills_jobs_whose_url_only_matches_after_normalizing(tmp_path, monkeypatch):
    """The backfill must not stop at exact URL equality.

    Tag-filtered SQL matches ON link_id, so a job left NULL can never appear in
    the query that would heal it — it would be silently absent from tag results
    forever. Job URLs arrive with tracking params; links store the normalized
    form, so exact equality misses precisely the realistic rows.
    """
    path = tmp_path / "backfill.db"
    monkeypatch.setattr(database.settings, "DB_PATH", str(path))
    _run(database.init_db())

    async def seed_then_remigrate() -> str | None:
        async with database.connection() as conn:
            await conn.execute(
                "INSERT INTO jobs (id, chat_id, url, content_type, status, link_id) "
                "VALUES ('j-tracked', 7, ?, 'article', 'done', NULL)",
                ("https://example.com/post/?utm_source=tg#top",),
            )
            await conn.execute(
                """INSERT INTO links
                   (id, chat_id, url, source_job, last_seen_at, created_at, updated_at)
                   VALUES ('link-norm', 7, 'https://example.com/post', 'other', '', '', '')"""
            )
            await conn.commit()
            # Re-run the migration against the seeded rows.
            await database._migrate_jobs_link_id(conn)
            cur = await conn.execute("SELECT link_id FROM jobs WHERE id = 'j-tracked'")
            return (await cur.fetchone())["link_id"]

    assert _run(seed_then_remigrate()) == "link-norm"

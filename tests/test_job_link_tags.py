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

"""Newsletter digest processor / candidate-promotion regression tests.

Note (issue #609): the inbound-email receipt flow (`newsletter_subscriptions`,
`create_email_digest_receipt_job`, `email_webhook.receive_email_digest`) was
retired by the ADR-0060 migration to public-archive watches — those tests
moved to `tests/test_newsletter_watch.py`, which covers the new
`newsletter_watches` / `publications` schema this file's helpers now build
on. `src/api/email_webhook.py` itself is left in place (out of scope for this
slice) but its DB-backed helpers no longer have a table to read from; nothing
here exercises it. The `job_recovery` / stale-job-reaping tests below key
only on the `jobs.url LIKE 'email_digest:%'` sentinel, which is unaffected by
the schema change, so they are unchanged.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src import database
from src.api import newsletter_digest
from src.processors import email_digest
from src.services import job_recovery

pytestmark = pytest.mark.asyncio

_ISSUES = [
    {"slug": "issue-1", "title": "Issue 1", "url": "https://example.com/p/issue-1"},
]


async def _init_db(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "email_digest.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    await database.init_db()


async def _watch(name: str = "Signals", chat_id: int = 123, archive_url: str = "https://example.com") -> dict:
    return await database.create_newsletter_watch(
        chat_id=chat_id,
        name=name,
        archive_url=archive_url,
        feed_url=None,
        issue_path_prefix="/p/",
        fetched_title="Example",
        recent_issues=_ISSUES,
    )


async def test_generic_recovery_excludes_email_digest_receipts(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    enqueue = AsyncMock()
    monkeypatch.setattr(job_recovery.queue, "enqueue", enqueue)
    digest_job = await database.create_job(
        chat_id=123,
        url="email_digest:abc123",
        content_type="link",
        status="error",
    )
    normal_job = await database.create_job(
        chat_id=123,
        url="https://example.com/normal",
        content_type="short",
        status="error",
    )

    summary = await job_recovery.recovery_summary(123)
    retried = await job_recovery.retry_error(123)

    assert summary["error_jobs"] == 1
    assert retried["replaced"] == 1
    assert enqueue.await_count == 1
    assert (await database.get_job(digest_job))["status"] == "error"
    assert (await database.get_job(normal_job))["status"] == "cancelled"


async def test_stale_email_digest_job_reaped_without_false_notification(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    enqueue = AsyncMock()
    send_message = AsyncMock()
    monkeypatch.setattr(job_recovery.queue, "enqueue", enqueue)
    monkeypatch.setattr("src.telegram.sender.send_message", send_message)

    digest_job = await database.create_job(
        chat_id=123,
        url="email_digest:stale123",
        content_type="link",
        status="processing",
    )
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET updated_at = datetime('now', '-20 minutes') WHERE id = ?",
            (digest_job,),
        )
        await conn.commit()

    retried = await job_recovery.retry_error(123)

    # Reaped to 'error' (so the dedicated newsletter-digest retry can find it)...
    assert (await database.get_job(digest_job))["status"] == "error"
    assert retried["reaped"] == 1
    # ...but never claimed as generic error work, and never falsely told the user
    # it was "re-queued automatically" — it wasn't.
    assert retried["replaced"] == 0
    enqueue.assert_not_awaited()
    send_message.assert_not_awaited()


async def test_digest_run_extracts_candidates_from_issue_body(tmp_path, monkeypatch) -> None:
    """`run()` reads the issue body from `publication_issues.body_html` via
    the payload's `(publication_id, slug)` join — never from a per-job
    subject/html/text column, which the #609 migration drops."""
    await _init_db(tmp_path, monkeypatch)
    watch = await _watch()
    job_id = watch["delivery_job_id"]
    await database._execute_rowcount(
        "UPDATE publication_issues SET body_html = ? WHERE publication_id = ? AND slug = 'issue-1'",
        (
            '<a href="https://example.com/article?utm_source=x">Article</a>',
            watch["publication_id"],
        ),
    )
    monkeypatch.setattr(
        email_digest,
        "resolve_public_redirect_url",
        AsyncMock(return_value="https://example.com/article?utm_source=x"),
    )
    monkeypatch.setattr(email_digest, "fetch_public_html", AsyncMock(return_value=None))

    job = await database.get_job(job_id)
    await email_digest.run(job)

    candidates = await database.list_digest_candidates(watch["space_id"])
    assert len(candidates) == 1
    assert candidates[0]["url"] == "https://example.com/article?utm_source=x"
    assert (await database.get_job(job_id))["status"] == "done"


async def test_document_candidate_promotion_delegates_to_doc_parser(tmp_path, monkeypatch) -> None:
    await _init_db(tmp_path, monkeypatch)
    watch = await _watch()
    candidate_id = await database.insert_digest_candidate(
        space_id=watch["space_id"],
        url="https://example.com/report.pdf",
        canonical_url="https://example.com/report.pdf",
        title="Report",
    )
    job_id = await database.create_job(
        chat_id=123,
        url="documents/report.pdf",
        content_type="document",
    )
    upload_url = AsyncMock(return_value={"job_id": job_id, "status": "pending", "content_type": "document"})
    create_job = AsyncMock()
    monkeypatch.setattr(newsletter_digest, "upload_url", upload_url)
    monkeypatch.setattr(newsletter_digest, "create_job", create_job)
    request = SimpleNamespace(state=SimpleNamespace(user={"id": 123}))

    result = await newsletter_digest.promote_candidate(watch["id"], candidate_id, request)

    assert result["job_id"] == job_id
    upload_url.assert_awaited_once()
    create_job.assert_not_awaited()
    candidate = await database.get_digest_candidate(watch["space_id"], candidate_id)
    assert candidate["status"] == "promoted"
    assert candidate["job_id"] == job_id
    row = await database._fetch_one(
        "SELECT 1 FROM space_urls WHERE space_id = ? AND job_id = ?",
        (watch["space_id"], job_id),
    )
    assert row is not None


async def test_article_candidate_promotion_creates_a_job(tmp_path, monkeypatch) -> None:
    """Digest candidates are ordinary blog links pulled out of a newsletter
    issue, not URLs the reader has curated into their article-domain
    allowlist. promote_candidate must not require that allowlist membership
    just because the pipeline route it delegates to (`create_job`) does."""
    await _init_db(tmp_path, monkeypatch)
    enqueue = AsyncMock()
    monkeypatch.setattr("src.services.jobs.queue.enqueue", enqueue)
    watch = await _watch()
    candidate_id = await database.insert_digest_candidate(
        space_id=watch["space_id"],
        url="https://example.com/some-article",
        canonical_url="https://example.com/some-article",
        title="Some Article",
    )
    request = SimpleNamespace(state=SimpleNamespace(user={"id": 123}))

    result = await newsletter_digest.promote_candidate(watch["id"], candidate_id, request)

    assert result["job_id"]
    enqueue.assert_awaited_once()
    candidate = await database.get_digest_candidate(watch["space_id"], candidate_id)
    assert candidate["status"] == "promoted"
    assert candidate["job_id"] == result["job_id"]

"""Tests for the newsletter poll worker (ADR-0060, PLAN.md §3/§4, issue #610):
the scheduler selection query, the lease claim, the worker dispatch contract,
missing-deliveries fan-out, crash recovery, and failure backoff.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.services.jina import JinaFetchError, JinaOversizeError

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _public_urls(monkeypatch):
    """Default every URL to public so poll tests don't depend on real DNS.
    Tests that exercise the rejection path override this."""
    from src.processors import newsletter_poll

    async def _always_public(url: str) -> bool:
        return True

    monkeypatch.setattr(newsletter_poll, "is_public_url", _always_public)


async def _init_db(tmp_path, monkeypatch) -> "object":
    db_file = tmp_path / "newsletter_poll.db"
    monkeypatch.setattr("src.config.settings.DB_PATH", str(db_file))
    monkeypatch.setattr("src.database.settings.DB_PATH", str(db_file))
    from src import database

    await database.init_db()
    return database


async def _watch(database, *, chat_id: int = 1, archive_url: str = "https://x.example", **kw) -> dict:
    watch = await database.create_newsletter_watch(
        chat_id=chat_id,
        name=kw.pop("name", "Signals"),
        archive_url=archive_url,
        feed_url=kw.pop("feed_url", None),
        issue_path_prefix=kw.pop("issue_path_prefix", "/p/"),
        fetched_title=kw.pop("fetched_title", "X"),
        recent_issues=kw.pop("recent_issues", []),
    )
    # Backdate watched_from so issues discovered later in the same test (whose
    # first_seen_at is stamped "now") unambiguously satisfy `watched_from <
    # first_seen_at` — without this, a fast test can hit the exact
    # clock-precision collapse PLAN.md §6 calls out for the explicit
    # first-delivery path, but here for *ordinary* newly-discovered issues.
    await database._execute_rowcount(
        "UPDATE newsletter_watches SET watched_from = datetime('now', '-5 seconds') WHERE id = ?",
        (watch["id"],),
    )
    watch["watched_from"] = "backdated"
    return watch


_ROOT_HTML = (
    '<a href="/p/issue-new">Issue New</a>'
    '<a href="/p/issue-old">Issue Old</a>'
)

# A single-issue fixture for tests asserting "one fetch, one Gemini call" —
# `_ROOT_HTML` above carries two issues, which would legitimately cost two of
# each and defeat that assertion.
_SINGLE_ISSUE_ROOT_HTML = '<a href="/p/issue-new">Issue New</a>'


# ---------------------------------------------------------------------------
# Worker dispatch contract
# ---------------------------------------------------------------------------


async def test_newsletter_poll_is_rowless_and_dispatches_with_publication_id(monkeypatch) -> None:
    from src import database, worker
    from src.processors import newsletter_poll

    assert "newsletter_poll" in worker._ROWLESS_TASKS
    assert worker._TASK_HANDLERS["newsletter_poll"] is worker._handle_newsletter_poll

    run_mock = AsyncMock()
    monkeypatch.setattr(newsletter_poll, "run", run_mock)
    get_job = AsyncMock(side_effect=AssertionError("rowless task must not load a job"))
    monkeypatch.setattr(database, "get_job", get_job)

    await worker._dispatch({"task": "newsletter_poll", "job_id": "pub-123"})

    run_mock.assert_awaited_once_with("pub-123")
    get_job.assert_not_called()


# ---------------------------------------------------------------------------
# Scheduler selection query + lease claim
# ---------------------------------------------------------------------------


async def test_first_poll_claims_lease_on_null_columns(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)

    due_ids = await database.list_due_unleased_watched_publication_ids(limit=10)
    assert watch["publication_id"] in due_ids

    claimed = await database.claim_publication_poll_lease(watch["publication_id"])
    assert claimed is True

    pub = await database.get_publication(watch["publication_id"])
    assert pub["poll_lease_until"] is not None


async def test_lease_refuses_not_yet_due_publication(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database._execute_rowcount(
        "UPDATE publications SET next_poll_after = datetime('now', '+1 hour') WHERE id = ?",
        (watch["publication_id"],),
    )

    due_ids = await database.list_due_unleased_watched_publication_ids(limit=10)
    assert watch["publication_id"] not in due_ids

    claimed = await database.claim_publication_poll_lease(watch["publication_id"])
    assert claimed is False


async def test_lease_contention_between_two_workers(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)

    results = await asyncio.gather(
        database.claim_publication_poll_lease(watch["publication_id"]),
        database.claim_publication_poll_lease(watch["publication_id"]),
    )
    assert sorted(results) == [False, True]


async def test_unwatched_publication_not_selected(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.delete_newsletter_watch(watch_id=watch["id"], chat_id=watch["chat_id"])

    due_ids = await database.list_due_unleased_watched_publication_ids(limit=10)
    assert watch["publication_id"] not in due_ids


# ---------------------------------------------------------------------------
# run(): idempotency, backoff
# ---------------------------------------------------------------------------


async def test_run_no_op_when_lease_not_claimed(tmp_path, monkeypatch) -> None:
    """Replaying the same envelope after a successful run must not re-poll —
    the lease clause plus the not-yet-due `next_poll_after` clause together
    make this a no-op."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.record_publication_poll_success(watch["publication_id"])

    fetch_html = AsyncMock(side_effect=AssertionError("must not fetch when not due"))
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)

    await newsletter_poll.run(watch["publication_id"])

    fetch_html.assert_not_called()


async def test_run_success_sets_backoff_and_clears_lease(tmp_path, monkeypatch) -> None:
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    monkeypatch.setattr(newsletter_poll, "fetch_html", AsyncMock(return_value="<html></html>"))

    await newsletter_poll.run(watch["publication_id"])

    pub = await database.get_publication(watch["publication_id"])
    assert pub["poll_lease_until"] is None
    assert pub["last_successful_poll_at"] is not None
    assert pub["poll_failures"] == 0
    assert pub["next_poll_after"] is not None


async def test_run_failure_backs_off_and_clears_lease(tmp_path, monkeypatch) -> None:
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    monkeypatch.setattr(
        newsletter_poll, "fetch_html", AsyncMock(side_effect=JinaFetchError(500))
    )

    await newsletter_poll.run(watch["publication_id"])

    pub = await database.get_publication(watch["publication_id"])
    assert pub["poll_lease_until"] is None
    assert pub["poll_failures"] == 1

    first_next_poll = pub["next_poll_after"]

    # Backoff is computed from the streak *before* this failure (resolved call —
    # PLAN.md §4 step 6 leaves pre/post-increment open): one transient blip must
    # cost the normal 4h cadence, not double it. Schedule is 4h, 8h, 16h, 24h.
    assert await _hours_until_next_poll(database, watch["publication_id"]) == 4

    # A second failure must escalate the backoff further (not repeat the same delay).
    await database._execute_rowcount(
        "UPDATE publications SET next_poll_after = NULL WHERE id = ?",
        (watch["publication_id"],),
    )
    await newsletter_poll.run(watch["publication_id"])
    pub2 = await database.get_publication(watch["publication_id"])
    assert pub2["poll_failures"] == 2
    assert pub2["next_poll_after"] != first_next_poll
    assert await _hours_until_next_poll(database, watch["publication_id"]) == 8


async def _hours_until_next_poll(database, publication_id: str) -> int:
    """Whole hours between now and the publication's `next_poll_after`, rounded
    to the nearest hour so the few milliseconds the poll itself takes don't
    turn an exact 4h into 3."""
    row = await database._fetch_one(
        """SELECT CAST(
                 ROUND((julianday(next_poll_after) - julianday('now')) * 24
             ) AS INTEGER) AS hours
             FROM publications WHERE id = ?""",
        (publication_id,),
    )
    return row["hours"]


# ---------------------------------------------------------------------------
# Fan-out: N jobs, 1 fetch, 1 Gemini call; oldest-first ordering
# ---------------------------------------------------------------------------


async def test_multi_watcher_fan_out_one_fetch_one_gemini_call(tmp_path, monkeypatch) -> None:
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch_a = await _watch(database, chat_id=1, archive_url="https://shared.example")
    watch_b = await _watch(database, chat_id=2, archive_url="https://shared.example")
    assert watch_a["publication_id"] == watch_b["publication_id"]

    fetch_html = AsyncMock(side_effect=[_SINGLE_ISSUE_ROOT_HTML, "<p>issue body text</p>"])
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)
    generate = AsyncMock(return_value="Editorial context.")
    monkeypatch.setattr(newsletter_poll.gemini, "generate", generate)
    enqueue = AsyncMock()
    monkeypatch.setattr(newsletter_poll.queue, "enqueue", enqueue)

    await newsletter_poll.run(watch_a["publication_id"])

    assert fetch_html.await_count == 2  # 1 root/feed fetch + 1 issue fetch (shared by both watchers)
    generate.assert_awaited_once()
    assert enqueue.await_count == 2  # N jobs across N watchers

    payload_a = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch_a["id"],),
    )
    payload_b = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch_b["id"],),
    )
    assert payload_a["context_md"] == "Editorial context."
    assert payload_b["context_md"] == "Editorial context."


async def test_issue_ordering_oldest_first_with_missing_published_at(tmp_path, monkeypatch) -> None:
    """`published_at ASC NULLS LAST, source_order DESC, first_seen_at ASC` —
    the DESC on source_order reverses the feed/archive's newest-first listing
    even when published_at is entirely missing."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    monkeypatch.setattr(newsletter_poll, "fetch_html", AsyncMock(return_value=_ROOT_HTML))

    await database.insert_publication_issues(
        watch["publication_id"],
        newsletter_poll._extract_issue_links(_ROOT_HTML, "https://x.example", "/p/"),
    )
    outstanding = await database.list_outstanding_newsletter_deliveries(watch["publication_id"])
    slugs_in_order = [row["slug"] for row in outstanding]
    assert slugs_in_order == ["issue-old", "issue-new"]


async def test_issue_ordering_prefers_published_at_over_source_order(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [
            {"slug": "issue-new", "url": "https://x.example/p/issue-new", "title": "New"},
            {"slug": "issue-old", "url": "https://x.example/p/issue-old", "title": "Old"},
        ],
    )
    # A malformed/parsed published_at on the newest (source_order 0) issue makes
    # it sort before the one with no published_at at all.
    await database._execute_rowcount(
        "UPDATE publication_issues SET published_at = '2020-01-01' "
        "WHERE publication_id = ? AND slug = 'issue-new'",
        (watch["publication_id"],),
    )

    outstanding = await database.list_outstanding_newsletter_deliveries(watch["publication_id"])
    slugs_in_order = [row["slug"] for row in outstanding]
    assert slugs_in_order == ["issue-new", "issue-old"]


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------


async def test_crash_recovery_issue_inserted_but_fan_out_never_ran(tmp_path, monkeypatch) -> None:
    """A prior run's `INSERT OR IGNORE` into publication_issues succeeded but
    crashed before fan-out — the *next* poll must still deliver it, because
    outstanding work is computed from ALL issues, not "just inserted" ones."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "issue-new", "url": "https://x.example/p/issue-new", "title": "New"}],
    )
    # No payload row exists yet for this issue — simulating the crash gap.
    monkeypatch.setattr(newsletter_poll, "fetch_html", AsyncMock(return_value="<p>body</p>"))
    monkeypatch.setattr(newsletter_poll.gemini, "generate", AsyncMock(return_value="ctx"))
    enqueue = AsyncMock()
    monkeypatch.setattr(newsletter_poll.queue, "enqueue", enqueue)

    await newsletter_poll.run(watch["publication_id"])

    payload = await database._fetch_one(
        "SELECT job_id FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch["id"],),
    )
    assert payload is not None
    enqueue.assert_awaited_once()


async def test_crash_recovery_after_outage_longer_than_any_recency_window(tmp_path, monkeypatch) -> None:
    """No recency window: an issue first seen long ago (simulating an outage
    far exceeding any bounded lookback) is still delivered."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    # The watcher has been watching since well before the outage window...
    await database._execute_rowcount(
        "UPDATE newsletter_watches SET watched_from = datetime('now', '-100 days') WHERE id = ?",
        (watch["id"],),
    )
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "ancient-issue", "url": "https://x.example/p/ancient-issue", "title": "Old"}],
    )
    # ...and the issue was first seen (inserted) 90 days ago but never fanned
    # out — well past any bounded "last N days" lookback a recency window
    # would apply.
    await database._execute_rowcount(
        "UPDATE publication_issues SET first_seen_at = datetime('now', '-90 days') "
        "WHERE publication_id = ? AND slug = 'ancient-issue'",
        (watch["publication_id"],),
    )
    monkeypatch.setattr(newsletter_poll, "fetch_html", AsyncMock(return_value="<p>body</p>"))
    monkeypatch.setattr(newsletter_poll.gemini, "generate", AsyncMock(return_value="ctx"))
    monkeypatch.setattr(newsletter_poll.queue, "enqueue", AsyncMock())

    await newsletter_poll.run(watch["publication_id"])

    payload = await database._fetch_one(
        "SELECT job_id FROM email_digest_payloads WHERE watch_id = ? AND slug = 'ancient-issue'",
        (watch["id"],),
    )
    assert payload is not None


async def test_stale_pending_payload_is_reenqueued(tmp_path, monkeypatch) -> None:
    """A job+payload row that was committed but never enqueued (crash between
    the two) must be re-enqueued by the next poll — not re-created."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "issue-stuck", "url": "https://x.example/p/issue-stuck", "title": "Stuck"}],
    )
    job_id = await database.create_newsletter_delivery(
        watch_id=watch["id"],
        chat_id=watch["chat_id"],
        name=watch["name"],
        publication_id=watch["publication_id"],
        slug="issue-stuck",
        context_md=None,
    )
    assert job_id is not None
    await database._execute_rowcount(
        "UPDATE jobs SET updated_at = datetime('now', '-1 hour') WHERE id = ?", (job_id,)
    )

    monkeypatch.setattr(newsletter_poll, "fetch_html", AsyncMock(return_value="<html></html>"))
    create_delivery = AsyncMock(side_effect=AssertionError("must not re-create, only re-enqueue"))
    monkeypatch.setattr(newsletter_poll.database, "create_newsletter_delivery", create_delivery)
    enqueue = AsyncMock()
    monkeypatch.setattr(newsletter_poll.queue, "enqueue", enqueue)

    await newsletter_poll.run(watch["publication_id"])

    enqueue.assert_awaited_once()
    assert enqueue.await_args.args[0]["job_id"] == job_id
    create_delivery.assert_not_called()


# ---------------------------------------------------------------------------
# Duplicate fan-out: no orphan job on UNIQUE(watch_id, slug) violation
# ---------------------------------------------------------------------------


async def test_duplicate_fan_out_rolls_back_job_and_payload(tmp_path, monkeypatch) -> None:
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "issue-x", "url": "https://x.example/p/issue-x", "title": "X"}],
    )
    first_job_id = await database.create_newsletter_delivery(
        watch_id=watch["id"],
        chat_id=watch["chat_id"],
        name=watch["name"],
        publication_id=watch["publication_id"],
        slug="issue-x",
        context_md=None,
    )
    assert first_job_id is not None

    second_job_id = await database.create_newsletter_delivery(
        watch_id=watch["id"],
        chat_id=watch["chat_id"],
        name=watch["name"],
        publication_id=watch["publication_id"],
        slug="issue-x",
        context_md=None,
    )
    assert second_job_id is None

    # The rolled-back attempt's job row must not have survived (no orphan job).
    jobs = await database._fetch_all("SELECT id FROM jobs WHERE url LIKE 'email_digest:%'")
    assert len(jobs) == 1
    assert jobs[0]["id"] == first_job_id


# ---------------------------------------------------------------------------
# Gemini failure: context_md NULL, no per-watcher fallback
# ---------------------------------------------------------------------------


async def test_gemini_failure_produces_null_context_with_no_per_watcher_fallback(
    tmp_path, monkeypatch
) -> None:
    from src.processors import newsletter_poll
    from src.services.gemini import GeminiUnavailableError

    database = await _init_db(tmp_path, monkeypatch)
    watch_a = await _watch(database, chat_id=1, archive_url="https://gem.example")
    watch_b = await _watch(database, chat_id=2, archive_url="https://gem.example")

    fetch_html = AsyncMock(side_effect=[_SINGLE_ISSUE_ROOT_HTML, "<p>issue body text</p>"])
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)
    generate = AsyncMock(side_effect=GeminiUnavailableError("down"))
    monkeypatch.setattr(newsletter_poll.gemini, "generate", generate)
    monkeypatch.setattr(newsletter_poll.queue, "enqueue", AsyncMock())

    await newsletter_poll.run(watch_a["publication_id"])

    generate.assert_awaited_once()  # still just one attempt, not one per watcher
    payload_a = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch_a["id"],),
    )
    payload_b = await database._fetch_one(
        "SELECT context_md FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch_b["id"],),
    )
    assert payload_a["context_md"] is None
    assert payload_b["context_md"] is None


async def test_oversized_issue_fetch_marked_terminal_without_aborting_run(
    tmp_path, monkeypatch
) -> None:
    """An oversized issue fetch is marked `skip_reason = 'oversize'` and
    treated as terminal (issue #611); the run itself still completes as a
    success and continues with the rest of the run."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    fetch_html = AsyncMock(
        side_effect=[_SINGLE_ISSUE_ROOT_HTML, JinaOversizeError("https://x.example/p/issue-new")]
    )
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)
    generate = AsyncMock(side_effect=AssertionError("must not generate context for a skipped issue"))
    monkeypatch.setattr(newsletter_poll.gemini, "generate", generate)

    await newsletter_poll.run(watch["publication_id"])

    payload = await database._fetch_one(
        "SELECT job_id FROM email_digest_payloads WHERE watch_id = ? AND slug = 'issue-new'",
        (watch["id"],),
    )
    assert payload is None
    issue = await database.get_publication_issue(watch["publication_id"], "issue-new")
    assert issue["skip_reason"] == "oversize"
    pub = await database.get_publication(watch["publication_id"])
    assert pub["poll_failures"] == 0  # a per-issue skip is not a run failure


async def test_extract_issue_links_ignores_cross_origin_matches(tmp_path, monkeypatch) -> None:
    """Council review, blocker. A publisher page can carry a link whose *path*
    matches the learned prefix but whose host is unrelated. Without a
    same-origin check it is persisted as an issue and later fetched through
    the Jina proxy, and its content lands in a watcher's Space."""
    from src.processors import newsletter_poll

    html = (
        '<a href="/p/real-issue">Real</a>'
        '<a href="http://169.254.169.254/p/metadata">Link-local</a>'
        '<a href="https://evil.example/p/planted">Other host</a>'
    )
    issues = newsletter_poll._extract_issue_links(html, "https://x.example", "/p/")

    assert [i["slug"] for i in issues] == ["real-issue"]


async def test_extract_issue_links_ignores_same_host_scheme_downgrade(
    tmp_path, monkeypatch
) -> None:
    """A same-host link that downgrades http://<->https:// is a different
    origin and must not be treated as matching the base URL's scheme."""
    from src.processors import newsletter_poll

    html = (
        '<a href="https://x.example/p/real-issue">Real</a>'
        '<a href="http://x.example/p/downgraded">Downgraded</a>'
    )
    issues = newsletter_poll._extract_issue_links(html, "https://x.example", "/p/")

    assert [i["slug"] for i in issues] == ["real-issue"]


async def test_poll_refuses_a_non_public_publication_url(tmp_path, monkeypatch) -> None:
    """Council review, blocker. The resolver validates once at watch creation;
    this fetch then recurs every 4h forever, unattended, with no probe cap and
    no user to rate-limit — so it must re-check before every proxy call."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    fetch_html = AsyncMock(side_effect=AssertionError("must not fetch a non-public URL"))
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)
    monkeypatch.setattr(newsletter_poll, "is_public_url", AsyncMock(return_value=False))

    await newsletter_poll.run(watch["publication_id"])

    fetch_html.assert_not_called()
    pub = await database.get_publication(watch["publication_id"])
    assert pub["poll_failures"] == 1  # recorded as a run failure, lease released
    assert pub["poll_lease_until"] is None


async def test_fan_out_marks_a_non_public_issue_url_terminally_skipped(
    tmp_path, monkeypatch
) -> None:
    """A stored issue URL that no longer resolves publicly is skipped
    terminally rather than retried through the proxy every four hours."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "issue-x", "url": "https://x.example/p/issue-x", "title": "X"}],
    )
    monkeypatch.setattr(newsletter_poll, "is_public_url", AsyncMock(return_value=False))
    fetch_html = AsyncMock(side_effect=AssertionError("must not fetch a non-public URL"))
    monkeypatch.setattr(newsletter_poll, "fetch_html", fetch_html)

    await newsletter_poll._fan_out_issue(watch["publication_id"], "issue-x", [])

    fetch_html.assert_not_called()
    issue = await database.get_publication_issue(watch["publication_id"], "issue-x")
    assert issue["skip_reason"] == "not_public"


async def test_oversized_issue_stops_being_selected_as_outstanding_work(
    tmp_path, monkeypatch
) -> None:
    """A `skip_reason` issue must not be re-fetched/re-attempted on the next
    poll — `list_outstanding_newsletter_deliveries` already filters it out."""
    from src.processors import newsletter_poll

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": "issue-big", "url": "https://x.example/p/issue-big", "title": "Big"}],
    )
    await database.mark_publication_issue_oversize(watch["publication_id"], "issue-big")

    outstanding = await database.list_outstanding_newsletter_deliveries(watch["publication_id"])
    assert outstanding == []


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


async def test_scheduler_enqueues_due_publications(tmp_path, monkeypatch) -> None:
    from src import main

    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    enqueue = AsyncMock()
    monkeypatch.setattr(main.queue, "enqueue", enqueue)

    await main._enqueue_due_newsletter_polls()

    enqueue.assert_awaited_once_with({"task": "newsletter_poll", "job_id": watch["publication_id"]})


async def test_scheduler_swallows_scan_errors(tmp_path, monkeypatch) -> None:
    from src import main

    await _init_db(tmp_path, monkeypatch)
    monkeypatch.setattr(
        main.database,
        "list_due_unleased_watched_publication_ids",
        AsyncMock(side_effect=RuntimeError("db down")),
    )
    enqueue = AsyncMock()
    monkeypatch.setattr(main.queue, "enqueue", enqueue)

    await main._enqueue_due_newsletter_polls()  # must not raise

    enqueue.assert_not_awaited()


# ---------------------------------------------------------------------------
# body_html reclamation (issue #611, PLAN.md §1)
# ---------------------------------------------------------------------------


async def _seeded_issue_with_body(database, watch, *, slug: str = "issue-a") -> None:
    """Give the publication one issue carrying a stored body, discovered after
    the watch's backdated `watched_from` so it counts as a live delivery."""
    await database.insert_publication_issues(
        watch["publication_id"],
        [{"slug": slug, "url": f"https://x.example/p/{slug}", "title": "A"}],
    )
    await database.set_publication_issue_body(watch["publication_id"], slug, "<p>body</p>")


async def _body_of(database, publication_id: str, slug: str) -> str | None:
    issue = await database.get_publication_issue(publication_id, slug)
    return issue["body_html"]


async def test_body_html_not_cleared_while_a_live_watch_lacks_a_payload_row(
    tmp_path, monkeypatch
) -> None:
    """Half 1 of the predicate. Two watchers, only one served: the body must
    survive for the watcher whose payload row does not exist yet."""
    database = await _init_db(tmp_path, monkeypatch)
    served = await _watch(database, chat_id=1)
    unserved = await _watch(database, chat_id=2)
    assert served["publication_id"] == unserved["publication_id"]
    await _seeded_issue_with_body(database, served)

    job_id = await database.create_newsletter_delivery(
        watch_id=served["id"],
        chat_id=1,
        name="Signals",
        publication_id=served["publication_id"],
        slug="issue-a",
        context_md=None,
    )
    await database.update_job_status(job_id, "done")

    # Half 2 is satisfied (the only existing payload's job is done); half 1 is
    # not, because `unserved` still has no payload row. Both are required.
    assert await database.reclaim_publication_issue_bodies(served["publication_id"]) == 0
    assert await _body_of(database, served["publication_id"], "issue-a") == "<p>body</p>"


async def test_body_html_not_cleared_when_no_payload_rows_exist_at_all(
    tmp_path, monkeypatch
) -> None:
    """The crash case: body stored, then the run died before creating any
    payload row. Half 2 passes vacuously over zero rows, so half 1 is the only
    thing standing between this issue and a body cleared out from under a
    delivery that was never made."""
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await _seeded_issue_with_body(database, watch)

    payloads = await database._fetch_dicts(
        "SELECT job_id FROM email_digest_payloads WHERE slug = 'issue-a'", ()
    )
    assert payloads == []

    assert await database.reclaim_publication_issue_bodies(watch["publication_id"]) == 0
    assert await _body_of(database, watch["publication_id"], "issue-a") == "<p>body</p>"


async def test_body_html_survives_an_errored_digest_and_it_stays_retryable(
    tmp_path, monkeypatch
) -> None:
    """An `error` job is not terminal — clearing its body would make the digest
    permanently unretryable, the failure mode PLAN.md §1 refuses to accept."""
    database = await _init_db(tmp_path, monkeypatch)
    watch = await _watch(database)
    await _seeded_issue_with_body(database, watch)

    job_id = await database.create_newsletter_delivery(
        watch_id=watch["id"],
        chat_id=1,
        name="Signals",
        publication_id=watch["publication_id"],
        slug="issue-a",
        context_md=None,
    )
    await database.update_job_status(job_id, "error", error_msg="boom")

    assert await database.reclaim_publication_issue_bodies(watch["publication_id"]) == 0
    assert await _body_of(database, watch["publication_id"], "issue-a") == "<p>body</p>"
    # Still retryable afterwards — the retry path can find it and its body.
    retryable = await database.latest_retryable_email_digest_job(watch["id"])
    assert retryable is not None and retryable["id"] == job_id


async def test_body_html_cleared_once_every_live_delivery_is_terminal(
    tmp_path, monkeypatch
) -> None:
    """Both halves satisfied: every live watch has a payload row, and every one
    of those belongs to a `done` or `cancelled` job."""
    database = await _init_db(tmp_path, monkeypatch)
    first = await _watch(database, chat_id=1)
    second = await _watch(database, chat_id=2)
    await _seeded_issue_with_body(database, first)

    done_job = await database.create_newsletter_delivery(
        watch_id=first["id"],
        chat_id=1,
        name="Signals",
        publication_id=first["publication_id"],
        slug="issue-a",
        context_md=None,
    )
    cancelled_job = await database.create_newsletter_delivery(
        watch_id=second["id"],
        chat_id=2,
        name="Signals",
        publication_id=second["publication_id"],
        slug="issue-a",
        context_md=None,
    )
    await database.update_job_status(done_job, "done")
    await database.update_job_status(cancelled_job, "cancelled")

    assert await database.reclaim_publication_issue_bodies(first["publication_id"]) == 1
    assert await _body_of(database, first["publication_id"], "issue-a") is None

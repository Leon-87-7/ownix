"""Newsletter watches, publications, issue polling and digest candidates.
"""

from __future__ import annotations


import aiosqlite

from src.db import core
from src.db.core import (
    log,
    _execute_rowcount,
    _fetch_all,
    _fetch_dicts,
    _fetch_one,
    generate_id,
)

# ---------------------------------------------------------------------------
# Newsletter watches / publications (ADR-0060, PLAN.md §1/§5/§6, issue #609)
# ---------------------------------------------------------------------------

# How long a publication's scraped metadata (feed_url / issue_path_prefix /
# fetched_title) is left alone after a resolve before a later resolve may
# replace an already-populated value. A *missing* value is always filled
# regardless of this window; the cooldown only guards replacement of an
# existing one, so two concurrent "add this newsletter" requests can't
# ping-pong its metadata back and forth (PLAN.md §8).
_PUBLICATION_METADATA_COOLDOWN_SECONDS = 300

_RECONCILE_PUBLICATION_METADATA_SQL = """
    UPDATE publications
       SET feed_url = CASE
               WHEN :feed_url IS NOT NULL
                    AND (last_resolved_at IS NULL
                         OR last_resolved_at < datetime('now', :cooldown))
                 THEN :feed_url
               ELSE COALESCE(feed_url, :feed_url)
           END,
           issue_path_prefix = CASE
               WHEN :issue_path_prefix IS NOT NULL
                    AND (last_resolved_at IS NULL
                         OR last_resolved_at < datetime('now', :cooldown))
                 THEN :issue_path_prefix
               ELSE COALESCE(issue_path_prefix, :issue_path_prefix)
           END,
           fetched_title = CASE
               WHEN :fetched_title IS NOT NULL
                    AND (last_resolved_at IS NULL
                         OR last_resolved_at < datetime('now', :cooldown))
                 THEN :fetched_title
               ELSE COALESCE(fetched_title, :fetched_title)
           END,
           last_resolved_at = CASE
               WHEN last_resolved_at IS NULL
                    OR last_resolved_at < datetime('now', :cooldown)
                 THEN CURRENT_TIMESTAMP
               ELSE last_resolved_at
           END
     WHERE archive_url = :archive_url
"""


async def create_newsletter_watch(
    *,
    chat_id: int,
    name: str,
    archive_url: str,
    feed_url: str | None,
    issue_path_prefix: str,
    fetched_title: str,
    recent_issues: list[dict],
) -> dict:
    """Create-or-reuse the publication, seed its issues, and insert the watch
    with its explicit first delivery — all in one transaction (PLAN.md §6/§8).

    Two users adding the same `archive_url` concurrently race on its UNIQUE
    constraint; `INSERT OR IGNORE` plus a follow-up `SELECT` inside the same
    transaction collapses that race to one row. Publication metadata is then
    reconciled (missing fields filled, existing ones replaced only past the
    cooldown) rather than frozen or blindly overwritten.

    `recent_issues` must be newest-first — `[{"slug", "title", "url"}, ...]`,
    index 0 = newest — matching `source_order`'s contract (PLAN.md §1). The
    newest issue with no `skip_reason` is delivered immediately as an
    explicit `(watch_id, slug)` job/payload, the same skip-aware pick the
    poll worker uses, rather than relying on `watched_from` — both
    timestamps land in this same transaction, so a `watched_from <
    first_seen_at` comparison could collapse at clock precision.

    Returns the created watch with an added `delivery_job_id` key (`None` if
    the publication currently has no eligible issue to deliver).
    """
    publication_id = generate_id()
    watch_id = generate_id()
    space_id = generate_id()
    job_id = generate_id()
    cooldown = f"-{_PUBLICATION_METADATA_COOLDOWN_SECONDS} seconds"

    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(
                """INSERT OR IGNORE INTO publications
                   (id, archive_url, feed_url, issue_path_prefix, fetched_title,
                    last_resolved_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    publication_id,
                    archive_url,
                    feed_url,
                    issue_path_prefix or None,
                    fetched_title or None,
                ),
            )
            await conn.execute(
                _RECONCILE_PUBLICATION_METADATA_SQL,
                {
                    "feed_url": feed_url,
                    "issue_path_prefix": issue_path_prefix or None,
                    "fetched_title": fetched_title or None,
                    "cooldown": cooldown,
                    "archive_url": archive_url,
                },
            )
            pub_cur = await conn.execute(
                "SELECT id FROM publications WHERE archive_url = ?", (archive_url,)
            )
            pub_row = await pub_cur.fetchone()
            resolved_publication_id: str = pub_row["id"]

            for index, issue in enumerate(recent_issues):
                await conn.execute(
                    """INSERT OR IGNORE INTO publication_issues
                       (publication_id, slug, url, title, source_order, first_seen_at)
                       VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        resolved_publication_id,
                        issue["slug"],
                        issue["url"],
                        issue.get("title"),
                        index,
                    ),
                )

            await conn.execute(
                "INSERT INTO spaces (id, chat_id, name, color, icon) VALUES (?, ?, ?, ?, ?)",
                (space_id, chat_id, name, "#6366f1", "newspaper"),
            )
            await conn.execute(
                """INSERT INTO newsletter_watches
                   (id, chat_id, publication_id, space_id, name, watched_from)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (watch_id, chat_id, resolved_publication_id, space_id, name),
            )

            # Same skip-aware pick the poll worker uses: source_order 0 is the
            # newest issue in the fetched batch, so ASC + skip_reason IS NULL
            # walks newest-to-oldest until it finds one still eligible.
            issue_cur = await conn.execute(
                """SELECT slug FROM publication_issues
                    WHERE publication_id = ? AND skip_reason IS NULL
                    ORDER BY source_order ASC
                    LIMIT 1""",
                (resolved_publication_id,),
            )
            issue_row = await issue_cur.fetchone()

            delivery_job_id: str | None = None
            if issue_row is not None:
                delivery_job_id = job_id
                await conn.execute(
                    """INSERT INTO jobs (id, chat_id, url, content_type, status, title)
                       VALUES (?, ?, ?, 'link', 'pending', ?)""",
                    (
                        job_id,
                        chat_id,
                        f"email_digest:{watch_id}:{issue_row['slug']}",
                        f"Newsletter digest: {name}".strip()[:500],
                    ),
                )
                await conn.execute(
                    """INSERT INTO email_digest_payloads
                       (job_id, watch_id, publication_id, slug)
                       VALUES (?, ?, ?, ?)""",
                    (job_id, watch_id, resolved_publication_id, issue_row["slug"]),
                )

            watch_cur = await conn.execute(
                """SELECT nw.id, nw.chat_id, nw.publication_id, nw.space_id, nw.name,
                          nw.watched_from, nw.created_at,
                          p.archive_url, p.feed_url, p.fetched_title
                     FROM newsletter_watches nw
                     JOIN publications p ON p.id = nw.publication_id
                    WHERE nw.id = ?""",
                (watch_id,),
            )
            watch_row = await watch_cur.fetchone()
            await conn.commit()
            watch = dict(watch_row)  # type: ignore[arg-type]
            watch["delivery_job_id"] = delivery_job_id
            watch["error_count"] = 0
            watch["pending_count"] = 0
            watch["promoting_count"] = 0
            watch["promoted_count"] = 0
            watch["dismissed_count"] = 0
            watch["candidate_count"] = 0
            return watch
        except Exception:
            await conn.rollback()
            raise


async def list_newsletter_watches(chat_id: int) -> list[dict]:
    return await _fetch_dicts(
        """SELECT nw.id, nw.chat_id, nw.publication_id, nw.space_id, nw.name,
                  nw.watched_from, nw.created_at,
                  p.archive_url, p.feed_url, p.fetched_title,
                  COALESCE(SUM(CASE WHEN dc.status = 'pending' THEN 1 ELSE 0 END), 0)
                      AS pending_count,
                  COALESCE(SUM(CASE WHEN dc.status = 'promoting' THEN 1 ELSE 0 END), 0)
                      AS promoting_count,
                  COALESCE(SUM(CASE WHEN dc.status = 'promoted' THEN 1 ELSE 0 END), 0)
                      AS promoted_count,
                  COALESCE(SUM(CASE WHEN dc.status = 'dismissed' THEN 1 ELSE 0 END), 0)
                      AS dismissed_count,
                  COUNT(dc.id) AS candidate_count,
                  COALESCE((
                      SELECT COUNT(*)
                        FROM email_digest_payloads edp
                        JOIN jobs j ON j.id = edp.job_id
                       WHERE edp.watch_id = nw.id
                         AND j.status = 'error'
                         AND j.url LIKE 'email_digest:%'
                  ), 0) AS error_count
             FROM newsletter_watches nw
             JOIN publications p ON p.id = nw.publication_id
             LEFT JOIN digest_candidates dc ON dc.space_id = nw.space_id
            WHERE nw.chat_id = ?
            GROUP BY nw.id
            ORDER BY nw.created_at DESC, nw.id DESC""",
        (chat_id,),
    )


async def get_newsletter_watch(watch_id: str, chat_id: int) -> dict | None:
    row = await _fetch_one(
        """SELECT nw.id, nw.chat_id, nw.publication_id, nw.space_id, nw.name,
                  nw.watched_from, nw.created_at,
                  p.archive_url, p.feed_url, p.fetched_title,
                  COALESCE((
                      SELECT COUNT(*)
                        FROM email_digest_payloads edp
                        JOIN jobs j ON j.id = edp.job_id
                       WHERE edp.watch_id = nw.id
                         AND j.status = 'error'
                         AND j.url LIKE 'email_digest:%'
                  ), 0) AS error_count
             FROM newsletter_watches nw
             JOIN publications p ON p.id = nw.publication_id
            WHERE nw.id = ? AND nw.chat_id = ?""",
        (watch_id, chat_id),
    )
    return dict(row) if row else None


async def update_newsletter_watch_name(
    *, watch_id: str, chat_id: int, name: str
) -> dict | None:
    """PUT edits the watch's `name` only — the display label, distinct from
    `publications.fetched_title` (scraped, never user-facing)."""
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "SELECT space_id FROM newsletter_watches WHERE id = ? AND chat_id = ?",
                (watch_id, chat_id),
            )
            row = await cur.fetchone()
            if row is None:
                await conn.commit()
                return None
            await conn.execute(
                "UPDATE newsletter_watches SET name = ? WHERE id = ? AND chat_id = ?",
                (name, watch_id, chat_id),
            )
            await conn.execute(
                """UPDATE spaces
                      SET name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND chat_id = ?""",
                (name, row["space_id"], chat_id),
            )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    return await get_newsletter_watch(watch_id, chat_id)


async def delete_newsletter_watch(*, watch_id: str, chat_id: int) -> bool:
    """Delete the backing Space; `digest_candidates`/`space_urls`/`context_blobs`
    and the watch row itself all cascade on `space_id`. The publication and
    its issues are left alone (other tenants may still watch them; PLAN.md
    explicitly leaves orphaned-publication cleanup out of scope)."""
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "SELECT space_id FROM newsletter_watches WHERE id = ? AND chat_id = ?",
                (watch_id, chat_id),
            )
            row = await cur.fetchone()
            if row is None:
                await conn.commit()
                return False
            delete_cur = await conn.execute(
                "DELETE FROM spaces WHERE id = ? AND chat_id = ?",
                (row["space_id"], chat_id),
            )
            await conn.commit()
            return delete_cur.rowcount > 0
        except Exception:
            await conn.rollback()
            raise


async def claim_email_digest_job(job_id: str) -> bool:
    changed = await _execute_rowcount(
        """UPDATE jobs
              SET status = 'processing', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status IN ('pending', 'error')""",
        (job_id,),
    )
    return changed == 1


async def get_email_digest_payload(job_id: str) -> dict | None:
    """Join through to the watch (for space/chat ownership) and the shared
    issue row (for the body and title) — the payload itself no longer carries
    any of that content (PLAN.md §1)."""
    row = await _fetch_one(
        """SELECT edp.job_id, edp.watch_id, edp.publication_id, edp.slug, edp.context_md,
                  pi.body_html, pi.title AS issue_title, pi.url AS issue_url,
                  nw.space_id, nw.chat_id, nw.name AS watch_name
             FROM email_digest_payloads edp
             LEFT JOIN newsletter_watches nw ON nw.id = edp.watch_id
             LEFT JOIN publication_issues pi
               ON pi.publication_id = edp.publication_id AND pi.slug = edp.slug
            WHERE edp.job_id = ?""",
        (job_id,),
    )
    return dict(row) if row else None


async def clear_email_digest_payload(job_id: str) -> None:
    """Cleared on success only; an error row keeps `context_md` so a retry
    needs no regeneration (PLAN.md §1/§5)."""
    await _execute_rowcount(
        "UPDATE email_digest_payloads SET context_md = NULL WHERE job_id = ?",
        (job_id,),
    )


async def insert_digest_candidate(
    *, space_id: str, url: str, canonical_url: str, title: str | None = None
) -> str | None:
    candidate_id = generate_id()
    async with core.connection() as conn:
        cur = await conn.execute(
            """INSERT OR IGNORE INTO digest_candidates
               (id, space_id, url, canonical_url, title)
               VALUES (?, ?, ?, ?, ?)""",
            (candidate_id, space_id, url, canonical_url, title),
        )
        await conn.commit()
        if cur.rowcount != 1:
            return None
        return candidate_id


async def update_digest_candidate_preview(
    *, candidate_id: str, title: str | None, thumbnail_url: str | None
) -> None:
    await _execute_rowcount(
        """UPDATE digest_candidates
              SET title = COALESCE(?, title), thumbnail_url = COALESCE(?, thumbnail_url)
            WHERE id = ?""",
        (title, thumbnail_url, candidate_id),
    )


async def list_digest_candidates(space_id: str) -> list[dict]:
    return await _fetch_dicts(
        """SELECT id, space_id, url, canonical_url, title, thumbnail_url, status,
                  job_id, created_at
             FROM digest_candidates
            WHERE space_id = ?
            ORDER BY created_at DESC, id DESC""",
        (space_id,),
    )


async def get_digest_candidate(space_id: str, candidate_id: str) -> dict | None:
    row = await _fetch_one(
        """SELECT id, space_id, url, canonical_url, title, thumbnail_url, status,
                  job_id, created_at
             FROM digest_candidates
            WHERE id = ? AND space_id = ?""",
        (candidate_id, space_id),
    )
    return dict(row) if row else None


async def claim_digest_candidate(*, space_id: str, candidate_id: str) -> bool:
    changed = await _execute_rowcount(
        """UPDATE digest_candidates
              SET status = 'promoting'
            WHERE id = ? AND space_id = ? AND status = 'pending'""",
        (candidate_id, space_id),
    )
    return changed == 1


async def mark_digest_candidate_promoted(
    *, space_id: str, candidate_id: str, job_id: str
) -> bool:
    changed = await _execute_rowcount(
        """UPDATE digest_candidates
              SET status = 'promoted', job_id = ?
            WHERE id = ? AND space_id = ? AND status = 'promoting'""",
        (job_id, candidate_id, space_id),
    )
    return changed == 1


async def reset_digest_candidate_pending(*, space_id: str, candidate_id: str) -> None:
    await _execute_rowcount(
        """UPDATE digest_candidates
              SET status = 'pending'
            WHERE id = ? AND space_id = ? AND status = 'promoting'""",
        (candidate_id, space_id),
    )


async def dismiss_digest_candidate(
    *, space_id: str, candidate_id: str, pending_only: bool = False
) -> bool:
    """Dismiss one candidate. `pending_only` narrows the claim to `pending`
    (issue #613): a bulk `Dismiss rest` loop works from a UI snapshot, so a
    candidate that turned `promoting` in the meantime must not be flipped to
    `dismissed` while its job is being created. Single-card dismiss keeps the
    original `pending`/`promoting` behaviour.
    """
    # Two literal statements rather than a composed IN(...) clause: the values
    # were never user-derived, but this is the module's only non-parameterized
    # SQL and reads as an injection site to both reviewers and scanners.
    sql = (
        """UPDATE digest_candidates
              SET status = 'dismissed'
            WHERE id = ? AND space_id = ? AND status = 'pending'"""
        if pending_only
        else """UPDATE digest_candidates
                   SET status = 'dismissed'
                 WHERE id = ? AND space_id = ? AND status IN ('pending', 'promoting')"""
    )
    changed = await _execute_rowcount(sql, (candidate_id, space_id))
    return changed == 1


async def latest_retryable_email_digest_job(watch_id: str) -> dict | None:
    """Rewritten against the new schema (not re-pointed): the old filter
    checked `edp.subject`/`html`/`text` for content, columns this schema
    drops. A payload's `(publication_id, slug)` composite FK guarantees its
    issue body still exists, so `error` status is the only signal needed."""
    row = await _fetch_one(
        """SELECT j.id, j.chat_id, j.status, j.updated_at
             FROM email_digest_payloads edp
             JOIN jobs j ON j.id = edp.job_id
            WHERE edp.watch_id = ?
              AND j.url LIKE 'email_digest:%'
              AND j.status = 'error'
            ORDER BY j.updated_at DESC, j.id DESC
            LIMIT 1""",
        (watch_id,),
    )
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Newsletter poll worker (ADR-0060, PLAN.md §3/§4, issue #610)
# ---------------------------------------------------------------------------

# How long a claimed poll lease holds before another worker may reclaim the
# same publication. It must cover one whole fetch-and-fan-out pass, and that
# pass is not bounded by a single fetch: after an outage the missing-delivery
# scan can return a backlog of issues, and each one costs a page fetch, a
# Gemini call and N job/payload inserts, sequentially. Ten minutes was too
# tight for that — an overrun lets a second worker claim a publication whose
# first run is still going, doubling the Jina and Gemini spend for no benefit.
_POLL_LEASE_MINUTES = 30

# Success cadence and failure backoff (PLAN.md §4 step 6). Backoff is
# `min(4h * 2**poll_failures, 24h)` computed from the streak *before* this
# failure, so one transient blip costs the normal 4h cadence rather than
# doubling it: 4h, 8h, 16h, then the 24h cap.
_POLL_SUCCESS_INTERVAL_HOURS = 4
_POLL_BACKOFF_BASE_HOURS = 4
_POLL_BACKOFF_MAX_HOURS = 24

# A payload's `jobs` row is considered "stuck pending" (committed but never
# enqueued, e.g. a crash between the two) once it has sat past one scheduler
# tick without moving to 'processing'/'done'/'error'.
_STALE_PENDING_MINUTES = 15


async def list_due_unleased_watched_publication_ids(*, limit: int) -> list[str]:
    """Publications that are due, unleased, and watched (PLAN.md §3).

    `IS NULL` is required on **both** time clauses: a newly created
    publication has neither `next_poll_after` nor `poll_lease_until` set, and
    a bare `<` comparison would never claim it. Spreading load is done by this
    cap plus `ORDER BY next_poll_after`, not delayed delivery — the queue is a
    plain Redis list with no scheduled-task support.
    """
    rows = await _fetch_all(
        """SELECT p.id
             FROM publications p
            WHERE (p.next_poll_after IS NULL OR p.next_poll_after < CURRENT_TIMESTAMP)
              AND (p.poll_lease_until IS NULL OR p.poll_lease_until < CURRENT_TIMESTAMP)
              AND EXISTS (SELECT 1 FROM newsletter_watches w WHERE w.publication_id = p.id)
            ORDER BY p.next_poll_after
            LIMIT ?""",
        (limit,),
    )
    return [row["id"] for row in rows]


async def claim_publication_poll_lease(publication_id: str) -> bool:
    """Claim the poll lease for one publication (PLAN.md §4 step 1).

    No match means either another worker already owns the lease, or the
    publication simply is not due yet — the second `next_poll_after` clause
    is what stops a duplicate queued envelope from re-polling immediately
    after a successful run.
    """
    changed = await _execute_rowcount(
        """UPDATE publications
              SET poll_lease_until = datetime('now', ?)
            WHERE id = ?
              AND (poll_lease_until IS NULL OR poll_lease_until < CURRENT_TIMESTAMP)
              AND (next_poll_after IS NULL OR next_poll_after < CURRENT_TIMESTAMP)""",
        (f"+{_POLL_LEASE_MINUTES} minutes", publication_id),
    )
    return changed == 1


async def get_publication(publication_id: str) -> dict | None:
    row = await _fetch_one("SELECT * FROM publications WHERE id = ?", (publication_id,))
    return dict(row) if row else None


async def record_publication_poll_success(publication_id: str) -> None:
    """Clear the lease, stamp the successful poll, and reset the failure streak."""
    await _execute_rowcount(
        """UPDATE publications
              SET poll_lease_until = NULL,
                  last_successful_poll_at = CURRENT_TIMESTAMP,
                  next_poll_after = datetime('now', ?),
                  poll_failures = 0
            WHERE id = ?""",
        (f"+{_POLL_SUCCESS_INTERVAL_HOURS} hours", publication_id),
    )


async def record_publication_poll_failure(publication_id: str) -> None:
    """Clear the lease, increment the failure streak, and back off
    `next_poll_after` so a failed run is not silently stuck at the normal
    cadence with no escalation (PLAN.md §4 step 6)."""
    row = await _fetch_one(
        "SELECT poll_failures FROM publications WHERE id = ?", (publication_id,)
    )
    current_failures = row["poll_failures"] if row else 0
    new_failures = current_failures + 1
    # Backoff is computed from the streak *before* this failure, so a single
    # transient blip costs nothing beyond the normal 4h cadence (4h, 8h, 16h,
    # then the 24h cap) rather than doubling latency on the first stumble.
    # PLAN.md §4 step 6 does not pin the pre/post-increment reading; this is
    # the resolved call.
    backoff_hours = min(
        _POLL_BACKOFF_BASE_HOURS * (2**current_failures), _POLL_BACKOFF_MAX_HOURS
    )
    await _execute_rowcount(
        """UPDATE publications
              SET poll_lease_until = NULL,
                  poll_failures = ?,
                  next_poll_after = datetime('now', ?)
            WHERE id = ?""",
        (new_failures, f"+{backoff_hours} hours", publication_id),
    )


async def insert_publication_issues(publication_id: str, issues: list[dict]) -> None:
    """`INSERT OR IGNORE` the discovered issues into the shared seen-set —
    this is the seen-set, not the work list (PLAN.md §4 step 3). `source_order`
    is each issue's index in the fetched document; both feeds and archive
    pages list newest first, so index 0 is the newest."""
    if not issues:
        return
    async with core.connection() as conn:
        for index, issue in enumerate(issues):
            await conn.execute(
                """INSERT OR IGNORE INTO publication_issues
                   (publication_id, slug, url, title, source_order)
                   VALUES (?, ?, ?, ?, ?)""",
                (publication_id, issue["slug"], issue["url"], issue.get("title"), index),
            )
        await conn.commit()


async def get_publication_issue(publication_id: str, slug: str) -> dict | None:
    row = await _fetch_one(
        "SELECT * FROM publication_issues WHERE publication_id = ? AND slug = ?",
        (publication_id, slug),
    )
    return dict(row) if row else None


async def set_publication_issue_body(publication_id: str, slug: str, body_html: str) -> None:
    await _execute_rowcount(
        """UPDATE publication_issues
              SET body_html = ?, body_fetched_at = CURRENT_TIMESTAMP
            WHERE publication_id = ? AND slug = ?""",
        (body_html, publication_id, slug),
    )


async def mark_publication_issue_oversize(publication_id: str, slug: str) -> None:
    """Mark an issue whose fetch exceeded the Jina streaming cap as terminally
    skipped (PLAN.md §1/§4 step 2, issue #611). `skip_reason` is what
    `list_outstanding_newsletter_deliveries` already filters on, so once set
    this issue stops being re-fetched every poll and stops blocking its own
    body-cleanup accounting (it never acquires a body to reclaim)."""
    await mark_publication_issue_skipped(publication_id, slug, "oversize")


async def mark_publication_issue_skipped(publication_id: str, slug: str, reason: str) -> None:
    """Mark an issue terminally skipped for *reason* (`oversize`, `not_public`).
    Once set, `list_outstanding_newsletter_deliveries` filters it out, so the
    issue is neither re-fetched every poll nor left blocking its own
    body-cleanup accounting."""
    await _execute_rowcount(
        "UPDATE publication_issues SET skip_reason = ? WHERE publication_id = ? AND slug = ?",
        (reason, publication_id, slug),
    )


async def reclaim_publication_issue_bodies(publication_id: str) -> int:
    """Clear `body_html` for issues no live delivery still needs (PLAN.md §1,
    issue #611). A two-halves predicate, both required — this is a standalone
    cleanup pass, deliberately **not** invoked from fan-out or from
    enqueue-completion, so an errored digest stays retryable after it runs:

    1. No live watch is still missing a payload row for this
       `(publication_id, slug)` — the same missing-delivery definition
       `list_outstanding_newsletter_deliveries` uses for repair. Checking only
       half 2 below would pass vacuously while payload rows don't exist yet:
       a fast first watcher could clear the body before later watchers' rows
       are created, and a crash after storing `body_html` but before any
       payload creation would look "clean" with zero rows.
    2. Every existing payload row for it, whose watch still exists (payloads
       whose watch was deleted carry `watch_id IS NULL` via `ON DELETE SET
       NULL` and are excluded by the join), belongs to a job that is either
       `done` or intentionally `cancelled` (the status `retry_error`/
       `clear_failed` move a dismissed error to) — never `pending`,
       `processing`, or `error`, so a still-retryable errored digest keeps
       its body.

    Returns the number of issues reclaimed, for logging/tests.
    """
    return await _execute_rowcount(
        """UPDATE publication_issues
              SET body_html = NULL, body_fetched_at = NULL
            WHERE publication_id = ?
              AND body_html IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM newsletter_watches nw
                   WHERE nw.publication_id = publication_issues.publication_id
                     AND nw.watched_from < publication_issues.first_seen_at
                     AND NOT EXISTS (
                         SELECT 1 FROM email_digest_payloads edp
                          WHERE edp.watch_id = nw.id AND edp.slug = publication_issues.slug
                     )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM email_digest_payloads edp2
                  JOIN newsletter_watches nw2 ON nw2.id = edp2.watch_id
                  JOIN jobs j ON j.id = edp2.job_id
                   WHERE edp2.publication_id = publication_issues.publication_id
                     AND edp2.slug = publication_issues.slug
                     AND j.status NOT IN ('done', 'cancelled')
              )""",
        (publication_id,),
    )


async def list_outstanding_newsletter_deliveries(publication_id: str) -> list[dict]:
    """Outstanding work as **missing deliveries**, not newly-inserted issues
    (PLAN.md §4 step 4): join *all* `publication_issues` for this publication
    against live `newsletter_watches` where `watched_from < first_seen_at`,
    selecting `(watch_id, slug)` pairs with no `email_digest_payloads` row.
    "Rows that just inserted" would lose an issue permanently whenever a run
    crashes after the insert but before fan-out. No recency window — a
    bounded "last N days" scan would silently give up on any outage longer
    than N. Issues carrying a `skip_reason` are excluded (#611 owns writing
    that column; this scan only needs to respect it once set).

    Oldest first: `published_at ASC NULLS LAST, source_order DESC,
    first_seen_at ASC` — `(published_at IS NULL)` is a portable NULLS-LAST
    rendition. The `DESC` on `source_order` is not a typo: both feeds and
    archive pages list newest first, so it reverses that ordering.
    """
    return await _fetch_dicts(
        """SELECT nw.id AS watch_id, nw.chat_id, nw.name,
                  pi.slug, pi.url AS issue_url, pi.title AS issue_title,
                  pi.published_at, pi.source_order, pi.first_seen_at
             FROM publication_issues pi
             JOIN newsletter_watches nw ON nw.publication_id = pi.publication_id
            WHERE pi.publication_id = ?
              AND pi.skip_reason IS NULL
              AND nw.watched_from < pi.first_seen_at
              AND NOT EXISTS (
                  SELECT 1 FROM email_digest_payloads edp
                   WHERE edp.watch_id = nw.id AND edp.slug = pi.slug
              )
            ORDER BY (pi.published_at IS NULL), pi.published_at ASC,
                     pi.source_order DESC, pi.first_seen_at ASC""",
        (publication_id,),
    )


async def list_stale_pending_newsletter_job_ids(publication_id: str) -> list[str]:
    """Payloads whose `jobs` row has sat `pending` past one scheduler tick,
    repairing a crash between commit and enqueue (PLAN.md §4 step 4 / §5) —
    this is why no durable enqueue outbox is needed here."""
    rows = await _fetch_all(
        """SELECT edp.job_id
             FROM email_digest_payloads edp
             JOIN jobs j ON j.id = edp.job_id
            WHERE edp.publication_id = ?
              AND j.url LIKE 'email_digest:%'
              AND j.status = 'pending'
              AND j.updated_at < datetime('now', ?)""",
        (publication_id, f"-{_STALE_PENDING_MINUTES} minutes"),
    )
    return [row["job_id"] for row in rows]


async def create_newsletter_delivery(
    *,
    watch_id: str,
    chat_id: int,
    name: str,
    publication_id: str,
    slug: str,
    context_md: str | None,
) -> str | None:
    """Per-watcher fan-out: create the `jobs` row **and** its
    `email_digest_payloads` row in one transaction (PLAN.md §4 step 5). A
    `UNIQUE(watch_id, slug)` violation rolls back both — the just-created job
    included, so no orphan survives — and the caller simply skips this
    watcher (already delivered, e.g. by the watch's explicit first-delivery
    or a previous poll). Returns the new job id, or `None` if skipped.
    """
    job_id = generate_id()
    async with core.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            await conn.execute(
                """INSERT INTO jobs (id, chat_id, url, content_type, status, title)
                   VALUES (?, ?, ?, 'link', 'pending', ?)""",
                (
                    job_id,
                    chat_id,
                    f"email_digest:{watch_id}:{slug}",
                    f"Newsletter digest: {name}".strip()[:500],
                ),
            )
            await conn.execute(
                """INSERT INTO email_digest_payloads
                   (job_id, watch_id, publication_id, slug, context_md)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, watch_id, publication_id, slug, context_md),
            )
            await conn.commit()
            return job_id
        except aiosqlite.IntegrityError:
            await conn.rollback()
            return None
        except Exception:
            # Every other multi-statement writer in this module rolls back
            # explicitly rather than relying on connection close to discard the
            # transaction — and a failure here is worth a traceback, since it
            # means a watcher silently missed a delivery.
            await conn.rollback()
            log.exception(
                "newsletter.delivery_create_failed", watch_id=watch_id, slug=slug
            )
            raise

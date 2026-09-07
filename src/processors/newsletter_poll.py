"""Newsletter poll worker — polls watched publications and fans issues out to
every watcher (ADR-0060, PLAN.md §3/§4, issues #610/#611).

Envelope: `{"task": "newsletter_poll", "job_id": <publication_id>}`. This is a
rowless task (`src/worker.py`'s `_ROWLESS_TASKS`): the envelope's `job_id`
carries a `publications.id`, not a `jobs.id` — the established convention for
tasks that operate on something other than a job row (`job_purge`,
`bookmarks_enrich`).

One poll run: claim the publication's lease, fetch its feed (or archive root)
through the shared streaming Jina helper, record every discovered issue as a
seen-set row, then compute outstanding work as **missing deliveries** — not
newly-inserted issues — so a crash between seeding and fan-out is repaired on
the next poll rather than silently losing the issue. Per issue: fetch the
issue page once, generate its editorial context once (best-effort), then
create one `jobs` + `email_digest_payloads` row per watcher, all before any of
that issue's jobs is enqueued. An issue whose fetch exceeds the streaming cap
is marked `skip_reason = 'oversize'` and treated as terminal (issue #611) —
fan-out continues with the rest of the run. A standalone cleanup pass at the
end of each poll reclaims `body_html` for issues no live delivery still needs
(PLAN.md §1, issue #611).
"""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit, urlunsplit

from src import database, job_queue as queue
from src.processors.email_digest import (
    DigestLink,
    _build_context_prompt,
    extract_digest_links,
    strip_html_text,
)
from src.services import gemini
from src.services.gemini import GeminiUnavailableError
from src.services.jina import JinaFetchError, JinaOversizeError, fetch_html
from src.utils.logger import get_logger
from src.utils.public_html import is_public_url

log = get_logger(__name__)


class NewsletterPollError(Exception):
    """A poll run cannot proceed. Raised out of `_poll` so `run()` records the
    failure and applies the backoff, rather than failing silently."""


def _normalized_prefix(issue_path_prefix: str | None) -> str | None:
    if not issue_path_prefix:
        return None
    prefix = issue_path_prefix if issue_path_prefix.startswith("/") else f"/{issue_path_prefix}"
    if not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _extract_issue_links(html: str, base_url: str, issue_path_prefix: str | None) -> list[dict]:
    """Extract issues matching the publication's learned `issue_path_prefix`,
    in document order (index 0 = first appearing = newest, since feeds and
    archive pages both list newest first — this order becomes `source_order`).

    Same-origin only, matching the resolver's `_group_issue_links`. The prefix
    is already known here, so this filters and dedupes by it rather than
    discovering it — but the origin check is not optional: a publisher page,
    or anything injected into one (a compromised CMS, a widget, a hijacked
    feed), can carry a link whose *path* happens to match the prefix while
    pointing at an unrelated host. Without this, that URL is persisted as an
    issue, later fetched through the Jina proxy on Ownix's quota, and its
    content lands in a watcher's Space.
    """
    prefix = _normalized_prefix(issue_path_prefix)
    if prefix is None:
        log.info("newsletter_poll.no_issue_path_prefix", base_url=base_url[:200])
        return []

    base_netloc = urlsplit(base_url).netloc.lower()
    seen: dict[str, dict] = {}
    order: list[str] = []
    links: list[DigestLink] = extract_digest_links(html)
    for link in links:
        href = (link.href or "").strip()
        if not href or href.startswith("#"):
            continue
        resolved = urljoin(base_url, href)
        parts = urlsplit(resolved)
        if parts.scheme not in {"http", "https"}:
            continue
        if parts.netloc.lower() != base_netloc:
            continue
        if not parts.path.startswith(prefix):
            continue
        remainder = parts.path[len(prefix) :]
        slug = remainder.split("/", 1)[0]
        if not slug:
            continue
        clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        if slug not in seen:
            seen[slug] = {"slug": slug, "url": clean_url, "title": link.text.strip() or None}
            order.append(slug)
    return [seen[slug] for slug in order]


def _group_by_issue(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group outstanding-delivery rows by slug, preserving the SQL's
    oldest-first order — rows for the same issue share the same
    published_at/source_order/first_seen_at, so they are already adjacent;
    grouping in Python (rather than trusting SQL tie-breaking) keeps that
    order exact regardless of how ties are physically returned."""
    order: list[str] = []
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        slug = row["slug"]
        if slug not in grouped:
            grouped[slug] = []
            order.append(slug)
        grouped[slug].append(row)
    return [(slug, grouped[slug]) for slug in order]


async def _generate_issue_context(title: str | None, body_html: str) -> str | None:
    """One best-effort Gemini call per issue (PLAN.md §4 step 5). A failure —
    Gemini unavailable or any other error — sets `context_md = NULL` for
    every watcher of this issue rather than sinking the whole poll run,
    matching `_create_context_blob`'s existing non-fatal posture. There is no
    per-watcher fallback generation."""
    body_text = strip_html_text(body_html)
    if not body_text.strip():
        return None
    prompt = _build_context_prompt(title or "Untitled", body_text)
    try:
        content = await gemini.generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError:
        log.info("newsletter_poll.context_gemini_unavailable")
        return None
    except Exception as exc:
        log.info("newsletter_poll.context_failed", error=str(exc)[:160])
        return None
    return content.strip() or None


async def _enqueue_or_error(job_id: str, *, watch_id: str) -> None:
    """Commit → enqueue → mark-error posture (PLAN.md §5, mirrors
    `email_webhook.py`'s enqueue-failure handling): a Redis push cannot join
    the SQLite transaction that already created the job/payload rows."""
    try:
        await queue.enqueue({"task": "email_digest", "job_id": job_id, "watch_id": watch_id})
    except Exception:
        log.exception("newsletter_poll.enqueue_failed", job_id=job_id)
        await database.update_job_status(
            job_id, "error", error_msg="Failed to enqueue newsletter digest"
        )


async def _repair_stale_pending(publication_id: str) -> None:
    """Re-enqueue payloads whose `jobs` row has been stuck `pending` past one
    scheduler tick — repairing a crash between commit and enqueue. This is
    why no durable enqueue outbox is needed for this feature (PLAN.md §5)."""
    stale_job_ids = await database.list_stale_pending_newsletter_job_ids(publication_id)
    for job_id in stale_job_ids:
        payload = await database.get_email_digest_payload(job_id)
        if payload is None:
            # No payload row means this is not a repairable delivery — running
            # it would only make `email_digest.run()` raise on the missing
            # payload. Leave it for generic recovery rather than re-driving it.
            log.warning("newsletter_poll.stale_pending_without_payload", job_id=job_id)
            continue
        await _enqueue_or_error(job_id, watch_id=payload["watch_id"])


async def _fan_out_issue(publication_id: str, slug: str, watchers: list[dict]) -> None:
    issue = await database.get_publication_issue(publication_id, slug)
    if issue is None:
        return

    body_html = issue.get("body_html")
    if not body_html:
        # Re-checked on every fetch, not just when the URL was first stored:
        # this path runs unattended forever, and the stored URL came off a
        # publisher page rather than from the user.
        if not await is_public_url(issue["url"]):
            log.warning(
                "newsletter_poll.issue_url_rejected",
                publication_id=publication_id,
                slug=slug,
                url=issue["url"][:200],
            )
            await database.mark_publication_issue_skipped(publication_id, slug, "not_public")
            return
        try:
            body_html = await fetch_html(issue["url"])
        except JinaOversizeError:
            # Terminal (PLAN.md §1/§4 step 2, issue #611): mark skip_reason so
            # this issue stops being re-fetched every poll and stops blocking
            # its own body-cleanup accounting — it never acquires a body to
            # reclaim. Fan-out continues with the remaining issues: this
            # function runs once per issue inside _poll()'s loop, so a
            # `return` here only skips this one issue.
            log.info(
                "newsletter_poll.issue_oversize_skipped",
                publication_id=publication_id,
                slug=slug,
            )
            await database.mark_publication_issue_oversize(publication_id, slug)
            return
        except JinaFetchError as exc:
            # Best-effort, not terminal: leave this issue for a later poll to
            # retry — a transient fetch failure is not the same as a
            # permanently-oversized issue.
            log.info(
                "newsletter_poll.issue_fetch_failed",
                publication_id=publication_id,
                slug=slug,
                error=str(exc)[:160],
            )
            return
        await database.set_publication_issue_body(publication_id, slug, body_html)

    context_md = await _generate_issue_context(issue.get("title"), body_html)

    created: list[tuple[str, str]] = []
    for watcher in watchers:
        job_id = await database.create_newsletter_delivery(
            watch_id=watcher["watch_id"],
            chat_id=watcher["chat_id"],
            name=watcher["name"],
            publication_id=publication_id,
            slug=slug,
            context_md=context_md,
        )
        if job_id is not None:
            created.append((job_id, watcher["watch_id"]))

    # All payload rows for this issue exist before any of its jobs is
    # enqueued — enqueuing as we went would let a fast job finish, run the
    # cleanup predicate, and clear body_html while later watchers here still
    # had no payload row.
    for job_id, watch_id in created:
        await _enqueue_or_error(job_id, watch_id=watch_id)


async def _poll(publication_id: str) -> None:
    publication = await database.get_publication(publication_id)
    if publication is None:
        return

    fetch_url = publication["feed_url"] or publication["archive_url"]
    # The resolver validated this URL once, at watch-creation time. That is not
    # enough: this fetch recurs every 4 hours forever, unattended, with no
    # probe cap and no user to rate-limit — and DNS for a host can change under
    # a stored URL. Re-check before every proxy call (ADR-0060 / #608).
    if not await is_public_url(fetch_url):
        log.warning(
            "newsletter_poll.fetch_url_rejected",
            publication_id=publication_id,
            url=fetch_url[:200],
        )
        raise NewsletterPollError(f"Publication URL is not publicly fetchable: {fetch_url[:120]}")
    html = await fetch_html(fetch_url)  # JinaFetchError/JinaOversizeError -> caller records failure

    issues = _extract_issue_links(html, fetch_url, publication.get("issue_path_prefix"))
    await database.insert_publication_issues(publication_id, issues)

    await _repair_stale_pending(publication_id)

    outstanding = await database.list_outstanding_newsletter_deliveries(publication_id)
    for slug, watchers in _group_by_issue(outstanding):
        await _fan_out_issue(publication_id, slug, watchers)

    # A standalone cleanup pass (PLAN.md §1, issue #611) — deliberately not
    # folded into _fan_out_issue or _enqueue_or_error, so clearing a body
    # never races a job that was merely *created* this cycle, and an errored
    # digest stays retryable after this runs.
    await database.reclaim_publication_issue_bodies(publication_id)


async def run(publication_id: str) -> None:
    """Poll one watched publication. `publication_id` is the task envelope's
    `job_id` (PLAN.md §4 — this task is rowless with respect to `jobs`)."""
    claimed = await database.claim_publication_poll_lease(publication_id)
    if not claimed:
        log.info("newsletter_poll.lease_not_claimed", publication_id=publication_id)
        return

    try:
        await _poll(publication_id)
    except Exception:
        log.exception("newsletter_poll.failed", publication_id=publication_id)
        await database.record_publication_poll_failure(publication_id)
        return

    await database.record_publication_poll_success(publication_id)

"""Newsletter digest watch and candidate-management API (ADR-0060, PLAN.md §6/§8).

A [[Watched newsletter]] follows a publication's public archive rather than
an inbound-email alias (issue #609). `resolve_newsletter` is read-only and
creates nothing; `create_watch` re-resolves the given `archive_url`
server-side rather than trusting the client's earlier resolve response, then
creates (or reuses) the shared `publications` row, seeds its issue seen-set,
and inserts the watch with its explicit first-issue delivery — all in one
transaction (`database.create_newsletter_watch`).
"""

from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from src import database, job_queue as queue
from src.api.jobs import JobCreateRequest, create_job
from src.api.parsed import UrlIn as ParsedUrlIn
from src.api.parsed import upload_url
from src.services import newsletter_archive
from src.utils.validators import detect_pipeline

newsletter_digest_router = APIRouter(prefix="/api/newsletter-digest", tags=["newsletter-digest"])


class ResolveIn(BaseModel):
    query: str = Field(..., min_length=1, max_length=320)


class RecentIssueOut(BaseModel):
    slug: str
    title: str
    url: str


class ResolveOut(BaseModel):
    archive_url: str
    feed_url: str | None
    issue_path_prefix: str
    fetched_title: str
    recent_issues: list[RecentIssueOut]


def _name_not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("name must not be blank")
    return value


class WatchCreateIn(BaseModel):
    archive_url: str = Field(..., min_length=1, max_length=2048)
    name: str = Field(..., min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _name_not_blank(value)


class WatchUpdateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        return _name_not_blank(value)


async def _get_owned_watch(watch_id: str, chat_id: int) -> dict:
    watch = await database.get_newsletter_watch(watch_id, chat_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="Newsletter watch not found")
    return watch


async def _resolve_or_422(query: str, *, chat_id: int) -> newsletter_archive.NewsletterResolution:
    try:
        return await newsletter_archive.resolve_newsletter_archive(query, chat_id=chat_id)
    except newsletter_archive.NewsletterResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _resolve_out(result: newsletter_archive.NewsletterResolution) -> ResolveOut:
    return ResolveOut(
        archive_url=result.archive_url,
        feed_url=result.feed_url,
        issue_path_prefix=result.issue_path_prefix,
        fetched_title=result.fetched_title,
        recent_issues=[
            RecentIssueOut(slug=issue.slug, title=issue.title, url=issue.url)
            for issue in result.recent_issues
        ],
    )


@newsletter_digest_router.post("/resolve")
async def resolve_newsletter(body: ResolveIn, request: Request) -> ResolveOut:
    """Resolve a newsletter's public archive from a URL or sender email.

    Read-only — creates nothing. Rate-limited per chat inside
    `newsletter_archive.resolve_newsletter_archive` (PLAN.md §2 / issue #608).
    """
    chat_id: int = request.state.user["id"]
    result = await _resolve_or_422(body.query.strip(), chat_id=chat_id)
    return _resolve_out(result)


async def _enqueue_delivery(*, job_id: str, watch_id: str) -> None:
    """Commit → enqueue → mark-error posture (PLAN.md §5, mirrors
    `email_webhook.py`'s enqueue-failure handling): a Redis push cannot join
    the SQLite transaction that already created the job/payload rows."""
    try:
        await queue.enqueue({"task": "email_digest", "job_id": job_id, "watch_id": watch_id})
    except Exception:
        await database.update_job_status(job_id, "error")


@newsletter_digest_router.post("", status_code=201)
async def create_watch(body: WatchCreateIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    # Re-resolve server-side — the client's earlier /resolve response (if any)
    # is never trusted for archive_url, feed_url, issue_path_prefix, etc.
    resolution = await _resolve_or_422(body.archive_url.strip(), chat_id=chat_id)

    try:
        watch = await database.create_newsletter_watch(
            chat_id=chat_id,
            name=body.name.strip(),
            archive_url=resolution.archive_url,
            feed_url=resolution.feed_url,
            issue_path_prefix=resolution.issue_path_prefix,
            fetched_title=resolution.fetched_title,
            recent_issues=[
                {"slug": issue.slug, "title": issue.title, "url": issue.url}
                for issue in resolution.recent_issues
            ],
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Already watching this newsletter") from exc

    delivery_job_id = watch.pop("delivery_job_id", None)
    if delivery_job_id:
        await _enqueue_delivery(job_id=delivery_job_id, watch_id=watch["id"])
    return watch


@newsletter_digest_router.get("")
async def list_watches(request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    return await database.list_newsletter_watches(chat_id)


@newsletter_digest_router.get("/{watch_id}")
async def get_watch(watch_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    return await _get_owned_watch(watch_id, chat_id)


@newsletter_digest_router.put("/{watch_id}")
async def update_watch(watch_id: str, body: WatchUpdateIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_watch(watch_id, chat_id)
    watch = await database.update_newsletter_watch_name(
        watch_id=watch_id, chat_id=chat_id, name=body.name.strip()
    )
    if watch is None:
        raise HTTPException(status_code=404, detail="Newsletter watch not found")
    return watch


@newsletter_digest_router.delete("/{watch_id}", status_code=204)
async def delete_watch(watch_id: str, request: Request) -> Response:
    chat_id: int = request.state.user["id"]
    await _get_owned_watch(watch_id, chat_id)
    deleted = await database.delete_newsletter_watch(watch_id=watch_id, chat_id=chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Newsletter watch not found")
    return Response(status_code=204)


@newsletter_digest_router.get("/{watch_id}/candidates")
async def list_candidates(watch_id: str, request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    watch = await _get_owned_watch(watch_id, chat_id)
    return await database.list_digest_candidates(watch["space_id"])


@newsletter_digest_router.post("/{watch_id}/candidates/{candidate_id}/promote")
async def promote_candidate(watch_id: str, candidate_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    watch = await _get_owned_watch(watch_id, chat_id)
    space_id = watch["space_id"]

    claimed = await database.claim_digest_candidate(space_id=space_id, candidate_id=candidate_id)
    if not claimed:
        raise HTTPException(status_code=409, detail="Candidate is not pending")
    candidate = await database.get_digest_candidate(space_id, candidate_id)
    if candidate is None:
        await database.reset_digest_candidate_pending(space_id=space_id, candidate_id=candidate_id)
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        pipeline = detect_pipeline(
            candidate["url"],
            frozenset(await database.list_allowed_domains(chat_id)),
        )
        if pipeline == "document":
            result = await upload_url(ParsedUrlIn(url=candidate["url"]), request)
        else:
            result = await create_job(request, JobCreateRequest(url=candidate["url"]))
        job_id = result.get("job_id") or result.get("id")
        if not job_id:
            raise RuntimeError("promotion did not return a job id")
        await database.mark_digest_candidate_promoted(
            space_id=space_id,
            candidate_id=candidate_id,
            job_id=job_id,
        )
        await database.add_space_url(space_id=space_id, job_id=job_id)
        return {**result, "candidate_id": candidate_id}
    except Exception:
        await database.reset_digest_candidate_pending(space_id=space_id, candidate_id=candidate_id)
        raise


@newsletter_digest_router.delete("/{watch_id}/candidates/{candidate_id}", status_code=204)
async def dismiss_candidate(
    watch_id: str,
    candidate_id: str,
    request: Request,
    pending_only: bool = False,
) -> Response:
    """`pending_only=true` is what `Dismiss rest` sends (issue #613), so a bulk
    loop working from a UI snapshot cannot dismiss a candidate that turned
    `promoting` after that snapshot was taken. A batch *endpoint* is
    deliberately not added: it would impose all-or-nothing semantics that are
    wrong here, since one candidate failing must not roll back the others.
    """
    chat_id: int = request.state.user["id"]
    watch = await _get_owned_watch(watch_id, chat_id)
    dismissed = await database.dismiss_digest_candidate(
        space_id=watch["space_id"],
        candidate_id=candidate_id,
        pending_only=pending_only,
    )
    if not dismissed:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return Response(status_code=204)


@newsletter_digest_router.post("/{watch_id}/retry")
async def retry_digest(watch_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_watch(watch_id, chat_id)
    job = await database.latest_retryable_email_digest_job(watch_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No retryable digest job")
    await queue.enqueue(
        {
            "task": "email_digest",
            "job_id": job["id"],
            "watch_id": watch_id,
        }
    )
    return {"job_id": job["id"], "status": "queued"}

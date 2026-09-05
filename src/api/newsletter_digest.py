"""Newsletter digest subscription and candidate-management API."""

from __future__ import annotations

import re

import aiosqlite
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from src import database, job_queue as queue
from src.api.jobs import JobCreateRequest, create_job
from src.api.parsed import UrlIn as ParsedUrlIn
from src.api.parsed import upload_url
from src.utils.validators import detect_pipeline

newsletter_digest_router = APIRouter(prefix="/api/newsletter-digest", tags=["newsletter-digest"])

_ALIAS_DOMAIN = "leondev.xyz"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SubscriptionIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    sender_email: str = Field(..., min_length=3, max_length=320)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value

    @field_validator("sender_email")
    @classmethod
    def sender_email_valid(cls, value: str) -> str:
        email = value.strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValueError("sender_email must be an email address")
        return email


def _with_alias(subscription: dict) -> dict:
    return {
        **subscription,
        "alias": f"{subscription['alias_local_part']}@{_ALIAS_DOMAIN}",
    }


async def _get_owned_subscription(subscription_id: str, chat_id: int) -> dict:
    subscription = await database.get_newsletter_subscription(subscription_id, chat_id)
    if subscription is None:
        raise HTTPException(status_code=404, detail="Newsletter subscription not found")
    return subscription


@newsletter_digest_router.post("", status_code=201)
async def create_subscription(body: SubscriptionIn, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    try:
        subscription = await database.create_newsletter_subscription(
            chat_id=chat_id,
            name=body.name.strip(),
            sender_email=body.sender_email,
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Newsletter subscription already exists") from exc
    return _with_alias(subscription)


@newsletter_digest_router.get("")
async def list_subscriptions(request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    return [_with_alias(row) for row in await database.list_newsletter_subscriptions(chat_id)]


@newsletter_digest_router.get("/{subscription_id}")
async def get_subscription(subscription_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    return _with_alias(await _get_owned_subscription(subscription_id, chat_id))


@newsletter_digest_router.put("/{subscription_id}")
async def update_subscription(
    subscription_id: str, body: SubscriptionIn, request: Request
) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_subscription(subscription_id, chat_id)
    try:
        subscription = await database.update_newsletter_subscription(
            subscription_id=subscription_id,
            chat_id=chat_id,
            name=body.name.strip(),
            sender_email=body.sender_email,
        )
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Newsletter subscription already exists") from exc
    if subscription is None:
        raise HTTPException(status_code=404, detail="Newsletter subscription not found")
    return _with_alias(subscription)


@newsletter_digest_router.delete("/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: str, request: Request) -> Response:
    chat_id: int = request.state.user["id"]
    await _get_owned_subscription(subscription_id, chat_id)
    deleted = await database.delete_newsletter_subscription(
        subscription_id=subscription_id,
        chat_id=chat_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Newsletter subscription not found")
    return Response(status_code=204)


@newsletter_digest_router.get("/{subscription_id}/candidates")
async def list_candidates(subscription_id: str, request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    subscription = await _get_owned_subscription(subscription_id, chat_id)
    return await database.list_digest_candidates(subscription["space_id"])


@newsletter_digest_router.post("/{subscription_id}/candidates/{candidate_id}/promote")
async def promote_candidate(subscription_id: str, candidate_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    subscription = await _get_owned_subscription(subscription_id, chat_id)
    space_id = subscription["space_id"]

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


@newsletter_digest_router.delete("/{subscription_id}/candidates/{candidate_id}", status_code=204)
async def dismiss_candidate(subscription_id: str, candidate_id: str, request: Request) -> Response:
    chat_id: int = request.state.user["id"]
    subscription = await _get_owned_subscription(subscription_id, chat_id)
    dismissed = await database.dismiss_digest_candidate(
        space_id=subscription["space_id"],
        candidate_id=candidate_id,
    )
    if not dismissed:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return Response(status_code=204)


@newsletter_digest_router.post("/{subscription_id}/retry")
async def retry_digest(subscription_id: str, request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    await _get_owned_subscription(subscription_id, chat_id)
    job = await database.latest_retryable_email_digest_job(subscription_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No retryable digest job")
    await queue.enqueue(
        {
            "task": "email_digest",
            "job_id": job["id"],
            "subscription_id": subscription_id,
        }
    )
    return {"job_id": job["id"], "status": "queued"}

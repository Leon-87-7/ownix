"""Cloudflare Email Routing webhook for newsletter digest ingestion."""

from __future__ import annotations

import hashlib
from email.utils import parseaddr
from secrets import compare_digest

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from src import database, job_queue as queue
from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/webhook/email-digest", tags=["email-digest-webhook"])

_MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
_DAILY_ISSUE_CAP = 20


class EmailDigestPayload(BaseModel):
    envelopeTo: str = Field(..., min_length=1)
    from_email: str = Field(..., alias="from")
    subject: str | None = None
    html: str | None = None
    text: str | None = None
    messageId: str | None = None


def _local_part(address: str) -> str:
    parsed = parseaddr(address)[1] or address
    return parsed.split("@", 1)[0].strip()


def _normalized_sender(address: str) -> str:
    return (parseaddr(address)[1] or address).strip().lower()


def _receipt_identity(message_id: str | None, *, subject: str, html: str, text: str) -> str:
    normalized = (message_id or "").strip().lower()
    if normalized:
        return normalized
    body_hash = hashlib.sha256(
        f"{subject.strip()}\n{html}\n{text}".encode("utf-8", errors="replace")
    ).hexdigest()
    return f"content:{body_hash}"


def receipt_key(alias_local_part: str, message_id: str | None, *, subject: str, html: str, text: str) -> str:
    identity = _receipt_identity(message_id, subject=subject, html=html, text=text)
    return hashlib.sha256(f"{alias_local_part}:{identity}".encode()).hexdigest()


async def _enqueue_email_digest(job: dict, subscription_id: str) -> None:
    await queue.enqueue(
        {
            "task": "email_digest",
            "job_id": job["id"],
            "subscription_id": subscription_id,
        }
    )


@router.post("")
async def receive_email_digest(
    body: EmailDigestPayload,
    x_ownix_email_secret: str | None = Header(default=None, alias="X-Ownix-Email-Secret"),
) -> dict:
    if not compare_digest(x_ownix_email_secret or "", settings.EMAIL_WEBHOOK_SECRET):
        log.warning("email_digest_webhook.bad_secret")
        return {"ok": True}

    alias = _local_part(body.envelopeTo)
    subscription = await database.get_newsletter_subscription_by_alias(alias)
    if subscription is None:
        log.info("email_digest_webhook.unknown_alias", alias=alias[:8])
        return {"ok": True}

    sender = _normalized_sender(body.from_email)
    if sender != subscription["sender_email"].lower():
        log.info(
            "email_digest_webhook.sender_mismatch",
            subscription_id=subscription["id"],
            sender=sender[:120],
        )
        return {"ok": True}

    subject = body.subject or ""
    html = body.html or ""
    text = body.text or ""
    key = receipt_key(
        subscription["alias_local_part"],
        body.messageId,
        subject=subject,
        html=html,
        text=text,
    )
    existing = await database.get_email_digest_receipt(subscription["id"], key)
    if existing is not None:
        if existing["status"] == "pending":
            await _enqueue_email_digest(existing, subscription["id"])
            log.info(
                "email_digest_webhook.dedup_pending_requeued",
                subscription_id=subscription["id"],
                job_id=existing["id"],
            )
        else:
            log.info(
                "email_digest_webhook.dedup_hit",
                subscription_id=subscription["id"],
                job_id=existing["id"],
            )
        return {"ok": True, "job_id": existing["id"], "deduped": True}

    payload_bytes = len(html.encode("utf-8")) + len(text.encode("utf-8"))
    if payload_bytes > _MAX_PAYLOAD_BYTES:
        log.info(
            "email_digest_webhook.payload_too_large",
            subscription_id=subscription["id"],
            bytes=payload_bytes,
        )
        return {"ok": True}

    created = await database.create_email_digest_receipt_job(
        subscription=subscription,
        receipt_key=key,
        receipt_url=f"email_digest:{key[:16]}",
        subject=subject,
        html=html,
        text=text,
        daily_cap=_DAILY_ISSUE_CAP,
    )
    if created["status"] == "over_cap":
        log.info("email_digest_webhook.daily_cap", subscription_id=subscription["id"])
        return {"ok": True}

    job = created["job"]
    if job and job["status"] == "pending":
        try:
            await _enqueue_email_digest(job, subscription["id"])
        except Exception:
            await database.update_job_status(job["id"], "error", error_msg="Failed to enqueue email digest")
            log.exception("email_digest_webhook.enqueue_failed", job_id=job["id"])
            raise

    return {"ok": True, "job_id": job["id"] if job else None, "deduped": created["status"] == "deduped"}

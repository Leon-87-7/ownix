"""Generic dashboard actions — the replacement for Telegram inline keyboards.

`POST /api/intake/action` (src/api/intake.py) builds an `IntakeMessage` whose
`idempotency_key` is deterministically `f"action:{action_id}"`, so the
router's existing per-(actor, idempotency_key) cache already gives "a
double-fired action does not double-apply" for free — this module only needs
to implement the actual per-`kind` effect, not its own idempotency tracking.
"""

from __future__ import annotations

from src import database
from src.intake import commands, responses, tag_tokens
from src.intake.models import IntakeAction, IntakeMessage, IntakeResponse
from src.services.jobs import create_and_enqueue_job


async def apply(msg: IntakeMessage) -> IntakeResponse:
    action = msg.action
    chat_id = msg.actor.legacy_chat_id
    if action is None or chat_id is None:
        return responses.error("No action to apply.", retryable=False)

    if action.kind == "cancel_pending":
        return await commands.cancel_pending(chat_id)

    if action.kind == "retry_job":
        return await _retry_job(chat_id, action.job_id)

    if action.kind == "create_tag":
        return await _create_tag(chat_id, action)

    return responses.unsupported(f"Unknown action: {action.kind}")


async def _create_tag(chat_id: int, action: IntakeAction) -> IntakeResponse:
    """Create the tag an unknown `#tag` token named, and attach it (issue #489).

    Idempotent by construction rather than by the action cache: a normalized
    lookup runs first, so a double-fire — or a tag someone created from the
    Controls page between the offer and the save — reuses the existing row
    instead of colliding with `UNIQUE(chat_id, name)`.
    """
    payload = action.payload or {}
    name = str(payload.get("tag_name") or "").strip()
    if not name:
        return responses.error("A tag needs a name.", retryable=False)

    if action.job_id:
        job = await database.get_job(action.job_id)
        if job is None or job["chat_id"] != chat_id:
            return responses.error("Job not found.", retryable=False)

    key = tag_tokens.normalize(name)
    existing = {tag_tokens.normalize(t["name"]): t for t in await database.list_tags(chat_id)}
    tag = existing.get(key)
    created = tag is None
    if tag is None:
        tag = await database.create_tag(
            chat_id=chat_id,
            name=name,
            meaning=str(payload.get("meaning") or ""),
            # The form always sends a palette colour; the schema default is only
            # a backstop for a caller that omits it.
            color=str(payload.get("color") or "#8b5cf6"),
            icon=payload.get("icon") or None,
        )

    if action.job_id:
        await database.attach_job_tag(action.job_id, tag["id"])
        suffix = f" and tagged job_{action.job_id[-4:]}"
    else:
        suffix = ""

    verb = "Created" if created else "Reused existing tag"
    return responses.action_ack(f"{verb} #{tag['name']}{suffix}.", job_id=action.job_id)


async def _retry_job(chat_id: int, job_id: str | None) -> IntakeResponse:
    if not job_id:
        return responses.error("retry_job requires a job_id.", retryable=False)
    job = await database.get_job(job_id)
    if job is None or job["chat_id"] != chat_id:
        return responses.error("Job not found.", retryable=False)
    if job["status"] != "error":
        return responses.action_ack(
            f"job_{job_id[-4:]} isn't in an error state — nothing to retry.",
            job_id=job_id,
        )
    retried = await create_and_enqueue_job(
        chat_id,
        job["url"],
        job["content_type"],
        template=job.get("template"),
        freestyle_prompt=job.get("freestyle_prompt"),
        skip_cache=True,
    )
    return responses.action_ack(
        f"Retrying job_{retried['id'][-4:]}.",
        job_id=retried["id"],
    )

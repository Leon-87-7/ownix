"""Generic dashboard actions — the replacement for Telegram inline keyboards.

`POST /api/intake/action` (src/api/intake.py) builds an `IntakeMessage` whose
`idempotency_key` is deterministically `f"action:{action_id}"`, so the
router's existing per-(actor, idempotency_key) cache already gives "a
double-fired action does not double-apply" for free — this module only needs
to implement the actual per-`kind` effect, not its own idempotency tracking.
"""

from __future__ import annotations

from src import database
from src.intake import commands, responses
from src.intake.models import IntakeMessage
from src.intake.models import IntakeResponse
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

    return responses.unsupported(f"Unknown action: {action.kind}")


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
        chat_id, job["url"], job["content_type"], skip_cache=True
    )
    return responses.action_ack(
        f"Retrying job_{retried['id'][-4:]}.",
        job_id=retried["id"],
    )

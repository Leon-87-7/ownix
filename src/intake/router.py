"""Channel-neutral intake router (plan §"Intake Message Contract" /
§"Architecture Direction").

Receives an `IntakeMessage` from any adapter and returns an `IntakeResponse`.
Must never import FastAPI/Starlette/Telegram types, and must never branch on
`metadata` to make a core routing decision (`metadata` is channel-private
scratch space per the contract).

Ownership stays `chat_id`-keyed in this batch (plan Non-Goals — the `user_id`
migration is Phase 9, deferred), so every routing decision below keys off
`actor.legacy_chat_id`, not `actor.user_id`.
"""

from __future__ import annotations

from src import database
from src.intake import commands, idempotency, responses
from src.intake.models import SCHEMA_VERSION, IntakeMessage, IntakeResponse
from src.services.jobs import create_and_enqueue_job
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline, normalize_repo_url

log = get_logger(__name__)


def actor_key(msg: IntakeMessage) -> str:
    """Stable per-actor key for idempotency/rate-limit scoping."""
    if msg.actor.legacy_chat_id is not None:
        return f"chat:{msg.actor.legacy_chat_id}"
    return f"user:{msg.actor.user_id}"


async def handle(msg: IntakeMessage) -> IntakeResponse:
    if msg.schema_version != SCHEMA_VERSION:
        return responses.unknown_schema_version(msg.schema_version)

    key = actor_key(msg)

    if msg.idempotency_key:
        cached = await idempotency.get_cached(key, msg.idempotency_key)
        if cached is not None:
            return IntakeResponse.model_validate(cached)

    result = await _route(msg)

    if msg.idempotency_key:
        await idempotency.store(key, msg.idempotency_key, result.model_dump(mode="json"))
    return result


async def _route(msg: IntakeMessage) -> IntakeResponse:
    if msg.action is not None:
        from src.intake import actions

        return await actions.apply(msg)

    if msg.files:
        from src.intake import uploads

        return await uploads.handle_files(msg)

    chat_id = msg.actor.legacy_chat_id
    if chat_id is None:
        return responses.error("No owner resolved for this message.", retryable=False)

    url = (msg.url or "").strip()
    text = (msg.text or "").strip()

    if not url and text.startswith("/"):
        return await _dispatch_command(chat_id, text)

    candidate = url or text
    if not candidate:
        return responses.unsupported("Send a URL, a command, or upload a file.")

    pipeline = detect_pipeline(candidate, frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline in {"rejected", "document"}:
        # "document" (.pdf) is a file-shaped pipeline routed via the upload
        # endpoint, not a plain URL/text submit.
        return responses.unsupported(
            "Unsupported URL. Ownix accepts YouTube/Shorts, Reels, TikTok, "
            "Facebook/X video, allowlisted article domains, and GitHub repos."
        )

    url_for_job = normalize_repo_url(candidate) if pipeline == "repo" else candidate
    job = await create_and_enqueue_job(chat_id, url_for_job, pipeline)
    return responses.job_created(job, deduped=bool(job.get("_deduped")))


async def _dispatch_command(chat_id: int, text: str) -> IntakeResponse:
    parts = text.split()
    cmd = parts[0].lower()
    handler = commands.SHARED_COMMANDS.get(cmd)
    if handler is None:
        return responses.unsupported(f"Unknown or not-yet-migrated command: {cmd}")
    return await handler(chat_id, parts)


__all__ = ["handle", "actor_key"]

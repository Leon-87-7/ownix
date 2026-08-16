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

from urllib.parse import urlparse

from src import database
from src.intake import commands, idempotency, responses, tag_tokens
from src.intake.models import SCHEMA_VERSION, IntakeAction, IntakeMessage, IntakeResponse
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

    # A retryable response (transient upstream failure) must never be cached
    # under the caller's idempotency key — caching it would make the retry
    # this response is telling the caller to attempt just replay the same
    # failure forever instead of actually trying again.
    if msg.idempotency_key and not result.retryable:
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

    if not url and len(text) > 1 and text[0] == "-" and text[1].isalnum():
        return await commands.user_template_shortcut(chat_id, text)

    # Strip `#tag` tokens before anything else looks at the text — the whole
    # string used to reach `detect_pipeline`, so trailing tokens made an
    # otherwise-valid URL unparseable (issue #482).
    text, tag_names = tag_tokens.extract(text)

    candidate = url or text
    if not candidate:
        if tag_names:
            return responses.unsupported(
                f"#{tag_names[0]} on its own has nothing to attach to — "
                "send it with a URL or a file."
            )
        return responses.unsupported("Send a URL, a command, or upload a file.")

    pipeline = detect_pipeline(candidate, frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "document":
        return await _create_remote_document(chat_id, candidate)
    if pipeline == "rejected" and msg.intent == "article":
        parsed_candidate = urlparse(candidate)
        hostname = (parsed_candidate.hostname or "").lower()
        if parsed_candidate.scheme not in {"http", "https"} or not hostname:
            return responses.unsupported("Article capture needs a valid HTTP(S) URL.")
        # Consent is deliberately durable even when job creation/enqueue fails.
        await database.add_allowed_domain(chat_id, hostname)
        pipeline = "article"
    elif pipeline == "rejected" and msg.intent == "link":
        parsed_candidate = urlparse(candidate)
        if (
            parsed_candidate.scheme not in {"http", "https"}
            or not parsed_candidate.hostname
        ):
            return responses.unsupported("Link capture needs a valid HTTP(S) URL.")
        pipeline = "link"
    elif pipeline == "rejected" and msg.intent == "document":
        return await _create_remote_document(chat_id, candidate, require_document_path=False)
    elif pipeline == "rejected":
        return responses.unsupported(
            "Unsupported URL. Ownix accepts YouTube/Shorts, Reels, TikTok, "
            "Facebook/X video, allowlisted article domains, and GitHub repos."
        )

    url_for_job = normalize_repo_url(candidate) if pipeline == "repo" else candidate
    job = await create_and_enqueue_job(chat_id, url_for_job, pipeline)
    result = responses.job_created(job, deduped=bool(job.get("_deduped")))
    if tag_names:
        result = await apply_tag_tokens(chat_id, job["id"], tag_names, result)
    return result


async def _create_remote_document(
    chat_id: int, url: str, *, require_document_path: bool = True
) -> IntakeResponse:
    from src.services.document_intake import DocumentIntakeError, create_remote_document_job

    try:
        job = await create_remote_document_job(
            chat_id, url, require_document_path=require_document_path
        )
    except DocumentIntakeError as exc:
        return responses.error(exc.public_message, retryable=exc.status_code >= 500)
    return responses.job_created(
        {"id": job["job_id"], "content_type": job.get("content_type", "document")},
        deduped=bool(job.get("_deduped")),
    )


async def apply_tag_tokens(
    chat_id: int,
    job_id: str,
    names: list[str],
    result: IntakeResponse,
) -> IntakeResponse:
    """Attach every token that names an existing tag; report the rest.

    Matching is on the normalized key, so `#readlater` finds an existing
    "Read Later" instead of reading as a new tag (CONTEXT.md "Tag token").
    An unmatched name never fails the submit — the job is already created.
    """
    existing = tag_tokens.groups(await database.list_tags(chat_id))

    attached: list[str] = []
    unknown: list[str] = []
    ambiguous: list[str] = []
    invalid: list[str] = []
    failed: list[str] = []
    for name in names:
        key = tag_tokens.normalize(name)
        if not key:
            invalid.append(name)
            continue
        matches = existing.get(key, [])
        if not matches:
            unknown.append(name)
            continue
        if len(matches) > 1:
            ambiguous.append(name)
            continue
        tag = matches[0]
        try:
            await database.attach_job_tag(job_id, tag["id"])
        except Exception:
            log.exception("intake.tag_attachment_failed", job_id=job_id, tag_id=tag["id"])
            failed.append(name)
        else:
            attached.append(tag["name"])

    notes = []
    if attached:
        notes.append("Tagged " + ", ".join(f"#{n}" for n in attached) + ".")
    if unknown:
        notes.append("No tag named " + ", ".join(f"#{n}" for n in unknown) + " yet.")
    if ambiguous:
        notes.append("Ambiguous " + ", ".join(f"#{n}" for n in ambiguous) + ".")
    if invalid:
        notes.append("Invalid " + ", ".join(f"#{n}" for n in invalid) + ".")
    if failed:
        notes.append("Could not attach " + ", ".join(f"#{n}" for n in failed) + ".")

    # One offer per unknown name. The console opens them one at a time, so each
    # save is its own committed step — cancelling the second never rolls back
    # the first (issue #489).
    offers = [
        IntakeAction(
            action_id=f"create_tag:{job_id}:{tag_tokens.normalize(name)}",
            kind="create_tag",
            label=f"Create #{name}",
            job_id=job_id,
            payload={"tag_name": name},
        )
        for name in unknown
    ]

    update: dict = {}
    update["tag_outcome"] = {
        "attached": attached, "unknown": unknown, "ambiguous": ambiguous,
        "invalid": invalid, "failed": failed,
    }
    if notes:
        update["text"] = f"{result.text} " + " ".join(notes)
    if offers:
        update["actions"] = [*result.actions, *offers]
    return result.model_copy(update=update) if update else result


async def _dispatch_command(chat_id: int, text: str) -> IntakeResponse:
    parts = text.split()
    cmd = parts[0].lower()
    command = commands.SHARED_COMMANDS.get(cmd)
    if command is None:
        return responses.unsupported(f"Unknown or not-yet-migrated command: {cmd}")
    return await command.handler(chat_id, parts)


__all__ = ["actor_key", "apply_tag_tokens", "handle"]

"""Shared command bodies usable by any intake channel.

Only command behavior that is genuinely channel-agnostic lives here. Anything
that depends on Telegram-specific transport (callback acks, message editing,
`file_id` downloads, Markdown-vs-plain formatting, Mini App buttons) stays in
`src/telegram/webhook.py` per the plan's command-migration guidance — this
module holds the shared remainder, not a rewrite of the whole `_SLASH_TABLE`.

`src/telegram/webhook.py`'s `_cmd_cancel` delegates to `cancel_pending` here so
the two channels can't drift on that one. `_cmd_help` deliberately does *not*:
Telegram keeps its own `_HELP_TEXT` (`webhook.py:1030`) because it advertises
the full fourteen-entry `_SLASH_TABLE` in Markdown with emoji, while
`help_text()` below describes only what this channel actually accepts. Other
`_SLASH_TABLE` entries (`/find`, `/spec`, `/force`, `/allowlist`, …) are
Telegram-only for now and intentionally not migrated in this batch — each one
touches enough Telegram-specific plumbing (Gemini calls, Drive links, file
downloads) that moving it is its own reviewable slice, not a side effect of
wiring the shared router.

`SHARED_COMMANDS` is the single registry (issue #484): the `/intake` palette,
its argument hints, and `/help` are all derived from it, so a migrated command
becomes discoverable by landing rather than by someone remembering to edit a
second list.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.intake import responses, state
from src.intake.models import IntakeResponse
from src.utils.logger import get_logger

log = get_logger(__name__)

Handler = Callable[[int, list[str]], Awaitable[IntakeResponse]]


@dataclass(frozen=True)
class Command:
    """One shared command, with the metadata the palette needs to describe it."""

    name: str
    summary: str
    handler: Handler = field(compare=False)
    #: Argument hint shown after the name, e.g. `<query>`. Empty = takes none.
    args: str = ""

    @property
    def usage(self) -> str:
        return f"{self.name} {self.args}".strip()


async def cancel_pending(chat_id: int) -> IntakeResponse:
    """Clear any pending awaiting_intent/awaiting_freestyle state.

    Mirrors the reply text `src/telegram/webhook.py`'s `_cmd_cancel` already
    sends, so the two channels can't say different things for the same action.
    """
    pending = await state.get_state(chat_id)
    await state.clear_state(chat_id)
    if pending is None:
        return responses.command_result("Nothing to cancel.")
    if pending["mode"] == "awaiting_intent":
        return responses.command_result("Intent canceled.")
    if pending["mode"] == "awaiting_freestyle":
        return responses.command_result("Freestyle prompt abandoned.")
    return responses.command_result("Nothing to cancel.")


async def help_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    del chat_id, parts
    return responses.command_result(help_text())


async def cancel_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    del parts
    return await cancel_pending(chat_id)


#: Mirrors the thresholds `_cmd_find` used before the migration — score filter
#: from `settings.BRAIN_MIN_SCORE` isn't tight enough for a results list (it's
#: tuned for "related" suggestions elsewhere in Brain), so `/find` has always
#: applied its own, higher bar on top.
_FIND_MIN_SCORE = 0.58
_FIND_MAX_RESULTS = 5


async def find_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    """Second Brain search (issue #485). Channel-agnostic half of `/find`.

    Message formatting (HTML, emoji, Drive links) stays in
    `src/telegram/webhook.py:_cmd_find` — this returns `artifacts`, not
    preformatted text, so each channel renders its own presentation.

    Not tenant-scoped: neither was the Telegram command it replaces
    (`src/brain.py:search_links` takes no `chat_id`). See issue #459.
    """
    del chat_id
    if len(parts) < 2:
        return responses.command_result("Usage: /find <query>")

    query = " ".join(parts[1:]).strip()

    from src import brain
    from src.services.github import enrich_github_links

    candidates = await brain.search_links(query, top_k=10)
    results = [r for r in candidates if r["score"] >= _FIND_MIN_SCORE][:_FIND_MAX_RESULTS]
    if not results:
        return responses.command_result(f'Nothing found for "{query}".', actions=[])

    await enrich_github_links(results)  # mutates in place; no-ops non-GitHub URLs
    plural = "s" if len(results) != 1 else ""
    text = f'{len(results)} result{plural} for "{query}".'
    return IntakeResponse(kind="command_result", text=text, artifacts=results)


async def force_command(
    chat_id: int, parts: list[str], *, message_id: int | None = None
) -> IntakeResponse:
    """Force-reprocess a URL (issue #486). Migrated from `_cmd_force`.

    Not a pipeline override — there is no such argument. Three states, same as
    the Telegram original: reset + reprocess if a job already exists (bypassing
    `create_and_enqueue_job`'s dedup, which is the entire point of the
    command); clear an orphaned markdown-cache row if only that exists;
    otherwise detect the pipeline normally and create a job directly.

    `message_id` is Telegram-only metadata (which message to reply to), passed
    through as plain data rather than widening this into a Telegram-aware
    function — the dashboard simply omits it.
    """
    from src import database, queue
    from src.intake import tag_tokens
    from src.services.jobs import task_for_content_type
    from src.utils.validators import detect_pipeline, normalize_repo_url

    if len(parts) < 2:
        return responses.command_result("Usage: /force <url> [#tags]")
    url = parts[1]
    _, tag_names = tag_tokens.extract(" ".join(parts[2:]))
    if parts[2:] and len(tag_names) != len(parts[2:]):
        return responses.command_result("Usage: /force <url> [#tags]")

    async def with_tags(response: IntakeResponse, job_id: str) -> IntakeResponse:
        if not tag_names:
            return response
        # Local import avoids making router/commands module initialization circular.
        from src.intake.router import apply_tag_tokens
        return await apply_tag_tokens(chat_id, job_id, tag_names, response)

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(url, frozenset(extra_domains))
    lookup_url = normalize_repo_url(url) if pipeline == "repo" else url
    existing_job = (
        await database.find_recent_job_by_url(chat_id, lookup_url)
        if pipeline != "rejected"
        else None
    )
    existing_cache = await database.get_markdown_cache(url)

    if existing_job:
        if existing_cache:
            await database.delete_markdown_cache(url)
        job_id = existing_job["id"]
        await database.reset_job(job_id)
        task_type = task_for_content_type(existing_job.get("content_type"), default="video")
        if pipeline == "repo":
            try:
                path_parts = [s for s in urlparse(lookup_url).path.split("/") if s]
                owner_r, repo_r = path_parts[0], path_parts[1]
                redis_client = queue._client()
                await redis_client.delete(
                    f"github_repo_bundle:{owner_r}/{repo_r}",
                    f"github_meta:{owner_r}/{repo_r}",
                )
            except Exception:
                log.warning("force.repo_cache_clear_failed", url=lookup_url)
        await queue.enqueue({"task": task_type, "job_id": job_id})
        return await with_tags(
            responses.action_ack(f"Force-reprocessing job_{job_id[-4:]}.", job_id=job_id), job_id
        )

    if existing_cache:
        await database.delete_markdown_cache(url)

    if pipeline == "rejected":
        return responses.unsupported(
            "Unsupported URL. Ownix accepts YouTube/Shorts, Reels, TikTok, "
            "Facebook/X video, allowlisted article domains, and GitHub repos."
        )

    url_to_store = normalize_repo_url(url) if pipeline == "repo" else url
    job_id = await database.create_job(
        chat_id=chat_id, url=url_to_store, content_type=pipeline, message_id=message_id
    )
    task_type = task_for_content_type(pipeline, default="video")
    await queue.enqueue({"task": task_type, "job_id": job_id})
    return await with_tags(responses.job_created({"id": job_id, "content_type": pipeline}), job_id)


async def freestyle_command(
    chat_id: int, parts: list[str], *, message_id: int | None = None
) -> IntakeResponse:
    """`/freestyle <url>` — one-shot form only (issue #487).

    Migrated from `_cmd_freestyle` + `_handle_freestyle_url`. Bare `/freestyle`
    (no URL) arms a Telegram-only Redis continuation (`pending_template`) that
    the *next plain message* picks up outside command dispatch entirely — not
    migrated, see the issue's scoping comment.

    Arms `chat_state(mode='awaiting_freestyle')` for every pipeline except
    `repo` (explicitly excluded, same as the original) and `rejected`. This is
    the exact state `IntakeStateBanner` already renders — the dashboard could
    see the flow but never arm it before this.
    """
    from src import database, queue
    from src.utils.validators import detect_pipeline, normalize_repo_url

    if len(parts) < 2:
        return responses.command_result("Usage: /freestyle <url>")
    url = parts[1]

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(url, frozenset(extra_domains))
    if pipeline == "rejected":
        return responses.unsupported(
            "Unsupported URL. Ownix accepts YouTube/Shorts, Reels, TikTok, "
            "Facebook/X video, allowlisted article domains, and GitHub repos."
        )

    if pipeline == "repo":
        # Freestyle doesn't apply to repos — same fallback as the original:
        # a plain job, no template, no awaiting_freestyle state.
        repo_url = normalize_repo_url(url)
        existing = await database.find_recent_job_by_url(chat_id, repo_url)
        if existing:
            return responses.job_created(existing, deduped=True)
        job_id = await database.create_job(
            chat_id=chat_id, url=repo_url, content_type="repo", message_id=message_id
        )
        await queue.enqueue({"task": "repo", "job_id": job_id})
        return responses.job_created({"id": job_id, "content_type": "repo"})

    job_id = await database.create_job(
        chat_id=chat_id,
        url=url,
        content_type=pipeline,
        message_id=message_id,
        template="freestyle",
    )
    await database.update_job_status(job_id, "pending", template_detection_method="explicit_command")
    await state.set_state(chat_id, "awaiting_freestyle", job_id, expires_minutes=10)
    if pipeline == "long":
        await queue.enqueue({"task": "video", "job_id": job_id})
    return responses.job_created({"id": job_id, "content_type": pipeline})


_CHECKLISTS_CONTENT_TYPES = ("short", "long")
_CHECKLISTS_READY_STATUSES = ("transcript_done", "done")


async def checklists_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    """`/checklists <suffix>` — on-demand engineering-recommendation checklist.

    Channel-agnostic: reached identically from Telegram and the dashboard
    composer. One inline Gemini call, no lock, no queue (see
    docs/superpowers/plans/2026-08-11-checklists-command.md).
    """
    if len(parts) < 2:
        return responses.command_result("Usage: /checklists <suffix>")
    suffix = parts[1][-4:]

    from src import database
    from src.processors.checklists import run_checklists
    from src.services.gemini import GeminiUnavailableError

    rows = await database.find_jobs_by_suffix(chat_id, suffix)
    candidates = [
        j
        for j in rows
        if j["content_type"] in _CHECKLISTS_CONTENT_TYPES
        and j["status"] in _CHECKLISTS_READY_STATUSES
        and (j.get("transcript") or "").strip()
    ]
    if not candidates:
        return responses.error(f"No short/long job ending in {suffix} with a transcript ready.")

    job = candidates[0]
    try:
        _, md = await run_checklists(job)
    except GeminiUnavailableError:
        log.warning("checklists.gemini_failed", job_id=job["id"])
        return responses.error(
            "Checklist generation failed — Gemini is unavailable. Try again.", retryable=True
        )
    except Exception:
        log.exception("checklists.failed", job_id=job["id"])
        return responses.error("Checklist generation failed. Try again.", retryable=True)

    generated_at = datetime.now(timezone.utc).isoformat()
    await database.update_job_fields(
        job["id"], checklists_md=md, checklists_generated_at=generated_at
    )
    log.info("checklists.generated", job_id=job["id"], chat_id=chat_id)
    return IntakeResponse(kind="checklists_result", text=md, job_id=job["id"])


SHARED_COMMANDS: dict[str, Command] = {
    "/help": Command("/help", "this message", help_command),
    "/cancel": Command("/cancel", "cancel the current pending prompt", cancel_command),
    "/find": Command("/find", "search your processed content", find_command, args="<query>"),
    "/force": Command("/force", "reprocess a URL (skip cache)", force_command, args="<url>"),
    "/freestyle": Command(
        "/freestyle", "use a custom Gemini prompt for the next job", freestyle_command, args="<url>"
    ),
    "/checklists": Command(
        "/checklists",
        "engineering checklist from a short/long transcript",
        checklists_command,
        args="<suffix>",
    ),
}


def help_text() -> str:
    """Render `/help` from the registry, so it can't drift from what exists."""
    lines = ["Commands:"]
    lines += [f"{c.usage} — {c.summary}" for c in SHARED_COMMANDS.values()]
    return "\n".join(lines)


def palette() -> list[dict[str, str]]:
    """The command list `GET /api/intake/commands` serves to the palette."""
    return [
        {"name": c.name, "args": c.args, "summary": c.summary, "usage": c.usage}
        for c in SHARED_COMMANDS.values()
    ]

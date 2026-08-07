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

from src.intake import responses, state
from src.intake.models import IntakeResponse

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


SHARED_COMMANDS: dict[str, Command] = {
    "/help": Command("/help", "this message", help_command),
    "/cancel": Command("/cancel", "cancel the current pending prompt", cancel_command),
    "/find": Command("/find", "<query>", find_command),
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

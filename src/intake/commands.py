"""Shared command bodies usable by any intake channel.

Only command behavior that is genuinely channel-agnostic lives here. Anything
that depends on Telegram-specific transport (callback acks, message editing,
`file_id` downloads, Markdown-vs-plain formatting, Mini App buttons) stays in
`src/telegram/webhook.py` per the plan's command-migration guidance — this
module holds the shared remainder, not a rewrite of the whole `_SLASH_TABLE`.

`src/telegram/webhook.py`'s `_cmd_cancel` and `_cmd_help` delegate to
`cancel_pending`/`HELP_TEXT` here so the two channels can't drift; other
`_SLASH_TABLE` entries (`/find`, `/spec`, `/force`, `/allowlist`, …) are
Telegram-only for now and intentionally not migrated in this batch — each one
touches enough Telegram-specific plumbing (Gemini calls, Drive links, file
downloads) that moving it is its own reviewable slice, not a side effect of
wiring the shared router.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from src.intake import responses, state
from src.intake.models import IntakeResponse

HELP_TEXT = (
    "Commands:\n"
    "/help — this message\n"
    "/cancel — cancel the current pending prompt"
)


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
    return responses.command_result(HELP_TEXT)


async def cancel_command(chat_id: int, parts: list[str]) -> IntakeResponse:
    del parts
    return await cancel_pending(chat_id)


SHARED_COMMANDS: dict[str, Callable[[int, list[str]], Awaitable[IntakeResponse]]] = {
    "/help": help_command,
    "/cancel": cancel_command,
}

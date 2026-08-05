"""Telegram <-> IntakeMessage/IntakeResponse conversion (issue #477).

Converts an incoming Telegram `message` update into an `IntakeMessage` —
`idempotency_key` comes from the Telegram `update_id`, so redelivery of the
same webhook update can't double-create a job — and renders an
`IntakeResponse` back into a Telegram send operation.

This is the reusable conversion core. `src/telegram/webhook.py` still owns
everything genuinely Telegram-only: callback-query acks, message editing,
`file_id` downloads, inline-keyboard rendering, Markdown formatting, and
ops-bot transport (ADR-0036). Only `/cancel`'s pending-state lookup has been
switched to the shared `src.intake.state` module so far (see that command's
docstring) — this adapter is not yet wired into the webhook's main dispatch
loop for live URL/text traffic; that remains the next slice (see the
cloud-patch handoff summary for exactly what's left and why).
"""

from __future__ import annotations

from src.intake.models import IntakeActor, IntakeMessage, IntakeResponse
from src.telegram.sender import send_message


def update_to_intake_message(update: dict) -> IntakeMessage | None:
    """Convert a Telegram `message` update carrying plain text into an `IntakeMessage`.

    Returns None for updates this adapter doesn't handle (no `message`, no
    `text` — photos/documents/callback_query stay on their existing
    Telegram-only paths in webhook.py).
    """
    message = update.get("message")
    if not message:
        return None
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = message.get("text")
    if chat_id is None or not text:
        return None

    update_id = update.get("update_id")
    return IntakeMessage(
        idempotency_key=f"telegram:{update_id}" if update_id is not None else None,
        actor=IntakeActor(
            user_id=chat_id,
            channel_id=f"telegram:{chat_id}",
            channel_type="telegram",
            legacy_chat_id=chat_id,
        ),
        text=text.strip(),
        source_message_id=message.get("message_id"),
    )


async def render_response(chat_id: int, response: IntakeResponse) -> None:
    """Render an `IntakeResponse` as a plain Telegram message.

    `response.actions` are not rendered here — inline-keyboard actions stay
    on the existing `send_inline_keyboard` call sites in webhook.py until a
    command that needs them is actually migrated.
    """
    await send_message(chat_id, response.text)

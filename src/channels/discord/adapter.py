"""Discord DM conversion into the channel-neutral intake contract."""

from __future__ import annotations

from src.intake.models import IntakeActor, IntakeMessage, IntakeResponse


def message_to_intake_message(message, owner_id: int) -> IntakeMessage:
    sender_id = str(message.author.id)
    return IntakeMessage(
        idempotency_key=f"discord:{message.id}",
        actor=IntakeActor(
            user_id=owner_id,
            channel_id=f"discord:{sender_id}",
            channel_type="discord",
            legacy_chat_id=owner_id,
        ),
        text=(message.content or "").strip(),
        source_message_id=str(message.id),
    )


async def render_response(message, response: IntakeResponse) -> None:
    await message.channel.send(response.text)

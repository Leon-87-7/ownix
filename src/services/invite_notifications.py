"""Invite-gate operator notifications shared by Telegram and web auth flows."""

from __future__ import annotations

from src import database
from src.config import settings
from src.telegram.sender import send_inline_keyboard
from src.utils.logger import get_logger

log = get_logger(__name__)


async def notify_operator_invite(chat_id: int, email: str) -> bool:
    """Send the operator an approval/block keyboard for a pending invite."""
    operator_chat_id = settings.OPERATOR_CHAT_ID
    if operator_chat_id is None:
        log.warning("invite.operator_chat_id_unset", chat_id=chat_id)
        return False

    user = await database.get_user(chat_id) or {}
    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    name = " ".join(part for part in (first, last) if part).strip() or str(chat_id)
    username = (user.get("username") or "unknown").lstrip("@")
    await send_inline_keyboard(
        operator_chat_id,
        f"👤 {name} · {email} · @{username}",
        buttons=[
            [
                {"text": "✅ Approve", "callback_data": f"invite_approve:{chat_id}"},
                {"text": "🚫 Block", "callback_data": f"invite_block:{chat_id}"},
            ]
        ],
    )
    return True

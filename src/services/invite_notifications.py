"""Invite-gate operator notifications shared by Telegram and web auth flows."""

from __future__ import annotations

from src.config import settings
from src.services import ops_bot
from src.utils.logger import get_logger

log = get_logger(__name__)


async def notify_operator_invite(chat_id: int, email: str, *, dev: bool = False) -> bool:
    """Send Ops bot approval/block keyboards for a pending invite."""
    if dev and not settings.OPS_DEV_NOTIFICATIONS:
        log.info("invite.dev_notification_quiet", chat_id=chat_id)
        return False
    if not settings.OPS_BOT_TOKEN:
        log.warning("invite.ops_bot_token_unset", chat_id=chat_id, dev=dev)
        return False
    return await ops_bot.notify_invite(chat_id, email, dev=dev)

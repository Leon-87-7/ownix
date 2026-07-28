"""Best-effort transactional email helpers."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


def _feed_url() -> str | None:
    base = settings.DASHBOARD_URL.strip().rstrip("/")
    if not base:
        return None
    return f"{base}/feed"


def _display_name(user: dict) -> str:
    return (
        " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x).strip()
        or "there"
    )


def _smtp_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def _send_email_sync(message: EmailMessage) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def send_welcome_email(user: dict) -> bool:
    """Send an approval welcome email with the user's Feed URL."""
    email = (user.get("email") or "").strip()
    feed_url = _feed_url()
    if not email or not feed_url:
        log.info(
            "welcome_email_skipped",
            tg_id=user.get("tg_id"),
            has_email=bool(email),
            has_dashboard_url=bool(feed_url),
        )
        return False
    if not _smtp_configured():
        log.info("welcome_email_smtp_unconfigured", tg_id=user.get("tg_id"))
        return False

    name = _display_name(user)
    message = EmailMessage()
    message["Subject"] = "You're in - your Ownix Feed is live"
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Hi {name},",
                "",
                "You're in - welcome to Ownix.",
                "",
                "Your Feed is live here:",
                feed_url,
                "",
                (
                    "Send the Ownix Telegram bot any link you want to save. "
                    "We'll process it and add it to your Feed."
                ),
                "",
                "Leon",
            ]
        )
    )
    await asyncio.to_thread(_send_email_sync, message)
    log.info("welcome_email_sent", tg_id=user.get("tg_id"), email=email)
    return True

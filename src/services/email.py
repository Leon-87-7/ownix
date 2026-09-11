"""Best-effort transactional email helpers."""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

import dns.exception
import dns.resolver

from src import database
from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


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


def _domain_accepts_mail_sync(domain: str) -> bool:
    """MX lookup; also rejects RFC 7505 Null MX (domain explicitly refuses mail)."""
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
    except dns.exception.DNSException:
        return False
    return not (len(answers) == 1 and str(answers[0].exchange) == ".")


def _send_email_sync(message: EmailMessage) -> None:
    # Magic-link mail carries a bearer token, so a plaintext hop off this host
    # would leak it (CWE-319). Only a loopback relay may skip STARTTLS.
    if not settings.SMTP_STARTTLS and settings.SMTP_HOST not in _LOOPBACK_HOSTS:
        raise RuntimeError("SMTP_STARTTLS is required for a non-loopback SMTP relay")
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_STARTTLS:
            # Default context verifies the cert and hostname; smtplib's own
            # fallback does neither, so STARTTLS alone would not stop a MITM.
            smtp.starttls(context=ssl.create_default_context())
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

    domain = email.rsplit("@", 1)[-1]
    if not await asyncio.to_thread(_domain_accepts_mail_sync, domain):
        log.warning("welcome_email_domain_unreachable", tg_id=user.get("tg_id"), domain=domain)
        tg_id = user.get("tg_id")
        if tg_id is not None:
            await database.set_user_status(int(tg_id), "blocked")
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


async def send_magic_link_email(email: str, link: str) -> bool:
    """Send a one-time sign-in link without revealing account existence."""
    if not _smtp_configured():
        log.info("magic_link_email_smtp_unconfigured")
        return False
    domain = email.rsplit("@", 1)[-1]
    if not await asyncio.to_thread(_domain_accepts_mail_sync, domain):
        log.warning("magic_link_email_domain_unreachable", domain=domain)
        return False
    message = EmailMessage()
    message["Subject"] = "Your Ownix sign-in link"
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = email
    message.set_content(
        f"Use this one-time link to sign in to Ownix:\n\n{link}\n\n"
        "It expires in 15 minutes and can only be used once."
    )
    await asyncio.to_thread(_send_email_sync, message)
    # Domain only — the full address in a retained log is a sign-in trail
    # linking a person to this account (CWE-532).
    log.info("magic_link_email_sent", domain=domain)
    return True

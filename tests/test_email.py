from __future__ import annotations

from email.message import EmailMessage

import pytest

from src.services import email as email_service


async def test_welcome_email_skips_when_smtp_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "")

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is False


async def test_welcome_email_sends_feed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[EmailMessage] = []

    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example/")
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "smtp.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_PORT", 587)
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "hello@ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_NAME", "Ownix")
    monkeypatch.setattr("src.services.email._send_email_sync", sent.append)

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is True

    assert len(sent) == 1
    message = sent[0]
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "You're in - your Ownix Feed is live"
    content = message.get_content()
    assert "You're in - welcome to Ownix." in content
    assert "Your Feed is live here:\nhttps://ownix.example/feed" in content
    assert (
        "Send the Ownix Telegram bot any link you want to save. We'll process it and add it to your Feed."
        in content
    )

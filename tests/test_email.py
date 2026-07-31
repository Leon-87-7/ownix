from __future__ import annotations

from email.message import EmailMessage

import pytest

from src.services import email as email_service


def _configure_smtp(monkeypatch: pytest.MonkeyPatch, sent: list[EmailMessage]) -> None:
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "smtp.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_PORT", 587)
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "hello@ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_NAME", "Ownix")
    monkeypatch.setattr("src.services.email._send_email_sync", sent.append)


# --- Welcome (onboarding) email -------------------------------------------


async def test_welcome_email_skips_when_smtp_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "")

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is False


async def test_welcome_email_does_not_require_feed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The onboarding email fires pre-approval, so it must not depend on a Feed URL."""
    sent: list[EmailMessage] = []
    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "")
    _configure_smtp(monkeypatch, sent)

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is True
    assert len(sent) == 1


async def test_welcome_email_onboards_pending_user(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[EmailMessage] = []
    _configure_smtp(monkeypatch, sent)

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is True

    message = sent[0]
    assert message["To"] == "user@example.com"
    assert message["Subject"] == "Welcome to Ownix, Ada — here's the quick tour"

    text = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()

    # The four day-to-day features are introduced in both bodies.
    for feature_title in (
        "Add from anywhere",
        "Your Link Table",
        "Tags that mean something",
        "Settings, your way",
    ):
        assert feature_title in text
        assert feature_title in html
    assert "OwnixAdd" in text and "OwnixAdd" in html

    # Pre-approval framing: sets expectation, promises no Feed access yet.
    assert "on the list" in text.lower()
    assert "requesting access to Ownix" in text
    assert "requesting access to Ownix" in html
    # No "your Feed is live" claim and no Feed button in the onboarding email.
    assert "Feed is live" not in text
    assert "Open your Feed" not in html

    # Personal note from the developer, with name, role, and links.
    assert email_service.DEVELOPER_NAME in text and email_service.DEVELOPER_NAME in html
    assert email_service.DEVELOPER_ROLE in text
    assert email_service.DEVELOPER_GITHUB_URL in text and email_service.DEVELOPER_GITHUB_URL in html
    assert email_service.DEVELOPER_LINKEDIN_URL in text
    assert email_service.DEVELOPER_LINKEDIN_URL in html


async def test_welcome_email_subject_without_first_name(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[EmailMessage] = []
    _configure_smtp(monkeypatch, sent)

    assert await email_service.send_welcome_email(
        {"tg_id": 2, "email": "noname@example.com"}
    ) is True

    assert sent[0]["Subject"] == "Welcome to Ownix — here's the quick tour"
    assert "Hi there," in sent[0].get_body(preferencelist=("plain",)).get_content()


# --- Feed-ready (approval) email ------------------------------------------


async def test_feed_ready_email_skips_when_smtp_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "")

    assert await email_service.send_feed_ready_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is False


async def test_feed_ready_email_skips_without_dashboard_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[EmailMessage] = []
    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "")
    _configure_smtp(monkeypatch, sent)

    assert await email_service.send_feed_ready_email(
        {"tg_id": 1, "email": "user@example.com", "first_name": "Ada"}
    ) is False
    assert sent == []


async def test_feed_ready_email_sends_feed_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The approval notice is unchanged from its original bare behavior."""
    sent: list[EmailMessage] = []
    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example/")
    _configure_smtp(monkeypatch, sent)

    assert await email_service.send_feed_ready_email(
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
        "Send the Ownix Telegram bot any link you want to save. "
        "We'll process it and add it to your Feed." in content
    )

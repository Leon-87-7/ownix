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
    assert message["Subject"] == "Welcome to Ownix, Ada — here's how to get started"

    # Multipart: plain-text fallback + HTML alternative.
    text_part = message.get_body(preferencelist=("plain",))
    html_part = message.get_body(preferencelist=("html",))
    assert text_part is not None and html_part is not None
    text = text_part.get_content()
    html = html_part.get_content()

    # Feed CTA is present in both bodies.
    assert "https://ownix.example/feed" in text
    assert "https://ownix.example/feed" in html

    # The four day-to-day features are introduced.
    for feature_title in (
        "Add from anywhere",
        "Your Link Table",
        "Tags that mean something",
        "Settings, your way",
    ):
        assert feature_title in text
        assert feature_title in html

    # In-app ingest keys and the mobile OwnixAdd button are named.
    assert "OwnixAdd" in text
    assert "OwnixAdd" in html

    # Personal note from the developer, with name, role, and links.
    assert "note from the developer".lower() in text.lower()
    assert email_service.DEVELOPER_NAME in text
    assert email_service.DEVELOPER_NAME in html
    assert email_service.DEVELOPER_ROLE in text
    assert email_service.DEVELOPER_GITHUB_URL in text
    assert email_service.DEVELOPER_GITHUB_URL in html
    assert email_service.DEVELOPER_LINKEDIN_URL in text
    assert email_service.DEVELOPER_LINKEDIN_URL in html


async def test_welcome_email_subject_without_first_name(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[EmailMessage] = []

    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "smtp.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "hello@ownix.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_NAME", "Ownix")
    monkeypatch.setattr("src.services.email._send_email_sync", sent.append)

    assert await email_service.send_welcome_email(
        {"tg_id": 2, "email": "noname@example.com"}
    ) is True

    assert sent[0]["Subject"] == "Welcome to Ownix — here's how to get started"
    # Falls back to a friendly greeting when no name is on file.
    assert "Hi there," in sent[0].get_body(preferencelist=("plain",)).get_content()

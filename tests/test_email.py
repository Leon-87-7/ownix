from __future__ import annotations

from email.message import EmailMessage

import dns.exception
import pytest

from src.services import email as email_service


class _MxRecord:
    def __init__(self, exchange: str) -> None:
        self.exchange = exchange


def test_domain_accepts_mail_when_mx_records_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve(domain: str, record_type: str, lifetime: int) -> list[_MxRecord]:
        assert domain == "realmail.example"
        assert record_type == "MX"
        assert lifetime == 5
        return [_MxRecord("mail.realmail.example.")]

    monkeypatch.setattr("src.services.email.dns.resolver.resolve", fake_resolve)

    assert email_service._domain_accepts_mail_sync("realmail.example") is True


def test_domain_rejects_rfc7505_null_mx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.services.email.dns.resolver.resolve",
        lambda domain, record_type, lifetime: [_MxRecord(".")],
    )

    assert email_service._domain_accepts_mail_sync("nomail.example") is False


def test_domain_rejects_dns_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_resolve(domain: str, record_type: str, lifetime: int) -> list[_MxRecord]:
        raise dns.exception.Timeout

    monkeypatch.setattr("src.services.email.dns.resolver.resolve", fail_resolve)

    assert email_service._domain_accepts_mail_sync("missing.example") is False


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
    monkeypatch.setattr("src.services.email._domain_accepts_mail_sync", lambda domain: True)
    monkeypatch.setattr("src.services.email._send_email_sync", sent.append)

    assert await email_service.send_welcome_email(
        {"tg_id": 1, "email": "user@realmail.example", "first_name": "Ada"}
    ) is True

    assert len(sent) == 1
    message = sent[0]
    assert message["To"] == "user@realmail.example"
    assert message["Subject"] == "You're in - your Ownix Feed is live"
    content = message.get_content()
    assert "You're in - welcome to Ownix." in content
    assert "Your Feed is live here:\nhttps://ownix.example/feed" in content
    assert (
        "Send the Ownix Telegram bot any link you want to save. We'll process it and add it to your Feed."
        in content
    )


async def test_welcome_email_blocks_user_when_domain_has_no_mx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked: list[tuple[int, str]] = []
    sent: list[EmailMessage] = []

    monkeypatch.setattr("src.services.email.settings.DASHBOARD_URL", "https://ownix.example/")
    monkeypatch.setattr("src.services.email.settings.SMTP_HOST", "smtp.example")
    monkeypatch.setattr("src.services.email.settings.SMTP_FROM_EMAIL", "hello@ownix.example")
    monkeypatch.setattr("src.services.email._domain_accepts_mail_sync", lambda domain: False)
    monkeypatch.setattr("src.services.email._send_email_sync", sent.append)

    async def fake_set_user_status(tg_id: int, status: str) -> None:
        blocked.append((tg_id, status))

    monkeypatch.setattr("src.services.email.database.set_user_status", fake_set_user_status)

    assert await email_service.send_welcome_email(
        {"tg_id": 7, "email": "first@example.com", "first_name": "Ada"}
    ) is False

    assert blocked == [(7, "blocked")]
    assert sent == []

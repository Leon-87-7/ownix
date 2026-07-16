"""Unit tests for src/config.py — startup validation guards."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings


def _base_env(**overrides: str) -> dict[str, str]:
    env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_WEBHOOK_SECRET": "s3cr3t"}
    env.update(overrides)
    return env


def test_settings_rejects_empty_webhook_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_WEBHOOK_SECRET=""))


def test_settings_rejects_empty_bot_token() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_BOT_TOKEN=""))


def test_settings_accepts_nonempty_required_fields() -> None:
    s = Settings(**_base_env())
    assert s.TELEGRAM_WEBHOOK_SECRET == "s3cr3t"
    assert s.TELEGRAM_BOT_TOKEN == "123:ABC"


def test_settings_loads_local_env_file_after_base_env(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_DRIVE_FOLDER_BRAIN", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    base_env = tmp_path / ".env"
    local_env = tmp_path / ".env.local"
    base_env.write_text(
        "\n".join(
            [
                "TELEGRAM_BOT_TOKEN=123:ABC",
                "TELEGRAM_WEBHOOK_SECRET=s3cr3t",
                "GOOGLE_DRIVE_FOLDER_BRAIN=prod-folder",
                "DB_PATH=/app/data/jobs.db",
            ]
        ),
        encoding="utf-8",
    )
    local_env.write_text(
        "\n".join(
            [
                "GOOGLE_DRIVE_FOLDER_BRAIN=",
                "DB_PATH=./data/local-dev.db",
            ]
        ),
        encoding="utf-8",
    )

    s = Settings(_env_file=(base_env, local_env))

    assert s.GOOGLE_DRIVE_FOLDER_BRAIN == ""
    assert s.DB_PATH == "./data/local-dev.db"

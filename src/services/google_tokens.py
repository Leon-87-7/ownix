"""Encrypted per-user Google OAuth token store."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import sqlite3
from cryptography.fernet import Fernet

from src import database
from src.config import settings


def _fernet() -> Fernet:
    raw = settings.GOOGLE_TOKEN_ENCRYPTION_KEY or settings.TELEGRAM_WEBHOOK_SECRET
    if not raw:
        raise RuntimeError("GOOGLE_TOKEN_ENCRYPTION_KEY is required for per-user Google tokens")
    try:
        return Fernet(raw.encode())
    except Exception:
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
        return Fernet(key)


def encrypt_token(payload: dict[str, Any]) -> str:
    return _fernet().encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decrypt_token(ciphertext: str) -> dict[str, Any]:
    return json.loads(_fernet().decrypt(ciphertext.encode()).decode())


async def store_google_token(chat_id: int, token_payload: dict[str, Any]) -> None:
    encrypted = encrypt_token(token_payload)
    async with database.connection() as conn:
        await conn.execute(
            """
            INSERT INTO google_oauth_tokens (chat_id, encrypted_token, scopes, updated_at, revoked_notified_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, NULL)
            ON CONFLICT(chat_id) DO UPDATE SET
                encrypted_token = excluded.encrypted_token,
                scopes = excluded.scopes,
                updated_at = excluded.updated_at,
                revoked_notified_at = NULL
            """,
            (chat_id, encrypted, " ".join(token_payload.get("scopes") or [])),
        )
        await conn.commit()


async def load_google_token(chat_id: int) -> dict[str, Any] | None:
    row = await database._fetch_one("SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ?", (chat_id,))
    if row is None:
        return None
    return decrypt_token(row["encrypted_token"])


async def delete_google_token(chat_id: int) -> None:
    await database._execute("DELETE FROM google_oauth_tokens WHERE chat_id = ?", (chat_id,))


def load_google_token_sync(chat_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            return decrypt_token(row["encrypted_token"]) if row else None
    except Exception:
        return None


def has_google_connection_sync(chat_id: int) -> bool:
    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            cur = conn.execute("SELECT 1 FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1", (chat_id,))
            return cur.fetchone() is not None
    except Exception:
        return False

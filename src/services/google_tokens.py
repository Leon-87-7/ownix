"""Encrypted per-user Google OAuth token store."""
from __future__ import annotations

import json
from typing import Any

import sqlite3
from cryptography.fernet import Fernet, InvalidToken

from src import database
from src.config import settings
from src.utils.google_token_crypto import google_token_fernet
from src.utils.logger import get_logger

log = get_logger(__name__)


def _fernet() -> Fernet:
    return google_token_fernet(settings.GOOGLE_TOKEN_ENCRYPTION_KEY)


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
    try:
        return decrypt_token(row["encrypted_token"])
    except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError):
        log.warning("google_token_load_invalid", chat_id=chat_id)
        return None


async def delete_google_token(chat_id: int) -> bool:
    return await database._execute_rowcount("DELETE FROM google_oauth_tokens WHERE chat_id = ?", (chat_id,)) > 0


async def store_google_oauth_state(state: str, chat_id: int, *, ttl_seconds: int = 600) -> None:
    async with database.connection() as conn:
        await conn.execute("DELETE FROM google_oauth_states WHERE expires_at <= CURRENT_TIMESTAMP")
        await conn.execute(
            """
            INSERT OR REPLACE INTO google_oauth_states (state, chat_id, expires_at)
            VALUES (?, ?, datetime('now', ? || ' seconds'))
            """,
            (state, chat_id, ttl_seconds),
        )
        await conn.commit()


async def consume_google_oauth_state(state: str) -> int | None:
    async with database.connection() as conn:
        cur = await conn.execute(
            """
            DELETE FROM google_oauth_states
            WHERE state = ? AND expires_at > CURRENT_TIMESTAMP
            RETURNING chat_id
            """,
            (state,),
        )
        row = await cur.fetchone()
        await conn.execute("DELETE FROM google_oauth_states WHERE expires_at <= CURRENT_TIMESTAMP")
        await conn.commit()
        return int(row["chat_id"]) if row else None


def load_google_token_sync(chat_id: int) -> dict[str, Any] | None:
    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT encrypted_token FROM google_oauth_tokens WHERE chat_id = ? LIMIT 1", (chat_id,))
            row = cur.fetchone()
            return decrypt_token(row["encrypted_token"]) if row else None
    except sqlite3.Error:
        log.exception("google_token_sync_load_db_failed", chat_id=chat_id)
        return None
    except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError):
        log.warning("google_token_sync_load_invalid", chat_id=chat_id)
        return None


def has_google_connection_sync(chat_id: int) -> bool:
    return load_google_token_sync(chat_id) is not None

"""Shared Google API auth and OAuth token lifecycle (Drive, Sheets, GCS)."""
from __future__ import annotations

import os
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings
from src.services.google_tokens import delete_google_token, load_google_token, load_google_token_sync
from src.telegram import sender
from src.utils.logger import get_logger

log = get_logger(__name__)

GOOGLE_EXPORT_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


async def handle_google_refresh_error(chat_id: int | None) -> bool:
    """Delete a revoked Google token and send the reconnect prompt at most once."""
    if chat_id is None:
        return False
    should_notify = await delete_google_token(chat_id)
    if should_notify:
        try:
            await sender.send_message(
                chat_id,
                "Google export disconnected. Please /connect again to keep exporting to Drive/Sheets.",
            )
        except Exception:
            log.exception("google_reconnect_notification_failed", chat_id=chat_id)
    log.warning("google_oauth_refresh_invalid", chat_id=chat_id)
    return should_notify

async def revoke_google_refresh_token(refresh_token: str) -> None:
    """Best-effort Google token revocation; local disconnect must still complete."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post("https://oauth2.googleapis.com/revoke", data={"token": refresh_token})
    except Exception:
        log.exception("google_oauth_revoke_failed")


async def disconnect_google(chat_id: int) -> None:
    token_payload = await load_google_token(chat_id)
    if token_payload and token_payload.get("refresh_token"):
        await revoke_google_refresh_token(token_payload["refresh_token"])
    await delete_google_token(chat_id)


def build_google_credentials(
    scopes: list[str], *, prefer_service_account: bool = False, chat_id: int | None = None
) -> Any:
    """Build authenticated Google credentials for the given scopes.

    Per-user tokens are encrypted in ``google_oauth_tokens`` and win when a
    chat_id is supplied. Otherwise preserve the legacy operator env/service
    account fallback.
    """
    if chat_id is not None:
        token_payload = load_google_token_sync(chat_id)
        if token_payload:
            creds = Credentials(
                token=None,
                refresh_token=token_payload["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=token_payload.get("client_id") or settings.GOOGLE_OAUTH_CLIENT_ID,
                client_secret=token_payload.get("client_secret") or settings.GOOGLE_OAUTH_CLIENT_SECRET,
                scopes=scopes,
            )
            creds.refresh(Request())
            return creds

    if prefer_service_account and os.path.exists(settings.GOOGLE_SERVICE_ACCOUNT_JSON):
        return service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
        )
    if settings.GOOGLE_OAUTH_REFRESH_TOKEN:
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=scopes,
        )
        creds.refresh(Request())
        return creds
    return service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
    )


def build_google_service(
    api: str, version: str, scopes: list[str], *, chat_id: int | None = None
) -> Any:
    """Build an authenticated Google API discovery client (Drive, Sheets)."""
    creds = build_google_credentials(scopes, chat_id=chat_id)
    return build(api, version, credentials=creds, cache_discovery=False)

"""Shared Google API auth (Drive, Sheets, GCS)."""
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings


def build_google_credentials(
    scopes: list[str], *, prefer_service_account: bool = False
) -> Any:
    """Build authenticated Google credentials for the given scopes.

    Default order: OAuth refresh token (required for personal accounts) →
    service-account fallback (Shared Drives / Workspace).

    `prefer_service_account` flips the order for GCS: an existing Drive/Sheets
    OAuth refresh token does NOT carry the storage scope and can't be widened,
    so storage prefers the service account when its key file is present. See
    docs/handoff/gcs-setup.md.
    """
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


def build_google_service(api: str, version: str, scopes: list[str]) -> Any:
    """Build an authenticated Google API discovery client (Drive, Sheets)."""
    creds = build_google_credentials(scopes)
    return build(api, version, credentials=creds, cache_discovery=False)

"""Shared Google API service builder (Drive, Sheets)."""
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src.config import settings


def build_google_service(api: str, version: str, scopes: list[str]) -> Any:
    """Build an authenticated Google API client.

    Prefers the OAuth refresh token (required for personal accounts); falls
    back to the service account (Shared Drives / Workspace).
    """
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
    else:
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes
        )
    return build(api, version, credentials=creds, cache_discovery=False)

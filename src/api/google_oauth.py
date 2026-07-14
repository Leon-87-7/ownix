"""Per-user Google OAuth endpoints."""
from __future__ import annotations

import asyncio
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.config import settings
from src.services.google_auth import disconnect_google
from src.services.google_tokens import (
    consume_google_oauth_state,
    load_google_token,
    store_google_oauth_state,
    store_google_token,
)
from src.services.google_workspace import user_folder_id

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

google_oauth_router = APIRouter(prefix="/api/google", tags=["google-oauth"])


def _redirect_uri(request: Request) -> str:
    return settings.GOOGLE_OAUTH_REDIRECT_URI or str(request.url_for("google_oauth_callback"))


def _require_google_oauth_config() -> None:
    if (
        not settings.GOOGLE_OAUTH_CLIENT_ID
        or not settings.GOOGLE_OAUTH_CLIENT_SECRET
        or not settings.GOOGLE_TOKEN_ENCRYPTION_KEY
    ):
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")


@google_oauth_router.get("/connect")
async def connect_google(request: Request) -> RedirectResponse:
    _require_google_oauth_config()
    chat_id = int(request.state.user["id"])
    state = secrets.token_urlsafe(24)
    await store_google_oauth_state(state, chat_id)
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params),
        status_code=303,
        headers={"Referrer-Policy": "no-referrer"},
    )


@google_oauth_router.get("/callback", name="google_oauth_callback")
async def google_oauth_callback(
    request: Request, state: str, code: str | None = None, error: str | None = None
) -> RedirectResponse:
    _require_google_oauth_config()
    chat_id = await consume_google_oauth_state(state)
    if chat_id is None:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if error or not code:
        return RedirectResponse("/feed?google=denied", status_code=303)
    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "redirect_uri": _redirect_uri(request),
                "grant_type": "authorization_code",
            },
        )
    if res.status_code >= 400:
        raise HTTPException(status_code=400, detail="Google token exchange failed")
    data = res.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Google did not return a refresh token; try reconnecting")
    await store_google_token(chat_id, {
        "refresh_token": refresh_token,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "scopes": GOOGLE_SCOPES,
    })
    return RedirectResponse("/feed?google=connected", status_code=303)


@google_oauth_router.get("/status")
async def google_status(request: Request) -> dict:
    chat_id = int(request.state.user["id"])
    return {"connected": await load_google_token(chat_id) is not None}


@google_oauth_router.get("/folder")
async def google_folder(request: Request) -> dict:
    chat_id = int(request.state.user["id"])
    folder_id = await asyncio.to_thread(user_folder_id, chat_id)
    if not folder_id:
        raise HTTPException(status_code=404, detail="Google not connected")
    return {"folder_url": f"https://drive.google.com/drive/folders/{folder_id}"}


@google_oauth_router.post("/disconnect")
async def google_disconnect(request: Request) -> dict:
    chat_id = int(request.state.user["id"])
    await disconnect_google(chat_id)
    return {"connected": False}

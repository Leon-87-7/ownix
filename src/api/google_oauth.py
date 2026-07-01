"""Per-user Google OAuth endpoints."""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.config import settings
from src.services.google_auth import disconnect_google, google_connected
from src.services.google_tokens import store_google_token

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]

google_oauth_router = APIRouter(prefix="/api/google", tags=["google-oauth"])
_STATE: dict[str, int] = {}


def _redirect_uri(request: Request) -> str:
    return settings.GOOGLE_OAUTH_REDIRECT_URI or str(request.url_for("google_oauth_callback"))


@google_oauth_router.get("/connect")
async def connect_google(request: Request) -> RedirectResponse:
    chat_id = int(request.state.user["id"])
    state = secrets.token_urlsafe(24)
    _STATE[state] = chat_id
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), status_code=303)


@google_oauth_router.get("/callback", name="google_oauth_callback")
async def google_oauth_callback(request: Request, code: str, state: str) -> RedirectResponse:
    chat_id = _STATE.pop(state, None)
    if chat_id is None:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
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
    return RedirectResponse("/?google=connected", status_code=303)


@google_oauth_router.get("/status")
async def google_status(request: Request) -> dict:
    chat_id = int(request.state.user["id"])
    return {"connected": google_connected(chat_id)}


@google_oauth_router.post("/disconnect")
async def google_disconnect(request: Request) -> dict:
    chat_id = int(request.state.user["id"])
    await disconnect_google(chat_id)
    return {"connected": False}

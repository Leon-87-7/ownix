"""Auth endpoints: Telegram Login Widget → session cookie."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src import database
from src.auth import session as session_store
from src.auth.hmac_verify import verify_telegram_auth
from src.auth.middleware import COOKIE_NAME
from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)

_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class TelegramPayload(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


@auth_router.post("/telegram")
async def telegram_login(payload: TelegramPayload, response: Response) -> dict:
    # Build string-typed dict for HMAC verification (Telegram uses string values)
    raw: dict = {
        k: str(v)
        for k, v in payload.model_dump().items()
        if v is not None
    }

    user = verify_telegram_auth(raw, settings.TELEGRAM_BOT_TOKEN)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth payload")

    await database.upsert_user(
        tg_id=payload.id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        photo_url=payload.photo_url,
    )

    session_user = {
        "id": payload.id,
        "first_name": payload.first_name,
        "username": payload.username,
        "photo_url": payload.photo_url,
    }
    session_id = await session_store.mint(session_user)

    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    log.info("auth.telegram_login", tg_id=payload.id, username=payload.username)
    return {"ok": True}


@auth_router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        await session_store.revoke(session_id)
    response = RedirectResponse(url="/logout", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
    return response


@auth_router.get("/me")
async def me(request: Request) -> dict:
    return request.state.user

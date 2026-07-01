"""Auth endpoints: Telegram Login Widget → session cookie."""

from __future__ import annotations


from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src import database
from src.auth import session as session_store
from src.auth.hmac_verify import verify_telegram_auth
from src.auth.telegram_miniapp import trusted_chat_id, verify_init_data
from src.auth.middleware import COOKIE_NAME
from src.config import settings
from src.utils.logger import get_logger
from src.utils.validators import normalize_email

log = get_logger(__name__)

_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class MiniAppSessionPayload(BaseModel):
    init_data: str


class TelegramPayload(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


@auth_router.post("/miniapp/session")
async def miniapp_session(payload: MiniAppSessionPayload, response: Response) -> dict:
    verified = verify_init_data(payload.init_data, settings.TELEGRAM_BOT_TOKEN)
    if verified is None:
        raise HTTPException(status_code=401, detail="Invalid Telegram Mini App initData")

    user = verified["user"]
    chat_id = trusted_chat_id(verified)
    await database.upsert_user(
        tg_id=chat_id,
        username=user.get("username"),
        first_name=user.get("first_name") or "Telegram user",
        last_name=user.get("last_name"),
        photo_url=user.get("photo_url"),
    )

    session_user = {
        "id": chat_id,
        "first_name": user.get("first_name") or "Telegram user",
        "username": user.get("username"),
        "photo_url": user.get("photo_url"),
        "source": "telegram_mini_app",
    }
    session_id = await session_store.mint(session_user)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    log.info("auth.miniapp_session", tg_id=user.get("id"), chat_id=chat_id)
    # openLink hands off to the system browser, which has no access to this webview's
    # session cookie. A single-use, 60s handoff token (not the session id itself) lets
    # /connect authenticate without putting a long-lived credential in the URL, where
    # it would leak via browser history and server access logs.
    handoff_token = await session_store.mint_handoff(session_id)
    return {
        "ok": True,
        "chat_id": chat_id,
        "google_connect_url": f"/api/google/connect?token={handoff_token}",
    }


class EmailPayload(BaseModel):
    email: str


@auth_router.post("/telegram")
async def telegram_login(payload: TelegramPayload, response: Response) -> dict:
    # Build string-typed dict for HMAC verification (Telegram uses string values)
    raw: dict = {k: str(v) for k, v in payload.model_dump().items() if v is not None}

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
    session_user = request.state.user
    tg_id = int(session_user["id"])
    db_user = await database.get_user(tg_id)
    status = await database.get_user_status(tg_id)
    return {
        **session_user,
        "email": db_user.get("email") if db_user else None,
        "status": status,
    }


@auth_router.put("/email")
async def set_email(payload: EmailPayload, request: Request) -> dict:
    email = normalize_email(payload.email)
    if email is None:
        raise HTTPException(status_code=422, detail="Invalid email")
    tg_id = int(request.state.user["id"])
    await database.set_user_email(tg_id, email)
    status = await database.get_user_status(tg_id)
    return {"email": email, "status": status}


# Compatibility aliases for older tests/callers; canonical routes live in src.api.google_oauth.
from src.api.google_oauth import connect_google as google_connect  # noqa: E402

"""Auth endpoints: Telegram Login Widget → session cookie."""

from __future__ import annotations

import html
import hmac
import random
import re
import secrets
import time
from urllib.parse import urlencode

import httpx

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from src import database
from src.auth import session as session_store
from src.auth.hmac_verify import verify_telegram_auth
from src.auth.identity import resolve_owner
from src.auth.telegram_miniapp import trusted_chat_id, verify_init_data
from src.auth.middleware import COOKIE_NAME
from src.config import settings
from src.intake import rate_limit
from src.services.account import delete_account
from src.services.invite_notifications import notify_operator_invite
from src.services.email import send_magic_link_email
from src.utils.logger import get_logger
from src.utils.validators import normalize_email

log = get_logger(__name__)

_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

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


async def _resume_deletion_if_stuck(tg_id: int) -> dict | None:
    """Finish a deletion left mid-flight instead of minting a session into a
    half-deleted account (a prior /api/auth/me DELETE that failed partway,
    e.g. a network blip during Google token cleanup, still reads "deleting"
    here). Returns the response body to send back if a stuck deletion was
    resumed, or None to mean "continue with normal login". Every step in
    delete_account() is delete-if-exists / best-effort, so resuming is safe
    even if a previous call finished some steps already.
    """
    if await database.get_user_status(tg_id) != "deleting":
        return None
    await delete_account(tg_id)
    log.info("auth.resumed_account_deletion", tg_id=tg_id)
    return {"ok": True, "account_deleted": True}


async def _login_telegram_user(
    payload: TelegramPayload, response: Response, *, source: str | None = None
) -> dict:
    await database.upsert_user(
        tg_id=payload.id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        photo_url=payload.photo_url,
    )

    # upsert_user() never touches `status`, so a row left mid-deletion (a prior
    # /api/auth/me DELETE that failed partway through, e.g. a network blip
    # during Google token cleanup) still reads "deleting" here. Finish it now
    # instead of minting a session into a half-deleted account — every step in
    # delete_account() is delete-if-exists / best-effort, so resuming is safe.
    resumed = await _resume_deletion_if_stuck(payload.id)
    if resumed is not None:
        return resumed

    session_user = {
        "id": payload.id,
        "first_name": payload.first_name,
        "username": payload.username,
        "photo_url": payload.photo_url,
    }
    if source:
        session_user["source"] = source
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
    status = await database.get_user_status(payload.id)
    if status != "pending":
        response.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
    else:
        response.set_cookie(
            key="ownix_preview",
            value="1",
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    log.info("auth.telegram_login", tg_id=payload.id, username=payload.username)
    return {"ok": True}


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

    # See _login_telegram_user: resume a deletion left mid-flight rather than
    # minting a session into a half-deleted account.
    resumed = await _resume_deletion_if_stuck(chat_id)
    if resumed is not None:
        return resumed

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


async def _external_login(
    *,
    provider: str,
    subject: str,
    email: str | None,
    email_verified: bool,
    first_name: str,
    username: str | None,
    photo_url: str | None,
) -> RedirectResponse:
    normalized = normalize_email(email) if email else None
    known_identity = await database.get_identity_owner(provider, subject)
    known_email = await database.get_user_by_email(normalized) if normalized else None
    owner_id = await resolve_owner(
        provider, subject, email=normalized, email_verified=email_verified
    )
    resumed = await _resume_deletion_if_stuck(owner_id)
    if resumed is not None:
        raise HTTPException(status_code=401, detail="Account deletion completed; sign in again")

    is_new_tenant = known_identity is None and known_email is None
    if normalized and email_verified:
        user = await database.get_user(owner_id)
        if not user or not user.get("email"):
            await database.set_user_email(owner_id, normalized)
        if is_new_tenant and await database.get_user_status(owner_id) == "pending":
            try:
                await notify_operator_invite(owner_id, normalized)
            except Exception:
                log.exception("invite.operator_notification_failed", tg_id=owner_id)

    session_id = await session_store.mint(
        {
            "id": owner_id,
            "first_name": first_name,
            "username": username,
            "photo_url": photo_url,
            "source": provider,
        }
    )
    response = RedirectResponse("/feed", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    if await database.get_user_status(owner_id) == "pending":
        response.set_cookie(
            "ownix_preview", "1", httponly=True, secure=settings.SESSION_COOKIE_SECURE,
            samesite="lax", path="/"
        )
    else:
        response.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
    return response


_GITHUB_STATE_COOKIE = "gh_oauth_state"
_GOOGLE_LOGIN_STATE_COOKIE = "google_login_oauth_state"
_OAUTH_STATE_COOKIE_MAX_AGE = 600  # matches mint_*_oauth_state's default TTL


@auth_router.get("/github/connect")
async def github_connect() -> RedirectResponse:
    if not settings.GITHUB_OAUTH_CLIENT_ID or not settings.GITHUB_OAUTH_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="GitHub sign-in is not configured")
    state = await session_store.mint_github_oauth_state(secrets.token_urlsafe(16))
    query = urlencode(
        {"client_id": settings.GITHUB_OAUTH_CLIENT_ID,
         "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
         "scope": "read:user user:email", "state": state}
    )
    redirect = RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")
    # Binds `state` to this browser (login CSRF guard) — without it, an
    # attacker can start their own flow, get a valid `state`+`code`, and
    # trick a victim into completing the callback, landing the victim's
    # browser in a session tied to the attacker's GitHub identity.
    redirect.set_cookie(
        _GITHUB_STATE_COOKIE, state, httponly=True,
        secure=settings.SESSION_COOKIE_SECURE, samesite="lax",
        max_age=_OAUTH_STATE_COOKIE_MAX_AGE, path="/api/auth/github/",
    )
    return redirect


@auth_router.get("/github/callback")
async def github_callback(request: Request, code: str, state: str) -> RedirectResponse:
    cookie_state = request.cookies.get(_GITHUB_STATE_COOKIE)
    if not cookie_state or not hmac.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="OAuth state mismatch")
    if await session_store.redeem_github_oauth_state(state) is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={"client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                  "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET, "code": code,
                  "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI},
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if not token:
            raise HTTPException(status_code=400, detail="GitHub authorization failed")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        user_response = await client.get("https://api.github.com/user", headers=headers)
        email_response = await client.get("https://api.github.com/user/emails", headers=headers)
        user_response.raise_for_status()
        email_response.raise_for_status()
    user = user_response.json()
    primary = next((item for item in email_response.json()
                    if item.get("primary") and item.get("verified")), None)
    response = await _external_login(
        provider="github", subject=str(user["id"]),
        email=primary.get("email") if primary else None, email_verified=bool(primary),
        first_name=user.get("name") or user.get("login") or "GitHub user",
        username=user.get("login"), photo_url=user.get("avatar_url"),
    )
    response.delete_cookie(_GITHUB_STATE_COOKIE, path="/api/auth/github/")
    return response


@auth_router.get("/google/connect")
async def google_login_connect() -> RedirectResponse:
    if not settings.GOOGLE_LOGIN_CLIENT_ID or not settings.GOOGLE_LOGIN_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    state = await session_store.mint_google_login_state(secrets.token_urlsafe(16))
    query = urlencode(
        {"client_id": settings.GOOGLE_LOGIN_CLIENT_ID,
         "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
         "response_type": "code", "scope": "openid email profile", "state": state}
    )
    redirect = RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{query}")
    # Same login-CSRF guard as /github/connect — binds `state` to this browser.
    redirect.set_cookie(
        _GOOGLE_LOGIN_STATE_COOKIE, state, httponly=True,
        secure=settings.SESSION_COOKIE_SECURE, samesite="lax",
        max_age=_OAUTH_STATE_COOKIE_MAX_AGE, path="/api/auth/google/",
    )
    return redirect


@auth_router.get("/google/callback")
async def google_login_callback(request: Request, code: str, state: str) -> RedirectResponse:
    cookie_state = request.cookies.get(_GOOGLE_LOGIN_STATE_COOKIE)
    if not cookie_state or not hmac.compare_digest(cookie_state, state):
        raise HTTPException(status_code=400, detail="OAuth state mismatch")
    if await session_store.redeem_google_login_state(state) is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={"client_id": settings.GOOGLE_LOGIN_CLIENT_ID,
                  "client_secret": settings.GOOGLE_LOGIN_CLIENT_SECRET, "code": code,
                  "redirect_uri": settings.GOOGLE_LOGIN_REDIRECT_URI,
                  "grant_type": "authorization_code"},
        )
        token_response.raise_for_status()
        token = token_response.json().get("access_token")
        if not token:
            raise HTTPException(status_code=400, detail="Google authorization failed")
        user_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
        user_response.raise_for_status()
    user = user_response.json()
    response = await _external_login(
        provider="google", subject=str(user["sub"]), email=user.get("email"),
        email_verified=user.get("email_verified") is True,
        first_name=user.get("given_name") or user.get("name") or "Google user",
        username=None, photo_url=user.get("picture"),
    )
    response.delete_cookie(_GOOGLE_LOGIN_STATE_COOKIE, path="/api/auth/google/")
    return response


@auth_router.post("/email/request")
async def request_magic_link(payload: EmailPayload) -> dict:
    email = normalize_email(payload.email)
    if email is None:
        raise HTTPException(status_code=422, detail="Invalid email")
    # Unauthenticated and triggers a real outbound send — without this,
    # anyone can spam an arbitrary mailbox with sign-in links. Same shape as
    # reviewer_login's per-email cap just below.
    rate_limit.enforce(f"magic_link_request:{email}", max_requests=5)
    token = await session_store.mint_email_magic_link(email)
    base = settings.DASHBOARD_URL.strip().rstrip("/")
    link = f"{base}/api/auth/email/callback?token={token}"
    try:
        await send_magic_link_email(email, link)
    except Exception:
        log.exception("magic_link.send_failed")
    return {"ok": True, "message": "If that address can receive email, a sign-in link was sent."}


@auth_router.get("/email/callback")
async def redeem_magic_link(token: str = Query(..., max_length=512)) -> RedirectResponse:
    email = await session_store.redeem_email_magic_link(token)
    if email is None:
        raise HTTPException(status_code=400, detail="This link has expired or was already used")
    return await _external_login(
        provider="email", subject=email, email=email, email_verified=True,
        first_name=email.split("@", 1)[0], username=None, photo_url=None,
    )


@auth_router.post("/discord/pair")
async def discord_pair(request: Request) -> dict:
    code = await session_store.mint_discord_pairing(int(request.state.user["id"]))
    return {"code": code, "instructions": "Send this one-time code in a DM to the Ownix bot."}


class ReviewerLoginPayload(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)


@auth_router.post("/telegram")
async def telegram_login(payload: TelegramPayload, response: Response) -> dict:
    # Build string-typed dict for HMAC verification (Telegram uses string values)
    raw: dict = {k: str(v) for k, v in payload.model_dump().items() if v is not None}

    user = verify_telegram_auth(raw, settings.TELEGRAM_BOT_TOKEN)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth payload")

    return await _login_telegram_user(payload, response)


@auth_router.post("/reviewer-login")
async def reviewer_login(payload: ReviewerLoginPayload, response: Response) -> dict:
    """Temporary email+code login for Chrome Web Store review.

    This is not a general auth provider. It exists so external reviewers can
    exercise the extension pairing flow without a Telegram account.
    """
    configured_email = normalize_email(settings.REVIEWER_LOGIN_EMAIL)
    submitted_email = normalize_email(payload.email)
    configured_password = settings.REVIEWER_LOGIN_PASSWORD
    submitted_password = payload.password.strip()
    if not (settings.REVIEWER_LOGIN_ENABLED and configured_email and configured_password):
        raise HTTPException(status_code=404, detail="Reviewer login is disabled")
    rate_limit.enforce(f"reviewer_login:{submitted_email}", max_requests=5)
    if submitted_email != configured_email or not hmac.compare_digest(
        submitted_password.encode("utf-8"),
        configured_password.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid reviewer credentials")

    reviewer_id = settings.REVIEWER_LOGIN_USER_ID
    # See _login_telegram_user / miniapp_session: resume a deletion left
    # mid-flight rather than minting a session into a half-deleted account.
    # Must run before upsert_user — otherwise upsert_user would resurrect
    # the row before this check ever sees "deleting". A not-yet-existing
    # reviewer row safely reads "pending" (database.get_user_status), so
    # this is a no-op on the very first reviewer login.
    resumed = await _resume_deletion_if_stuck(reviewer_id)
    if resumed is not None:
        return resumed

    await database.upsert_user(
        tg_id=reviewer_id,
        username="chrome_reviewer",
        first_name="Chrome Reviewer",
        last_name=None,
        photo_url=None,
    )
    await database.set_user_email(reviewer_id, configured_email)
    await database.set_user_status(reviewer_id, "approved")
    session_id = await session_store.mint(
        {
            "id": reviewer_id,
            "first_name": "Chrome Reviewer",
            "username": "chrome_reviewer",
            "photo_url": None,
            "source": "reviewer_login",
        }
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    response.delete_cookie(
        "ownix_preview",
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
    )
    log.info("auth.reviewer_login", reviewer_id=reviewer_id)
    return {"ok": True}


@auth_router.get("/handoff", response_class=HTMLResponse)
async def handoff_login(token: str = Query(..., max_length=512), job_id: str = Query(...)) -> HTMLResponse:
    """Render a same-origin POST confirmation for Telegram dashboard handoff links."""
    if not _JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id")
    return HTMLResponse(
        f"""<!doctype html><html><head><title>Open your dashboard</title></head>
        <body><main><h1>Open your dashboard</h1>
        <form method="post" action="/api/auth/handoff">
        <input type="hidden" name="token" value="{html.escape(token, quote=True)}">
        <input type="hidden" name="job_id" value="{html.escape(job_id, quote=True)}">
        <button type="submit">Open your dashboard</button></form>
        <script>document.forms[0].submit()</script></main></body></html>"""
    )


@auth_router.post("/handoff")
async def redeem_handoff_login(
    token: str = Form(..., max_length=512), job_id: str = Form(...)
) -> RedirectResponse:
    """Redeem a job-link handoff token and land the user straight on their job page."""
    if not _JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id")

    chat_id = await session_store.redeem_dashboard_handoff(token)
    if chat_id is None:
        raise HTTPException(status_code=401, detail="This link has expired or was already used")

    # See _login_telegram_user: resume a deletion left mid-flight rather than
    # minting a session into a half-deleted account. Unlike the other two
    # login paths, this route redirects rather than returning a session JSON
    # body, so on resume it rejects with the same 401 the "user is None" path
    # below already uses (delete_account() will have just made that true).
    if await database.get_user_status(chat_id) == "deleting":
        await delete_account(chat_id)
        log.info("auth.resumed_account_deletion", tg_id=chat_id)
        raise HTTPException(status_code=401, detail="Dashboard access is unavailable")

    user = await database.get_user(chat_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Dashboard access is unavailable")

    session_id = await session_store.mint(
        {
            "id": chat_id,
            "first_name": user.get("first_name"),
            "username": user.get("username"),
            "photo_url": user.get("photo_url"),
        }
    )
    redirect = RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    redirect.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    return redirect


@auth_router.post("/dev-login")
async def dev_login(response: Response) -> dict:
    if not settings.DEV_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail="Dev login is disabled")

    payload = TelegramPayload(
        id=random.randint(10**8, 10**9 - 1),
        first_name="New Guy",
        auth_date=int(time.time()),
        hash="dev-login-bypasses-widget-hmac",
    )
    return await _login_telegram_user(payload, response, source="dev_login")


@auth_router.post("/dev-approve")
async def dev_approve(request: Request) -> dict:
    """Local-only fallback to approve the current Dev login session without Telegram callbacks."""
    if not settings.DEV_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail="Dev approval is disabled")
    tg_id = int(request.state.user["id"])
    if await database.get_user_status(tg_id) == "deleting":
        raise HTTPException(status_code=403, detail="Account deletion in progress")
    await database.set_user_status(tg_id, "approved")
    log.info("auth.dev_approve", tg_id=tg_id)
    return {"ok": True, "status": "approved"}


@auth_router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        await session_store.revoke(session_id)
    response = RedirectResponse(url="/logout", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
    return response


@auth_router.get("/me")
async def me(request: Request, response: Response) -> dict:
    session_user = request.state.user
    tg_id = int(session_user["id"])
    db_user = await database.get_user(tg_id)
    status = await database.get_user_status(tg_id)
    if status == "approved" and "ownix_preview" in request.cookies:
        # A stale preview cookie on an approved session would render the
        # dashboard in Restricted mode (ADR-0035 §1 says approved users get
        # their own Feed) — clear it whenever we see it.
        response.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
    return {
        **session_user,
        "email": db_user.get("email") if db_user else None,
        "status": status,
    }


@auth_router.delete("/me", status_code=204)
async def delete_account_route(request: Request) -> Response:
    """Self-serve full account deletion: hard-deletes every job/link/credential/
    setting owned by the caller, disconnects Google, then ends the session.

    begin_account_deletion() atomically flips status to "deleting" (and every
    session belonging to the account is revoked, not just the caller's) before
    the cleanup runs, not after: every other account-write route already
    rejects non-"approved" users (src/auth/middleware.py), so flipping status
    first shuts out concurrent writes from other sessions/devices, and
    revoking every session first closes both the same-tab race the naive
    "delete then revoke" order leaves open, and the window where a
    stale-but-still-valid session on another device could reach a
    pre-approval route (e.g. PUT /api/auth/email) after the row is gone and
    re-create it. The lock is compare-and-set (WHERE status != 'deleting'), so a
    second concurrent call — another tab/device with a still-valid session,
    since /api/auth/me stays reachable during deletion — short-circuits here
    instead of running delete_account() a second time (which would otherwise
    insert duplicate purge_tasks rows and double-revoke the Google token).
    delete_account()'s steps are all delete-if-exists / best-effort, so if
    this call fails partway the row is left in "deleting" (still locked out)
    and a later retry safely resumes rather than redoing already-finished
    work.
    """
    tg_id = int(request.state.user["id"])
    if settings.OPERATOR_CHAT_ID is not None and tg_id == settings.OPERATOR_CHAT_ID:
        # get_user_status()/set_user_status() force the operator to "approved"
        # (src/database.py) — the "deleting" lock above would silently no-op
        # for this account, so refuse self-service deletion outright instead.
        raise HTTPException(status_code=403, detail="Operator account cannot be deleted")

    locked = await database.begin_account_deletion(tg_id)
    if not locked:
        # Another concurrent call already holds the lock and owns the
        # cleanup — the account is/will be gone either way, so report the
        # same success the winning call's caller will also see rather than
        # running delete_account() again. Still revoke every session for
        # this account, though: the winner's revoke_account() call may not
        # have run yet, and the docstring promises every DELETE /api/auth/me
        # call ends the account's sessions rather than letting them outlive
        # the account until their natural TTL.
        await session_store.revoke_account(tg_id)
        out = Response(status_code=204)
        out.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
        out.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
        return out

    await session_store.revoke_account(tg_id)

    await delete_account(tg_id)

    out = Response(status_code=204)
    out.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
    out.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
    return out


@auth_router.put("/email")
async def set_email(payload: EmailPayload, request: Request) -> dict:
    email = normalize_email(payload.email)
    if email is None:
        raise HTTPException(status_code=422, detail="Invalid email")
    tg_id = int(request.state.user["id"])
    # /email is in _PRE_APPROVAL_AUTH_PATHS (middleware.py) so it bypasses the
    # approval-status gate on purpose (pending users need it) — that means it
    # also bypasses the "deleting" lock, and unlike DELETE /me a second call
    # here isn't idempotent/safe, so check explicitly. A second session/device
    # still holding a valid cookie is the only way to reach this mid-deletion:
    # delete_account_route revokes the triggering session before cleanup runs.
    if await database.get_user_status(tg_id) == "deleting":
        raise HTTPException(status_code=403, detail="Account deletion in progress")
    await database.set_user_email(tg_id, email)
    status = await database.get_user_status(tg_id)
    if status == "pending":
        is_dev_login = request.state.user.get("source") == "dev_login"
        try:
            await notify_operator_invite(tg_id, email, dev=is_dev_login)
        except Exception:
            log.exception(
                "invite.dev_operator_notification_failed"
                if is_dev_login
                else "invite.operator_notification_failed",
                tg_id=tg_id,
            )
    return {"email": email, "status": status}

"""Session middleware — gates /api/* routes; exempts /webhook, /health, login, Mini App bootstrap, and Google callback."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src import database
from src.auth import extension_tokens, session as session_store
from src.config import settings

COOKIE_NAME = "vig_session"
_BEARER_PREFIX = "bearer "

# Paths that bypass the session gate entirely
_OPEN_PATHS = frozenset(["/webhook", "/webhook/ops", "/webhook/email-digest", "/health"])

# Login/bootstrap endpoints — must be reachable without a session.
_OPEN_API_PATHS = frozenset(
    [
        "/api/auth/telegram",
        "/api/auth/dev-login",
        "/api/auth/reviewer-login",
        "/api/auth/miniapp/session",
        "/api/auth/handoff",
        "/api/google/callback",
        # The pairing code itself is the credential here (issue #479) — there
        # is no session to check yet when the extension redeems it.
        "/api/extension/token",
    ]
)
_OPEN_API_PREFIXES = ("/api/preview/",)

_PRE_APPROVAL_AUTH_PATHS = frozenset(
    [
        "/api/auth/me",
        "/api/auth/email",
        "/api/auth/logout",
        "/api/auth/dev-approve",
    ]
)

# Mini App "Connect Google" opens this path via Telegram's openLink, which hands off
# to the system browser — a separate cookie jar with no access to the webview session.
# The Mini App page appends a single-use handoff token (not the session id itself) as
# a query param so this one path can authenticate without the cookie.
_HANDOFF_TOKEN_PATHS = frozenset(["/api/google/connect"])

# A bearer extension token (issue #479) is scoped to Intake only — it must
# never carry the same authority as a full dashboard session (account email
# changes, Google disconnect, job deletes, minting more pairing codes, …).
# Least-privilege: only these prefixes will even attempt bearer resolution.
_BEARER_ALLOWED_PREFIXES = ("/api/intake/",)


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        if path in _OPEN_PATHS or path in _OPEN_API_PATHS or path.startswith(_OPEN_API_PREFIXES):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        session_id = request.cookies.get(COOKIE_NAME)
        user = await session_store.resolve(session_id) if session_id else None

        # Bearer traffic (Chrome extension, issue #479) is distinct from
        # session-cookie traffic — checked only when no session cookie
        # resolved, so a same-site request can't be confused for one. Scoped
        # to _BEARER_ALLOWED_PREFIXES: a stolen/leaked extension token must
        # not double as a full-account session on unrelated routes.
        if user is None and path.startswith(_BEARER_ALLOWED_PREFIXES):
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith(_BEARER_PREFIX):
                token = auth_header[len(_BEARER_PREFIX) :].strip()
                chat_id = await extension_tokens.resolve_extension_token(token) if token else None
                if chat_id is not None:
                    user = {"id": chat_id, "auth": "extension_token"}

        # A stale/expired same-origin cookie must not block the handoff-token
        # fallback — fall back to it whenever cookie resolution didn't yield a user.
        if user is None and path in _HANDOFF_TOKEN_PATHS:
            token = request.query_params.get("token")
            if token:
                handoff_session_id = await session_store.redeem_handoff(token)
                if handoff_session_id:
                    user = await session_store.resolve(handoff_session_id)
        if user is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        if (
            not settings.REVIEWER_LOGIN_ENABLED
            and (
                user.get("source") == "reviewer_login"
                or user.get("username") == "chrome_reviewer"
            )
        ):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        request.state.user = user
        # Only these auth routes are intentionally reachable before approval.
        if path in _PRE_APPROVAL_AUTH_PATHS:
            return await call_next(request)

        status = await database.get_user_status(int(user["id"]))
        if status != "approved":
            return JSONResponse({"detail": "Approval required"}, status_code=403)

        return await call_next(request)

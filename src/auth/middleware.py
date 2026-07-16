"""Session middleware — gates /api/* routes; exempts /webhook, /health, login, Mini App bootstrap, and Google callback."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src import database
from src.auth import session as session_store

COOKIE_NAME = "vig_session"

# Paths that bypass the session gate entirely
_OPEN_PATHS = frozenset(["/webhook", "/webhook/ops", "/health"])

# Login/bootstrap endpoints — must be reachable without a session.
_OPEN_API_PATHS = frozenset(
    [
        "/api/auth/telegram",
        "/api/auth/dev-login",
        "/api/auth/miniapp/session",
        "/api/google/callback",
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


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        if path in _OPEN_PATHS or path in _OPEN_API_PATHS or path.startswith(_OPEN_API_PREFIXES):
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        session_id = request.cookies.get(COOKIE_NAME)
        user = await session_store.resolve(session_id) if session_id else None
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

        request.state.user = user
        # Only these auth routes are intentionally reachable before approval.
        if path in _PRE_APPROVAL_AUTH_PATHS:
            return await call_next(request)

        status = await database.get_user_status(int(user["id"]))
        if status != "approved":
            return JSONResponse({"detail": "Approval required"}, status_code=403)

        return await call_next(request)

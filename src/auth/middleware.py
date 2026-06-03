"""Session middleware — gates /api/* routes; exempts /webhook, /health, /api/auth/telegram."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.auth import session as session_store

COOKIE_NAME = "vig_session"

# Paths that bypass the session gate entirely
_OPEN_PATHS = frozenset(["/webhook", "/health"])
# /api/auth/telegram is the login endpoint — must be reachable without a session
_OPEN_API_PATHS = frozenset(["/api/auth/telegram"])


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        if path in _OPEN_PATHS or path in _OPEN_API_PATHS:
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        session_id = request.cookies.get(COOKIE_NAME)
        if not session_id:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        user = await session_store.resolve(session_id)
        if user is None:
            return JSONResponse({"detail": "Invalid or expired session"}, status_code=401)

        request.state.user = user
        return await call_next(request)

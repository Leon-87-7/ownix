"""MCP pairing, token management, and authenticated path probe (issue #632)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.api.preview import _preview_client_key
from src.auth import mcp_tokens
from src.intake import rate_limit

mcp_auth_router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def _require_session_auth(request: Request) -> int:
    """Reject an MCP bearer token on the pairing/token-management routes.

    A token minted for MCP tool calls must not also double as authority to
    mint more pairing codes or list/revoke credentials for its own chat —
    that requires the full dashboard session, same least-privilege boundary
    the extension bearer token respects on non-intake routes.
    """
    user = request.state.user
    if user.get("auth") == "mcp_token":
        raise HTTPException(status_code=401, detail="Session authentication required")
    return user["id"]


@mcp_auth_router.post("/pair")
async def create_pairing_code(request: Request) -> dict:
    chat_id = _require_session_auth(request)
    rate_limit.enforce(f"mcp_pair:{chat_id}", max_requests=10)
    code = await mcp_tokens.mint_pairing_code(chat_id)
    return {"code": code, "expires_in": mcp_tokens.PAIRING_TTL_SECONDS}


class PairingRedeemRequest(BaseModel):
    code: str = Field(..., max_length=64)


@mcp_auth_router.post("/token")
async def redeem_pairing_code(request: Request, body: PairingRedeemRequest) -> dict:
    client_key = _preview_client_key(request)
    rate_limit.enforce(f"mcp_redeem:{client_key}", max_requests=20)
    chat_id = await mcp_tokens.redeem_pairing_code(body.code)
    if chat_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired pairing code")
    token = await mcp_tokens.issue_mcp_token(chat_id)
    return {"token": token, "chat_id": chat_id}


@mcp_auth_router.get("/tokens")
async def list_tokens(request: Request) -> list[dict]:
    chat_id = _require_session_auth(request)
    rate_limit.enforce(f"mcp_tokens_list:{chat_id}", max_requests=60)
    return await mcp_tokens.list_mcp_tokens(chat_id)


@mcp_auth_router.delete("/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: str, request: Request) -> Response:
    chat_id = _require_session_auth(request)
    rate_limit.enforce(f"mcp_tokens_revoke:{chat_id}", max_requests=30)
    if not await mcp_tokens.revoke_mcp_token(chat_id, token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    return Response(status_code=204)


@mcp_auth_router.get("/ping")
async def ping(request: Request) -> dict[str, int]:
    """Minimal end-to-end proof that MCP bearer resolution populated state."""
    if request.state.user.get("auth") != "mcp_token":
        raise HTTPException(status_code=401, detail="MCP bearer token required")
    rate_limit.enforce(f"mcp_ping:{request.state.user['id']}", max_requests=60)
    return {"chat_id": request.state.user["id"]}

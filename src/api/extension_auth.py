"""Chrome extension pairing auth (issue #479).

`POST /api/extension/pair` (session-authed) mints a single-use, short-TTL
pairing code. `POST /api/extension/token` (unauthenticated — the pairing
code IS the credential here, see `_OPEN_API_PATHS` in
`src/auth/middleware.py`) redeems it for an opaque bearer token; only its
hash is ever stored server-side (`src/auth/extension_tokens.py`). The
extension must never see or store a raw dashboard session cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.auth import extension_tokens
from src.intake import rate_limit

extension_auth_router = APIRouter(prefix="/api/extension", tags=["extension"])


@extension_auth_router.post("/pair")
async def create_pairing_code(request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"extension_pair:{chat_id}", max_requests=10)
    code = await extension_tokens.mint_pairing_code(chat_id)
    return {"code": code, "expires_in": extension_tokens.PAIRING_TTL_SECONDS}


class PairingRedeemRequest(BaseModel):
    code: str = Field(..., max_length=64)


@extension_auth_router.post("/token")
async def redeem_pairing_code(request: Request, body: PairingRedeemRequest) -> dict:
    client_key = request.client.host if request.client is not None else "unknown"
    rate_limit.enforce(f"extension_redeem:{client_key}", max_requests=20)

    chat_id = await extension_tokens.redeem_pairing_code(body.code)
    if chat_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired pairing code")
    token = await extension_tokens.issue_extension_token(chat_id)
    return {"token": token, "chat_id": chat_id}


@extension_auth_router.get("/tokens")
async def list_tokens(request: Request) -> list[dict]:
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"extension_tokens_list:{chat_id}", max_requests=60)
    return await extension_tokens.list_extension_tokens(chat_id)


@extension_auth_router.delete("/tokens/{token_id}", status_code=204)
async def revoke_token(token_id: str, request: Request) -> Response:
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"extension_tokens_revoke:{chat_id}", max_requests=30)
    revoked = await extension_tokens.revoke_extension_token(chat_id, token_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Token not found")
    return Response(status_code=204)

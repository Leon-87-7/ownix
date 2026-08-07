"""POST /api/intake/* — the Ownix Intake product-interaction API.

`/api/jobs` stays the low-level job API (unmodified). This is the versioned,
channel-neutral surface: every mutating endpoint here authenticates via the
existing session middleware, enforces a per-user rate limit, normalizes into
an `IntakeMessage`, and calls the shared `src/intake/router.py` — it never
re-implements dedup, job creation, or URL-routing decisions itself (ADR-0033).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from src.intake import commands, idempotency, mime_sniff, quota, rate_limit, state
from src.intake.models import IntakeAction, IntakeActor, IntakeFile, IntakeMessage
from src.intake.router import handle as handle_intake_message

intake_router = APIRouter(prefix="/api/intake", tags=["intake"])

# Mirrors src.services.pdf_intake.MAX_PDF_BYTES — the larger of the two file
# kinds this endpoint accepts (images are always far smaller in practice).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class IntakeMessageRequest(BaseModel):
    text: str | None = Field(default=None, max_length=4_000)
    url: str | None = Field(default=None, max_length=2_048)


def _dashboard_actor(chat_id: int) -> IntakeActor:
    return IntakeActor(
        user_id=chat_id,
        channel_id=f"dashboard:{chat_id}",
        channel_type="dashboard",
        legacy_chat_id=chat_id,
    )


async def _cached_upload_response(chat_id: int, idempotency_key: str | None) -> dict | None:
    """Peek the router's idempotency cache before charging the upload quota.

    Mirrors `src.intake.router.actor_key`'s `f"chat:{chat_id}"` derivation for
    a dashboard actor — without this, a legitimate at-least-once retry of the
    same upload (same Idempotency-Key) would get charged the daily quota
    again for a request that just replays the cached response.
    """
    if not idempotency_key:
        return None
    cached = await idempotency.get_cached(f"chat:{chat_id}", idempotency_key)
    if cached is not None and cached.get("job_id"):
        cached["job_url"] = f"/jobs/{cached['job_id']}"
    return cached


@intake_router.post("/message")
async def post_intake_message(
    request: Request,
    body: IntakeMessageRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> dict:
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"message:{chat_id}")

    text = body.text.strip() if body.text else None
    url = body.url.strip() if body.url else None
    if not text and not url:
        raise HTTPException(status_code=422, detail="text or url is required")

    msg = IntakeMessage(
        idempotency_key=idempotency_key,
        actor=_dashboard_actor(chat_id),
        text=text,
        url=url,
        received_at=time.time(),
    )
    response = await handle_intake_message(msg)
    payload = response.model_dump(mode="json")
    if response.job_id:
        payload["job_url"] = f"/jobs/{response.job_id}"
    return payload


@intake_router.post("/upload")
async def post_intake_upload(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> dict:
    """Accepts one `multipart/form-data` file under the `file` field.

    Hardening runs in this exact order, each step rejecting before any
    bytes reach the pipeline: rate limit -> size cap (413) -> content-sniffed
    MIME allowlist (415, never the client `Content-Type`) -> daily
    upload/byte quota (429).
    """
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"upload:{chat_id}", max_requests=10)

    cached = await _cached_upload_response(chat_id, idempotency_key)
    if cached is not None:
        return cached

    try:
        # max_part_size only limits non-file form fields (Starlette's
        # MultiPartParser skips the check for any part with a filename, i.e.
        # our actual `file` field) — this endpoint's own read-and-compare
        # below is what actually enforces the size cap on the upload itself.
        # Passed through anyway so a client that smuggles an extra oversized
        # text field alongside `file` still gets bounded, not an unbounded
        # buffer.
        form = await request.form(max_part_size=MAX_UPLOAD_BYTES)
    except MultiPartException as exc:
        # Defensive: only reachable if Starlette ever stops converting this
        # to an HTTPException itself (see except clause below).
        raise HTTPException(status_code=413, detail="File must be 20 MB or smaller") from exc
    except StarletteHTTPException as exc:
        # Request._get_form catches MultiPartException internally and
        # re-raises it as a *base* starlette HTTPException(400, ...) whenever
        # the request has an app scope (always true here) — so the
        # `except MultiPartException` above never actually fires for that
        # path. Remap the size-limit case to the 413 this endpoint promises;
        # let any other 400 (e.g. a malformed boundary) pass through as-is.
        if exc.status_code == 400 and "exceeded maximum size" in str(exc.detail):
            raise HTTPException(status_code=413, detail="File must be 20 MB or smaller") from exc
        raise
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise HTTPException(status_code=422, detail="file is required")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File must be 20 MB or smaller")

    sniffed = mime_sniff.sniff(data)
    if sniffed is None:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    quota.enforce(chat_id, len(data))

    filename = getattr(upload, "filename", None) or "upload"
    msg = IntakeMessage(
        idempotency_key=idempotency_key,
        actor=_dashboard_actor(chat_id),
        files=[IntakeFile(filename=filename, content_type=sniffed, size=len(data), data=data)],
        received_at=time.time(),
    )
    response = await handle_intake_message(msg)
    payload = response.model_dump(mode="json")
    if response.job_id:
        payload["job_url"] = f"/jobs/{response.job_id}"
    return payload


class IntakeActionRequest(BaseModel):
    action_id: str = Field(..., max_length=200)
    kind: str = Field(..., max_length=100)
    job_id: str | None = None
    payload: dict = Field(default_factory=dict)


@intake_router.post("/action")
async def post_intake_action(request: Request, body: IntakeActionRequest) -> dict:
    """Generic replacement for a Telegram inline-keyboard tap.

    Idempotent per (actor, action_id): the router's idempotency cache is keyed
    on `f"action:{action_id}"`, so a double-tapped button or re-delivered
    request replays the original response instead of re-applying the action.
    """
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"action:{chat_id}")

    msg = IntakeMessage(
        idempotency_key=f"action:{body.action_id}",
        actor=_dashboard_actor(chat_id),
        action=IntakeAction(
            action_id=body.action_id,
            kind=body.kind,
            job_id=body.job_id,
            payload=body.payload,
        ),
        received_at=time.time(),
    )
    response = await handle_intake_message(msg)
    payload = response.model_dump(mode="json")
    if response.job_id:
        payload["job_url"] = f"/jobs/{response.job_id}"
    return payload


class IntakeStateResponse(BaseModel):
    pending: dict | None = None


@intake_router.get("/commands")
async def get_intake_commands() -> dict:
    """Commands this channel actually accepts, for the composer palette (#484).

    Derived from `SHARED_COMMANDS` rather than hardcoded, so a migrated command
    lights up its own palette entry on landing.
    """
    return {"commands": commands.palette()}


@intake_router.get("/state")
async def get_intake_state(request: Request) -> IntakeStateResponse:
    """Return the caller's pending awaiting_intent/awaiting_freestyle flow, if any.

    Pending state is last-write-wins across channels, not per-channel — see
    `src/intake/state.py`'s module docstring for why that's the deliberate
    semantic rather than a gap.
    """
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"state:{chat_id}", max_requests=60)
    pending = await state.get_state(chat_id)
    return IntakeStateResponse(pending=pending)


@intake_router.delete("/state")
async def delete_intake_state(request: Request) -> dict:
    chat_id: int = request.state.user["id"]
    rate_limit.enforce(f"state:{chat_id}", max_requests=60)
    cleared = await state.clear_state(chat_id)
    return {"cleared": cleared}

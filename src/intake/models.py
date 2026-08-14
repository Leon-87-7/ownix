"""Channel-neutral intake contract (plan: "Intake Message Contract").

Every channel adapter (dashboard, Chrome extension, PWA share target, Telegram,
future Discord) converts its native payload into an `IntakeMessage` and renders
an `IntakeResponse` back into its own transport. Nothing here may import
FastAPI/Starlette request types or Telegram types — that coupling is exactly
what `src/intake/router.py` exists to avoid.

Contract stability rules (do not violate silently):
- Every message/response carries `schema_version`. A version the receiver
  can't parse must be rejected, not mis-read.
- Fields are added, never repurposed.
- `idempotency_key` is the retry contract: the same key from the same actor
  must yield the same response, never a duplicate side effect.
- `metadata` is channel-private scratch space; the router must never branch
  on its contents to make core decisions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1
ProcessingIntent = Literal["automatic", "article", "link", "document"]


class IntakeActor(BaseModel):
    """Who sent this message. Ownership stays `chat_id`-keyed in this batch
    (see plan Non-Goals — no `user_id` migration yet), so `legacy_chat_id` is
    the field every router decision actually keys off."""

    user_id: str | int
    channel_id: str
    channel_type: str
    legacy_chat_id: int | None = None


class IntakeFile(BaseModel):
    """A file attachment, already read into memory by the adapter/endpoint.

    `content_type` must be the server-sniffed MIME type, never the client-
    supplied header, per the plan's upload hardening requirement.
    """

    filename: str
    content_type: str
    size: int
    data: bytes = b""


class IntakeAction(BaseModel):
    """The generic replacement for a Telegram inline-keyboard button."""

    action_id: str
    kind: str
    label: str | None = None
    job_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class IntakeMessage(BaseModel):
    schema_version: int = SCHEMA_VERSION
    idempotency_key: str | None = None
    actor: IntakeActor
    text: str | None = None
    url: str | None = None
    intent: ProcessingIntent = "automatic"
    files: list[IntakeFile] = Field(default_factory=list)
    action: IntakeAction | None = None
    source_message_id: str | int | None = None
    received_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntakeResponse(BaseModel):
    schema_version: int = SCHEMA_VERSION
    kind: str
    text: str
    job_id: str | None = None
    actions: list[IntakeAction] = Field(default_factory=list)
    state: dict[str, Any] | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    retryable: bool = False
    # Structured, adapter-neutral result of best-effort Job-tag attachment.
    tag_outcome: dict[str, list[str]] | None = None

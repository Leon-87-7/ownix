"""IntakeResponse constructors — one place that decides the `kind`/`retryable`
shape for each router outcome, so every channel adapter renders a consistent
contract instead of each inventing its own text-to-kind mapping."""

from __future__ import annotations

from src.intake.models import IntakeAction, IntakeResponse


def job_created(job: dict, *, deduped: bool = False) -> IntakeResponse:
    job_id = job["id"]
    content_type = job.get("content_type", "link")
    text = (
        f"Already tracked as job_{job_id[-4:]} ({content_type})."
        if deduped
        else f"Received — job_{job_id[-4:]} ({content_type})."
    )
    return IntakeResponse(
        kind="job_deduped" if deduped else "job_created",
        text=text,
        job_id=job_id,
    )


def unsupported(reason: str) -> IntakeResponse:
    return IntakeResponse(kind="unsupported", text=reason, retryable=False)


def rejected(reason: str) -> IntakeResponse:
    return IntakeResponse(kind="rejected", text=reason, retryable=False)


def error(reason: str, *, retryable: bool = False) -> IntakeResponse:
    return IntakeResponse(kind="error", text=reason, retryable=retryable)


def unknown_schema_version(requested: int) -> IntakeResponse:
    return IntakeResponse(
        kind="error",
        text=f"Unsupported schema_version: {requested}",
        retryable=False,
    )


def state_update(text: str, state: dict | None) -> IntakeResponse:
    return IntakeResponse(kind="state_update", text=text, state=state)


def action_ack(text: str, *, job_id: str | None = None, state: dict | None = None) -> IntakeResponse:
    return IntakeResponse(kind="action_ack", text=text, job_id=job_id, state=state)


def command_result(text: str, *, actions: list[IntakeAction] | None = None) -> IntakeResponse:
    return IntakeResponse(kind="command_result", text=text, actions=actions or [])

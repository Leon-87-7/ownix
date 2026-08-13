"""Shared storage/job orchestration behind every remote Document intake channel."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from src import database
from src.services import parse, storage
from src.services.jobs import create_and_enqueue_job
from src.services.pdf_intake import (
    fetch_remote_document,
    validate_document,
    validate_remote_document_url,
)


class DocumentIntakeError(Exception):
    """Transport-neutral representation of a safe Document intake failure."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        if isinstance(detail, dict):
            message = str(detail.get("message") or "Document intake failed.")
        elif isinstance(detail, str):
            message = detail
        else:
            message = "Document intake failed."
        self.public_message = message
        super().__init__(message)


async def create_document_job(
    chat_id: int,
    data: bytes,
    filename: str,
    ext: str | None = None,
    *,
    source_url: str | None = None,
    job_creator: Callable[..., Any] = create_and_enqueue_job,
    delivery_setter: Callable[..., Any] = database.set_job_telegram_delivery,
) -> dict:
    ext = ext or validate_document(data, filename)
    source_ext = parse._ext_from_name(filename)
    if source_ext not in parse.SUPPORTED_EXTS:
        source_ext = ext
    sha = hashlib.sha256(data).hexdigest()
    key = storage.object_key("documents", sha, source_ext)
    await storage.upload(key, data, parse.content_type_for(source_ext))
    job_kwargs = {"chat_id": chat_id, "url": key, "content_type": "document"}
    if source_url is not None:
        job_kwargs["dedup_url"] = source_url
    job = await job_creator(**job_kwargs)
    if not job.get("_deduped"):
        await delivery_setter(job["id"], "off")
    return {
        "job_id": job["id"], "sha256": sha, "gcs_key": key,
        "status": job.get("status", "pending"),
        "content_type": job.get("content_type", "document"),
        "_deduped": bool(job.get("_deduped")),
    }


async def create_remote_document_job(
    chat_id: int, url: str, *, require_document_path: bool = True
) -> dict:
    try:
        url = validate_remote_document_url(url, require_document_path=require_document_path)
        existing = await database.find_recent_job_by_url(chat_id, url)
        if existing:
            return {
                "job_id": existing["id"],
                "status": existing.get("status", "pending"),
                "content_type": existing.get("content_type", "document"),
                "_deduped": True,
            }
        data, filename, ext = await fetch_remote_document(
            url, require_document_path=require_document_path
        )
        return await create_document_job(chat_id, data, filename, ext, source_url=url)
    except HTTPException as exc:
        raise DocumentIntakeError(exc.status_code, exc.detail) from exc

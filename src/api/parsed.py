"""Doc Parser dashboard API (ADR-0029)."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src import database, queue
from src.api.deps import get_owned_job
from src.processors import document as document_processor
from src.services import storage
from src.services.parse import ParseError
from src.services.pdf_intake import (
    MAX_PDF_BYTES,
    fetch_remote_pdf,
    read_capped_body,
    validate_pdf,
)
from src.telegram.sender import send_document
from src.utils.logger import get_logger

log = get_logger(__name__)

parsed_router = APIRouter(prefix="/api/parsed", tags=["parsed"])


async def _try_send_document(chat_id: int, data: bytes, filename: str) -> bool:
    """Telegram delivery is best-effort: the output is already persisted to GCS +
    document_outputs, so a send failure must not 500 the request."""
    try:
        await send_document(chat_id, data, filename)
        return True
    except Exception:
        log.exception("parsed.telegram_send_failed", filename=filename)
        return False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def get_owned_document_job(job_id: str, request: Request) -> dict:
    """get_owned_job + a content_type guard. Document-only routes must not run on
    an owned article/repo job: its url is a plain HTTP address, not a GCS key, so
    the SHA/parse path 500s and the Telegram toggle would mutate the wrong job."""
    job = await get_owned_job(job_id, request)
    if job.get("content_type") != "document":
        raise HTTPException(status_code=404, detail="Document job not found")
    return job


async def _create_document_job(chat_id: int, data: bytes, filename: str) -> dict:
    validate_pdf(data, filename)
    sha = _sha(data)
    key = storage.object_key("documents", sha, "pdf")
    await storage.upload(key, data, "application/pdf")
    job_id = await database.create_job(chat_id=chat_id, url=key, content_type="document")
    # Dashboard uploads default to NOT delivering to Telegram (user opts in via
    # the per-job toggle). Bot-submitted jobs keep the DB default ('on') so the
    # existing Telegram flow is unchanged.
    await database.set_job_telegram_delivery(job_id, "off")
    await queue.enqueue({"task": "document", "job_id": job_id})
    return {"job_id": job_id, "sha256": sha, "gcs_key": key, "status": "pending"}


@parsed_router.post("/upload", status_code=201)
async def upload_pdf(request: Request) -> dict:
    # Keep import-time lightweight in environments without python-multipart; parse
    # multipart lazily only when this endpoint is exercised. Tests may also send a
    # raw application/pdf body with X-Filename.
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status_code=422, detail={"field": "file", "message": "PDF file is required"})
        data = await upload.read(MAX_PDF_BYTES + 1)
        filename = getattr(upload, "filename", None) or "document.pdf"
    else:
        data = await read_capped_body(request)
        filename = request.headers.get("x-filename", "document.pdf")
    return await _create_document_job(request.state.user["id"], data, filename)


class UrlIn(BaseModel):
    url: str = Field(..., min_length=1)


@parsed_router.post("/url", status_code=201)
async def upload_url(body: UrlIn, request: Request) -> dict:
    data, filename = await fetch_remote_pdf(body.url)
    return await _create_document_job(request.state.user["id"], data, filename)


class FreestyleIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)


async def _generate_output(job: dict, kind: str, prompt: str | None = None) -> dict:
    # get_owned_job only checks ownership; a non-document job (article/repo) has a
    # plain URL, not documents/<sha>.pdf, so the SHA/parse path below would 500.
    if job.get("content_type") != "document":
        raise HTTPException(status_code=422, detail={"field": "job", "message": "Not a document job"})
    sha = document_processor._sha_from_key(job["url"])
    try:
        text = await document_processor._cached_parse(sha, "txt")
    except ParseError as exc:
        # Scanned/image-only PDF (or a prior failed parse): surface as a readable
        # 422 instead of a generic 500.
        raise HTTPException(status_code=422, detail={"field": "job", "message": "Document text could not be extracted (scanned or image-only PDF)"}) from exc
    from src.services.gemini import gemini_client
    if kind == "clean":
        instruction = "Clean this parsed PDF text into well-formatted Markdown while preserving the same content."
        key = f"enriched/{sha}_clean.md"
        title = "Clean version"
    else:  # freestyle
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        instruction = prompt or "Summarize this document."
        key = f"enriched/{sha}_freestyle_{ts}.md"
        title = "Freestyle"
    md = await gemini_client.generate(f"{instruction}\n\nDOCUMENT:\n{text}", model="gemini-2.5-flash")
    await storage.upload(key, md.encode("utf-8"), "text/markdown")
    output = await database.add_document_output(job["id"], kind, key, title)
    if job.get("telegram_delivery") == "on":
        await _try_send_document(job["chat_id"], md.encode("utf-8"), key.rsplit("/", 1)[-1])
    return {**output, "content": md}


@parsed_router.post("/{job_id}/clean", status_code=201)
async def clean(job_id: str, request: Request) -> dict:
    job = await get_owned_document_job(job_id, request)
    return await _generate_output(job, "clean")


@parsed_router.post("/{job_id}/freestyle", status_code=201)
async def freestyle(job_id: str, body: FreestyleIn, request: Request) -> dict:
    job = await get_owned_document_job(job_id, request)
    return await _generate_output(job, "freestyle", body.prompt)


class DeliveryIn(BaseModel):
    state: str = Field(..., pattern="^(off|on|retroactive)$")


@parsed_router.put("/{job_id}/telegram-delivery")
async def telegram_delivery(job_id: str, body: DeliveryIn, request: Request) -> dict:
    job = await get_owned_document_job(job_id, request)
    sent = 0
    state = body.state
    if state == "retroactive":
        for output in await database.list_document_outputs(job_id):
            data = await storage.download(output["gcs_key"])
            if await _try_send_document(job["chat_id"], data, output["gcs_key"].rsplit("/", 1)[-1]):
                sent += 1
        state = "on"
    updated = await database.set_job_telegram_delivery(job_id, state)
    return {"telegram_delivery": updated.get("telegram_delivery", state) if updated else state, "sent": sent}


@parsed_router.get("/{job_id}/outputs")
async def outputs(job_id: str, request: Request) -> list[dict]:
    await get_owned_document_job(job_id, request)
    rows = await database.list_document_outputs(job_id)
    # Fetch the blobs concurrently — sequential awaits are O(n) round-trips.
    blobs = await asyncio.gather(*(storage.download(row["gcs_key"]) for row in rows))
    return [
        {
            **row,
            "preview": "\n".join(blob.decode("utf-8", "replace").splitlines()[:8]),
            "content_url": f"/api/parsed/{job_id}/outputs/{row['id']}",
        }
        for row, blob in zip(rows, blobs)
    ]


@parsed_router.get("/{job_id}/outputs/{output_id}")
async def output_content(job_id: str, output_id: str, request: Request) -> Response:
    await get_owned_document_job(job_id, request)
    row = next((r for r in await database.list_document_outputs(job_id) if r["id"] == output_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Output not found")
    data = await storage.download(row["gcs_key"])
    return Response(content=data, media_type="text/markdown")


@parsed_router.get("/events")
async def events(request: Request) -> StreamingResponse:
    chat_id = request.state.user["id"]
    async def gen():
        last = ""
        # One connection for the whole stream, not one per 2s poll cycle.
        async with database.connection() as conn:
            while True:
                if await request.is_disconnected():
                    break
                cur = await conn.execute("SELECT id,status,updated_at FROM jobs WHERE chat_id=? AND content_type='document' ORDER BY updated_at DESC LIMIT 20", (chat_id,))
                rows = [dict(r) for r in await cur.fetchall()]
                payload = json.dumps(rows)
                if payload != last:
                    last = payload
                    yield f"event: jobs\ndata: {payload}\n\n"
                await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")

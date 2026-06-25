"""Doc Parser dashboard API (ADR-0029)."""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from src import database, queue
from src.api.deps import get_owned_job
from src.processors import document as document_processor
from src.services import storage
from src.telegram.sender import send_document

parsed_router = APIRouter(prefix="/api/parsed", tags=["parsed"])

MAX_PDF_BYTES = 20 * 1024 * 1024


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_pdf(data: bytes, name: str = "document.pdf") -> None:
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=422, detail={"field": "file", "message": "PDF must be 20 MB or smaller"})
    if not name.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail={"field": "file", "message": "Only PDF files are supported"})


async def _create_document_job(chat_id: int, data: bytes, filename: str) -> dict:
    _validate_pdf(data, filename)
    sha = _sha(data)
    key = storage.object_key("documents", sha, "pdf")
    await storage.upload(key, data, "application/pdf")
    job_id = await database.create_job(chat_id=chat_id, url=key, content_type="document")
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
        data = await request.body()
        filename = request.headers.get("x-filename", "document.pdf")
    return await _create_document_job(request.state.user["id"], data, filename)


class UrlIn(BaseModel):
    url: str = Field(..., min_length=1)


@parsed_router.post("/url", status_code=201)
async def upload_url(body: UrlIn, request: Request) -> dict:
    parsed = urlparse(body.url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.path.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail={"field": "url", "message": "Enter a direct HTTPS PDF URL"})
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(body.url.strip())
            resp.raise_for_status()
            data = resp.content
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not fetch PDF URL") from exc
    return await _create_document_job(request.state.user["id"], data, parsed.path.rsplit("/", 1)[-1] or "document.pdf")


class FreestyleIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)


async def _generate_output(job: dict, kind: str, prompt: str | None = None) -> dict:
    sha = document_processor._sha_from_key(job["url"])
    text = await document_processor._cached_parse(sha, "txt")
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
        await send_document(job["chat_id"], md.encode("utf-8"), key.rsplit("/", 1)[-1])
    return {**output, "content": md}


@parsed_router.post("/{job_id}/clean", status_code=201)
async def clean(job_id: str, request: Request) -> dict:
    job = await get_owned_job(job_id, request)
    return await _generate_output(job, "clean")


@parsed_router.post("/{job_id}/freestyle", status_code=201)
async def freestyle(job_id: str, body: FreestyleIn, request: Request) -> dict:
    job = await get_owned_job(job_id, request)
    return await _generate_output(job, "freestyle", body.prompt)


class DeliveryIn(BaseModel):
    state: str = Field(..., pattern="^(off|on|retroactive)$")


@parsed_router.put("/{job_id}/telegram-delivery")
async def telegram_delivery(job_id: str, body: DeliveryIn, request: Request) -> dict:
    job = await get_owned_job(job_id, request)
    sent = 0
    state = body.state
    if state == "retroactive":
        for output in await database.list_document_outputs(job_id):
            data = await storage.download(output["gcs_key"])
            await send_document(job["chat_id"], data, output["gcs_key"].rsplit("/", 1)[-1])
            sent += 1
        state = "on"
    updated = await database.set_job_telegram_delivery(job_id, state)
    return {"telegram_delivery": updated.get("telegram_delivery", state) if updated else state, "sent": sent}


@parsed_router.get("/{job_id}/outputs")
async def outputs(job_id: str, request: Request) -> list[dict]:
    await get_owned_job(job_id, request)
    rows = await database.list_document_outputs(job_id)
    result = []
    for row in rows:
        content = (await storage.download(row["gcs_key"])).decode("utf-8", "replace")
        result.append({**row, "preview": "\n".join(content.splitlines()[:8]), "content_url": f"/api/parsed/{job_id}/outputs/{row['id']}"})
    return result


@parsed_router.get("/{job_id}/outputs/{output_id}")
async def output_content(job_id: str, output_id: str, request: Request) -> Response:
    await get_owned_job(job_id, request)
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
        while True:
            if await request.is_disconnected():
                break
            async with database.connection() as conn:
                cur = await conn.execute("SELECT id,status,updated_at FROM jobs WHERE chat_id=? AND content_type='document' ORDER BY updated_at DESC LIMIT 20", (chat_id,))
                rows = [dict(r) for r in await cur.fetchall()]
            payload = json.dumps(rows)
            if payload != last:
                last = payload
                yield f"event: jobs\ndata: {payload}\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")

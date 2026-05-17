"""POST /webhook — receives Telegram updates, creates job, enqueues task envelope.

Slice #1 scope: validate secret, parse message, route URL via detect_pipeline(), create
the job row, enqueue {"task":"video","job_id":...}, reply with the job_id. Pipeline
logic itself lives in slices #2 (short) and #3 (long).
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from src import database, queue
from src.config import settings
from src.telegram.sender import send_message
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline

log = get_logger(__name__)
router = APIRouter()


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    # Validate the secret header from Telegram (PRD §2.2.1).
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        log.warning("webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret")

    update = await request.json()
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id")

    log.info(
        "webhook_received",
        chat_id=chat_id,
        message_id=message_id,
        text_len=len(text),
    )

    if not chat_id or not text:
        # Non-text update (sticker, photo without caption, edited reaction, etc.) — ack and ignore.
        return {"ok": True}

    pipeline = detect_pipeline(text)
    if pipeline == "rejected":
        await send_message(
            chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels (not /p/ carousels), and TikTok videos.",
        )
        log.info("url_rejected", chat_id=chat_id, url=text)
        return {"ok": True}

    job_id = await database.create_job(
        chat_id=chat_id,
        url=text,
        content_type=pipeline,
        message_id=message_id,
    )
    await queue.enqueue({"task": "video", "job_id": job_id})
    await send_message(chat_id, f"📥 Received! Job ID: {job_id}")
    return {"ok": True}

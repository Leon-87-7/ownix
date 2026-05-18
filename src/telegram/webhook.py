"""POST /webhook — receives Telegram updates and callback queries."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from src import database, queue
from src.config import settings
from src.telegram.sender import answer_callback_query, send_message
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline

log = get_logger(__name__)
router = APIRouter()


async def _handle_callback(callback: dict) -> None:
    """Dispatch callback_query events from inline keyboard button presses."""
    cq_id = callback.get("id", "")
    data = callback.get("data", "")
    chat_id = (callback.get("message") or {}).get("chat", {}).get("id")

    log.info("callback_received", callback_data=data, chat_id=chat_id)

    if data.startswith("gemini_no:"):
        job_id = data.split(":", 1)[1]
        await database.update_job_status(job_id, "complete")
        await answer_callback_query(cq_id)

    elif data.startswith("gemini_yes:"):
        # Slice #4 implements enrichment; stub here
        job_id = data.split(":", 1)[1]
        log.info("gemini_yes_stub", job_id=job_id, note="Phase 2 not yet implemented")
        await answer_callback_query(cq_id, text="Gemini enrichment coming soon!")

    elif data.startswith("prd_build_spec:"):
        # Slice #7 implements intent routing; stub here
        job_id = data.split(":", 1)[1]
        log.info("prd_build_spec_stub", job_id=job_id, note="PRD spec not yet implemented")
        await answer_callback_query(cq_id)

    else:
        log.warning("unknown_callback", data=data)
        await answer_callback_query(cq_id)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        log.warning("webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret")

    update = await request.json()

    # Handle callback queries (inline keyboard button presses)
    callback = update.get("callback_query")
    if callback:
        await _handle_callback(callback)
        return {"ok": True}

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

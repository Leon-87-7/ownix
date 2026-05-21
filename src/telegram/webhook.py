"""POST /webhook — receives Telegram updates and callback queries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Header, HTTPException, Request

from src import database, queue
from src.config import settings
from src.telegram.sender import answer_callback_query, download_photo, send_message
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline

log = get_logger(__name__)
router = APIRouter()


async def _is_batch_active(chat_id: int) -> bool:
    return bool(await queue._client().get(f"photo_batch_active:{chat_id}"))


async def _add_to_batch(chat_id: int, file_id: str) -> None:
    client = queue._client()
    await client.rpush(f"photo_batch_files:{chat_id}", file_id)
    await client.expire(f"photo_batch_files:{chat_id}", 300)


async def _get_batch_files(chat_id: int) -> list[str]:
    return await queue._client().lrange(f"photo_batch_files:{chat_id}", 0, -1)


async def _clear_batch(chat_id: int) -> None:
    client = queue._client()
    await client.delete(f"photo_batch_active:{chat_id}", f"photo_batch_files:{chat_id}")


async def _handle_single_photo(chat_id: int, file_id: str, caption: str | None) -> None:
    from src.services.gemini_photo import call_gemini_photo_links
    from src.utils.markdown import build_links_message

    await send_message(chat_id, "🔍 Scanning image for links...")
    photo_bytes, mime_type = await download_photo(file_id)
    result = await call_gemini_photo_links(
        [{"bytes": photo_bytes, "mime_type": mime_type}],
        settings.GEMINI_FREE_API_KEY,
        settings.GEMINI_PAID_API_KEY,
        caption,
    )
    links = result.get("links", [])
    summary = result.get("summary", "")
    if links:
        await send_message(chat_id, build_links_message(links))
        if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
            from src import brain
            asyncio.create_task(
                brain.ingest_links(links, topic=summary, source_job_id=f"photo_{chat_id}")
            )
    else:
        await send_message(
            chat_id,
            f"🔍 No links found in this image.\nThat is what I did see:\n{summary}",
        )


async def _process_batch(chat_id: int) -> None:
    from src.services.gemini_photo import call_gemini_photo_links
    from src.utils.markdown import build_links_message

    file_ids = await _get_batch_files(chat_id)
    await _clear_batch(chat_id)
    if not file_ids:
        await send_message(chat_id, "🔍 No links found in this image.")
        return
    await send_message(chat_id, f"📸 Processing {len(file_ids)} image(s)...")
    images = []
    for fid in file_ids:
        b, mt = await download_photo(fid)
        images.append({"bytes": b, "mime_type": mt})
    result = await call_gemini_photo_links(
        images, settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY
    )
    links = result.get("links", [])
    if links:
        await send_message(chat_id, build_links_message(links))
        if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
            from src import brain
            asyncio.create_task(
                brain.ingest_links(
                    links,
                    topic=result.get("summary", ""),
                    source_job_id=f"photo_batch_{chat_id}",
                )
            )
    else:
        await send_message(chat_id, "🔍 No links found in this image.")


async def _batch_auto_close(chat_id: int) -> None:
    await asyncio.sleep(300)
    if await _is_batch_active(chat_id):
        await _process_batch(chat_id)


async def _handle_callback(callback: dict) -> None:
    """Dispatch callback_query events from inline keyboard button presses."""
    from src.telegram.sender import (
        answer_callback_query,
        send_force_reply,
        send_inline_keyboard,
        send_message,
    )
    cq_id = callback.get("id", "")
    data = callback.get("data", "")
    chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
    log.info("callback_received", callback_data=data, chat_id=chat_id)

    if data.startswith("gemini_no:"):
        job_id = data.split(":", 1)[1]
        await database.update_job_status(job_id, "done")
        await answer_callback_query(cq_id)

    elif data.startswith("gemini_yes:"):
        job_id = data.split(":", 1)[1]
        job = await database.get_job(job_id)
        if not job or job.get("status") != "transcript_done":
            await answer_callback_query(cq_id, text="This job is not ready for enrichment.")
            return
        await database.update_job_status(job_id, "enriching")
        await queue.enqueue({"task": "enrichment", "job_id": job_id})
        await answer_callback_query(cq_id)

    elif data.startswith("prd_build_spec:"):
        job_id = data.split(":", 1)[1]
        await send_inline_keyboard(
            chat_id,
            "📐 Build Spec — pick a path:",
            buttons=[[
                {"text": "🤖 Build auto Spec", "callback_data": f"prd_auto:{job_id}"},
                {"text": "✍️ Text your intent", "callback_data": f"prd_intent_prompt:{job_id}"},
            ]],
        )
        await answer_callback_query(cq_id)

    elif data.startswith("prd_auto:") or data.startswith("prd_retry_auto:"):
        job_id = data.split(":", 1)[1]
        job = await database.get_job(job_id)
        if not job:
            await answer_callback_query(cq_id, text="Job not found.")
            return
        await answer_callback_query(cq_id)
        if job.get("prd_auto_status") == "done" and job.get("prd_auto_json"):
            await send_message(chat_id, "📐 Re-sending your PRD...")
            await queue.enqueue({"task": "prd_auto_resend", "job_id": job_id})
        else:
            # Lazy generation. Atomic lock try before enqueueing.
            async with database.connection() as conn:
                cur = await conn.execute(
                    "UPDATE jobs SET prd_auto_status='generating', updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND (prd_auto_status IS NULL OR prd_auto_status='error')",
                    (job_id,),
                )
                await conn.commit()
                acquired = cur.rowcount > 0
            if acquired:
                await send_message(chat_id, "📐 Generating PRD, hang tight...")
                await queue.enqueue({"task": "prd_auto", "job_id": job_id})
            else:
                await send_message(chat_id, "📐 PRD already generating, hang tight.")

    elif data.startswith("prd_intent_prompt:"):
        job_id = data.split(":", 1)[1]
        existing = await database.get_chat_state(chat_id)
        if existing and existing["job_id"] == job_id:
            await answer_callback_query(cq_id)
            return
        await database.set_chat_state(chat_id=chat_id, mode="awaiting_intent", job_id=job_id)
        log.info("prd.chat_state.armed", chat_id=chat_id, job_id=job_id)
        await send_force_reply(
            chat_id,
            'Reply with your project direction. Example: "desktop app for agentic image '
            'processing" (reply within 10 minutes; type /cancel to abandon)',
        )
        await answer_callback_query(cq_id)

    elif data.startswith("prd_retry_intent:"):
        job_id = data.split(":", 1)[1]
        job = await database.get_job(job_id)
        if not job or not (job.get("prd_intent_text") or "").strip():
            await answer_callback_query(cq_id, text="No prior intent to retry — use ✍️ New Intent.")
            return
        await answer_callback_query(cq_id)
        await send_message(chat_id, "📐 Generating PRD, hang tight...")
        await queue.enqueue({"task": "prd_intent", "job_id": job_id})

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

    photo = message.get("photo")
    if photo and chat_id:
        file_id = photo[-1]["file_id"]
        caption = message.get("caption") or None
        if await _is_batch_active(chat_id):
            await _add_to_batch(chat_id, file_id)
        else:
            asyncio.create_task(_handle_single_photo(chat_id, file_id, caption))
        return {"ok": True}

    if not chat_id or not text:
        return {"ok": True}

    # Telegram slash commands
    if text.startswith("/find "):
        query = text[6:].strip()
        if not query:
            await send_message(chat_id, "Usage: /find <query>")
            return {"ok": True}
        from src import brain

        results = await brain.search_links(query, top_k=5)
        if not results:
            await send_message(chat_id, "No relevant links found in your brain.")
        else:
            lines = []
            for r in results:
                lines.append(
                    f"🔗 *{r['title']}* — {r['url']}\n   Topic: {r['topic']}\n   Score: {r['score']:.2f}"
                )
            await send_message(chat_id, "\n\n".join(lines), parse_mode="Markdown")
        return {"ok": True}

    if text == "/rebuild-graph":
        from src import brain

        if brain._rebuild_lock.locked():
            await send_message(chat_id, "Rebuild already in progress — please wait.")
            return {"ok": True}
        await send_message(chat_id, "Brain rebuild started — will take a few minutes")

        async def _do_rebuild():
            try:
                n = await brain.rebuild_graph()
                await send_message(chat_id, f"Graph rebuilt — {n} nodes written.")
            except Exception:
                await send_message(chat_id, "Rebuild failed. Check logs.")

        asyncio.create_task(_do_rebuild())
        return {"ok": True}

    if text == "/photoBatch-start":
        client = queue._client()
        await client.set(f"photo_batch_active:{chat_id}", "1", ex=300)
        await client.delete(f"photo_batch_files:{chat_id}")
        asyncio.create_task(_batch_auto_close(chat_id))
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=300)).strftime("%H:%M:%S")
        await send_message(chat_id, f"📸 Batch mode started! The bus leaves at {deadline} UTC.")
        return {"ok": True}

    if text == "/photoBatch-end":
        if not await _is_batch_active(chat_id):
            await send_message(chat_id, "No active batch — use /photoBatch-start first.")
            return {"ok": True}
        asyncio.create_task(_process_batch(chat_id))
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
    await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")
    return {"ok": True}

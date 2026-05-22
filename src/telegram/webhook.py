"""POST /webhook — receives Telegram updates and callback queries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Header, HTTPException, Request

from src import database, queue
from src.config import settings
from src.telegram.sender import (
    answer_callback_query,
    download_photo,
    send_force_reply,
    send_inline_keyboard,
    send_message,
)
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline

log = get_logger(__name__)
router = APIRouter()


async def _is_batch_active(chat_id: int) -> bool:
    return bool(await queue._client().get(f"photo_batch_active:{chat_id}"))


async def _add_to_batch(chat_id: int, file_id: str) -> None:
    client = queue._client()
    # redis-py async stubs miss rpush/lrange — they're awaitable at runtime.
    await client.rpush(f"photo_batch_files:{chat_id}", file_id)  # pyright: ignore[reportGeneralTypeIssues]
    await client.expire(f"photo_batch_files:{chat_id}", 300)


async def _get_batch_files(chat_id: int) -> list[str]:
    return await queue._client().lrange(f"photo_batch_files:{chat_id}", 0, -1)  # pyright: ignore[reportGeneralTypeIssues]


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
        elif job.get("prd_auto_status") == "generating":
            await send_message(chat_id, "📐 PRD already generating, hang tight.")
        else:
            # Lazy generation — worker is the single source of truth for the lock.
            # Webhook just enqueues optimistically; run_auto handles the atomic lock.
            await send_message(chat_id, "📐 Generating PRD, hang tight...")
            await queue.enqueue({"task": "prd_auto", "job_id": job_id})

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

    elif data.startswith("enrichment_retry:"):
        job_id = data.split(":", 1)[1]
        job = await database.get_job(job_id)
        if not job:
            await answer_callback_query(cq_id, text="Job not found.")
            return
        status = job.get("status")
        if status not in ("error", "transcript_done"):
            log.warning("enrichment_retry_rejected", job_id=job_id, status=status)
            await answer_callback_query(cq_id, text=f"Can't retry — job is in status '{status}'.")
            return
        await answer_callback_query(cq_id)
        await database.update_job_status(job_id, "enriching")
        await queue.enqueue({"task": "enrichment", "job_id": job_id})
        log.info("enrichment_retry_enqueued", job_id=job_id)
        await send_message(chat_id, "🍪 Retrying Gemini enrichment...")

    else:
        log.warning("unknown_callback", data=data)
        await answer_callback_query(cq_id)


async def _dispatch_slash(chat_id: int, text: str) -> None:
    """Slash command dispatch. Clears chat_state as a side effect (except /cancel reads first)."""
    parts = text.split()
    cmd = parts[0].lower()

    if cmd == "/cancel":
        state = await database.get_chat_state(chat_id)
        await database.clear_chat_state(chat_id)
        if state and state.get("mode") == "awaiting_intent":
            await send_message(chat_id, "✍️ Intent canceled.")
        else:
            await send_message(chat_id, "Nothing to cancel.")
        return

    # All other slash commands clear chat_state first
    await database.clear_chat_state(chat_id)

    if cmd == "/spec":
        await _handle_spec(chat_id, parts)
        return
    if cmd == "/find" and len(parts) > 1:
        query = " ".join(parts[1:]).strip()
        from src import brain
        results = await brain.search_links(query, top_k=5)
        if not results:
            await send_message(chat_id, "No relevant links found in your brain.")
        else:
            lines = [
                f"🔗 *{r['title']}* — {r['url']}\n   Topic: {r['topic']}\n   Score: {r['score']:.2f}"
                for r in results
            ]
            await send_message(chat_id, "\n\n".join(lines), parse_mode="Markdown")
        return
    if cmd == "/find":
        await send_message(chat_id, "Usage: /find <query>")
        return
    if cmd == "/rebuild-graph":
        from src import brain
        if brain._rebuild_lock.locked():
            await send_message(chat_id, "Rebuild already in progress — please wait.")
            return
        await send_message(chat_id, "Brain rebuild started — will take a few minutes")
        async def _do_rebuild():
            try:
                n = await brain.rebuild_graph()
                await send_message(chat_id, f"Graph rebuilt — {n} nodes written.")
            except Exception:
                await send_message(chat_id, "Rebuild failed. Check logs.")
        asyncio.create_task(_do_rebuild())
        return
    if cmd == "/photobatch-start":
        client = queue._client()
        await client.set(f"photo_batch_active:{chat_id}", "1", ex=300)
        await client.delete(f"photo_batch_files:{chat_id}")
        asyncio.create_task(_batch_auto_close(chat_id))
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=300)).strftime("%H:%M:%S")
        await send_message(chat_id, f"📸 Batch mode started! The bus leaves at {deadline} UTC.")
        return
    if cmd == "/photobatch-end":
        if not await _is_batch_active(chat_id):
            await send_message(chat_id, "No active batch — use /photoBatch-start first.")
            return
        asyncio.create_task(_process_batch(chat_id))
        return
    # /start, /help, and any other slash falls through — Telegram handles natively


async def _handle_awaiting_intent(chat_id: int, text: str, state: dict) -> None:
    """Routing path when chat_state is armed and not expired."""
    job_id = state["job_id"]
    pipeline = detect_pipeline(text)
    if pipeline in ("short", "long"):
        await database.clear_chat_state(chat_id)
        await send_message(chat_id, "🔄 Started new job; previous intent canceled.")
        log.info("prd.chat_state.canceled_by_url", chat_id=chat_id, old_job_id=job_id)
        new_job_id = await database.create_job(
            chat_id=chat_id, url=text, content_type=pipeline
        )
        await queue.enqueue({"task": "video", "job_id": new_job_id})
        await send_message(chat_id, f"📥 Received! \njob_{new_job_id[-4:]}")
        return
    stripped = text.strip()
    if len(stripped) < 5:
        await send_message(
            chat_id,
            "📐 Intent too short (min 5 chars). Reply with a few words describing your project direction.",
        )
        log.info("prd.intent.too_short", chat_id=chat_id, intent_text_len=len(stripped))
        return
    if len(stripped) > 1000:
        await send_message(
            chat_id,
            "📐 Intent too long (max 1000 chars). Try a shorter direction.",
        )
        log.info("prd.intent.too_long", chat_id=chat_id, intent_text_len=len(stripped))
        return
    # Valid intent — persist to DB and enqueue
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET prd_intent_text=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (stripped, job_id),
        )
        await conn.commit()
    await queue.enqueue({"task": "prd_intent", "job_id": job_id})
    await database.clear_chat_state(chat_id)
    log.info("prd.intent.enqueued", chat_id=chat_id, job_id=job_id, intent_text_len=len(stripped))
    log.info("prd.chat_state.consumed", chat_id=chat_id, job_id=job_id)


async def _handle_spec(chat_id: int, parts: list[str]) -> None:
    """Dispatch /spec <suffix> [intent...]."""
    if len(parts) < 2:
        await send_message(
            chat_id,
            'Usage: /spec <suffix> [intent text...]\nExample: /spec ABCD desktop app for X',
        )
        return
    suffix = parts[1][-4:]
    intent_text = " ".join(parts[2:]).strip() or None
    if intent_text is not None:
        if len(intent_text) < 5:
            await send_message(chat_id, "📐 Intent too short (min 5 chars).")
            return
        if len(intent_text) > 1000:
            await send_message(chat_id, "📐 Intent too long (max 1000 chars).")
            return
    rows = await database.find_jobs_by_suffix(chat_id, suffix)
    long_matches = [
        j for j in rows
        if j["content_type"] == "long" and j["status"] in ("transcript_done", "done")
    ]
    short_matches = [j for j in rows if j["content_type"] == "short"]

    if not long_matches and not short_matches:
        recent = await database.get_recent_jobs(chat_id, 5)
        bullet_lines = "\n".join(
            f"• job_{j['id'][-4:]} — {j.get('title') or '(no title)'} ({j['content_type']}/{j['status']})"
            for j in recent
        )
        await send_message(
            chat_id,
            f"No job ending in {suffix} found.\nLast 5 jobs in this chat:\n{bullet_lines}",
        )
        log.info("prd.spec.no_match", chat_id=chat_id, suffix=suffix)
        return

    if not long_matches and short_matches:
        await send_message(
            chat_id,
            f"📐 PRD is only available for long videos. Job {suffix} is a short.",
        )
        log.info("prd.spec.short_video_rejected", chat_id=chat_id, suffix=suffix)
        return

    job = long_matches[0]
    job_id = job["id"]
    title = job.get("title") or "(no title)"
    await send_message(chat_id, f'📐 PRD for: "{title}" — generating ...')
    log.info("prd.spec.matched", chat_id=chat_id, suffix=suffix, job_id=job_id, intent=bool(intent_text))

    if intent_text:
        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET prd_intent_text=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (intent_text, job_id),
            )
            await conn.commit()
        await queue.enqueue({"task": "prd_intent", "job_id": job_id})
        log.info("prd.intent.enqueued", chat_id=chat_id, job_id=job_id, intent_text_len=len(intent_text))
    else:
        if job.get("prd_auto_status") == "done" and job.get("prd_auto_json"):
            await queue.enqueue({"task": "prd_auto_resend", "job_id": job_id})
        else:
            await queue.enqueue({"task": "prd_auto", "job_id": job_id})


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

    log.info("webhook_received", chat_id=chat_id, message_id=message_id, text_len=len(text))

    # Photo path (unchanged)
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

    # 1. Slash command path
    if text.startswith("/"):
        await _dispatch_slash(chat_id, text)
        return {"ok": True}

    # 2. Awaiting-intent path
    state = await database.get_chat_state(chat_id)
    if state:
        from datetime import datetime as _dt, timezone as _tz
        expires_at_raw = state["expires_at"]
        try:
            expires_at = _dt.fromisoformat(expires_at_raw.replace(" ", "T"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=_tz.utc)
        except Exception:
            expires_at = None
        if expires_at and expires_at > _dt.now(_tz.utc):
            await _handle_awaiting_intent(chat_id, text, state)
            return {"ok": True}
        else:
            log.info("prd.chat_state.expired_or_missed", chat_id=chat_id)
            # fall through to normal URL routing

    # 3. Normal URL routing
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
        chat_id=chat_id, url=text, content_type=pipeline, message_id=message_id,
    )
    await queue.enqueue({"task": "video", "job_id": job_id})
    await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")
    return {"ok": True}

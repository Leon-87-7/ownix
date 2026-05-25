"""POST /webhook — receives Telegram updates and callback queries."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
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
from src.templates import PROMPT_TEMPLATES
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline

log = get_logger(__name__)
router = APIRouter()


@dataclass
class CallbackCtx:
    chat_id: int
    job_id: str      # payload after ":" in callback data
    cq_id: str
    data: str        # full raw data string


@dataclass
class SlashCtx:
    chat_id: int
    parts: list[str]   # split command + args
    message_id: int | None


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


async def _enrich_github_repos(links: list[dict]) -> list[dict]:
    """Mutate links in-place with GitHub enrichment data.

    For each link whose URL contains ``github.com``, attempts to fetch
    repository metadata via ``enrich_repo``.  Sets ``_enriched=True``
    and attaches ``_stars``, ``_forks``, ``_language``, ``_days_ago``,
    ``_gh_description`` on success; sets ``_enriched=False`` on failure
    (404, network error, or missing token).

    If ``settings.GITHUB_TOKEN`` is absent, returns ``links`` unchanged
    (no ``_enriched`` keys are set, so ``build_enriched_links_message``
    renders them via its un-enriched ``others`` branch).
    """
    from urllib.parse import urlparse
    from src.services.github import enrich_repo

    token = settings.GITHUB_TOKEN
    if not token:
        return links

    gh_links = [lnk for lnk in links if "github.com" in lnk.get("url", "")]
    if not gh_links:
        return links

    def _parse_owner_repo(url: str) -> tuple[str, str] | None:
        parsed = urlparse(url)
        segments = [s for s in parsed.path.split("/") if s]
        if len(segments) >= 2:
            return segments[0], segments[1]
        return None

    parsed_pairs = [_parse_owner_repo(lnk["url"]) for lnk in gh_links]

    # gather concurrently only for valid owner/repo pairs
    valid_indices = [(i, pair) for i, pair in enumerate(parsed_pairs) if pair is not None]
    if valid_indices:
        coros = [enrich_repo(owner, repo, token) for _, (owner, repo) in valid_indices]
        api_results: list[dict | None] = list(await asyncio.gather(*coros, return_exceptions=False))
    else:
        api_results = []

    now = datetime.now(timezone.utc)
    result_iter = iter(api_results)

    for i, lnk in enumerate(gh_links):
        pair = parsed_pairs[i]
        if pair is None:
            lnk["_enriched"] = False
            continue
        data = next(result_iter)
        if data is None:
            lnk["_enriched"] = False
        else:
            pushed_at_raw = data.get("pushed_at") or ""
            try:
                pushed = datetime.fromisoformat(pushed_at_raw.replace("Z", "+00:00"))
                days_ago = (now - pushed).days
            except Exception:
                days_ago = 0
            lnk["_enriched"] = True
            lnk["_stars"] = data.get("stars", 0)
            lnk["_forks"] = data.get("forks", 0)
            lnk["_language"] = data.get("language")
            lnk["_days_ago"] = days_ago
            lnk["_gh_description"] = data.get("description")

    return links


async def _handle_single_photo(chat_id: int, file_id: str, caption: str | None) -> None:
    from src.services.gemini_photo import call_gemini_photo_links
    from src.utils.markdown import build_enriched_links_message

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
        links = await _enrich_github_repos(links)
        await send_message(chat_id, build_enriched_links_message(links))
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
    from src.utils.markdown import build_enriched_links_message

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
        links = await _enrich_github_repos(links)
        await send_message(chat_id, build_enriched_links_message(links))
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


async def _cb_gemini_no(ctx: CallbackCtx) -> None:
    await database.update_job_status(ctx.job_id, "done")
    await answer_callback_query(ctx.cq_id)


async def _cb_gemini_yes(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job or job.get("status") != "transcript_done":
        await answer_callback_query(ctx.cq_id, text="This job is not ready for enrichment.")
        return
    await database.update_job_status(ctx.job_id, "enriching")
    await queue.enqueue({"task": "enrichment", "job_id": ctx.job_id})
    await answer_callback_query(ctx.cq_id)


async def _cb_prd_build_spec(ctx: CallbackCtx) -> None:
    await send_inline_keyboard(
        ctx.chat_id,
        "📐 Build Spec — pick a path:",
        buttons=[[
            {"text": "🤖 Build auto Spec", "callback_data": f"prd_auto:{ctx.job_id}"},
            {"text": "✍️ Text your intent", "callback_data": f"prd_intent_prompt:{ctx.job_id}"},
        ]],
    )
    await answer_callback_query(ctx.cq_id)


async def _cb_prd_auto(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job:
        await answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    await answer_callback_query(ctx.cq_id)
    if job.get("prd_auto_status") == "done" and job.get("prd_auto_json"):
        await send_message(ctx.chat_id, "📐 Re-sending your PRD...")
        await queue.enqueue({"task": "prd_auto_resend", "job_id": ctx.job_id})
    elif job.get("prd_auto_status") == "generating":
        await send_message(ctx.chat_id, "📐 PRD already generating, hang tight.")
    else:
        # Lazy generation — worker is the single source of truth for the lock.
        # Webhook just enqueues optimistically; run_auto handles the atomic lock.
        await send_message(ctx.chat_id, "📐 Generating PRD, hang tight...")
        await queue.enqueue({"task": "prd_auto", "job_id": ctx.job_id})


async def _cb_prd_intent_prompt(ctx: CallbackCtx) -> None:
    existing = await database.get_chat_state(ctx.chat_id)
    if existing and existing["job_id"] == ctx.job_id:
        await answer_callback_query(ctx.cq_id)
        return
    await database.set_chat_state(chat_id=ctx.chat_id, mode="awaiting_intent", job_id=ctx.job_id)
    log.info("prd.chat_state.armed", chat_id=ctx.chat_id, job_id=ctx.job_id)
    await send_force_reply(
        ctx.chat_id,
        'Reply with your project direction. Example: "desktop app for agentic image '
        'processing" (reply within 10 minutes; type /cancel to abandon)',
    )
    await answer_callback_query(ctx.cq_id)


async def _cb_prd_retry_intent(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job or not (job.get("prd_intent_text") or "").strip():
        await answer_callback_query(ctx.cq_id, text="No prior intent to retry — use ✍️ New Intent.")
        return
    await answer_callback_query(ctx.cq_id)
    await send_message(ctx.chat_id, "📐 Generating PRD, hang tight...")
    await queue.enqueue({"task": "prd_intent", "job_id": ctx.job_id})


async def _cb_enrichment_retry(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job:
        await answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    status = job.get("status")
    if status not in ("error", "transcript_done"):
        log.warning("enrichment_retry_rejected", job_id=ctx.job_id, status=status)
        await answer_callback_query(ctx.cq_id, text=f"Can't retry — job is in status '{status}'.")
        return
    await answer_callback_query(ctx.cq_id)
    await database.update_job_status(ctx.job_id, "enriching")
    await queue.enqueue({"task": "enrichment", "job_id": ctx.job_id})
    log.info("enrichment_retry_enqueued", job_id=ctx.job_id)
    await send_message(ctx.chat_id, "🍪 Retrying Gemini enrichment...")


async def _cb_reprocess(ctx: CallbackCtx) -> None:
    """One-tap retry for a 'processing' job orphaned by a restart (ADR-0010).

    Re-submits the stored URL as a brand-new job — identical to the user resending
    the link — so the orphaned row's Drive file / Sheets row are never re-touched.
    """
    job = await database.get_job(ctx.job_id)
    if not job:
        await answer_callback_query(ctx.cq_id, text="Job not found — please resend the link.")
        return
    await answer_callback_query(ctx.cq_id)
    new_job_id = await database.create_job(
        chat_id=ctx.chat_id,
        url=job["url"],
        content_type=job["content_type"],
        template=job.get("template"),
    )
    await queue.enqueue({"task": "video", "job_id": new_job_id})
    log.info("reprocess_enqueued", orphan_job_id=ctx.job_id, new_job_id=new_job_id)
    await send_message(ctx.chat_id, f"📥 Received! \njob_{new_job_id[-4:]}")


_CALLBACK_TABLE: dict[str, Callable[[CallbackCtx], Awaitable[None]]] = {
    "gemini_no":         _cb_gemini_no,
    "gemini_yes":        _cb_gemini_yes,
    "prd_build_spec":    _cb_prd_build_spec,
    "prd_auto":          _cb_prd_auto,
    "prd_retry_auto":    _cb_prd_auto,
    "prd_intent_prompt": _cb_prd_intent_prompt,
    "prd_retry_intent":  _cb_prd_retry_intent,
    "enrichment_retry":  _cb_enrichment_retry,
    "reprocess":         _cb_reprocess,
}


async def _handle_callback(callback: dict) -> None:
    """Dispatch callback_query events from inline keyboard button presses."""
    cq_id = callback.get("id", "")
    data = callback.get("data", "")
    chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
    log.info("callback_received", callback_data=data, chat_id=chat_id)

    prefix, _, job_id = data.partition(":")
    handler = _CALLBACK_TABLE.get(prefix)
    if handler is None:
        log.warning("unknown_callback", data=data)
        await answer_callback_query(cq_id)
        return

    ctx = CallbackCtx(chat_id=chat_id, job_id=job_id, cq_id=cq_id, data=data)
    await handler(ctx)


async def _cmd_cancel(ctx: SlashCtx) -> None:
    state = await database.get_chat_state(ctx.chat_id)
    await database.clear_chat_state(ctx.chat_id)
    await queue._client().delete(f"pending_template:{ctx.chat_id}")
    if state and state.get("mode") == "awaiting_intent":
        await send_message(ctx.chat_id, "✍️ Intent canceled.")
    else:
        await send_message(ctx.chat_id, "Nothing to cancel.")


async def _cmd_spec(ctx: SlashCtx) -> None:
    await _handle_spec(ctx.chat_id, ctx.parts)


async def _cmd_find(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /find <query>")
        return
    query = " ".join(ctx.parts[1:]).strip()
    from src import brain
    results = await brain.search_links(query, top_k=5)
    if not results:
        await send_message(ctx.chat_id, "No relevant links found in your brain.")
    else:
        lines = [
            f"🔗 *{r['title']}* — {r['url']}\n   Topic: {r['topic']}\n   Score: {r['score']:.2f}"
            for r in results
        ]
        await send_message(ctx.chat_id, "\n\n".join(lines), parse_mode="Markdown")


async def _cmd_rebuild_graph(ctx: SlashCtx) -> None:
    from src import brain
    if brain._rebuild_lock.locked():
        await send_message(ctx.chat_id, "Rebuild already in progress — please wait.")
        return
    await send_message(ctx.chat_id, "Brain rebuild started — will take a few minutes")

    async def _do_rebuild() -> None:
        try:
            n = await brain.rebuild_graph()
            await send_message(ctx.chat_id, f"Graph rebuilt — {n} nodes written.")
        except Exception:
            await send_message(ctx.chat_id, "Rebuild failed. Check logs.")

    asyncio.create_task(_do_rebuild())


async def _cmd_photobatch_start(ctx: SlashCtx) -> None:
    client = queue._client()
    await client.set(f"photo_batch_active:{ctx.chat_id}", "1", ex=300)
    await client.delete(f"photo_batch_files:{ctx.chat_id}")
    asyncio.create_task(_batch_auto_close(ctx.chat_id))
    deadline = (datetime.now(timezone.utc) + timedelta(seconds=300)).strftime("%H:%M:%S")
    await send_message(ctx.chat_id, f"📸 Batch mode started! The bus leaves at {deadline} UTC.")


async def _cmd_photobatch_end(ctx: SlashCtx) -> None:
    if not await _is_batch_active(ctx.chat_id):
        await send_message(ctx.chat_id, "No active batch — use /photoBatch-start first.")
        return
    asyncio.create_task(_process_batch(ctx.chat_id))


async def _cmd_template(ctx: SlashCtx) -> None:
    template = ctx.parts[0][1:]
    if len(ctx.parts) < 2:
        await queue._client().set(f"pending_template:{ctx.chat_id}", template, ex=120)
        await send_message(ctx.chat_id, f"📥 `/{template}` ready — send the URL now (2 min window).")
        return
    url = ctx.parts[1]
    pipeline = detect_pipeline(url)
    if pipeline == "rejected":
        await send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, and TikTok videos.",
        )
        return
    job_id = await database.create_job(
        chat_id=ctx.chat_id,
        url=url,
        content_type=pipeline,
        message_id=ctx.message_id,
        template=template,
    )
    await database.update_job_status(
        job_id, "pending",
        template_detection_method="explicit_command",
    )
    await queue.enqueue({"task": "video", "job_id": job_id})
    await send_message(ctx.chat_id, f"📥 Received with **{template}** template!\njob_{job_id[-4:]}")


_SLASH_TABLE: dict[str, Callable[[SlashCtx], Awaitable[None]]] = {
    "/cancel":           _cmd_cancel,
    "/spec":             _cmd_spec,
    "/find":             _cmd_find,
    "/rebuild-graph":    _cmd_rebuild_graph,
    "/photobatch-start": _cmd_photobatch_start,
    "/photobatch-end":   _cmd_photobatch_end,
    **{f"/{t}": _cmd_template for t in PROMPT_TEMPLATES},
}


async def _dispatch_slash(chat_id: int, text: str, message_id: int | None = None) -> None:
    """Slash command dispatch. Clears chat_state as a side effect (except /cancel reads first)."""
    parts = text.split()
    cmd = parts[0].lower()
    handler = _SLASH_TABLE.get(cmd)
    if handler is None:
        return
    ctx = SlashCtx(chat_id=chat_id, parts=parts, message_id=message_id)
    if cmd != "/cancel":
        await database.clear_chat_state(chat_id)
        await queue._client().delete(f"pending_template:{chat_id}")
    await handler(ctx)


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
        await _dispatch_slash(chat_id, text, message_id)
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
    client = queue._client()
    pending_template: str | None = await client.get(f"pending_template:{chat_id}")
    if pending_template:
        await client.delete(f"pending_template:{chat_id}")

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
        template=pending_template,
    )
    if pending_template:
        await database.update_job_status(
            job_id, "pending",
            template_detection_method="explicit_command",
        )
    await queue.enqueue({"task": "video", "job_id": job_id})
    if pending_template:
        await send_message(chat_id, f"📥 Received with **{pending_template}** template!\njob_{job_id[-4:]}")
    else:
        await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")
    return {"ok": True}

"""POST /webhook — receives Telegram updates and callback queries."""

from __future__ import annotations

import asyncio
import hashlib
import html
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress

import httpx
from secrets import compare_digest
from urllib.parse import urlparse
from dataclasses import dataclass

from fastapi import APIRouter, Header, HTTPException, Request

import re

from src import database, queue
from src.config import settings
from src.services import storage
from src.telegram.sender import (
    answer_callback_query,
    download_file,
    download_photo,
    edit_message_text,
    forward_message,
    send_document,
    send_force_reply,
    send_inline_keyboard,
    send_message,
)
from src.templates import PROMPT_TEMPLATES
from src.utils import job_tag
from src.utils.logger import get_logger
from src.utils.validators import detect_pipeline, normalize_repo_url, _ARTICLE_HINT, _REPO_HINT

log = get_logger(__name__)
router = APIRouter()

_BATCH_TASKS: dict[str, asyncio.Task] = {}


@dataclass
class CallbackCtx:
    chat_id: int
    job_id: str      # payload after ":" in callback data
    cq_id: str
    data: str        # full raw data string
    message_id: int | None = None  # message_id of the message containing the inline keyboard


@dataclass
class SlashCtx:
    chat_id: int
    parts: list[str]   # split command + args
    message_id: int | None


async def _accumulate_media_group(chat_id: int, media_group_id: str, file_id: str) -> None:
    """Append file_id to the Redis list for this media group, then reset the debounce task."""
    client = queue._client()
    await client.rpush(f"photo_group_files:{media_group_id}", file_id)  # pyright: ignore[reportGeneralTypeIssues]
    await client.expire(f"photo_group_files:{media_group_id}", 60)

    # Cancel any existing debounce task for this group and start a fresh 1-second one.
    existing = _BATCH_TASKS.get(media_group_id)
    if existing and not existing.done():
        existing.cancel()

    async def _debounce() -> None:
        await asyncio.sleep(1)
        try:
            await _process_media_group(chat_id, media_group_id)
        finally:
            _BATCH_TASKS.pop(media_group_id, None)

    _BATCH_TASKS[media_group_id] = asyncio.create_task(_debounce())


async def _report_photo_links(
    chat_id: int, result: dict, source_job_id: str, *, plural: bool
) -> None:
    """Send enriched links (and kick off brain ingest) or a no-links notice."""
    from src.services.github import enrich_github_links
    from src.utils.markdown import build_enriched_links_message

    links = result.get("links", [])
    summary = result.get("summary", "")
    if links:
        links = await enrich_github_links(links)
        await send_message(chat_id, build_enriched_links_message(links))
        if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
            from src import brain
            asyncio.create_task(
                brain.ingest_links(links, topic=summary, source_job_id=source_job_id)
            )
    else:
        noun = "these images" if plural else "this image"
        await send_message(
            chat_id,
            f"🔍 No links found in {noun}.\nThat is what I did see:\n{summary}",
        )


async def _handle_single_photo(chat_id: int, file_id: str, caption: str | None) -> None:
    from src.services.gemini import call_gemini_photo_links

    await send_message(chat_id, "🔍 Scanning image for links...")
    photo_bytes, mime_type = await download_photo(file_id)
    result = await call_gemini_photo_links(
        [{"bytes": photo_bytes, "mime_type": mime_type}],
        caption=caption,
    )
    await _report_photo_links(chat_id, result, f"photo_{chat_id}", plural=False)


async def _process_media_group(chat_id: int, media_group_id: str) -> None:
    """Read all accumulated file IDs for a media group, download them, and run Gemini."""
    from src.services.gemini import call_gemini_photo_links

    client = queue._client()
    file_ids: list[str] = await client.lrange(f"photo_group_files:{media_group_id}", 0, -1)  # pyright: ignore[reportGeneralTypeIssues]
    await client.delete(f"photo_group_files:{media_group_id}")
    if not file_ids:
        return
    await send_message(chat_id, f"📸 Processing {len(file_ids)} image(s)...")
    images = []
    for fid in file_ids:
        b, mt = await download_photo(fid)
        images.append({"bytes": b, "mime_type": mt})
    result = await call_gemini_photo_links(images, caption=None)
    await _report_photo_links(chat_id, result, f"photo_group_{media_group_id}", plural=True)


async def _cb_gemini_no(ctx: CallbackCtx) -> None:
    await database.update_job_status(ctx.job_id, "done")
    await answer_callback_query(ctx.cq_id)


async def _cb_gemini_yes(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job or job.get("status") != "transcript_done":
        await answer_callback_query(ctx.cq_id, text="This job is not ready for enrichment.")
        return
    await answer_callback_query(ctx.cq_id)
    await send_inline_keyboard(
        ctx.chat_id,
        "✨ Pick a Gemini template:",
        buttons=[
            [
                {"text": "📝 Summary",   "callback_data": f"template_pick:summary:{ctx.job_id}"},
                {"text": "🔧 Method",    "callback_data": f"template_pick:method:{ctx.job_id}"},
            ],
            [
                {"text": "💻 Technical", "callback_data": f"template_pick:technical:{ctx.job_id}"},
                {"text": "⭐ Review",    "callback_data": f"template_pick:review:{ctx.job_id}"},
            ],
            [
                {"text": "📖 Narrative", "callback_data": f"template_pick:narrative:{ctx.job_id}"},
                {"text": "✍️ Freestyle", "callback_data": f"template_freestyle:{ctx.job_id}"},
            ],
        ],
    )


async def _cb_template_pick(ctx: CallbackCtx) -> None:
    # ctx.job_id = "{template}:{actual_job_id}" (everything after first ":")
    template, _, actual_job_id = ctx.job_id.partition(":")
    if not actual_job_id:
        await answer_callback_query(ctx.cq_id, text="Invalid callback data.")
        return
    job = await database.get_job(actual_job_id)
    if not job or job.get("status") != "transcript_done":
        await answer_callback_query(ctx.cq_id, text="Job not ready for enrichment.")
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET template=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (template, actual_job_id),
        )
        await conn.commit()
    if ctx.message_id:
        await edit_message_text(ctx.chat_id, ctx.message_id, f"You chose {template.capitalize()}")
    await queue.enqueue({"task": "enrichment", "job_id": actual_job_id})
    await answer_callback_query(ctx.cq_id)
    log.info("template_pick.enqueued", chat_id=ctx.chat_id, job_id=actual_job_id, template=template)


async def _cb_template_freestyle(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job:
        await answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET template='freestyle', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (ctx.job_id,),
        )
        await conn.commit()
    await database.set_chat_state(ctx.chat_id, mode="awaiting_freestyle", job_id=ctx.job_id, expires_minutes=10)
    await answer_callback_query(ctx.cq_id)
    await send_force_reply(
        ctx.chat_id,
        "✍️ Reply with your Gemini prompt (reply within 10 min; /cancel to abandon)",
        input_field_placeholder="Your Gemini prompt...",
    )
    log.info("template_freestyle.armed", chat_id=ctx.chat_id, job_id=ctx.job_id)


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


async def _cb_article_retry(ctx: CallbackCtx) -> None:
    job = await database.get_job(ctx.job_id)
    if not job:
        await answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    status = job.get("status")
    if status != "error":
        await answer_callback_query(ctx.cq_id, text=f"Can't retry — job is in status '{status}'.")
        return
    await answer_callback_query(ctx.cq_id)
    await database.update_job_status(ctx.job_id, "pending")
    await queue.enqueue({"task": "article", "job_id": ctx.job_id, "skip_document": True})
    log.info("article_retry_enqueued", job_id=ctx.job_id)
    await send_message(ctx.chat_id, f"{job_tag(ctx.job_id)}\n📥 Retrying article analysis...")


def _task_for(pipeline: str | None) -> str:
    """Worker task name for a pipeline / content_type. Default video."""
    return pipeline if pipeline in ("repo", "article", "document") else "video"


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
    task_type = _task_for(job["content_type"])
    await queue.enqueue({"task": task_type, "job_id": new_job_id})
    log.info("reprocess_enqueued", orphan_job_id=ctx.job_id, new_job_id=new_job_id)
    await send_message(ctx.chat_id, f"📥 Received! \njob_{new_job_id[-4:]}")


async def _cb_show_done(ctx: CallbackCtx) -> None:
    """Forward the original completion message and collapse the dedup keyboard."""
    job = await database.get_job(ctx.job_id)
    if not job or not job.get("bot_message_id"):
        await answer_callback_query(ctx.cq_id, text="Original message not available.")
        return
    await answer_callback_query(ctx.cq_id)
    await forward_message(ctx.chat_id, ctx.chat_id, job["bot_message_id"])
    if ctx.message_id:
        await edit_message_text(ctx.chat_id, ctx.message_id, "here you go")


async def _cb_document_md(ctx: CallbackCtx) -> None:
    """📄 Get Markdown — render/serve parsed/<sha>.md on demand (#156)."""
    job = await database.get_job(ctx.job_id)
    if (
        not job
        or job.get("content_type") != "document"
        or str(job.get("chat_id")) != str(ctx.chat_id)
    ):
        await answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    await answer_callback_query(ctx.cq_id)
    from src.processors import document
    try:
        await document.deliver_markdown(job)
    except Exception:
        log.exception("document_md.failed", job_id=ctx.job_id)
        await send_message(ctx.chat_id, f"{job_tag(ctx.job_id)}\n⚠️ Couldn't render Markdown — try again later.")


_CALLBACK_TABLE: dict[str, Callable[[CallbackCtx], Awaitable[None]]] = {
    "gemini_no":          _cb_gemini_no,
    "gemini_yes":         _cb_gemini_yes,
    "template_pick":      _cb_template_pick,
    "template_freestyle":  _cb_template_freestyle,
    "prd_build_spec":     _cb_prd_build_spec,
    "prd_auto":           _cb_prd_auto,
    "prd_retry_auto":     _cb_prd_auto,
    "prd_intent_prompt":  _cb_prd_intent_prompt,
    "prd_retry_intent":   _cb_prd_retry_intent,
    "enrichment_retry":   _cb_enrichment_retry,
    "article_retry":      _cb_article_retry,
    "reprocess":          _cb_reprocess,
    "show_done":          _cb_show_done,
    "document_md":        _cb_document_md,
}


async def _handle_callback(callback: dict) -> None:
    """Dispatch callback_query events from inline keyboard button presses."""
    cq_id = callback.get("id", "")
    data = callback.get("data", "")
    cb_message = callback.get("message") or {}
    chat_id = cb_message.get("chat", {}).get("id")
    cb_message_id = cb_message.get("message_id")
    log.info("callback_received", callback_data=data, chat_id=chat_id)

    prefix, _, job_id = data.partition(":")
    handler = _CALLBACK_TABLE.get(prefix)
    if handler is None:
        log.warning("unknown_callback", data=data)
        await answer_callback_query(cq_id)
        return

    ctx = CallbackCtx(chat_id=chat_id, job_id=job_id, cq_id=cq_id, data=data, message_id=cb_message_id)
    await handler(ctx)


async def _handle_freestyle_url(chat_id: int, url: str, pipeline: str, message_id: int | None) -> None:
    """Shared logic for /freestyle <url> and pending_template=freestyle URL message."""
    job_id = await database.create_job(
        chat_id=chat_id, url=url, content_type=pipeline, message_id=message_id, template="freestyle",
    )
    await database.update_job_status(job_id, "pending", template_detection_method="explicit_command")
    if pipeline == "long":
        await queue.enqueue({"task": "video", "job_id": job_id})
        await send_message(chat_id, f"📥 Received\n✨ Kicking off Gemini analysis (freestyle)\njob_{job_id[-4:]}")
    elif pipeline == "article":
        await send_message(chat_id, f"📥 Article received — reply with your prompt\njob_{job_id[-4:]}")
    await database.set_chat_state(chat_id, mode="awaiting_freestyle", job_id=job_id, expires_minutes=10)
    await send_force_reply(
        chat_id,
        "✍️ Reply with your Gemini prompt (reply within 10 min; /cancel to abandon)",
        input_field_placeholder="Your Gemini prompt...",
    )
    log.info("freestyle.url.received", chat_id=chat_id, job_id=job_id, pipeline=pipeline)


async def _cmd_freestyle(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await queue._client().set(f"pending_template:{ctx.chat_id}", "freestyle", ex=120)
        await send_message(ctx.chat_id, "📥 `/freestyle` ready — send the URL now (2 min window).")
        return
    url = ctx.parts[1]
    extra_domains = await database.list_allowed_domains(ctx.chat_id)
    pipeline = detect_pipeline(url, frozenset(extra_domains))
    if pipeline == "rejected":
        await send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, and allowlisted article domains.",
        )
        return
    if pipeline == "repo":
        await send_message(
            ctx.chat_id,
            "ℹ️ `/freestyle` doesn't apply to repo URLs yet\nRuning standard analysis.",
        )
        repo_url = normalize_repo_url(url)
        cached = await database.find_recent_job_by_url(ctx.chat_id, repo_url)
        if cached:
            await _reply_cached_job(ctx.chat_id, cached)
            return
        job_id = await database.create_job(
            chat_id=ctx.chat_id, url=repo_url, content_type="repo", message_id=ctx.message_id,
        )
        await queue.enqueue({"task": "repo", "job_id": job_id})
        await send_message(ctx.chat_id, f"📥 Received! \njob_{job_id[-4:]}")
        return
    await _handle_freestyle_url(ctx.chat_id, url, pipeline, ctx.message_id)


async def _cmd_cancel(ctx: SlashCtx) -> None:
    state = await database.get_chat_state(ctx.chat_id)
    await database.clear_chat_state(ctx.chat_id)
    await queue._client().delete(f"pending_template:{ctx.chat_id}")
    if state and state.get("mode") == "awaiting_intent":
        await send_message(ctx.chat_id, "✍️ Intent canceled.")
    elif state and state.get("mode") == "awaiting_freestyle":
        await send_message(ctx.chat_id, "✍️ Freestyle prompt abandoned.")
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
    from src.services.github import enrich_github_links
    from src.utils.markdown import _humanize_age
    candidates = await brain.search_links(query, top_k=10)
    results = [r for r in candidates if r["score"] >= 0.58][:5]
    if not results:
        await send_message(ctx.chat_id, f'🔍 Nothing found for "<i>{html.escape(query)}</i>".\nTry a broader term or /rebuild-graph if you\'ve added links recently.', parse_mode="HTML")
    else:
        await enrich_github_links(results)  # mutates in place; no-ops non-GitHub URLs
        header = f'🔍 <b>{len(results)} result{"s" if len(results) != 1 else ""}</b> for "<i>{html.escape(query)}</i>"\n\n'
        lines = []
        for r in results:
            parsed = urlparse(r["url"])
            short_url = (parsed.netloc + parsed.path).rstrip("/")
            short_url = short_url.removeprefix("www.")
            entry = (
                f'🔗 <b>{html.escape(r["title"])}</b>\n'
                f'   <a href="{html.escape(r["url"], quote=True)}">{html.escape(short_url)}</a>'
            )
            if r.get("_enriched"):
                desc = (r.get("_gh_description") or "").strip()
                language = r.get("_language") or "N/A"
                meta = f'⭐ {r["_stars"]} | 🔀 {r["_forks"]} | 💻 {language} | 📅 {_humanize_age(r["_days_ago"])}'
                if desc:
                    entry += f"\n   {html.escape(desc)}"
                entry += f"\n   {meta}"
            else:
                topic = (r.get("topic") or "").strip()
                if topic.lower().startswith(("the image", "the screenshot", "the photo")):
                    topic_line = "📷 from a photo"
                elif topic:
                    topic_line = topic[:70].rstrip() + ("…" if len(topic) > 70 else "")
                else:
                    topic_line = ""
                if topic_line:
                    entry += f"\n   {html.escape(topic_line)}"
            lines.append(entry)
        await send_message(ctx.chat_id, header + "\n\n".join(lines), parse_mode="HTML")


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
    await queue.enqueue({"task": _task_for(pipeline), "job_id": job_id})
    await send_message(ctx.chat_id, f"📥 Received\n✨ Kicking off Gemini analysis ({template})\njob_{job_id[-4:]}")


async def _reply_cached_job(chat_id: int, job: dict) -> None:
    """Send a dedup notice. Caller should not enqueue."""
    job_tag = f"job_{job['id'][-4:]}"
    status = job.get("status", "")
    if status in ("done", "transcript_done"):
        sheet_id = settings.GOOGLE_SHEETS_ID
        sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else None
        drive_line = f"\n📊 <a href=\"{sheet_url}\">Open in Sheets</a>" if sheet_url else ""
        title_line = f"\n🎬 {html.escape(job['title'])}" if job.get("title") else ""
        body = f"⚡ Already processed ({job_tag}){title_line}{drive_line}\n\nUse /force &lt;url&gt; to reprocess."
        if job.get("bot_message_id"):
            await send_inline_keyboard(
                chat_id,
                body,
                buttons=[[{"text": "Show job done", "callback_data": f"show_done:{job['id']}"}]],
                parse_mode="HTML",
            )
        else:
            await send_message(chat_id, body, parse_mode="HTML")
    else:
        body = f"⏳ Already in queue ({job_tag}, {status}) — hang tight.\n\nUse /force &lt;url&gt; to start a second run."
        await send_message(chat_id, body, parse_mode="HTML")


async def _cmd_force(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /force <url>")
        return
    url = ctx.parts[1]

    # Check for existing job and/or markdown cache row.
    extra_domains = await database.list_allowed_domains(ctx.chat_id)
    pipeline = detect_pipeline(url, frozenset(extra_domains))
    lookup_url = normalize_repo_url(url) if pipeline == "repo" else url
    existing_job = await database.find_recent_job_by_url(ctx.chat_id, lookup_url) if pipeline != "rejected" else None
    existing_cache = await database.get_markdown_cache(url)

    if existing_job:
        # State 1: job exists (with or without a cache row) — reset + reprocess.
        if existing_cache:
            await database.delete_markdown_cache(url)
        job_id = existing_job["id"]
        await database.reset_job(job_id)
        content_type = existing_job.get("content_type")
        task_type = _task_for(content_type)
        if pipeline == "repo":
            try:
                from urllib.parse import urlparse as _urlparse
                parts = [s for s in _urlparse(lookup_url).path.split("/") if s]
                owner_r, repo_r = parts[0], parts[1]
                redis_client = queue._client()
                await redis_client.delete(
                    f"github_repo_bundle:{owner_r}/{repo_r}",
                    f"github_meta:{owner_r}/{repo_r}",
                )
                log.info("force.repo_bundle_cache_cleared", owner=owner_r, repo=repo_r)
            except Exception:
                log.warning("force.repo_cache_clear_failed", url=lookup_url)
        await queue.enqueue({"task": task_type, "job_id": job_id})
        await send_message(ctx.chat_id, f"🔁 Force-reprocessing!\njob_{job_id[-4:]}")
        return

    if existing_cache:
        # State 2: cache-only — delete cache and acknowledge.
        await database.delete_markdown_cache(url)
        await send_message(ctx.chat_id, "🗑️ Markdown cache cleared for that URL.")
        log.info("force.cache_only_cleared", chat_id=ctx.chat_id, url=url)
        return

    # State 3: neither — create and dispatch.
    if pipeline == "rejected":
        await send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, and allowlisted article domains.",
        )
        return
    url_to_store = normalize_repo_url(url) if pipeline == "repo" else url
    job_id = await database.create_job(
        chat_id=ctx.chat_id,
        url=url_to_store,
        content_type=pipeline,
        message_id=ctx.message_id,
    )
    task_type = _task_for(pipeline)
    await queue.enqueue({"task": task_type, "job_id": job_id})
    await send_message(ctx.chat_id, f"🔁 Force-reprocessing!\njob_{job_id[-4:]}")


def _sanitize_title(title: str, url: str, max_len: int = 80) -> str:
    """Return a safe filename stem from *title*, falling back to the URL hostname.

    Keeps ``[a-zA-Z0-9 \\-_]``, truncates to *max_len* chars.
    """
    if title:
        safe = re.sub(r"[^a-zA-Z0-9 \-_]", "", title)
        safe = safe.strip()[:max_len]
        if safe:
            return safe
    # Fallback: use hostname from URL
    return urlparse(url).hostname or "document"


async def _cmd_download_md(ctx: SlashCtx) -> None:
    """/download_md <URL> — fetch URL as Markdown via Jina, cache, send as document."""
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /download_md <URL>")
        return
    url = ctx.parts[1]

    # 1. Cache lookup
    cached = await database.get_markdown_cache(url)
    if cached:
        title_body = cached["content"]
        # Re-extract title for filename: stored content is title + "\n\n" + body
        # But we need the title separately — store it with a sentinel in content.
        # Actually content is just raw markdown; we re-derive filename from first heading.
        # Simpler: store as "title\n---\nbody" was not chosen. Instead derive from content.
        # We stored body (not title); title was stored separately? No — let's re-read the design:
        # insert_markdown_cache stores the *full* markdown content (title + "\n\n" + body)
        # Actually looking at the handler below we store title + "\n\n" + body as content.
        # For cache-hit, derive filename the same way.
        first_line = title_body.split("\n", 1)[0].lstrip("# ").strip()
        filename = _sanitize_title(first_line, url) + ".md"
        await send_document(ctx.chat_id, title_body.encode(), filename)
        log.info("download_md.cache_hit", chat_id=ctx.chat_id, url=url)
        return

    # 2. Cache miss — call Jina
    from src.services.jina import JinaFetchError, fetch_markdown
    try:
        title, body = await fetch_markdown(url)
    except JinaFetchError as exc:
        await send_message(ctx.chat_id, f"❌ Failed to fetch URL (HTTP {exc.status_code}).")
        return

    # 3. Build document content and persist
    content = (title + "\n\n" + body).strip() if title else body.strip()
    await database.insert_markdown_cache(url, content)

    # 4. Send as Telegram document
    filename = _sanitize_title(title, url) + ".md"
    await send_document(ctx.chat_id, content.encode(), filename)
    log.info("download_md.fetched", chat_id=ctx.chat_id, url=url, filename=filename)


_PROTECTED_DOMAINS = {"github.com"}


def _normalize_domain(raw: str) -> str:
    """Strip to bare hostname, lowercase, drop 'www.' prefix."""
    from urllib.parse import urlparse as _urlparse
    host = _urlparse(raw).hostname or raw
    return host.lower().removeprefix("www.")


def _format_domain_report(*sections: tuple[str, list[str]]) -> str:
    """Join non-empty '<label> `d1`, `d2`' lines for a domain-command reply."""
    return "\n".join(
        f"{label} " + ", ".join(f"`{d}`" for d in domains)
        for label, domains in sections
        if domains
    )


async def _cmd_ignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /ignore <domain or URL> [more...]")
        return
    added, protected = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if domain in _PROTECTED_DOMAINS:
            protected.append(domain)
            continue
        await database.add_ignored_domain(ctx.chat_id, domain)
        added.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("🚫 Ignored:", added), ("⛔ Cannot ignore:", protected)))


async def _cmd_unignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /unignore <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_ignored_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("✅ Removed:", removed), ("⚠️ Not found:", missing)))


async def _cmd_ignore_list(ctx: SlashCtx) -> None:
    domains = sorted(await database.get_ignored_domains(ctx.chat_id))
    if not domains:
        await send_message(ctx.chat_id, "No ignored domains yet. Use /ignore <domain>.")
        return
    lines = "\n".join(f"• `{d}`" for d in domains)
    await send_message(ctx.chat_id, f"🚫 Ignored domains ({len(domains)}):\n{lines}")


async def _cmd_allowlist(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /allowlist <domain or URL> [more...]")
        return
    added = []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        await database.add_allowed_domain(ctx.chat_id, domain)
        added.append(domain)
    await send_message(ctx.chat_id, "✅ Allowlisted: " + ", ".join(f"`{d}`" for d in added))


async def _cmd_unallowlist(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await send_message(ctx.chat_id, "Usage: /unallowlist <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_allowed_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await send_message(ctx.chat_id, _format_domain_report(
        ("✅ Removed:", removed), ("⚠️ Not in your allowlist:", missing)))


async def _cmd_allowlist_list(ctx: SlashCtx) -> None:
    domains = sorted(await database.list_allowed_domains(ctx.chat_id))
    if not domains:
        await send_message(ctx.chat_id, "No custom allowlist entries yet. Use /allowlist <domain>.")
        return
    lines = "\n".join(f"• `{d}`" for d in domains)
    await send_message(ctx.chat_id, f"✅ Allowlisted domains ({len(domains)}):\n{lines}")


_START_TEXT = (
    "👋 *vig — Video Intelligence Gateway*\n\n"
    "Send me a link and I'll process it:\n"
    "• YouTube video or Short\n"
    "• Instagram Reel\n"
    "• TikTok video\n"
    "• Article URL (use /allowlist to add domains)\n"
    "• GitHub repo URL\n"
    "• PDF file or link\n\n"
    "Type /help for available commands."
)

_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "/start — show welcome message\n"
    "/help — this message\n"
    "/find <query> — search your processed content\n"
    "/spec <suffix> [intent] — generate a mini-PRD from a long video\n"
    "/freestyle — use a custom Gemini prompt for the next job\n"
    "/force <url> — reprocess a URL (skip cache)\n"
    "/cancel — cancel the current pending prompt\n"
    "/ignore <domain> — hide a domain from link results\n"
    "/unignore <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "/allowlist <domain> — add an article domain\n"
    "/unallowlist <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "/rebuild-graph — rebuild the Second Brain link graph"
)


async def _cmd_start(ctx: SlashCtx) -> None:
    await send_message(ctx.chat_id, _START_TEXT, parse_mode="Markdown")


async def _cmd_help(ctx: SlashCtx) -> None:
    await send_message(ctx.chat_id, _HELP_TEXT, parse_mode="Markdown")


_SLASH_TABLE: dict[str, Callable[[SlashCtx], Awaitable[None]]] = {
    "/start":            _cmd_start,
    "/help":             _cmd_help,
    "/cancel":           _cmd_cancel,
    "/spec":             _cmd_spec,
    "/find":             _cmd_find,
    "/rebuild-graph":    _cmd_rebuild_graph,
    "/force":            _cmd_force,
    "/ignore":          _cmd_ignore,
    "/unignore":        _cmd_unignore,
    "/ignore_list":     _cmd_ignore_list,
    "/allowlist":        _cmd_allowlist,
    "/unallowlist":      _cmd_unallowlist,
    "/allowlist_list":   _cmd_allowlist_list,
    "/freestyle":        _cmd_freestyle,
    "/download_md":      _cmd_download_md,
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
    if pipeline in ("short", "long", "article", "repo"):
        await database.clear_chat_state(chat_id)
        log.info("prd.chat_state.canceled_by_url", chat_id=chat_id, old_job_id=job_id)
        url_to_store = normalize_repo_url(text) if pipeline == "repo" else text
        cached = await database.find_recent_job_by_url(chat_id, url_to_store)
        if cached:
            await send_message(chat_id, "🔄 Previous intent canceled.")
            await _reply_cached_job(chat_id, cached)
            return
        await send_message(chat_id, "🔄 Started new job; previous intent canceled.")
        new_job_id = await database.create_job(
            chat_id=chat_id, url=url_to_store, content_type=pipeline
        )
        task_type = "repo" if pipeline == "repo" else ("article" if pipeline == "article" else "video")
        await queue.enqueue({"task": task_type, "job_id": new_job_id})
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


async def _handle_awaiting_freestyle(chat_id: int, text: str, state: dict) -> None:
    """Handle user reply when awaiting_freestyle chat state is armed."""
    job_id = state["job_id"]
    stripped = text.strip()
    if len(stripped) < 5:
        await send_message(chat_id, "✍️ Prompt too short (min 5 chars). Reply again or /cancel to abandon.")
        return
    if len(stripped) > 1000:
        await send_message(chat_id, "✍️ Prompt too long (max 1000 chars). Reply again or /cancel to abandon.")
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET freestyle_prompt=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (stripped, job_id),
        )
        await conn.commit()
    await database.clear_chat_state(chat_id)
    log.info("freestyle.prompt.stored", chat_id=chat_id, job_id=job_id, prompt_len=len(stripped))
    job = await database.get_job(job_id)
    if job and job.get("content_type") == "short":
        await queue.enqueue({"task": "video", "job_id": job_id})
        log.info("freestyle.video.enqueued", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"📥 Received\n✨ Kicking off Gemini analysis (freestyle)\njob_{job_id[-4:]}")
    elif job and job.get("content_type") == "repo":
        await queue.enqueue({"task": "repo", "job_id": job_id})
        log.info("freestyle.repo.enqueued", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting repo analysis")
    elif job and job.get("content_type") == "article":
        await queue.enqueue({"task": "article", "job_id": job_id})
        log.info("freestyle.article.enqueued", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting article analysis")
    elif job and job.get("content_type") == "document":
        await queue.enqueue({"task": "document", "job_id": job_id})
        log.info("freestyle.document.enqueued", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"{job_tag(job_id)}\n✨ Freestyle prompt received — re-running document analysis")
    elif job and job.get("status") == "transcript_done":
        await queue.enqueue({"task": "enrichment", "job_id": job_id})
        log.info("freestyle.enrichment.enqueued", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting Gemini analysis")
    else:
        log.info("freestyle.prompt.deferred", chat_id=chat_id, job_id=job_id)
        await send_message(chat_id, f"{job_tag(job_id)}\n✍️ Prompt saved — Gemini will start when transcript is ready")


async def _parse_spec_args(chat_id: int, parts: list[str]) -> tuple[str, str | None] | None:
    """Validate /spec args; message the user and return None on bad input."""
    if len(parts) < 2:
        await send_message(
            chat_id,
            'Usage: /spec <suffix> [intent text...]\nExample: /spec ABCD desktop app for X',
        )
        return None
    suffix = parts[1][-4:]
    intent_text = " ".join(parts[2:]).strip() or None
    if intent_text is not None:
        if len(intent_text) < 5:
            await send_message(chat_id, "📐 Intent too short (min 5 chars).")
            return None
        if len(intent_text) > 1000:
            await send_message(chat_id, "📐 Intent too long (max 1000 chars).")
            return None
    return suffix, intent_text


async def _report_spec_no_match(chat_id: int, suffix: str) -> None:
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


async def _enqueue_spec_job(chat_id: int, job: dict, intent_text: str | None) -> None:
    job_id = job["id"]
    if intent_text:
        async with database.connection() as conn:
            await conn.execute(
                "UPDATE jobs SET prd_intent_text=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (intent_text, job_id),
            )
            await conn.commit()
        await queue.enqueue({"task": "prd_intent", "job_id": job_id})
        log.info("prd.intent.enqueued", chat_id=chat_id, job_id=job_id, intent_text_len=len(intent_text))
    elif job.get("prd_auto_status") == "done" and job.get("prd_auto_json"):
        await queue.enqueue({"task": "prd_auto_resend", "job_id": job_id})
    else:
        await queue.enqueue({"task": "prd_auto", "job_id": job_id})


async def _handle_spec(chat_id: int, parts: list[str]) -> None:
    """Dispatch /spec <suffix> [intent...]."""
    parsed = await _parse_spec_args(chat_id, parts)
    if parsed is None:
        return
    suffix, intent_text = parsed

    rows = await database.find_jobs_by_suffix(chat_id, suffix)
    long_matches = [
        j for j in rows
        if j["content_type"] == "long" and j["status"] in ("transcript_done", "done")
    ]
    short_matches = [j for j in rows if j["content_type"] == "short"]

    if not long_matches and not short_matches:
        await _report_spec_no_match(chat_id, suffix)
        return

    if not long_matches and short_matches:
        await send_message(
            chat_id,
            f"📐 PRD is only available for long videos. Job {suffix} is a short.",
        )
        log.info("prd.spec.short_video_rejected", chat_id=chat_id, suffix=suffix)
        return

    job = long_matches[0]
    title = job.get("title") or "(no title)"
    await send_message(chat_id, f'📐 PRD for: "{title}" — generating ...')
    log.info("prd.spec.matched", chat_id=chat_id, suffix=suffix, job_id=job["id"], intent=bool(intent_text))

    await _enqueue_spec_job(chat_id, job, intent_text)


def _resolve_chat_state(state: dict) -> bool:
    from datetime import datetime as _dt, timezone as _tz
    expires_at_raw = state["expires_at"]
    try:
        expires_at = _dt.fromisoformat(expires_at_raw.replace(" ", "T"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=_tz.utc)
    except Exception:
        expires_at = None
    return bool(expires_at and expires_at > _dt.now(_tz.utc))


async def _handle_user_template_shortcut(chat_id: int, text: str, message_id: int) -> bool:
    if not re.match(r"^-[a-zA-Z0-9][a-zA-Z0-9_-]*$", text.split()[0]):
        return False
    parts = text.split()
    tmpl_name = parts[0][1:].lower()  # strip leading '-'
    if len(parts) < 2:
        await send_message(chat_id, f"❌ Usage: `-{tmpl_name} <url>`")
        return True
    tmpl_row = await database.get_user_template_by_name(chat_id, tmpl_name)
    if tmpl_row is None:
        await send_message(
            chat_id,
            f"❌ Unknown template `-{tmpl_name}`. Create it at /prompts or check the name.",
        )
        return True
    url = parts[1]
    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(url, frozenset(extra_domains))
    if pipeline == "rejected":
        await send_message(
            chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, and allowlisted article domains.",
        )
        return True
    cached = await database.find_recent_job_by_url(chat_id, url)
    if cached:
        await _reply_cached_job(chat_id, cached)
        return True
    extra_instructions = (tmpl_row.get("extra_instructions") or "").strip()
    job_id = await database.create_job(
        chat_id=chat_id,
        url=url,
        content_type=pipeline,
        message_id=message_id,
        template="freestyle" if extra_instructions else None,
    )
    await database.set_job_template_prompt(
        job_id,
        freestyle_prompt=extra_instructions or None,
        template_detection_method=f"user_template:{tmpl_name}",
    )
    task_type = _task_for(pipeline)
    await queue.enqueue({"task": task_type, "job_id": job_id})
    await send_message(
        chat_id,
        f"📥 Received\n✨ Kicking off analysis ({tmpl_name})\njob_{job_id[-4:]}",
    )
    log.info("user_template_shortcut.enqueued", chat_id=chat_id, job_id=job_id, template=tmpl_name)
    return True


async def _enqueue_simple_job(
    chat_id: int, url: str, content_type: str, message_id: int
) -> None:
    """Create + enqueue an article/repo job and ack the user."""
    job_id = await database.create_job(
        chat_id=chat_id, url=url, content_type=content_type, message_id=message_id,
    )
    await queue.enqueue({"task": content_type, "job_id": job_id})
    await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")


async def _reject_url(chat_id: int, text: str) -> None:
    try:
        _host = (urlparse(text).hostname or "").lower().removeprefix("www.")
    except Exception:
        _host = ""
    _github_hint = f"\n{_REPO_HINT}" if _host == "github.com" or _host.endswith(".github.com") else ""
    await send_message(
        chat_id,
        "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
        "Instagram Reels (not /p/ carousels), and TikTok videos.\n"
        + _ARTICLE_HINT
        + _github_hint,
    )
    log.info("url_rejected", chat_id=chat_id, url=text)


async def _route_article(
    chat_id: int, text: str, message_id: int, pending_template: str | None
) -> None:
    if not pending_template:
        cached = await database.find_recent_job_by_url(chat_id, text)
        if cached:
            await _reply_cached_job(chat_id, cached)
            return
    await _enqueue_simple_job(chat_id, text, "article", message_id)


async def _route_repo(
    chat_id: int, text: str, message_id: int, pending_template: str | None, client
) -> None:
    repo_url = normalize_repo_url(text)
    if pending_template:
        await client.set(f"pending_template:{chat_id}", pending_template, ex=120)
        await send_message(
            chat_id,
            f"ℹ️ `/{pending_template}` templates don't apply to repo URLs yet — "
            "your template is still active for the next video or article.",
        )
    cached = await database.find_recent_job_by_url(chat_id, repo_url)
    if cached:
        await _reply_cached_job(chat_id, cached)
        return
    await _enqueue_simple_job(chat_id, repo_url, "repo", message_id)


async def _route_video(
    chat_id: int, text: str, pipeline: str, message_id: int, pending_template: str | None
) -> None:
    if pending_template == "freestyle":
        await _handle_freestyle_url(chat_id, text, pipeline, message_id)
        return

    if not pending_template:
        cached = await database.find_recent_job_by_url(chat_id, text)
        if cached:
            await _reply_cached_job(chat_id, cached)
            return

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
        await send_message(chat_id, f"📥 Received\n✨ Kicking off Gemini analysis ({pending_template})\njob_{job_id[-4:]}")
    else:
        await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")


async def _route_url(chat_id: int, text: str, message_id: int) -> None:
    client = queue._client()
    pending_template: str | None = await client.get(f"pending_template:{chat_id}")
    if pending_template:
        await client.delete(f"pending_template:{chat_id}")

    extra_domains = await database.list_allowed_domains(chat_id)
    pipeline = detect_pipeline(text, frozenset(extra_domains))
    if pipeline == "rejected":
        await _reject_url(chat_id, text)
        return
    if pipeline == "document":
        await _route_document_url(chat_id, text, message_id)
        return
    if pipeline == "article":
        await _route_article(chat_id, text, message_id, pending_template)
        return
    if pipeline == "repo":
        await _route_repo(chat_id, text, message_id, pending_template, client)
        return
    await _route_video(chat_id, text, pipeline, message_id, pending_template)


async def _is_public_host(host: str) -> bool:
    """True only when every resolved address for *host* is a public, routable IP.

    Blocks SSRF to loopback / private / link-local (incl. 169.254.169.254 cloud
    metadata) / reserved ranges. ponytail: validates via getaddrinfo, not pinned
    to the socket — a DNS-rebinding attacker could still race the resolution;
    upgrade to an IP-pinned httpx transport if that threat becomes real.
    """
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


async def _safe_get_pdf(url: str) -> bytes | None:
    """GET a user-supplied URL with SSRF guards. Returns body bytes or None.

    Redirects are followed manually so each hop's host is re-validated (httpx's
    own follow_redirects would skip the check on subsequent hops).
    """
    for _ in range(5):  # redirect cap
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        if not await _is_public_host(parsed.hostname):
            log.warning("document_url_blocked_ssrf", host=parsed.hostname)
            return None
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            async with client.stream("GET", url) as resp:
                if resp.is_redirect and resp.next_request is not None:
                    url = str(resp.next_request.url)
                    continue
                resp.raise_for_status()
                if int(resp.headers.get("content-length") or 0) > _MAX_DOC_BYTES:
                    log.warning("document_url_too_large", host=parsed.hostname)
                    return None
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf += chunk
                    if len(buf) > _MAX_DOC_BYTES:  # streamed cap: trust no Content-Length
                        log.warning("document_url_too_large", host=parsed.hostname)
                        return None
                return bytes(buf)
    return None  # too many redirects


async def _route_document_url(chat_id: int, url: str, message_id: int | None) -> None:
    """Fetch a .pdf URL, store it content-addressed, and enqueue a document job (#152)."""
    try:
        data = await _safe_get_pdf(url)
    except Exception:
        data = None
    if data is None:
        log.info("document_url_fetch_failed", chat_id=chat_id, url=url)
        await send_message(chat_id, "📄 Couldn't download that PDF. Check the link and try again.")
        return
    if not data.startswith(b"%PDF"):
        await send_message(chat_id, "📄 That link didn't return a PDF.")
        log.info("document_url_not_pdf", chat_id=chat_id, url=url)
        return
    await _enqueue_document_job(chat_id, data, message_id)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    if not compare_digest(x_telegram_bot_api_secret_token or "", settings.TELEGRAM_WEBHOOK_SECRET):
        log.warning("webhook_invalid_secret")
        raise HTTPException(status_code=403, detail="invalid secret")

    update = await request.json()

    # Handle callback queries (inline keyboard button presses)
    callback = update.get("callback_query")
    if callback:
        try:
            await _handle_callback(callback)
        except Exception:
            log.exception("webhook_callback_error")
            # Acknowledge so the client's inline button stops spinning even on failure.
            with suppress(Exception):
                await answer_callback_query(callback.get("id", ""))
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    message_id = message.get("message_id")

    log.info("webhook_received", chat_id=chat_id, message_id=message_id, text_len=len(text))

    # Photo path
    photo = message.get("photo")
    if photo and chat_id:
        await _handle_photo_update(chat_id, message, photo)
        return {"ok": True}

    # Document upload path (#151) — a file message has no `.text`, so this must
    # run before the text guard below.
    document = message.get("document")
    if document and chat_id:
        await _handle_document_update(chat_id, message, document)
        return {"ok": True}

    if not chat_id or not text:
        return {"ok": True}

    try:
        await _route_text(chat_id, text, message_id)
    except Exception:
        log.exception("webhook_handler_error", chat_id=chat_id)
        try:
            await send_message(chat_id, "⚠️ Something went wrong processing your message. Please try again.")
        except Exception:
            log.exception("webhook_error_notification_failed", chat_id=chat_id)
    return {"ok": True}


_MAX_DOC_BYTES = 20 * 1024 * 1024  # Telegram bot getFile cap (ADR-0023)
_DOC_TOO_LARGE_MSG = (
    "📄 File too large for Telegram (max 20MB). Upload via the web "
    "dashboard — feature coming soon."
)


async def _handle_document_update(chat_id: int, message: dict, document: dict) -> None:
    """Validate + ingest a Telegram document upload. PDF-only at MVP (#151)."""
    file_name = document.get("file_name") or ""
    is_pdf = document.get("mime_type") == "application/pdf" or file_name.lower().endswith(".pdf")
    if not is_pdf:
        await send_message(chat_id, "📄 Only PDF files are supported right now.")
        log.info("document_rejected_type", chat_id=chat_id, mime=document.get("mime_type"))
        return
    if (document.get("file_size") or 0) > _MAX_DOC_BYTES:
        await send_message(chat_id, _DOC_TOO_LARGE_MSG)
        log.info("document_rejected_size", chat_id=chat_id, size=document.get("file_size"))
        return
    # Heavy download/upload runs off the webhook request, mirroring the photo path.
    asyncio.create_task(_ingest_document(chat_id, document, message.get("message_id")))


async def _enqueue_document_job(chat_id: int, data: bytes, message_id: int | None) -> None:
    """Store PDF bytes content-addressed, create + enqueue the job, ack the user."""
    sha = hashlib.sha256(data).hexdigest()
    key = storage.object_key("documents", sha, "pdf")
    await storage.upload(key, data, "application/pdf")
    job_id = await database.create_job(
        chat_id=chat_id, url=key, content_type="document", message_id=message_id,
    )
    await queue.enqueue({"task": "document", "job_id": job_id})
    await send_message(chat_id, f"📥 Received! \njob_{job_id[-4:]}")


async def _ingest_document(chat_id: int, document: dict, message_id: int | None) -> None:
    # Runs unawaited via create_task, so swallow nothing silently: catch and tell the user.
    try:
        data = await download_file(document["file_id"])
        if not data.startswith(b"%PDF"):  # parity with the URL path; skip wasted upload+job
            await send_message(chat_id, "📄 That file isn't a valid PDF.")
            log.info("document_rejected_magic", chat_id=chat_id)
            return
        await _enqueue_document_job(chat_id, data, message_id)
    except Exception:
        log.exception("document_ingest_failed", chat_id=chat_id)
        await send_message(chat_id, "📄 Couldn't process that PDF. Please try again.")


async def _handle_photo_update(chat_id: int, message: dict, photo: list) -> None:
    file_id = photo[-1]["file_id"]
    caption = message.get("caption") or None
    media_group_id: str | None = message.get("media_group_id")
    if media_group_id:
        await _accumulate_media_group(chat_id, media_group_id, file_id)
    else:
        asyncio.create_task(_handle_single_photo(chat_id, file_id, caption))


async def _route_text(chat_id: int, text: str, message_id: int | None) -> None:
    # 1. Slash command path
    if text.startswith("/"):
        await _dispatch_slash(chat_id, text, message_id)
        return

    # 2. Awaiting-intent path
    state = await database.get_chat_state(chat_id)
    if state:
        if _resolve_chat_state(state):
            if state.get("mode") == "awaiting_freestyle":
                await _handle_awaiting_freestyle(chat_id, text, state)
            else:
                await _handle_awaiting_intent(chat_id, text, state)
            return
        log.info("prd.chat_state.expired_or_missed", chat_id=chat_id)
        # fall through to normal URL routing

    # 3. Plain-text command shortcut: "find code" → "/find code", "rebuild-graph" → "/rebuild-graph"
    first_word = text.split()[0].lower()
    if ("/" + first_word) in _SLASH_TABLE:
        await _dispatch_slash(chat_id, "/" + text, message_id)
        return

    # 3b. User-template shortcut: "-mytemplate <url>"
    if await _handle_user_template_shortcut(chat_id, text, message_id):
        return

    # 4. Normal URL routing
    await _route_url(chat_id, text, message_id)

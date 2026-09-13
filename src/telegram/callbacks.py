"""Inline-keyboard callback handlers: one `_cb_*` per `_CALLBACK_TABLE` prefix."""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable




from src import database, job_queue as queue
from src.services.jobs import (
    create_and_enqueue_job,
    task_for_content_type,
)
from src.services.repo_followup import enqueue_repo_pick
from src.telegram import sender
from src.templates import PROMPT_TEMPLATES
from src.utils import job_tag
from src.telegram.context import CallbackCtx, _extract_message_identity, log
from src.telegram.routing import admit_or_park


_ALLOWED_TEMPLATE_CALLBACKS = frozenset(PROMPT_TEMPLATES) | {"freestyle"}



async def _get_callback_owned_job(ctx: CallbackCtx, job_id: str | None = None) -> dict | None:
    actual_job_id = job_id or ctx.job_id
    job = await database.get_job(actual_job_id)
    if job is None or str(job.get("chat_id")) != str(ctx.chat_id):
        log.warning("callback.foreign_or_missing_job", chat_id=ctx.chat_id, job_id=actual_job_id)
        return None
    return job



async def _cb_gemini_no(ctx: CallbackCtx) -> None:
    await database.update_job_status(ctx.job_id, "done")
    await sender.answer_callback_query(ctx.cq_id)



async def _cb_gemini_yes(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job or job.get("status") != "transcript_done":
        await sender.answer_callback_query(ctx.cq_id, text="This job is not ready for enrichment.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    await sender.send_inline_keyboard(
        ctx.chat_id,
        "✨ Pick a Gemini template:",
        buttons=[
            [
                {
                    "text": "📝 Summary",
                    "callback_data": f"template_pick:summary:{ctx.job_id}",
                },
                {
                    "text": "🔧 Method",
                    "callback_data": f"template_pick:method:{ctx.job_id}",
                },
            ],
            [
                {
                    "text": "💻 Technical",
                    "callback_data": f"template_pick:technical:{ctx.job_id}",
                },
                {
                    "text": "⭐ Review",
                    "callback_data": f"template_pick:review:{ctx.job_id}",
                },
            ],
            [
                {
                    "text": "📖 Narrative",
                    "callback_data": f"template_pick:narrative:{ctx.job_id}",
                },
                {
                    "text": "✍️ Freestyle",
                    "callback_data": f"template_freestyle:{ctx.job_id}",
                },
            ],
        ],
    )



async def _cb_template_pick(ctx: CallbackCtx) -> None:
    # ctx.job_id = "{template}:{actual_job_id}" (everything after first ":")
    template, _, actual_job_id = ctx.job_id.partition(":")
    if not actual_job_id or template not in _ALLOWED_TEMPLATE_CALLBACKS:
        await sender.answer_callback_query(ctx.cq_id, text="Invalid callback data.")
        return
    job = await _get_callback_owned_job(ctx, actual_job_id)
    if not job or job.get("status") != "transcript_done":
        await sender.answer_callback_query(ctx.cq_id, text="Job not ready for enrichment.")
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET template=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (template, actual_job_id),
        )
        await conn.commit()
    if ctx.message_id:
        await sender.edit_message_text(ctx.chat_id, ctx.message_id, f"You chose {template.capitalize()}")
    await queue.enqueue({"task": "enrichment", "job_id": actual_job_id})
    await sender.answer_callback_query(ctx.cq_id)
    log.info(
        "template_pick.enqueued",
        chat_id=ctx.chat_id,
        job_id=actual_job_id,
        template=template,
    )



async def _cb_template_freestyle(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET template='freestyle', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (ctx.job_id,),
        )
        await conn.commit()
    await database.set_chat_state(
        ctx.chat_id, mode="awaiting_freestyle", job_id=ctx.job_id, expires_minutes=10
    )
    await sender.answer_callback_query(ctx.cq_id)
    await sender.send_force_reply(
        ctx.chat_id,
        "✍️ Reply with your Gemini prompt (reply within 10 min; /cancel to abandon)",
        input_field_placeholder="Your Gemini prompt...",
    )
    log.info("template_freestyle.armed", chat_id=ctx.chat_id, job_id=ctx.job_id)



async def _cb_prd_build_spec(ctx: CallbackCtx) -> None:
    await sender.send_inline_keyboard(
        ctx.chat_id,
        "📐 Build Spec — pick a path:",
        buttons=[
            [
                {
                    "text": "🤖 Build auto Spec",
                    "callback_data": f"prd_auto:{ctx.job_id}",
                },
                {
                    "text": "✍️ Text your intent",
                    "callback_data": f"prd_intent_prompt:{ctx.job_id}",
                },
            ]
        ],
    )
    await sender.answer_callback_query(ctx.cq_id)



async def _cb_prd_auto(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    if job.get("prd_auto_status") == "done" and job.get("prd_auto_json"):
        await sender.send_message(ctx.chat_id, "📐 Re-sending your PRD...")
        await queue.enqueue({"task": "prd_auto_resend", "job_id": ctx.job_id})
    elif job.get("prd_auto_status") == "generating":
        await sender.send_message(ctx.chat_id, "📐 PRD already generating, hang tight.")
    else:
        # Lazy generation — worker is the single source of truth for the lock.
        # Webhook just enqueues optimistically; run_auto handles the atomic lock.
        await sender.send_message(ctx.chat_id, "📐 Generating PRD, hang tight...")
        await queue.enqueue({"task": "prd_auto", "job_id": ctx.job_id})



async def _cb_prd_intent_prompt(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    existing = await database.get_chat_state(ctx.chat_id)
    if existing and existing["job_id"] == ctx.job_id:
        await sender.answer_callback_query(ctx.cq_id)
        return
    await database.set_chat_state(chat_id=ctx.chat_id, mode="awaiting_intent", job_id=ctx.job_id)
    log.info("prd.chat_state.armed", chat_id=ctx.chat_id, job_id=ctx.job_id)
    await sender.send_force_reply(
        ctx.chat_id,
        'Reply with your project direction. Example: "desktop app for agentic image '
        'processing" (reply within 10 minutes; type /cancel to abandon)',
    )
    await sender.answer_callback_query(ctx.cq_id)



async def _cb_prd_retry_intent(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job or not (job.get("prd_intent_text") or "").strip():
        await sender.answer_callback_query(ctx.cq_id, text="No prior intent to retry — use ✍️ New Intent.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    await sender.send_message(ctx.chat_id, "📐 Generating PRD, hang tight...")
    await queue.enqueue({"task": "prd_intent", "job_id": ctx.job_id})



async def _cb_enrichment_retry(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    status = job.get("status")
    if status not in ("error", "transcript_done"):
        log.warning("enrichment_retry_rejected", job_id=ctx.job_id, status=status)
        await sender.answer_callback_query(ctx.cq_id, text=f"Can't retry — job is in status '{status}'.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    await database.update_job_status(ctx.job_id, "enriching")
    await queue.enqueue({"task": "enrichment", "job_id": ctx.job_id})
    log.info("enrichment_retry_enqueued", job_id=ctx.job_id)
    await sender.send_message(ctx.chat_id, "🍪 Retrying Gemini enrichment...")



async def _cb_article_retry(ctx: CallbackCtx) -> None:
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    status = job.get("status")
    if status != "error":
        await sender.answer_callback_query(ctx.cq_id, text=f"Can't retry — job is in status '{status}'.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    await database.update_job_status(ctx.job_id, "pending")
    await queue.enqueue({"task": "article", "job_id": ctx.job_id, "skip_document": True})
    log.info("article_retry_enqueued", job_id=ctx.job_id)
    await sender.send_message(ctx.chat_id, f"{job_tag(ctx.job_id)}\n📥 Retrying article analysis...")



async def _cb_reprocess(ctx: CallbackCtx) -> None:
    """One-tap retry for a 'processing' job orphaned by a restart (ADR-0010).

    Re-submits the stored URL as a brand-new job — identical to the user resending
    the link — so the orphaned row's Drive file / Sheets row are never re-touched.
    """
    job = await _get_callback_owned_job(ctx)
    if not job:
        await sender.answer_callback_query(ctx.cq_id, text="Job not found — please resend the link.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    # skip_cache: this must always be a brand-new job, never a dedup hit off
    # the orphaned row's own URL (see docstring).
    result = await create_and_enqueue_job(
        ctx.chat_id,
        job["url"],
        job["content_type"],
        template=job.get("template"),
        skip_cache=True,
        task=task_for_content_type(job["content_type"], default="video"),
    )
    new_job_id = result["id"]
    log.info("reprocess_enqueued", orphan_job_id=ctx.job_id, new_job_id=new_job_id)
    await sender.send_message(ctx.chat_id, f"📥 Received!\njob_{new_job_id[-4:]}")



async def _cb_show_done(ctx: CallbackCtx) -> None:
    """Forward the original completion message and collapse the dedup keyboard."""
    job = await database.get_job(ctx.job_id)
    if not job or not job.get("bot_message_id"):
        await sender.answer_callback_query(ctx.cq_id, text="Original message not available.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    await sender.forward_message(ctx.chat_id, ctx.chat_id, job["bot_message_id"])
    if ctx.message_id:
        await sender.edit_message_text(ctx.chat_id, ctx.message_id, "here you go")



async def _cb_document_md(ctx: CallbackCtx) -> None:
    """📄 Get Markdown — render/serve parsed/<sha>.md on demand (#156)."""
    job = await database.get_job(ctx.job_id)
    if (
        not job
        or job.get("content_type") != "document"
        or str(job.get("chat_id")) != str(ctx.chat_id)
    ):
        await sender.answer_callback_query(ctx.cq_id, text="Job not found.")
        return
    await sender.answer_callback_query(ctx.cq_id)
    from src.processors import document

    try:
        await document.deliver_markdown(job)
    except Exception:
        log.exception("document_md.failed", job_id=ctx.job_id)
        await sender.send_message(
            ctx.chat_id,
            f"{job_tag(ctx.job_id)}\n⚠️ Couldn't render Markdown — try again later.",
        )



async def _cb_invite_decision(ctx: CallbackCtx, log_action: str) -> None:
    """Deprecated Ownix-bot invite callbacks; decisions now live on /webhook/ops."""
    log.warning("invite_decision.deprecated_ownix_callback", chat_id=ctx.chat_id, action=log_action)
    await sender.answer_callback_query(ctx.cq_id, text="Use the Ops bot approval card.")



async def _cb_invite_status(ctx: CallbackCtx) -> None:
    """Acknowledge taps on already-decided invite status buttons."""
    status, _, _target_chat_id = ctx.job_id.partition(":")
    text = "Already approved." if status == "approved" else "Already blocked."
    await sender.answer_callback_query(ctx.cq_id, text=text)



_cb_invite_approve = functools.partial(_cb_invite_decision, log_action="approved")

_cb_invite_block = functools.partial(_cb_invite_decision, log_action="blocked")



async def _cb_repo_pick(ctx: CallbackCtx) -> None:
    _, _, rest = ctx.data.partition(":")
    source_job_id, _, idx = rest.partition(":")
    job = await enqueue_repo_pick(source_job_id, idx)
    if job is None:
        await sender.answer_callback_query(
            ctx.cq_id, text="Repo choice expired. Run the source job again."
        )
        return
    await sender.answer_callback_query(ctx.cq_id, text="Repo analysis queued.")
    await sender.send_message(ctx.chat_id, f"📥 Repo analysis queued\njob_{job['id'][-4:]}")



_CALLBACK_TABLE: dict[str, Callable[[CallbackCtx], Awaitable[None]]] = {
    "gemini_no": _cb_gemini_no,
    "gemini_yes": _cb_gemini_yes,
    "template_pick": _cb_template_pick,
    "template_freestyle": _cb_template_freestyle,
    "prd_build_spec": _cb_prd_build_spec,
    "prd_auto": _cb_prd_auto,
    "prd_retry_auto": _cb_prd_auto,
    "prd_intent_prompt": _cb_prd_intent_prompt,
    "prd_retry_intent": _cb_prd_retry_intent,
    "enrichment_retry": _cb_enrichment_retry,
    "article_retry": _cb_article_retry,
    "reprocess": _cb_reprocess,
    "show_done": _cb_show_done,
    "document_md": _cb_document_md,
    "invite_approve": _cb_invite_approve,
    "invite_block": _cb_invite_block,
    "invite_status": _cb_invite_status,
    "repo_pick": _cb_repo_pick,
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
        await sender.answer_callback_query(cq_id)
        return

    if chat_id and prefix not in {"invite_approve", "invite_block"}:
        from_user = callback.get("from") or {}
        chat = cb_message.get("chat") or {}
        identity = _extract_message_identity(from_user, chat)
        if not await admit_or_park(chat_id, "", identity, via_callback=True):
            await sender.answer_callback_query(cq_id, text="Access restricted.")
            return

    ctx = CallbackCtx(
        chat_id=chat_id, job_id=job_id, cq_id=cq_id, data=data, message_id=cb_message_id
    )
    await handler(ctx)


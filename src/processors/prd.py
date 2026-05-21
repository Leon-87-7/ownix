"""Mini-PRD auto slot — slice #6."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

from src import database
from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Transcript sampling
# ---------------------------------------------------------------------------

def sample_transcript(text: str, cap: int = 60_000) -> str:
    """Return text unchanged if within cap; otherwise sample head/middle/tail windows.

    Uses three fixed 20k windows: head, middle (centred), and tail.
    """
    if len(text) <= cap:
        return text
    head = text[:20_000]
    mid = len(text) // 2
    middle = text[mid - 10_000 : mid + 10_000]
    tail = text[-20_000:]
    return head + "\n\n[...truncated...]\n\n" + middle + "\n\n[...truncated...]\n\n" + tail


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def build_prd_markdown(prd: dict, *, intent_text: str | None = None) -> str:
    """Render a PRD JSON dict to a structured markdown document.

    If intent_text is provided, insert a 'Your direction' line immediately
    after the title.
    """
    lines: list[str] = []

    lines.append(f"# PRD: {prd.get('project', 'Untitled')}")
    lines.append("")
    if intent_text:
        lines.append(f"**Your direction:** _{intent_text}_")
        lines.append("")

    category = prd.get("category", "")
    if category:
        lines.append(f"**Category:** {category}")
        lines.append("")

    overview = prd.get("overview", "")
    if overview:
        lines.append("## Overview")
        lines.append("")
        lines.append(overview)
        lines.append("")

    phases = prd.get("phases", [])
    if phases:
        lines.append("## Phases")
        lines.append("")
        for phase in phases:
            lines.append(f"### {phase.get('name', 'Unnamed Phase')}")
            lines.append("")
            for deliverable in phase.get("deliverables", []):
                lines.append(f"- {deliverable}")
            lines.append("")

    features = prd.get("features", [])
    if features:
        lines.append("## Features")
        lines.append("")
        for feature in features:
            name = feature.get("name", "Unnamed Feature")
            priority = feature.get("priority", "")
            header = f"### {name}"
            if priority:
                header += f" _(priority: {priority})_"
            lines.append(header)
            lines.append("")
            user_story = feature.get("user_story", "")
            if user_story:
                lines.append(f"_{user_story}_")
                lines.append("")

    open_questions = prd.get("open_questions", [])
    if open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for i, oq in enumerate(open_questions, 1):
            question = oq.get("question", "")
            context = oq.get("context", "")
            lines.append(f"{i}. **{question}**")
            if context:
                lines.append(f"   _{context}_")
            lines.append("")

    tech_stack = prd.get("tech_stack", [])
    if tech_stack:
        lines.append("## Tech Stack")
        lines.append("")
        lines.append("| Name | URL | Purpose |")
        lines.append("|------|-----|---------|")
        for t in tech_stack:
            name = t.get("name", "")
            url = t.get("url", "")
            purpose = t.get("purpose", "")
            url_cell = f"[{url}]({url})" if url else ""
            lines.append(f"| {name} | {url_cell} | {purpose} |")
        lines.append("")

    return "\n".join(lines)


def build_summary_lines(prd: dict) -> list[str]:
    """Build a 2-4 line summary for Telegram delivery.

    Always starts with 'Project: <name>' and ends with '{N} phases, {M} features'.
    The middle is 0, 1, or 2 sentences from prd['overview'].
    """
    lines = [f"Project: {prd.get('project', 'Untitled')}"]
    overview = (prd.get("overview") or "").strip()
    if overview:
        # Naive sentence split — sufficient for Gemini-generated overview text
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", overview) if s.strip()]
        lines.extend(sentences[:2])
    n_phases = len(prd.get("phases", []))
    n_features = len(prd.get("features", []))
    lines.append(f"{n_phases} phases, {n_features} features")
    return lines


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


# ---------------------------------------------------------------------------
# Gemini schema
# ---------------------------------------------------------------------------

PRD_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "project": {"type": "string"},
        "category": {
            "type": "string",
            "enum": ["Technical Tutorial", "Market Analysis", "General Educational", "Other"],
        },
        "overview": {"type": "string"},
        "phases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "deliverables": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["name", "deliverables"],
            },
        },
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "user_story": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "open_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["question", "context"],
            },
        },
        "tech_stack": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "url": {"type": "string"},
                    "purpose": {"type": "string"},
                },
                "required": ["name", "purpose"],
            },
        },
    },
    "required": ["project", "category", "overview", "phases", "open_questions"],
}


# ---------------------------------------------------------------------------
# Reaper
# ---------------------------------------------------------------------------

async def reaper() -> None:
    """Reset stale in-progress PRD jobs (run once at worker startup)."""
    async with database.connection() as conn:
        cur = await conn.execute(
            "UPDATE jobs SET prd_auto_status='error', updated_at=CURRENT_TIMESTAMP "
            "WHERE prd_auto_status='generating' AND updated_at < datetime('now','-10 minutes')"
        )
        await conn.commit()
        if cur.rowcount:
            log.info("prd.reaper.released", count=cur.rowcount)


async def reaper_intent() -> None:
    """Reset stale in-progress intent-slot PRD jobs (run once at worker startup)."""
    async with database.connection() as conn:
        cur = await conn.execute(
            "UPDATE jobs SET prd_intent_status='error', updated_at=CURRENT_TIMESTAMP "
            "WHERE prd_intent_status='generating' AND updated_at < datetime('now','-10 minutes')"
        )
        await conn.commit()
        if cur.rowcount:
            log.info("prd.reaper_intent.released", count=cur.rowcount)


# ---------------------------------------------------------------------------
# Gemini call (sync wrapper for asyncio.to_thread)
# ---------------------------------------------------------------------------

def _call_gemini_prd_sync(prompt: str, api_key: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=PRD_JSON_SCHEMA,
    )
    response = client.models.generate_content(
        model=settings.PRD_AUTO_MODEL, contents=prompt, config=config
    )
    return response.text


def _call_gemini_intent_sync(prompt: str, api_key: str) -> str:
    """Same as _call_gemini_prd_sync but uses PRD_INTENT_MODEL."""
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=PRD_JSON_SCHEMA,
    )
    response = client.models.generate_content(
        model=settings.PRD_INTENT_MODEL, contents=prompt, config=config
    )
    return response.text


# ---------------------------------------------------------------------------
# Auto-resend (re-deliver cached PRD without re-calling Gemini)
# ---------------------------------------------------------------------------

async def run_auto_resend(job_id: str) -> None:
    """Re-deliver an existing auto-slot PRD without re-calling Gemini.

    Reads ``prd_auto_json`` and ``prd_auto_drive_file_id`` from the DB,
    re-renders markdown (in case ``build_prd_markdown`` improved), updates
    the Drive file in place, and re-sends the document to Telegram.
    """
    job = await database.get_job(job_id)
    if not job:
        log.error("prd.auto_resend.job_not_found", job_id=job_id)
        return
    chat_id = job["chat_id"]
    cached_file_id = job.get("prd_auto_drive_file_id")
    cached_json = job.get("prd_auto_json")
    if not cached_file_id or not cached_json:
        log.warning(
            "prd.auto_resend.cache_missing",
            job_id=job_id,
            has_file_id=bool(cached_file_id),
            has_json=bool(cached_json),
        )
        from src.telegram.sender import send_message
        await send_message(chat_id, "⚠️ Cached PRD missing. Regenerating from scratch...")
        await run_auto(job_id)
        return

    try:
        prd_data = json.loads(cached_json)
    except Exception:
        log.error("prd.auto_resend.json_parse_failed", job_id=job_id)
        await run_auto(job_id)
        return

    md_content = build_prd_markdown(prd_data)
    slug = re.sub(r"[^a-z0-9]+", "_", (prd_data.get("project") or "prd").lower())[:40].strip("_")
    filename = f"{slug}_{job_id[-4:]}_auto.md"

    from src.services.drive import update_file
    from src.telegram.sender import send_document, send_message, send_inline_keyboard
    try:
        await update_file(cached_file_id, md_content)
        log.info("prd.drive.updated", job_id=job_id, file_id=cached_file_id, slot="auto_resend")
    except Exception:
        log.exception("prd.auto_resend.drive_failed", job_id=job_id)
        # Fall through — we still have md_content locally, deliver it
    await send_document(
        chat_id, md_content.encode("utf-8"), filename, caption="📐 Auto-generated PRD"
    )
    summary_lines = build_summary_lines(prd_data)
    await send_message(chat_id, "\n".join(summary_lines))
    await send_inline_keyboard(
        chat_id,
        "💡 Want to refine? Build a deeper spec:",
        buttons=[[{"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"}]],
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_auto(job_id: str) -> None:
    """Generate, upload, log and deliver a Mini-PRD for a Technical Tutorial job."""

    # a. Fetch job
    job = await database.get_job(job_id)
    if not job:
        log.error("prd.auto.job_not_found", job_id=job_id)
        return
    chat_id = job["chat_id"]

    # b. Atomic lock
    async with database.connection() as conn:
        cur = await conn.execute(
            "UPDATE jobs SET prd_auto_status='generating', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND (prd_auto_status IS NULL OR prd_auto_status='error')",
            (job_id,),
        )
        await conn.commit()
        if cur.rowcount == 0:
            log.info("prd.lock_contention", job_id=job_id)
            return
    log.info("prd.lock_acquired", job_id=job_id)

    # c. Build prompt
    transcript = sample_transcript(
        job.get("transcript") or "", settings.PRD_MAX_TRANSCRIPT_CHARS
    )
    prompt = (
        "You are a product architect. Based on the following transcript and enrichment "
        "analysis, generate a Mini-PRD JSON document.\n\n"
        f"Video: {job.get('title', '')}\n"
        f"Topic: {job.get('ai_topic', '')}\n"
        f"Objective: {job.get('ai_objective', '')}\n"
        f"Action Points: {job.get('ai_action_points', '')}\n"
        f"Tools: {job.get('ai_tools', '')}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Return the PRD as JSON matching the provided schema."
    )

    # d. Call Gemini (free → paid fallback)
    raw_prd = None
    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            raw_prd = await asyncio.to_thread(_call_gemini_prd_sync, prompt, key)
            log.info("prd.gemini.success", job_id=job_id)
            break
        except Exception:
            log.warning("prd.gemini.fallback", job_id=job_id)
    if raw_prd is None:
        log.error("prd.gemini.both_keys_failed", job_id=job_id, slot="auto")
        await database.update_job_status(job_id, job["status"], prd_auto_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generation failed (Gemini keys exhausted). Try again in a few minutes.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]],
        )
        return

    # e. Parse JSON
    try:
        prd_data = _extract_json(raw_prd)
    except Exception:
        log.error("prd.parse_failed", job_id=job_id, raw_preview=raw_prd[:200], slot="auto")
        await database.update_job_status(job_id, job["status"], prd_auto_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generation produced invalid output.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]],
        )
        return

    # f. Build markdown
    md_content = build_prd_markdown(prd_data)

    # g. Drive upload (create on first run, update in place thereafter)
    from src.services.drive import upload_file, update_file

    slug = re.sub(r"[^a-z0-9]+", "_", (prd_data.get("project") or "prd").lower())[:40].strip("_")
    filename = f"{slug}_{job_id[-4:]}_auto.md"
    cached_file_id = job.get("prd_auto_drive_file_id")
    try:
        if cached_file_id:
            drive_url = await update_file(cached_file_id, md_content)
            file_id = cached_file_id
            log.info("prd.drive.updated", job_id=job_id, file_id=file_id, slot="auto")
        else:
            file_id, drive_url = await upload_file(
                md_content, filename, settings.GOOGLE_DRIVE_FOLDER_PRD
            )
            log.info("prd.drive.uploaded", job_id=job_id, file_id=file_id, slot="auto")
    except Exception:
        log.error("prd.drive.failed", job_id=job_id, slot="auto")
        await database.update_job_status(job_id, job["status"], prd_auto_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ Drive upload failed.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]],
        )
        return

    # h. Sheets append
    from src.services.sheets import append_prd_row

    try:
        await append_prd_row(
            job_id=job_id,
            video_url=job["url"],
            title=job.get("title", ""),
            drive_url=drive_url,
            slot="auto",
        )
        log.info("prd.sheets.appended", job_id=job_id, slot="auto")
    except Exception:
        log.warning("prd.sheets.failed", job_id=job_id, slot="auto")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generated but sheet append failed.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]],
        )
        # Continue to deliver the document — sheets failure isn't fatal for the user

    # i. Update job DB
    await database.update_job_status(
        job_id,
        job["status"],
        prd_auto_status="done",
        prd_auto_drive_file_id=file_id,
        prd_auto_drive_url=drive_url,
        prd_auto_json=json.dumps(prd_data),
    )

    # j. Brain ingest (fire-and-forget)
    tech_stack = prd_data.get("tech_stack", [])
    brain_links = [
        {"url": t["url"], "label": t["name"], "description": t.get("purpose", "")}
        for t in tech_stack
        if t.get("url")
    ]
    if brain_links and settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain

        asyncio.create_task(
            brain.ingest_links(
                brain_links, topic=prd_data.get("project", ""), source_job_id=job_id
            )
        )
        log.info("prd.brain.dispatched", job_id=job_id, count=len(brain_links))

    # k. Telegram delivery
    from src.telegram.sender import send_document, send_message, send_inline_keyboard
    await send_document(
        chat_id,
        md_content.encode("utf-8"),
        filename,
        caption="📐 Auto-generated PRD",
    )
    summary_lines = build_summary_lines(prd_data)
    await send_message(chat_id, "\n".join(summary_lines))
    await send_inline_keyboard(
        chat_id,
        "💡 Want to refine? Build a deeper spec:",
        buttons=[[{"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"}]],
    )


async def run_intent(job_id: str) -> None:
    """Generate, upload, log and deliver an intent-slot Mini-PRD.

    Reads ``intent_text`` from ``job.prd_intent_text`` (set by the webhook
    handler before enqueueing). Never receives intent_text via the Redis
    envelope (privacy + retry support).
    """
    job = await database.get_job(job_id)
    if not job:
        log.error("prd.intent.job_not_found", job_id=job_id)
        return
    chat_id = job["chat_id"]
    intent_text = (job.get("prd_intent_text") or "").strip()
    if not intent_text:
        log.error("prd.intent.no_intent_text", job_id=job_id)
        return
    if not (job.get("transcript") or "").strip():
        from src.telegram.sender import send_message
        await send_message(chat_id, "⚠️ No transcript available — can't generate PRD.")
        log.warning("prd.intent.no_transcript", job_id=job_id)
        return

    # a. Atomic lock + cooldown gate
    async with database.connection() as conn:
        cur = await conn.execute(
            "UPDATE jobs SET prd_intent_status='generating', updated_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND (prd_intent_status IS NULL OR prd_intent_status IN ('error','done')) "
            "AND (prd_intent_completed_at IS NULL OR prd_intent_completed_at < datetime('now','-' || ? || ' seconds'))",
            (job_id, settings.PRD_INTENT_COOLDOWN_SECONDS),
        )
        await conn.commit()
        if cur.rowcount == 0:
            log.info("prd.cooldown_blocked", job_id=job_id, slot="intent")
            from src.telegram.sender import send_message
            await send_message(chat_id, "📐 Last PRD just generated. Try again in a moment.")
            return
    log.info("prd.lock_acquired", job_id=job_id, slot="intent")

    # b. Prompt (intent-biased)
    transcript = sample_transcript(
        job.get("transcript") or "", settings.PRD_MAX_TRANSCRIPT_CHARS
    )
    prompt = (
        f"The user's project direction: {intent_text}. Use this to shape the PRD.\n\n"
        "You are a product architect. Based on the following transcript and enrichment "
        "analysis, generate a Mini-PRD JSON document.\n\n"
        f"Video: {job.get('title', '')}\n"
        f"Topic: {job.get('ai_topic', '')}\n"
        f"Objective: {job.get('ai_objective', '')}\n"
        f"Action Points: {job.get('ai_action_points', '')}\n"
        f"Tools: {job.get('ai_tools', '')}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Return the PRD as JSON matching the provided schema."
    )

    # c. Gemini call (free → paid fallback). Model = PRD_INTENT_MODEL.
    raw_prd = None
    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            raw_prd = await asyncio.to_thread(_call_gemini_intent_sync, prompt, key)
            log.info("prd.gemini.success", job_id=job_id, slot="intent")
            break
        except Exception:
            log.warning("prd.gemini.fallback", job_id=job_id, slot="intent")
    if raw_prd is None:
        log.error("prd.gemini.both_keys_failed", job_id=job_id, slot="intent")
        await database.update_job_status(job_id, job["status"], prd_intent_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generation failed (Gemini keys exhausted). Try again in a few minutes.",
            buttons=[[
                {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
                {"text": "✍️ New Intent", "callback_data": f"prd_intent_prompt:{job_id}"},
            ]],
        )
        return

    # d. Parse JSON
    try:
        prd_data = _extract_json(raw_prd)
    except Exception:
        log.error("prd.parse_failed", job_id=job_id, slot="intent", raw_preview=raw_prd[:200])
        await database.update_job_status(job_id, job["status"], prd_intent_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generation produced invalid output.",
            buttons=[[
                {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
                {"text": "✍️ New Intent", "callback_data": f"prd_intent_prompt:{job_id}"},
            ]],
        )
        return

    # e. Markdown
    md_content = build_prd_markdown(prd_data, intent_text=intent_text)
    slug = re.sub(r"[^a-z0-9]+", "_", (prd_data.get("project") or "prd").lower())[:40].strip("_")
    filename = f"{slug}_{job_id[-4:]}_intent.md"

    # f. Drive (create on first run, update in place thereafter)
    from src.services.drive import upload_file, update_file
    cached_file_id = job.get("prd_intent_drive_file_id")
    try:
        if cached_file_id:
            drive_url = await update_file(cached_file_id, md_content)
            file_id = cached_file_id
            log.info("prd.drive.updated", job_id=job_id, file_id=file_id, slot="intent")
        else:
            file_id, drive_url = await upload_file(
                md_content, filename, settings.GOOGLE_DRIVE_FOLDER_PRD
            )
            log.info("prd.drive.uploaded", job_id=job_id, file_id=file_id, slot="intent")
    except Exception:
        log.error("prd.drive.failed", job_id=job_id, slot="intent")
        await database.update_job_status(job_id, job["status"], prd_intent_status="error")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ Drive upload failed.",
            buttons=[[
                {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
                {"text": "✍️ New Intent", "callback_data": f"prd_intent_prompt:{job_id}"},
            ]],
        )
        return

    # g. Sheets append
    from src.services.sheets import append_prd_row
    try:
        await append_prd_row(
            job_id=job_id,
            video_url=job["url"],
            title=job.get("title", ""),
            drive_url=drive_url,
            slot="intent",
            intent_text=intent_text,
        )
        log.info("prd.sheets.appended", job_id=job_id, slot="intent")
    except Exception:
        log.warning("prd.sheets.failed", job_id=job_id, slot="intent")
        from src.telegram.sender import send_inline_keyboard
        await send_inline_keyboard(
            chat_id,
            "⚠️ PRD generated but sheet append failed.",
            buttons=[[
                {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
            ]],
        )
        # continue to deliver

    # h. Update job DB — prd_intent_completed_at written ONLY on success
    await database.update_job_status(
        job_id,
        job["status"],
        prd_intent_status="done",
        prd_intent_drive_file_id=file_id,
        prd_intent_drive_url=drive_url,
        prd_intent_json=json.dumps(prd_data),
        prd_intent_completed_at=datetime.now(timezone.utc).isoformat(),
    )

    # i. Brain ingest (fire-and-forget)
    tech_stack = prd_data.get("tech_stack", [])
    brain_links = [
        {"url": t["url"], "label": t["name"], "description": t.get("purpose", "")}
        for t in tech_stack
        if t.get("url")
    ]
    if brain_links and settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain
        asyncio.create_task(
            brain.ingest_links(brain_links, topic=prd_data.get("project", ""), source_job_id=job_id)
        )
        log.info("prd.brain.dispatched", job_id=job_id, slot="intent", count=len(brain_links))

    # j. Telegram delivery
    from src.telegram.sender import send_document, send_message, send_inline_keyboard
    await send_document(
        chat_id,
        md_content.encode("utf-8"),
        filename,
        caption=f"📐 PRD with your direction: _{intent_text}_",
    )
    summary_lines = build_summary_lines(prd_data)
    await send_message(chat_id, "\n".join(summary_lines))
    await send_inline_keyboard(
        chat_id,
        "💡 Want to refine further? Text another intent.",
        buttons=[[{"text": "✍️ Text your intent", "callback_data": f"prd_intent_prompt:{job_id}"}]],
    )

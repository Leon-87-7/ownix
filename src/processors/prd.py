"""Mini-PRD auto slot — slice #6."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Callable

from src import database
from src.config import settings
from src.utils.logger import get_logger
from src.services.gemini import extract_json

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

def _header_md(prd: dict, intent_text: str | None) -> list[str]:
    lines = [f"# PRD: {prd.get('project', 'Untitled')}", ""]
    if intent_text:
        lines += [f"**Your direction:** _{intent_text}_", ""]
    category = prd.get("category", "")
    if category:
        lines += [f"**Category:** {category}", ""]
    overview = prd.get("overview", "")
    if overview:
        lines += ["## Overview", "", overview, ""]
    return lines


def _phases_md(prd: dict) -> list[str]:
    phases = prd.get("phases", [])
    if not phases:
        return []
    lines = ["## Phases", ""]
    for phase in phases:
        lines += [f"### {phase.get('name', 'Unnamed Phase')}", ""]
        lines += [f"- {deliverable}" for deliverable in phase.get("deliverables", [])]
        lines.append("")
    return lines


def _features_md(prd: dict) -> list[str]:
    features = prd.get("features", [])
    if not features:
        return []
    lines = ["## Features", ""]
    for feature in features:
        name = feature.get("name", "Unnamed Feature")
        priority = feature.get("priority", "")
        header = f"### {name}"
        if priority:
            header += f" _(priority: {priority})_"
        lines += [header, ""]
        user_story = feature.get("user_story", "")
        if user_story:
            lines += [f"_{user_story}_", ""]
    return lines


def _open_questions_md(prd: dict) -> list[str]:
    open_questions = prd.get("open_questions", [])
    if not open_questions:
        return []
    lines = ["## Open Questions", ""]
    for i, oq in enumerate(open_questions, 1):
        question = oq.get("question", "")
        context = oq.get("context", "")
        lines.append(f"{i}. **{question}**")
        if context:
            lines.append(f"   _{context}_")
        lines.append("")
    return lines


def _tech_stack_md(prd: dict) -> list[str]:
    tech_stack = prd.get("tech_stack", [])
    if not tech_stack:
        return []
    lines = ["## Tech Stack", "", "| Name | URL | Purpose |", "|------|-----|---------|"]
    for t in tech_stack:
        name = t.get("name", "")
        url = t.get("url", "")
        purpose = t.get("purpose", "")
        url_cell = f"[{url}]({url})" if url else ""
        lines.append(f"| {name} | {url_cell} | {purpose} |")
    lines.append("")
    return lines


def build_prd_markdown(prd: dict, *, intent_text: str | None = None) -> str:
    """Render a PRD JSON dict to a structured markdown document.

    If intent_text is provided, insert a 'Your direction' line immediately
    after the title.
    """
    lines = (
        _header_md(prd, intent_text)
        + _phases_md(prd)
        + _features_md(prd)
        + _open_questions_md(prd)
        + _tech_stack_md(prd)
    )
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

async def _reap_stale(column: str, event: str) -> None:
    """Reset stale 'generating' rows in *column* (run once at worker startup)."""
    async with database.connection() as conn:
        cur = await conn.execute(
            f"UPDATE jobs SET {column}='error', updated_at=CURRENT_TIMESTAMP "
            f"WHERE {column}='generating' AND updated_at < datetime('now','-10 minutes')"
        )
        await conn.commit()
        if cur.rowcount:
            log.info(event, count=cur.rowcount)


async def reaper() -> None:
    """Reset stale in-progress PRD jobs (run once at worker startup)."""
    await _reap_stale("prd_auto_status", "prd.reaper.released")


async def reaper_intent() -> None:
    """Reset stale in-progress intent-slot PRD jobs (run once at worker startup)."""
    await _reap_stale("prd_intent_status", "prd.reaper_intent.released")


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prd_prompt(job: dict, intent_text: str | None = None) -> str:
    """Shared PRD prompt; an intent line is prepended when *intent_text* is given."""
    transcript = sample_transcript(job.get("transcript") or "", settings.PRD_MAX_TRANSCRIPT_CHARS)
    intent_prefix = (
        f"The user's project direction: {intent_text}. Use this to shape the PRD.\n\n"
        if intent_text else ""
    )
    return (
        intent_prefix
        + "You are a product architect. Based on the following transcript and enrichment "
        "analysis, generate a Mini-PRD JSON document.\n\n"
        f"Video: {job.get('title', '')}\n"
        f"Topic: {job.get('ai_topic', '')}\n"
        f"Objective: {job.get('ai_objective', '')}\n"
        f"Action Points: {job.get('ai_action_points', '')}\n"
        f"Tools: {job.get('ai_tools', '')}\n\n"
        f"Transcript:\n{transcript}\n\n"
        "Return the PRD as JSON matching the provided schema."
    )


def _build_auto_prompt(job: dict) -> str:
    return _build_prd_prompt(job)


def _build_intent_prompt(job: dict, intent_text: str) -> str:
    return _build_prd_prompt(job, intent_text)


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
        await update_file(cached_file_id, md_content, chat_id=chat_id)
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
# Unified PRD pipeline skeleton
# ---------------------------------------------------------------------------

async def _fail_prd(
    job_id: str, slot: str, chat_id: int, job: dict, headline: str, reason: str, buttons
) -> None:
    """Set the slot to error and send a retry keyboard with *headline*."""
    await database.set_prd_slot_status(job_id, slot, "error")
    from src.telegram.sender import send_inline_keyboard
    title = job.get("title", "(unknown video)")
    await send_inline_keyboard(
        chat_id,
        f"{headline}\nerror: {reason}\njob_title: {title}",
        buttons=buttons,
    )


async def _acquire_prd_lock(
    job_id: str, slot: str, lock_col: str, is_intent: bool, chat_id: int
) -> bool:
    """Atomically flip the slot to 'generating'. False (with user notice) on contention."""
    if is_intent:
        lock_sql = (
            f"UPDATE jobs SET {lock_col}='generating', updated_at=CURRENT_TIMESTAMP "
            f"WHERE id=? AND ({lock_col} IS NULL OR {lock_col} IN ('error','done')) "
            "AND (prd_intent_completed_at IS NULL OR prd_intent_completed_at < datetime('now','-' || ? || ' seconds'))"
        )
        lock_params: tuple = (job_id, settings.PRD_INTENT_COOLDOWN_SECONDS)
    else:
        lock_sql = (
            f"UPDATE jobs SET {lock_col}='generating', updated_at=CURRENT_TIMESTAMP "
            f"WHERE id=? AND ({lock_col} IS NULL OR {lock_col}='error')"
        )
        lock_params = (job_id,)

    async with database.connection() as conn:
        cur = await conn.execute(lock_sql, lock_params)
        await conn.commit()
        if cur.rowcount == 0:
            log.info("prd.lock_contention", job_id=job_id, slot=slot)
            if is_intent:
                from src.telegram.sender import send_message
                await send_message(chat_id, "📐 Last PRD just generated. Try again in a moment.")
            return False
    log.info("prd.lock_acquired", job_id=job_id, slot=slot)
    return True


async def _append_prd_sheet_row(
    job_id: str, job: dict, slot: str, is_intent: bool, drive_url: str, chat_id: int
) -> None:
    """Append the PRD row to Sheets; non-fatal — warn the user and continue on failure."""
    from src.services.sheets import append_prd_row

    sheets_kwargs: dict = {"slot": slot}
    if is_intent:
        sheets_kwargs["intent_text"] = job.get("prd_intent_text", "")

    try:
        await append_prd_row(
            job_id=job_id,
            video_url=job["url"],
            title=job.get("title", ""),
            drive_url=drive_url,
            chat_id=chat_id,
            **sheets_kwargs,
        )
        log.info("prd.sheets.appended", job_id=job_id, slot=slot)
    except Exception as exc:
        err_msg = str(exc).splitlines()[0][:120]
        log.warning("prd.sheets.failed", job_id=job_id, slot=slot)
        from src.telegram.sender import send_inline_keyboard
        title = job.get("title", "(unknown video)")
        sheets_retry_buttons = (
            [[{"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"}]]
            if is_intent else
            [[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]]
        )
        await send_inline_keyboard(
            chat_id,
            f"⚠️ PRD generated but sheet append failed\nerror: {err_msg}\njob_title: {title}",
            buttons=sheets_retry_buttons,
        )
        # Continue to deliver the document — sheets failure isn't fatal for the user


async def _deliver_prd(
    chat_id: int, job_id: str, job: dict, prd_data: dict,
    md_content: str, filename: str, slot: str, is_intent: bool,
) -> None:
    """Brain ingest (fire-and-forget) + Telegram delivery of the finished PRD."""
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
        log.info("prd.brain.dispatched", job_id=job_id, slot=slot, count=len(brain_links))

    caption = (
        f"📐 PRD with your direction: _{job.get('prd_intent_text', '')}_"
        if is_intent else "📐 Auto-generated PRD"
    )
    if is_intent:
        final_buttons = [[{"text": "✍️ Text your intent", "callback_data": f"prd_intent_prompt:{job_id}"}]]
        final_msg = "💡 Want to refine further? Text another intent."
    else:
        final_buttons = [[{"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"}]]
        final_msg = "💡 Want to refine? Build a deeper spec:"

    from src.telegram.sender import send_document, send_message, send_inline_keyboard
    await send_document(chat_id, md_content.encode("utf-8"), filename, caption=caption)
    summary_lines = build_summary_lines(prd_data)
    await send_message(chat_id, "\n".join(summary_lines))
    await send_inline_keyboard(chat_id, final_msg, buttons=final_buttons)


async def run_prd(
    job_id: str,
    *,
    slot: str,
    model: str,
    build_prompt: Callable[[dict], str],
) -> None:
    """Unified 7-step PRD pipeline. slot determines all slot-specific column names and messages."""

    lock_col = f"prd_{slot}_status"
    drive_file_col = f"prd_{slot}_drive_file_id"
    drive_url_col = f"prd_{slot}_drive_url"
    json_col = f"prd_{slot}_json"
    filename_suffix = f"_{slot}.md"
    is_intent = slot == "intent"

    # a. Fetch job
    job = await database.get_job(job_id)
    if not job:
        log.error("prd.job_not_found", job_id=job_id, slot=slot)
        return
    chat_id = job["chat_id"]

    # Retry buttons — differ by slot
    retry_buttons = (
        [[
            {"text": "🔄 Retry Same Intent", "callback_data": f"prd_retry_intent:{job_id}"},
            {"text": "✍️ New Intent", "callback_data": f"prd_intent_prompt:{job_id}"},
        ]]
        if is_intent else
        [[{"text": "🔄 Retry", "callback_data": f"prd_retry_auto:{job_id}"}]]
    )

    # b. Atomic lock
    if not await _acquire_prd_lock(job_id, slot, lock_col, is_intent, chat_id):
        return

    # c. Build prompt
    prompt = build_prompt(job)

    # d. Call Gemini (free → paid fallback)
    from src.services.gemini import gemini_client, GeminiUnavailableError
    raw_prd: str | None = None
    last_error: str | None = None
    try:
        raw_prd = await gemini_client.generate(prompt, model=model, schema=PRD_JSON_SCHEMA)
        log.info("prd.gemini.success", job_id=job_id, slot=slot)
    except GeminiUnavailableError as exc:
        last_error = str(exc)[:120]
        log.warning("prd.gemini.both_keys_failed", job_id=job_id, slot=slot)
    if raw_prd is None:
        log.error("prd.gemini.both_keys_failed", job_id=job_id, slot=slot)
        await _fail_prd(
            job_id, slot, chat_id, job, "⚠️ PRD generation failed",
            last_error or "Gemini keys exhausted", retry_buttons,
        )
        return

    # e. Parse JSON
    try:
        prd_data = extract_json(raw_prd)
    except Exception as exc:
        err_msg = str(exc).splitlines()[0][:120]
        log.error("prd.parse_failed", job_id=job_id, slot=slot, raw_preview=raw_prd[:200])
        await _fail_prd(
            job_id, slot, chat_id, job,
            "⚠️ PRD generation produced invalid output", err_msg, retry_buttons,
        )
        return

    # f. Build markdown
    intent_text = job.get("prd_intent_text", "") if is_intent else None
    md_content = build_prd_markdown(prd_data, intent_text=intent_text)

    # g. Drive upload (create on first run, update in place thereafter)
    from src.services.drive import upload_file, update_file

    slug = re.sub(r"[^a-z0-9]+", "_", (prd_data.get("project") or "prd").lower())[:40].strip("_")
    filename = f"{slug}_{job_id[-4:]}{filename_suffix}"
    cached_file_id = job.get(drive_file_col)
    try:
        if cached_file_id:
            drive_url = await update_file(cached_file_id, md_content, chat_id=chat_id)
            file_id = cached_file_id
            log.info("prd.drive.updated", job_id=job_id, file_id=file_id, slot=slot)
        else:
            file_id, drive_url = await upload_file(
                md_content, filename, settings.GOOGLE_DRIVE_FOLDER_PRD, chat_id=chat_id
            )
            log.info("prd.drive.uploaded", job_id=job_id, file_id=file_id, slot=slot)
    except Exception as exc:
        err_msg = str(exc).splitlines()[0][:120]
        log.error("prd.drive.failed", job_id=job_id, slot=slot)
        await _fail_prd(
            job_id, slot, chat_id, job, "⚠️ Drive upload failed", err_msg, retry_buttons,
        )
        return

    # h. Sheets append (non-fatal)
    await _append_prd_sheet_row(job_id, job, slot, is_intent, drive_url, chat_id)

    # i. Update job DB — preserve any cached Drive id/url when the export was a
    # no-op (gated non-operator job returns "" / ("", "")), so flipping on
    # OPERATOR_CHAT_ID for an existing deployment can't clobber a stored URL.
    db_kwargs: dict = {
        drive_file_col: file_id or job.get(drive_file_col, ""),
        drive_url_col: drive_url or job.get(drive_url_col, ""),
        json_col: json.dumps(prd_data),
    }
    if is_intent:
        db_kwargs["prd_intent_completed_at"] = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(job_id, job["status"], **db_kwargs)
    await database.set_prd_slot_status(job_id, slot, "done")

    # j+k. Brain ingest + Telegram delivery
    await _deliver_prd(chat_id, job_id, job, prd_data, md_content, filename, slot, is_intent)


# ---------------------------------------------------------------------------
# Public entry points (thin wrappers)
# ---------------------------------------------------------------------------

async def run_auto(job_id: str) -> None:
    """Generate, upload, log and deliver a Mini-PRD for a Technical Tutorial job."""
    await run_prd(job_id, slot="auto", model=settings.PRD_AUTO_MODEL,
                  build_prompt=_build_auto_prompt)


async def run_intent(job_id: str) -> None:
    """Generate, upload, log and deliver an intent-slot Mini-PRD."""
    job = await database.get_job(job_id)
    if not job:
        log.error("prd.intent.job_not_found", job_id=job_id)
        return
    intent_text = (job.get("prd_intent_text") or "").strip()
    if not intent_text:
        log.error("prd.intent.no_intent_text", job_id=job_id)
        return
    if not (job.get("transcript") or "").strip():
        from src.telegram.sender import send_message
        await send_message(job["chat_id"], "⚠️ No transcript available — can't generate PRD.")
        return
    await run_prd(job_id, slot="intent", model=settings.PRD_INTENT_MODEL,
                  build_prompt=lambda j: _build_intent_prompt(j, intent_text))

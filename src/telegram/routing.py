"""What to do with an inbound message: invite gate, then text/URL/file routing.

Owns the invite flow (`admit_or_park` and its three effect helpers), the
awaiting-intent and awaiting-freestyle states, per-pipeline URL routing, and
document/photo ingestion including media-group batching.
"""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

import asyncio
import hashlib
import re

import httpx
from urllib.parse import urlparse



from src import database, job_queue as queue
from src.config import settings
from src.services import storage
from src.services.parse import (
    MIME_BY_EXT,
    SUPPORTED_EXTS,
    _ext_from_name,
    content_type_for,
    detect_format,
)
from src.services.invite_notifications import notify_operator_invite
from src.services.jobs import (
    create_and_enqueue_job,
    enforce_job_rate_limit,
)
from src.telegram import sender
from src.utils import job_tag
from src.utils.background_tasks import spawn_background
from src.utils.ssrf import is_public_host
from src.utils.validators import (
    detect_pipeline,
    normalize_email,
    normalize_repo_url,
    _ARTICLE_HINT,
    _REPO_HINT,
)
from src.telegram.commands import _SLASH_TABLE, _dispatch_slash, _handle_freestyle_url
from src.telegram.context import (
    _admin_label,
    _INVITE_BLOCKED_MESSAGE,
    _INVITE_EMAIL_PROMPT_TEMPLATE,
    _INVITE_WAITING_MESSAGE_TEMPLATE,
    _reply_cached_job,
    _tagged_ack,
    log,
)


_BATCH_TASKS: dict[str, asyncio.Task] = {}



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
    from src.utils.markdown import build_enriched_links_message, build_plain_links_message

    links = result.get("links", [])
    summary = result.get("summary", "")
    if links:
        links = await enrich_github_links(links)
        await sender.send_message(chat_id, build_enriched_links_message(links))
        if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
            from src import brain

            spawn_background(brain.ingest_links(links, topic=summary, source_job_id=source_job_id))
        try:
            await sender.send_message(chat_id, build_plain_links_message(links))
        except Exception:
            log.exception("photo_links_plain_message_failed", chat_id=chat_id)
    else:
        noun = "these images" if plural else "this image"
        await sender.send_message(
            chat_id,
            f"🔍 No links found in {noun}.\nThat is what I did see:\n{summary}",
        )



async def _handle_single_photo(chat_id: int, file_id: str, caption: str | None) -> None:
    from src.services.gemini import call_gemini_photo_links

    await sender.send_message(chat_id, "🔍 Scanning image for links...")
    photo_bytes, mime_type = await sender.download_photo(file_id)
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
    await sender.send_message(chat_id, f"📸 Processing {len(file_ids)} image(s)...")
    images = []
    for fid in file_ids:
        b, mt = await sender.download_photo(fid)
        images.append({"bytes": b, "mime_type": mt})
    result = await call_gemini_photo_links(images, caption=None)
    await _report_photo_links(chat_id, result, f"photo_group_{media_group_id}", plural=True)



async def _handle_awaiting_intent(chat_id: int, text: str, state: dict) -> None:
    """Routing path when chat_state is armed and not expired."""
    job_id = state["job_id"]
    pipeline = detect_pipeline(text)
    if pipeline in ("short", "long", "unsized", "article", "repo"):
        url_to_store = normalize_repo_url(text) if pipeline == "repo" else text
        cached = await database.find_recent_job_by_url(chat_id, url_to_store)
        if cached:
            await database.clear_chat_state(chat_id)
            log.info("prd.chat_state.canceled_by_url", chat_id=chat_id, old_job_id=job_id)
            await sender.send_message(chat_id, "🔄 Previous intent canceled.")
            await _reply_cached_job(chat_id, cached)
            return
        # Create (rate-limited, deduplication skipped since `cached` above
        # already came back empty) before touching chat_state, so a 429 or a
        # failed enqueue leaves the pending intent workflow intact instead of
        # silently dropping it.
        task_type = (
            "repo" if pipeline == "repo" else ("article" if pipeline == "article" else "video")
        )
        result = await create_and_enqueue_job(
            chat_id, url_to_store, pipeline, skip_cache=True, task=task_type
        )
        new_job_id = result["id"]
        await database.clear_chat_state(chat_id)
        log.info("prd.chat_state.canceled_by_url", chat_id=chat_id, old_job_id=job_id)
        await sender.send_message(chat_id, "🔄 Started new job; previous intent canceled.")
        await sender.send_message(chat_id, f"📥 Received!\njob_{new_job_id[-4:]}")
        return
    stripped = text.strip()
    if len(stripped) < 5:
        await sender.send_message(
            chat_id,
            "📐 Intent too short (min 5 chars). Reply with a few words describing your project direction.",
        )
        log.info("prd.intent.too_short", chat_id=chat_id, intent_text_len=len(stripped))
        return
    if len(stripped) > 1000:
        await sender.send_message(
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
    log.info(
        "prd.intent.enqueued",
        chat_id=chat_id,
        job_id=job_id,
        intent_text_len=len(stripped),
    )
    log.info("prd.chat_state.consumed", chat_id=chat_id, job_id=job_id)



async def _handle_awaiting_freestyle(chat_id: int, text: str, state: dict) -> None:
    """Handle user reply when awaiting_freestyle chat state is armed."""
    job_id = state["job_id"]
    stripped = text.strip()
    if len(stripped) < 5:
        await sender.send_message(
            chat_id,
            "✍️ Prompt too short (min 5 chars). Reply again or /cancel to abandon.",
        )
        return
    if len(stripped) > 1000:
        await sender.send_message(
            chat_id,
            "✍️ Prompt too long (max 1000 chars). Reply again or /cancel to abandon.",
        )
        return
    async with database.connection() as conn:
        await conn.execute(
            "UPDATE jobs SET freestyle_prompt=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (stripped, job_id),
        )
        await conn.commit()
    await database.clear_chat_state(chat_id)
    log.info(
        "freestyle.prompt.stored",
        chat_id=chat_id,
        job_id=job_id,
        prompt_len=len(stripped),
    )
    job = await database.get_job(job_id)
    if job and job.get("content_type") == "short":
        await queue.enqueue({"task": "video", "job_id": job_id})
        log.info("freestyle.video.enqueued", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"📥 Received\n✨ Kicking off Gemini analysis (freestyle)\njob_{job_id[-4:]}",
        )
    elif job and job.get("content_type") == "repo":
        await queue.enqueue({"task": "repo", "job_id": job_id})
        log.info("freestyle.repo.enqueued", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting repo analysis",
        )
    elif job and job.get("content_type") == "article":
        await queue.enqueue({"task": "article", "job_id": job_id})
        log.info("freestyle.article.enqueued", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting article analysis",
        )
    elif job and job.get("content_type") == "document":
        await queue.enqueue({"task": "document", "job_id": job_id})
        log.info("freestyle.document.enqueued", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"{job_tag(job_id)}\n✨ Freestyle prompt received — re-running document analysis",
        )
    elif job and job.get("status") == "transcript_done":
        await queue.enqueue({"task": "enrichment", "job_id": job_id})
        log.info("freestyle.enrichment.enqueued", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"{job_tag(job_id)}\n✨ Freestyle prompt received — starting Gemini analysis",
        )
    else:
        log.info("freestyle.prompt.deferred", chat_id=chat_id, job_id=job_id)
        await sender.send_message(
            chat_id,
            f"{job_tag(job_id)}\n✍️ Prompt saved — Gemini will start when transcript is ready",
        )



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



async def _remember_invite_identity(
    chat_id: int,
    identity: dict[str, str | None] | None,
    *,
    status: str | None = None,
    user: dict | None = None,
) -> None:
    if identity is None:
        return
    first_name = identity.get("first_name") or ""
    last_name = identity.get("last_name")
    username = identity.get("username")
    if status == "approved" and user is not None:
        unchanged = (
            (user.get("first_name") or "") == first_name
            and user.get("last_name") == last_name
            and user.get("username") == username
        )
        if unchanged:
            return
    await database.upsert_user(
        tg_id=chat_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
    )



async def _notify_operator_invite(chat_id: int, email: str) -> None:
    await notify_operator_invite(chat_id, email)



async def _capture_invite_email(chat_id: int, text: str) -> bool:
    """Consume *text* as the email a waiting user was asked for.

    Returns False when this chat is not awaiting an email, so the caller falls
    through to the rest of the invite flow; True means *text* was the answer to
    the prompt and has been dealt with, valid or not.
    """
    state = await database.get_chat_state(chat_id)
    if not state or state.get("mode") != "awaiting_email" or not _resolve_chat_state(state):
        return False
    email = normalize_email(text)
    if email is None:
        await sender.send_message(chat_id, "Please send a valid email address.")
        return True
    await database.set_user_email(chat_id, email)
    await _notify_operator_invite(chat_id, email)
    await database.clear_chat_state(chat_id)
    await sender.send_message(
        chat_id, _INVITE_WAITING_MESSAGE_TEMPLATE.format(admin=_admin_label())
    )
    return True



async def _prompt_for_invite_email(chat_id: int) -> None:
    """Ask an unknown sender for the email the operator will review."""
    await database.set_chat_state(
        chat_id=chat_id,
        mode="awaiting_email",
        job_id=f"invite:{chat_id}",
        expires_minutes=60 * 24 * 30,
    )
    await sender.send_message(
        chat_id, _INVITE_EMAIL_PROMPT_TEMPLATE.format(admin=_admin_label())
    )



async def _park_pending_link(chat_id: int, text: str) -> None:
    """Hold a waiting user's link until approval, or say why it can't be held."""
    pipeline = detect_pipeline(text, frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "rejected":
        # Only an actual URL attempt earns the error. Greetings, slash commands and
        # the photo/document routes (which call the gate with text="") get the queue
        # status instead — this is the waiting template's second send site.
        if text.strip().lower().startswith(("http://", "https://")):
            await sender.send_message(
                chat_id,
                "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
                "Instagram Reels, TikTok videos, Facebook videos, X/Twitter videos, "
                "and allowlisted article domains.",
            )
        else:
            await sender.send_message(
                chat_id, _INVITE_WAITING_MESSAGE_TEMPLATE.format(admin=_admin_label())
            )
        return

    url = normalize_repo_url(text) if pipeline == "repo" else text
    # Same dedup rule as create_and_enqueue_job (ADR-0033), but protected by a
    # single write transaction so concurrent waiting-user resends cannot double-park.
    await database.create_held_job_unless_recent(
        chat_id=chat_id,
        url=url,
        content_type=pipeline,
    )
    await sender.send_message(chat_id, "Saved — it processes the moment you're in.")



async def admit_or_park(
    chat_id: int,
    text: str,
    identity: dict[str, str | None] | None,
    *,
    via_callback: bool = False,
) -> bool:
    """True when *chat_id* may proceed; otherwise handle the invite flow, return False.

    Deliberately not named as a predicate. Every False path has already answered
    the sender, and may also have recorded their email, notified the operator, or
    parked their link as a held job — so a call site reading
    `if not await admit_or_park(...): return` is finished, not merely blocked.
    """
    status = await database.get_user_status(chat_id)
    user = await database.get_user(chat_id)
    await _remember_invite_identity(chat_id, identity, status=status, user=user)

    if status == "approved":
        return True
    if status == "blocked":
        await sender.send_message(chat_id, _INVITE_BLOCKED_MESSAGE)
        return False
    # A callback press carries no text, so it can neither answer the email
    # prompt nor be parked as a link — it only ever gets turned away.
    if via_callback:
        return False
    if await _capture_invite_email(chat_id, text):
        return False
    if not user or not user.get("email"):
        await _prompt_for_invite_email(chat_id)
        return False
    await _park_pending_link(chat_id, text)
    return False



async def _handle_user_template_shortcut(chat_id: int, text: str, message_id: int | None) -> bool:
    if not re.match(r"^-[a-zA-Z0-9][a-zA-Z0-9_-]*$", text.split()[0]):
        return False
    from src.intake import commands as intake_commands

    result = await intake_commands.user_template_shortcut(chat_id, text, message_id=message_id)
    if result.kind == "job_deduped":
        if not result.job_id:
            log.error(
                "user_template_shortcut.deduped_missing_job_id",
                chat_id=chat_id,
                response_kind=result.kind,
            )
            await sender.send_message(chat_id, "❌ Could not find that saved job. Please try again.")
            return True
        job = await database.get_job(result.job_id)
        if job is None:
            log.error(
                "user_template_shortcut.deduped_job_missing",
                chat_id=chat_id,
                job_id=result.job_id,
            )
            await sender.send_message(chat_id, "❌ Could not find that saved job. Please try again.")
            return True
        await _reply_cached_job(chat_id, job)
        return True
    if result.kind == "job_created":
        if not result.job_id:
            log.error(
                "user_template_shortcut.created_missing_job_id",
                chat_id=chat_id,
                response_kind=result.kind,
            )
            await sender.send_message(chat_id, "❌ Could not create that job. Please try again.")
            return True
        job_id = result.job_id
        tmpl_name = text.split()[0][1:].lower()
        await sender.send_message(
            chat_id,
            f"📥 Received\n✨ Kicking off analysis ({tmpl_name})\njob_{job_id[-4:]}",
        )
        return True
    # command_result (usage) / error / unsupported — all render as a ❌ notice.
    await sender.send_message(chat_id, f"❌ {result.text}")
    return True



async def _enqueue_simple_job(
    chat_id: int,
    url: str,
    content_type: str,
    message_id: int | None,
    *,
    skip_cache: bool = False,
) -> dict:
    """Create + enqueue an article/repo job and ack the user."""
    job = await create_and_enqueue_job(
        chat_id, url, content_type, message_id=message_id, skip_cache=skip_cache
    )
    if job.get("_deduped"):
        await _reply_cached_job(chat_id, job)
    else:
        await sender.send_message(chat_id, f"📥 Received!\njob_{job['id'][-4:]}")
    return job



async def _reject_url(chat_id: int, text: str) -> None:
    try:
        _host = (urlparse(text).hostname or "").lower().removeprefix("www.")
    except Exception:
        _host = ""
    _github_hint = (
        f"\n{_REPO_HINT}" if _host == "github.com" or _host.endswith(".github.com") else ""
    )
    await sender.send_message(
        chat_id,
        "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
        "Instagram Reels (not /p/ carousels), TikTok videos, Facebook videos, "
        "and X/Twitter videos.\n" + _ARTICLE_HINT + _github_hint,
    )
    log.info("url_rejected", chat_id=chat_id, url=text)



async def _route_article(
    chat_id: int, text: str, message_id: int | None, pending_template: str | None
) -> None:
    # A pending template is an explicit request for a fresh run; the shared
    # helper would otherwise return a cached URL-only job.
    await _enqueue_simple_job(
        chat_id, text, "article", message_id, skip_cache=bool(pending_template)
    )



async def _route_repo(
    chat_id: int, text: str, message_id: int | None, pending_template: str | None, client
) -> None:
    repo_url = normalize_repo_url(text)
    if pending_template:
        await client.set(f"pending_template:{chat_id}", pending_template, ex=120)
        await sender.send_message(
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
    chat_id: int,
    text: str,
    pipeline: str,
    message_id: int | None,
    pending_template: str | None,
) -> None:
    if pending_template == "freestyle":
        await _handle_freestyle_url(chat_id, text, pipeline, message_id)
        return

    job = await create_and_enqueue_job(
        chat_id,
        text,
        pipeline,
        template=pending_template,
        message_id=message_id,
    )
    job_id = job["id"]
    if job.get("_deduped"):
        await _reply_cached_job(chat_id, job)
        return
    if pending_template:
        await sender.send_message(
            chat_id,
            f"📥 Received\n✨ Kicking off Gemini analysis ({pending_template})\njob_{job_id[-4:]}",
        )
    else:
        await sender.send_message(chat_id, f"📥 Received!\njob_{job_id[-4:]}")



async def _route_url(chat_id: int, text: str, message_id: int | None) -> None:
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



_is_public_host = is_public_host



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



async def _route_document_url(
    chat_id: int, url: str, message_id: int | None, *, tag_names: list[str] | None = None
) -> None:
    """Fetch a document URL, store it content-addressed, and enqueue a job (#152)."""
    try:
        data = await _safe_get_pdf(url)
    except Exception:
        data = None
    if data is None:
        log.info("document_url_fetch_failed", chat_id=chat_id, url=url)
        await sender.send_message(chat_id, "📄 Couldn't download that file. Check the link and try again.")
        return
    ext = detect_format(data, url)
    if ext is None:
        await sender.send_message(chat_id, "📄 That link didn't return a supported document.")
        log.info("document_url_unsupported", chat_id=chat_id, url=url)
        return
    await _enqueue_document_job(chat_id, data, ext, message_id, tag_names=tag_names)



_MAX_DOC_BYTES = 20 * 1024 * 1024  # Telegram bot getFile cap (ADR-0023)

_DOC_TOO_LARGE_MSG = (
    "📄 File too large for Telegram (max 20MB). Upload via the web dashboard — feature coming soon."
)



_DOCUMENT_MIMES = frozenset(MIME_BY_EXT.values()) | {
    "application/vnd.ms-word.document.macroEnabled.12",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
}



async def _handle_document_update(chat_id: int, message: dict, document: dict) -> None:
    """Validate + ingest a Telegram document upload (PDF + office formats, ADR-0023).

    Only file *metadata* is available here (bytes are fetched in _ingest_document),
    so this is a cheap pre-filter on the declared extension/MIME; the real gate is
    the content sniff after download."""
    file_name = document.get("file_name") or ""
    mime_type = document.get("mime_type")
    looks_supported = _ext_from_name(file_name) in SUPPORTED_EXTS or mime_type in _DOCUMENT_MIMES
    if not looks_supported:
        await sender.send_message(chat_id, "📄 Only documents (PDF, Word, Excel, PowerPoint, OpenDocument, RTF, EPUB, CSV) are supported.")
        log.info("document_rejected_type", chat_id=chat_id, mime=mime_type)
        return
    if (document.get("file_size") or 0) > _MAX_DOC_BYTES:
        await sender.send_message(chat_id, _DOC_TOO_LARGE_MSG)
        log.info("document_rejected_size", chat_id=chat_id, size=document.get("file_size"))
        return
    # Heavy download/upload runs off the webhook request, mirroring the photo path.
    spawn_background(_ingest_document(chat_id, document, message.get("message_id")))



async def _enqueue_document_job(
    chat_id: int,
    data: bytes,
    ext: str,
    message_id: int | None,
    *,
    tag_names: list[str] | None = None,
) -> None:
    """Store document bytes content-addressed, create + enqueue the job, ack the user."""
    enforce_job_rate_limit(chat_id)
    sha = hashlib.sha256(data).hexdigest()
    key = storage.object_key("documents", sha, ext)
    await storage.upload(key, data, content_type_for(ext))
    job_id = await database.create_job(
        chat_id=chat_id,
        url=key,
        content_type="document",
        message_id=message_id,
    )
    await queue.enqueue({"task": "document", "job_id": job_id})
    if tag_names:
        from src.intake.models import IntakeResponse
        from src.intake.router import apply_tag_tokens

        resp = await apply_tag_tokens(
            chat_id, job_id, tag_names, IntakeResponse(kind="job_created", text="", job_id=job_id)
        )
        await sender.send_message(chat_id, _tagged_ack(resp))
    else:
        await sender.send_message(chat_id, f"📥 Received!\njob_{job_id[-4:]}")



async def _ingest_document(chat_id: int, document: dict, message_id: int | None) -> None:
    # Runs unawaited via create_task, so swallow nothing silently: catch and tell the user.
    try:
        data = await sender.download_file(document["file_id"])
        ext = detect_format(data, document.get("file_name"))
        if ext is None:  # parity with the URL path; skip wasted upload+job
            await sender.send_message(chat_id, "📄 That file isn't a supported document.")
            log.info("document_rejected_magic", chat_id=chat_id)
            return
        await _enqueue_document_job(chat_id, data, ext, message_id)
    except Exception:
        log.exception("document_ingest_failed", chat_id=chat_id)
        await sender.send_message(chat_id, "📄 Couldn't process that file. Please try again.")



async def _handle_photo_update(chat_id: int, message: dict, photo: list) -> None:
    file_id = photo[-1]["file_id"]
    caption = message.get("caption") or None
    media_group_id: str | None = message.get("media_group_id")
    if media_group_id:
        await _accumulate_media_group(chat_id, media_group_id, file_id)
    else:
        spawn_background(_handle_single_photo(chat_id, file_id, caption))



async def _route_text(
    chat_id: int,
    text: str,
    message_id: int | None,
    identity: dict[str, str | None] | None = None,
) -> None:
    if not await admit_or_park(chat_id, text, identity):
        return

    # 1. Slash command path — includes /tag and /taglist (registered in
    # _SLASH_TABLE), so an explicit tagged submission is just another command.
    if text.startswith("/"):
        await _dispatch_slash(chat_id, text, message_id)
        return

    # 2. Plain tag-bearing text outranks an unrelated awaiting prompt. This is
    # a deliberately narrow adapter over the channel-neutral intake router.
    from src.intake import tag_tokens
    _, submitted_tags = tag_tokens.extract(text)
    if submitted_tags:
        await _route_tagged_submission(chat_id, text, message_id, explicit=False)
        return

    # 3. Awaiting-intent path
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

    # 4. Plain-text command shortcut: "find code" → "/find code", "rebuild-graph" → "/rebuild-graph"
    first_word = text.split()[0].lower()
    if ("/" + first_word) in _SLASH_TABLE:
        await _dispatch_slash(chat_id, "/" + text, message_id)
        return

    # 4b. User-template shortcut: "-mytemplate <url>"
    if await _handle_user_template_shortcut(chat_id, text, message_id):
        return

    # 5. Normal URL routing
    await _route_url(chat_id, text, message_id)



async def _route_tagged_submission(
    chat_id: int, text: str, message_id: int | None, *, explicit: bool
) -> None:
    """Validate Telegram grammar, then invoke shared tagged intake mechanics."""
    from src.intake import router as intake_router, tag_tokens
    from src.intake.models import IntakeActor, IntakeMessage

    candidate, names = tag_tokens.extract(text)
    parts = candidate.split()
    if not names or len(parts) != 1:
        usage = "Usage: /tag <url> #tag [#tag...]" if explicit else "Send one URL with #tags."
        await sender.send_message(chat_id, usage)
        return
    pipeline = detect_pipeline(parts[0], frozenset(await database.list_allowed_domains(chat_id)))
    if pipeline == "rejected":
        await sender.send_message(chat_id, "❌ Unsupported URL.")
        return
    if pipeline == "document":
        # Preserve the established safe download/content-addressed document path.
        await _route_document_url(chat_id, parts[0], message_id, tag_names=names)
        return
    actor = IntakeActor(
        user_id=chat_id, channel_id=str(chat_id), channel_type="telegram", legacy_chat_id=chat_id
    )
    resp = await intake_router.handle(
        IntakeMessage(actor=actor, text=text, source_message_id=message_id)
    )
    if resp.job_id:
        await sender.send_message(chat_id, _tagged_ack(resp))
    else:
        await sender.send_message(chat_id, resp.text)


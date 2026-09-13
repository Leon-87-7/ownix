"""Slash commands: one `_cmd_*` per entry in `_SLASH_TABLE`.

Telegram presentation over the channel-neutral bodies in `src/intake/` —
HTML formatting, inline keyboards and file sends live here, the shared
behaviour does not.
"""

# cspell:words allowlist allowlisted freestyle openrouter prd unallowlist unignore webapp

from __future__ import annotations

import html
from collections.abc import Awaitable, Callable
from contextlib import suppress

from urllib.parse import urlparse



from src import database, job_queue as queue
from src.config import settings
from src.services.jobs import (
    create_and_enqueue_job,
    enforce_job_rate_limit,
)
from src.telegram import sender
from src.templates import PROMPT_TEMPLATES
from src.utils.background_tasks import spawn_background
from src.utils.ssrf import is_public_ip, resolve_public_host
from src.utils.validators import (
    detect_pipeline,
    normalize_repo_url,
    coerce_url,
    sanitize_filename_chars,
    is_valid_domain_name,
)
from src.telegram.context import SlashCtx, _reply_cached_job, _tagged_ack, log

_MAX_DOWNLOAD_MD_URL_LENGTH = 2048



async def _validate_public_https_url(url: str) -> str | None:
    if len(url) > _MAX_DOWNLOAD_MD_URL_LENGTH:
        return "URL is too long."
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return "URL must be https with a host."
    infos = await resolve_public_host(parsed.hostname)
    if infos is None:
        return "URL host could not be resolved."
    if not all(is_public_ip(info[4][0]) for info in infos):
        return "URL host resolves to a non-public address."
    return None



async def _handle_freestyle_url(
    chat_id: int, url: str, pipeline: str, message_id: int | None
) -> None:
    """Shared logic for /freestyle <url> and pending_template=freestyle URL message."""
    enforce_job_rate_limit(chat_id)
    job_id = await database.create_job(
        chat_id=chat_id,
        url=url,
        content_type=pipeline,
        message_id=message_id,
        template="freestyle",
    )
    await database.update_job_status(
        job_id, "pending", template_detection_method="explicit_command"
    )
    if pipeline == "long":
        await queue.enqueue({"task": "video", "job_id": job_id})
        await sender.send_message(
            chat_id,
            f"📥 Received\n✨ Kicking off Gemini analysis (freestyle)\njob_{job_id[-4:]}",
        )
    elif pipeline == "article":
        await sender.send_message(
            chat_id, f"📥 Article received — reply with your prompt\njob_{job_id[-4:]}"
        )
    await database.set_chat_state(
        chat_id, mode="awaiting_freestyle", job_id=job_id, expires_minutes=10
    )
    await sender.send_force_reply(
        chat_id,
        "✍️ Reply with your Gemini prompt (reply within 10 min; /cancel to abandon)",
        input_field_placeholder="Your Gemini prompt...",
    )
    log.info("freestyle.url.received", chat_id=chat_id, job_id=job_id, pipeline=pipeline)



async def _cmd_freestyle(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        # Bare /freestyle arms a Telegram-only continuation (the next plain
        # message picks it up outside command dispatch entirely) — not shared,
        # see issue #487's scoping comment.
        await queue._client().set(f"pending_template:{ctx.chat_id}", "freestyle", ex=120)
        await sender.send_message(ctx.chat_id, "📥 `/freestyle` ready — send the URL now (2 min window).")
        return

    # The one-shot `/freestyle <url>` form is shared with the dashboard
    # (issue #487, src/intake/commands.py:freestyle_command) — only this
    # emoji rendering stays Telegram-only.
    from src.intake import commands as intake_commands

    url = ctx.parts[1]
    extra_domains = await database.list_allowed_domains(ctx.chat_id)
    pipeline_preview = detect_pipeline(url, frozenset(extra_domains))
    if pipeline_preview == "repo":
        await sender.send_message(
            ctx.chat_id,
            "Info: `/freestyle` doesn't apply to repo URLs yet\nRunning standard analysis.",
        )
        repo_url = normalize_repo_url(url)
        cached = await database.find_recent_job_by_url(ctx.chat_id, repo_url)
        if cached:
            await _reply_cached_job(ctx.chat_id, cached)
            return

    resp = await intake_commands.freestyle_command(ctx.chat_id, ctx.parts, message_id=ctx.message_id)

    if resp.kind == "unsupported":
        await sender.send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, Facebook videos, X/Twitter videos, "
            "and allowlisted article domains.",
        )
    elif pipeline_preview == "repo":
        if not resp.job_id:
            log.error(
                "freestyle.repo.missing_job_id",
                chat_id=ctx.chat_id,
                response_kind=resp.kind,
            )
            await sender.send_message(ctx.chat_id, "❌ Could not create the repo job. Please try again.")
            return
        await sender.send_message(ctx.chat_id, f"📥 Received!\njob_{resp.job_id[-4:]}")
    else:
        # long/article/short/document/unsized — every pipeline that reaches
        # `freestyle_command`'s state-arming tail gets the same force-reply;
        # long and article additionally get a head-start message.
        if not resp.job_id:
            log.error(
                "freestyle.url.missing_job_id",
                chat_id=ctx.chat_id,
                response_kind=resp.kind,
                pipeline=pipeline_preview,
            )
            await sender.send_message(ctx.chat_id, "❌ Could not create that job. Please try again.")
            return
        if pipeline_preview == "long":
            await sender.send_message(
                ctx.chat_id,
                f"📥 Received\n✨ Kicking off Gemini analysis (freestyle)\njob_{resp.job_id[-4:]}",
            )
        elif pipeline_preview == "article":
            await sender.send_message(
                ctx.chat_id, f"📥 Article received — reply with your prompt\njob_{resp.job_id[-4:]}"
            )
        await sender.send_force_reply(
            ctx.chat_id,
            "✍️ Reply with your Gemini prompt (reply within 10 min; /cancel to abandon)",
            input_field_placeholder="Your Gemini prompt...",
        )
        log.info(
            "freestyle.url.received", chat_id=ctx.chat_id, job_id=resp.job_id, pipeline=pipeline_preview
        )



async def _cmd_cancel(ctx: SlashCtx) -> None:
    # Shared with the dashboard's /api/intake/action "cancel_pending" (issue
    # #477/#475, src/intake/commands.py) — Telegram keeps its own emoji
    # formatting here; only the get/clear-pending-state decision is shared.
    from src.intake import state as intake_state

    pending = await intake_state.get_state(ctx.chat_id)
    await intake_state.clear_state(ctx.chat_id)
    await queue._client().delete(f"pending_template:{ctx.chat_id}")
    if pending and pending.get("mode") == "awaiting_intent":
        await sender.send_message(ctx.chat_id, "✍️ Intent canceled.")
    elif pending and pending.get("mode") == "awaiting_freestyle":
        await sender.send_message(ctx.chat_id, "✍️ Freestyle prompt abandoned.")
    else:
        await sender.send_message(ctx.chat_id, "Nothing to cancel.")



async def _cmd_spec(ctx: SlashCtx) -> None:
    await _handle_spec(ctx.chat_id, ctx.parts)



async def _cmd_checklists(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /checklists <suffix>")
        return

    from src.intake import commands as intake_commands

    status_result = await sender.send_message(ctx.chat_id, "checking lists 🙃")
    status_message_id = status_result.get("message_id")
    resp = await intake_commands.checklists_command(ctx.chat_id, ctx.parts)
    if resp.kind in ("error", "command_result"):
        if status_message_id:
            await sender.edit_message_text(ctx.chat_id, status_message_id, resp.text)
        else:
            await sender.send_message(ctx.chat_id, resp.text)
    elif resp.kind == "checklists_result":
        suffix = ctx.parts[1][-4:]
        await sender.send_document(
            ctx.chat_id,
            resp.text.encode("utf-8-sig"),
            f"checklist_{suffix}.md",
            caption="✅ Checklist ready",
        )
        if status_message_id:
            # Cleanup must not turn an accepted document upload into a webhook
            # failure, which could make Telegram retry and duplicate the file.
            with suppress(Exception):
                await sender.delete_message(ctx.chat_id, status_message_id)



async def _cmd_screenshots(ctx: SlashCtx) -> None:
    from src.intake import commands as intake_commands

    response = await intake_commands.screenshots_command(ctx.chat_id, ctx.parts)
    await sender.send_message(ctx.chat_id, response.text)



async def _cmd_find(ctx: SlashCtx) -> None:
    # Search, score-filter (0.58) and GitHub enrichment are shared with the
    # dashboard's /find (issue #485, src/intake/commands.py:find_command) —
    # usage/empty-result copy stays here, richer and HTML-formatted, rather
    # than being driven off the shared response's plain `text` (which the
    # dashboard renders as-is and has no reason to match Telegram's wording).
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /find <query>")
        return

    from src.intake import commands as intake_commands
    from src.utils.markdown import _humanize_age

    resp = await intake_commands.find_command(ctx.chat_id, ctx.parts)
    query = " ".join(ctx.parts[1:]).strip()

    if not resp.artifacts:
        await sender.send_message(
            ctx.chat_id,
            f'🔍 Nothing found for "<i>{html.escape(query)}</i>".\nTry a broader term or /rebuild-graph if you\'ve added links recently.',
            parse_mode="HTML",
        )
        return

    header = f'🔍 <b>{len(resp.artifacts)} result{"s" if len(resp.artifacts) != 1 else ""}</b> for "<i>{html.escape(query)}</i>"\n\n'
    lines = []
    for r in resp.artifacts:
        parsed = urlparse(r["url"])
        short_url = (parsed.netloc + parsed.path).rstrip("/")
        short_url = short_url.removeprefix("www.")
        entry = (
            f"🔗 <b>{html.escape(r['title'])}</b>\n"
            f'   <a href="{html.escape(r["url"], quote=True)}">{html.escape(short_url)}</a>'
        )
        if r.get("_enriched"):
            desc = (r.get("_gh_description") or "").strip()
            language = r.get("_language") or "N/A"
            meta = f"⭐ {r['_stars']} | 🔀 {r['_forks']} | 💻 {language} | 📅 {_humanize_age(r['_days_ago'])}"
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
    await sender.send_message(ctx.chat_id, header + "\n\n".join(lines), parse_mode="HTML")



async def _cmd_rebuild_graph(ctx: SlashCtx) -> None:
    from src import brain

    if brain.rebuild_in_progress():
        await sender.send_message(ctx.chat_id, "Rebuild already in progress — please wait.")
        return
    await sender.send_message(ctx.chat_id, "Brain rebuild started — will take a few minutes")

    async def _do_rebuild() -> None:
        try:
            n = await brain.rebuild_graph()
            await sender.send_message(ctx.chat_id, f"Graph rebuilt — {n} nodes written.")
        except Exception:
            await sender.send_message(ctx.chat_id, "Rebuild failed. Check logs.")

    spawn_background(_do_rebuild())



async def _cmd_template(ctx: SlashCtx) -> None:
    template = ctx.parts[0][1:]
    if len(ctx.parts) < 2:
        await queue._client().set(f"pending_template:{ctx.chat_id}", template, ex=120)
        await sender.send_message(
            ctx.chat_id, f"📥 `/{template}` ready — send the URL now (2 min window)."
        )
        return
    url = ctx.parts[1]
    pipeline = detect_pipeline(url)
    if pipeline == "rejected":
        await sender.send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, Facebook videos, and X/Twitter videos.",
        )
        return
    result = await create_and_enqueue_job(
        ctx.chat_id, url, pipeline, template=template, message_id=ctx.message_id
    )
    job_id = result["id"]
    await sender.send_message(
        ctx.chat_id,
        f"📥 Received\n✨ Kicking off Gemini analysis ({template})\njob_{job_id[-4:]}",
    )



async def _cmd_addlink(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /addlink <url>")
        return
    if len(ctx.parts) > 2:
        # ctx.parts is a whitespace split, so every token past the first was
        # silently dropped before this check. Batch intake is dashboard-only
        # (CONTEXT.md "Batch link paste").
        await sender.send_message(
            ctx.chat_id,
            "/addlink takes one URL. To add several at once, paste the list into "
            "Ingest Link on the dashboard.",
        )
        return
    # coerce_url so a bare domain works here exactly as it does on the
    # dashboard — one implementation of "is this a URL" (#490).
    url = coerce_url(ctx.parts[1])
    if url is None:
        await sender.send_message(ctx.chat_id, "Usage: /addlink <url> — use a valid HTTP(S) URL or bare domain")
        return
    warning = "`/addlink` saves the link as-is; it does not process it through the pipeline-detection flow."
    # create_and_enqueue_job owns dedup (ADR-0033): a cache hit on any content_type
    # returns the existing job instead of creating a duplicate link job.
    job = await create_and_enqueue_job(ctx.chat_id, url, "link", message_id=ctx.message_id)
    if job.get("content_type", "link") != "link":
        await sender.send_message(
            ctx.chat_id,
            f"⚠️ This URL already exists as a {job.get('content_type')} job "
            f"(job_{job['id'][-4:]}) — no link entry was created.\n\n{warning}",
            parse_mode="Markdown",
        )
        return
    if job.get("_deduped"):
        await _reply_cached_job(ctx.chat_id, job)
        await sender.send_message(ctx.chat_id, warning, parse_mode="Markdown")
        return
    await sender.send_message(
        ctx.chat_id, f"📥 Received\njob_{job['id'][-4:]}\n\n{warning}", parse_mode="Markdown"
    )



async def _cmd_force(ctx: SlashCtx) -> None:
    # All three states (reset+reprocess / clear orphaned cache / create) are
    # shared with the dashboard's /force (issue #486,
    # src/intake/commands.py:force_command) — only this emoji rendering, and
    # attaching ctx.message_id to a freshly created job, stay Telegram-only.
    from src.intake import commands as intake_commands

    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /force <url> [#tags]")
        return

    resp = await intake_commands.force_command(
        ctx.chat_id, ctx.parts, message_id=ctx.message_id
    )

    if resp.kind == "unsupported":
        await sender.send_message(
            ctx.chat_id,
            "❌ Unsupported URL. I accept YouTube videos, YouTube Shorts, "
            "Instagram Reels, TikTok videos, Facebook videos, X/Twitter videos, "
            "and allowlisted article domains.",
        )
    elif resp.kind == "command_result":
        # Only reachable non-usage case left is "cache cleared".
        await sender.send_message(ctx.chat_id, f"🗑️ {resp.text}")
    else:
        await sender.send_message(ctx.chat_id, _tagged_ack(resp, prefix="🔁 Force-reprocessing!"))



async def _cmd_tag(ctx: SlashCtx) -> None:
    # Deferred: routing imports this module for the slash table, so a top-level
    # import here would close the loop. The only command that reaches upward.
    from src.telegram.routing import _route_tagged_submission

    await _route_tagged_submission(ctx.chat_id, " ".join(ctx.parts[1:]), ctx.message_id, explicit=True)



async def _cmd_taglist(ctx: SlashCtx) -> None:
    from src.intake import tag_tokens
    if len(ctx.parts) != 1:
        await sender.send_message(ctx.chat_id, "Usage: /taglist")
        return
    tags = await database.list_tags(ctx.chat_id)
    if not tags:
        await sender.send_message(ctx.chat_id, "No tags yet. Create them in dashboard Controls.")
        return
    grouped = tag_tokens.groups(tags)
    entries = []
    for tag in tags:
        collision = len(grouped[tag_tokens.normalize(tag["name"])]) > 1
        if collision:
            line = f"⚠️ {html.escape(tag['name'])} — ambiguous"
        else:
            token = html.escape("#" + tag_tokens.encode(tag["name"]))
            line = f"<code>{token}</code> — {html.escape(tag['name'])}"
        if tag.get("meaning"):
            line += f" — {html.escape(tag['meaning'])}"
        entries.append(line)
    # Split only between complete entries; UTF-16 units are Telegram's limit.
    chunks, current = [], ""
    for entry in entries:
        candidate = f"{current}\n{entry}" if current else entry
        if current and len(candidate.encode("utf-16-le")) // 2 > 4000:
            chunks.append(current)
            current = entry
        else:
            current = candidate
    if current:
        chunks.append(current)
    for chunk in chunks:
        await sender.send_message(ctx.chat_id, chunk, parse_mode="HTML")



def _sanitize_title(title: str, url: str, max_len: int = 80) -> str:
    """Return a safe filename stem from *title*, falling back to the URL hostname."""
    safe = sanitize_filename_chars(title, max_len=max_len)
    return safe or (urlparse(url).hostname or "document")



async def _cmd_download_md(ctx: SlashCtx) -> None:
    """/download_md <URL> — fetch URL as Markdown via Jina, cache, send as document."""
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /download_md <URL>")
        return
    url = ctx.parts[1]
    validation_error = await _validate_public_https_url(url)
    if validation_error:
        await sender.send_message(ctx.chat_id, f"❌ {validation_error}")
        return

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
        await sender.send_document(ctx.chat_id, title_body.encode("utf-8-sig"), filename)
        log.info("download_md.cache_hit", chat_id=ctx.chat_id, url=url)
        return

    # 2. Cache miss — call Jina
    from src.services.jina import JinaFetchError, fetch_markdown

    try:
        title, body = await fetch_markdown(url)
    except JinaFetchError as exc:
        await sender.send_message(ctx.chat_id, f"❌ Failed to fetch URL (HTTP {exc.status_code}).")
        return

    # 3. Build document content and persist
    content = (title + "\n\n" + body).strip() if title else body.strip()
    await database.insert_markdown_cache(url, content)

    # 4. Send as Telegram document
    filename = _sanitize_title(title, url) + ".md"
    await sender.send_document(ctx.chat_id, content.encode("utf-8-sig"), filename)
    log.info("download_md.fetched", chat_id=ctx.chat_id, url=url, filename=filename)



_PROTECTED_DOMAINS = {"github.com"}



def _normalize_domain(raw: str) -> str:
    """Strip to bare hostname, lowercase, drop 'www.' prefix."""
    host = urlparse(raw).hostname or raw
    return host.lower().removeprefix("www.").rstrip(".")



def _format_domain_report(*sections: tuple[str, list[str]]) -> str:
    """Join non-empty '<label> `d1`, `d2`' lines for a domain-command reply."""
    return "\n".join(
        f"{label} " + ", ".join(f"`{d}`" for d in domains) for label, domains in sections if domains
    )



async def _cmd_ignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /ignore <domain or URL> [more...]")
        return
    added, protected, invalid = [], [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if not is_valid_domain_name(domain):
            # Reported rather than skipped: with every token invalid the other
            # two lists stay empty, and _format_domain_report's "" would reach
            # send_message, which Telegram rejects with a 400.
            invalid.append(domain)
            continue
        if domain in _PROTECTED_DOMAINS:
            protected.append(domain)
            continue
        await database.add_ignored_domain(ctx.chat_id, domain)
        added.append(domain)
    await sender.send_message(
        ctx.chat_id,
        _format_domain_report(
            ("🚫 Ignored:", added),
            ("⛔ Cannot ignore:", protected),
            ("⚠️ Not a domain:", invalid),
        ),
    )



async def _cmd_unignore(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /unignore <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_ignored_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await sender.send_message(
        ctx.chat_id,
        _format_domain_report(("✅ Removed:", removed), ("⚠️ Not found:", missing)),
    )



async def _cmd_ignore_list(ctx: SlashCtx) -> None:
    domains = sorted(await database.get_ignored_domains(ctx.chat_id))
    if not domains:
        await sender.send_message(ctx.chat_id, "No ignored domains yet. Use /ignore <domain>.")
        return
    lines = "\n".join(f"• `{d}`" for d in domains)
    await sender.send_message(ctx.chat_id, f"🚫 Ignored domains ({len(domains)}):\n{lines}")



async def _cmd_allowlist(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /allowlist <domain or URL> [more...]")
        return
    added = []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if not is_valid_domain_name(domain):
            continue
        await database.add_allowed_domain(ctx.chat_id, domain)
        added.append(domain)
    await sender.send_message(ctx.chat_id, "✅ Allowlisted: " + ", ".join(f"`{d}`" for d in added))



async def _cmd_unallowlist(ctx: SlashCtx) -> None:
    if len(ctx.parts) < 2:
        await sender.send_message(ctx.chat_id, "Usage: /unallowlist <domain or URL> [more...]")
        return
    removed, missing = [], []
    for raw in ctx.parts[1:]:
        domain = _normalize_domain(raw)
        if await database.remove_allowed_domain(ctx.chat_id, domain):
            removed.append(domain)
        else:
            missing.append(domain)
    await sender.send_message(
        ctx.chat_id,
        _format_domain_report(("✅ Removed:", removed), ("⚠️ Not in your allowlist:", missing)),
    )



async def _cmd_allowlist_list(ctx: SlashCtx) -> None:
    domains = sorted(await database.list_allowed_domains(ctx.chat_id))
    if not domains:
        await sender.send_message(ctx.chat_id, "No custom allowlist entries yet. Use /allowlist <domain>.")
        return
    lines = "\n".join(f"• `{d}`" for d in domains)
    await sender.send_message(ctx.chat_id, f"✅ Allowlisted domains ({len(domains)}):\n{lines}")



_START_TEXT = (
    "👋 *Ownix — your internet. own it.*\n\n"
    "Send me something worth keeping and I’ll turn it into a searchable entry:\n"
    "• YouTube video or Short\n"
    "• Instagram Reel\n"
    "• TikTok video\n"
    "• Facebook or X/Twitter video\n"
    "• Article URL (use /allowlist to add domains)\n"
    "• GitHub repo URL\n"
    "• PDF file or link\n\n"
    "Type /help for available commands.\n\n"
    "Visit [app.leondev.xyz](https://app.leondev.xyz) for the web app."
)


_HELP_TEXT = (
    "📖 *Commands*\n\n"
    "`/start` — show welcome message\n"
    "`/help` — this message\n"
    "`/find` <query> — search your processed content\n"
    "`/spec` <suffix> [intent] — generate a mini-PRD from a long video\n"
    "`/checklists` <suffix> — generate an engineering checklist\n"
    "`/freestyle` — use a custom Gemini prompt for the next job\n"
    "`/force` <url> — reprocess a URL (skip cache)\n"
    "`/tag` <url> <#tags> — submit a tagged URL\n"
    "`/taglist` — list your tag vocabulary\n"
    "`/cancel` — cancel the current pending prompt\n"
    "`/ignore` <domain> — hide a domain from link results\n"
    "`/unignore` <domain> — stop hiding a domain\n"
    "`/ignore_list` — show ignored domains\n"
    "`/allowlist` <domain> — add an article domain\n"
    "`/unallowlist` <domain> — remove an article domain\n"
    "`/allowlist_list` — show allowlisted domains\n"
    "`/download_md` <suffix> — download a job result as Markdown\n"
    "`/screenshots` <suffix> — capture screenshots from a long video\n"
    "`/rebuild-graph` — rebuild the Second Brain link graph"
)



async def _cmd_start(ctx: SlashCtx) -> None:
    if settings.MINI_APP_URL:
        await sender.send_inline_keyboard(
            ctx.chat_id,
            _START_TEXT + "\n\nOpen the Mini App to connect Google without leaving Telegram.",
            buttons=[[{"text": "Open Mini App", "web_app": {"url": settings.MINI_APP_URL}}]],
            parse_mode="Markdown",
        )
        return
    await sender.send_message(ctx.chat_id, _START_TEXT, parse_mode="Markdown")



async def _cmd_help(ctx: SlashCtx) -> None:
    await sender.send_message(ctx.chat_id, _HELP_TEXT, parse_mode="Markdown")



_SLASH_TABLE: dict[str, Callable[[SlashCtx], Awaitable[None]]] = {
    "/start": _cmd_start,
    "/help": _cmd_help,
    "/cancel": _cmd_cancel,
    "/spec": _cmd_spec,
    "/checklists": _cmd_checklists,
    "/screenshots": _cmd_screenshots,
    "/find": _cmd_find,
    "/rebuild-graph": _cmd_rebuild_graph,
    "/force": _cmd_force,
    "/tag": _cmd_tag,
    "/taglist": _cmd_taglist,
    "/addlink": _cmd_addlink,
    "/ignore": _cmd_ignore,
    "/unignore": _cmd_unignore,
    "/ignore_list": _cmd_ignore_list,
    "/allowlist": _cmd_allowlist,
    "/unallowlist": _cmd_unallowlist,
    "/allowlist_list": _cmd_allowlist_list,
    "/freestyle": _cmd_freestyle,
    "/download_md": _cmd_download_md,
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
    if cmd not in {"/cancel", "/tag", "/taglist"}:
        await database.clear_chat_state(chat_id)
        await queue._client().delete(f"pending_template:{chat_id}")
    await handler(ctx)



async def _parse_spec_args(chat_id: int, parts: list[str]) -> tuple[str, str | None] | None:
    """Validate /spec args; message the user and return None on bad input."""
    if len(parts) < 2:
        await sender.send_message(
            chat_id,
            "Usage: /spec <suffix> [intent text...]\nExample: /spec ABCD desktop app for X",
        )
        return None
    suffix = parts[1][-4:]
    intent_text = " ".join(parts[2:]).strip() or None
    if intent_text is not None:
        if len(intent_text) < 5:
            await sender.send_message(chat_id, "📐 Intent too short (min 5 chars).")
            return None
        if len(intent_text) > 1000:
            await sender.send_message(chat_id, "📐 Intent too long (max 1000 chars).")
            return None
    return suffix, intent_text



async def _report_spec_no_match(chat_id: int, suffix: str) -> None:
    recent = await database.get_recent_jobs(chat_id, 5)
    bullet_lines = "\n".join(
        f"• job_{j['id'][-4:]} — {j.get('title') or '(no title)'} ({j['content_type']}/{j['status']})"
        for j in recent
    )
    await sender.send_message(
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
        log.info(
            "prd.intent.enqueued",
            chat_id=chat_id,
            job_id=job_id,
            intent_text_len=len(intent_text),
        )
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
        j
        for j in rows
        if j["content_type"] == "long" and j["status"] in ("transcript_done", "done")
    ]
    short_matches = [j for j in rows if j["content_type"] == "short"]

    if not long_matches and not short_matches:
        await _report_spec_no_match(chat_id, suffix)
        return

    if not long_matches and short_matches:
        await sender.send_message(
            chat_id,
            f"📐 PRD is only available for long videos. Job {suffix} is a short.",
        )
        log.info("prd.spec.short_video_rejected", chat_id=chat_id, suffix=suffix)
        return

    job = long_matches[0]
    title = job.get("title") or "(no title)"
    await sender.send_message(chat_id, f'📐 PRD for: "{title}" — generating ...')
    log.info(
        "prd.spec.matched",
        chat_id=chat_id,
        suffix=suffix,
        job_id=job["id"],
        intent=bool(intent_text),
    )

    await _enqueue_spec_job(chat_id, job, intent_text)


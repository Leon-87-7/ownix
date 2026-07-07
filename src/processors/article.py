"""Article URL processor — Jina → cache → paywall → Gemini → Sheets → Brain."""

from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from src import database
from src.config import settings
from src.telegram.sender import edit_message_text, send_document, send_inline_keyboard, send_message
from src.services.gemini import extract_json
from src.utils import job_tag
from src.utils.logger import get_logger
from src.services.repo_followup import offer_repo_followups

log = get_logger(__name__)

_PAYWALL_PHRASES = (
    "subscribe to continue",
    "subscribe to read",
    "this post is for paid subscribers",
    "this post is for subscribers only",
    "member-only",
    "members only",
    "create a free account to keep reading",
    "log in to keep reading",
)

_PAYWALL_MIN_CHARS = 500
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""([:\w-]+)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)

_PROMISE_GAP_SUFFIX = """

### STEP 5: PROMISE-GAP ANALYSIS
Identify where the headline or lede sets expectations the article does not fully satisfy.

Add this field to your JSON output:
  "promise_gap": {
    "gaps": ["specific promise in the headline the article never delivers"],
    "hidden_value": ["genuinely useful insight not signalled by the headline"]
  }

Use empty arrays when nothing fits. This field is REQUIRED."""


def _check_paywall(body: str) -> bool:
    """Return True when the article body exhibits paywall signals."""
    body_lower = body.lower()
    if any(phrase in body_lower for phrase in _PAYWALL_PHRASES):
        return True
    return len(body.strip()) < _PAYWALL_MIN_CHARS


def _sanitize_title(title: str, url: str, max_len: int = 80) -> str:
    """Return a safe filename stem from *title*, falling back to the URL hostname."""
    if title:
        safe = re.sub(r"[^a-zA-Z0-9 \-_]", "", title)
        safe = safe.strip()[:max_len]
        if safe:
            return safe
    return urlparse(url).hostname or "document"


def _get_domain(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _extract_og_image_url(markup: str, base_url: str | None = None) -> str | None:
    """Extract og:image from an HTML document."""
    for tag in _META_TAG_RE.findall(markup):
        attrs = {name.lower(): html.unescape(value.strip()) for name, _quote, value in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        content = attrs.get("content", "").strip()
        if key == "og:image" and content:
            resolved = urljoin(base_url, content) if base_url else content
            if urlparse(resolved).scheme in ("http", "https"):
                return resolved
            continue
    return None


async def _fetch_og_image_url(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "vig/1.0 (+https://github.com/Leon-87-7/vig)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception as exc:
        log.info("article.og_image_fetch_failed", url=url, error=str(exc)[:120])
        return None
    return _extract_og_image_url(response.text, str(response.url))


def _build_article_prompt(title: str, body: str, freestyle_prompt: str | None = None) -> str:
    if freestyle_prompt:
        extra = f"\n### FREESTYLE INSTRUCTIONS\n{freestyle_prompt}"
    else:
        extra = ""
    return f"""Analyze the following article (Markdown). Extract structured insights.

Article title: "{title}"

### STEP 1: TOPIC
Identify the specific subject in 2–5 words. Be concrete, not categorical.

### STEP 2: EXTRACTION RULES
Focus on key concepts, actionable takeaways, and any tools, libraries, or services mentioned.

### STEP 3: URL RESOLUTION (applies to every entry in `tools`)
The `url` field is REQUIRED for every tool entry. Use the canonical homepage URL for
well-known tools; leave empty only for concepts too generic to have a URL.

### STEP 4: OUTPUT FORMAT
Respond ONLY with a valid JSON object. No markdown, no backticks, no text before or after.

{{
  "topic": "specific subject in 2-5 words",
  "objective": "One sentence: what is the specific goal of this article?",
  "action_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],
  "tools": [
    {{
      "name": "Tool/Library/Service name",
      "type": "tool|repo|library|service",
      "url": "Canonical URL — empty string only for true concepts",
      "description": "One sentence role/context"
    }}
  ]
}}{extra}{_PROMISE_GAP_SUFFIX}

### ARTICLE:
{body}"""


def _action_points_section(action_points_raw: str) -> list[str]:
    ap_list = [ap.strip() for ap in action_points_raw.split(" | ") if ap.strip()]
    if not ap_list:
        return []
    return ["", "✅ Action Points"] + [f"• {html.escape(ap)}" for ap in ap_list]


def _tools_section(tools: list[dict]) -> list[str]:
    if not tools:
        return []
    parts = ["", "🛠 Tools"]
    for t in tools:
        prefix = f"[{html.escape(t.get('type', 'tool'))}]"
        name = html.escape(t["name"])
        if t.get("url"):
            url_attr = html.escape(t["url"], quote=True)
            name = f'<a href="{url_attr}">{name}</a>'
        desc = html.escape(t.get("description", ""))
        parts.append(f"• {prefix} {name}: {desc}")
    return parts


def _promise_gap_section(promise_gap: dict | None) -> list[str]:
    gaps = promise_gap.get("gaps", []) if promise_gap else []
    hidden = promise_gap.get("hidden_value", []) if promise_gap else []
    if not gaps and not hidden:
        return []
    parts = ["\n=====PROMISE=GAP====="]
    if gaps:
        parts.append("❌ Unfulfilled:")
        parts += [f"• {html.escape(g)}" for g in gaps]
    if hidden:
        parts.append("💎 Hidden value:")
        parts += [f"• {html.escape(h)}" for h in hidden]
    return parts


def _build_enrichment_message(
    job: dict,
    tools: list[dict],
    promise_gap: dict | None,
    paywall_warning: bool,
) -> str:
    tag = f"job_{job['id'][-4:]}:"
    title = html.escape(job.get("title") or "Untitled")
    topic = html.escape(job.get("ai_topic") or "")
    objective = html.escape(job.get("ai_objective") or "")

    parts = []
    if paywall_warning:
        parts.append("⚠️ Article may be paywalled — analysis may be shallow\n")
    parts += [
        tag,
        f"✍️ {title}",
        f"🎫 {topic}" if topic else "",
        "",
        "🎯 Objective",
        objective,
    ]
    parts += _action_points_section(job.get("ai_action_points") or "")
    parts += _tools_section(tools)
    parts += _promise_gap_section(promise_gap)

    return "\n".join(p for p in parts if p is not None)


async def run(job: dict, *, skip_document: bool = False) -> None:
    """Article pipeline: Jina → cache → paywall → Gemini → Sheets → Brain."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    tag = job_tag(job_id)

    await database.update_job_status(job_id, "processing")
    status_result = await send_message(chat_id, f"{tag}\n🔊 Fetching article...")
    status_msg_id: int | None = status_result.get("message_id")

    # 1. Markdown cache lookup
    cached = await database.get_markdown_cache(url)
    if cached:
        content = cached["content"]
        if "\n\n" in content:
            title_line, body = content.split("\n\n", 1)
            title = job.get("title") or title_line.lstrip("# ").strip()
        else:
            body = content
            title = job.get("title") or content.split("\n", 1)[0].lstrip("# ").strip()
        log.info("article.cache_hit", job_id=job_id)
    else:
        from src.services.jina import JinaFetchError, fetch_markdown
        try:
            title, body = await fetch_markdown(url)
        except JinaFetchError as exc:
            await database.update_job_status(job_id, "error", error_msg=f"Jina HTTP {exc.status_code}")
            await send_message(chat_id, f"{tag}\n❌ Failed to fetch article (HTTP {exc.status_code}).")
            return

        content = (title + "\n\n" + body).strip() if title else body.strip()
        await database.insert_markdown_cache(url, content)
        if title and not job.get("title"):
            async with database.connection() as conn:
                await conn.execute(
                    "UPDATE jobs SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (title, job_id),
                )
                await conn.commit()
        log.info("article.jina_fetched", job_id=job_id, title=title[:80] if title else "")

    # og:image is resolved only after the content fetch succeeds, so a Jina
    # failure (which returns early above) never pays for a discarded round-trip.
    og_image_url = job.get("og_image_url") or await _fetch_og_image_url(url)

    if status_msg_id:
        await edit_message_text(chat_id, status_msg_id, f"{tag}\n🍪 Article fetched, running Gemini analysis...")
    else:
        await send_message(chat_id, f"{tag}\n🍪 Article fetched, running Gemini analysis...")

    # 2. Paywall heuristic (never aborts)
    paywall_warning = _check_paywall(body)
    if paywall_warning:
        log.info("article.paywall_detected", job_id=job_id)

    # 3. Send document to Telegram
    filename = _sanitize_title(title, url) + ".md"
    if not skip_document:
        await send_document(chat_id, content.encode(), filename)

    # 4. Build Gemini prompt
    freestyle_prompt = job.get("freestyle_prompt")
    prompt = _build_article_prompt(title, body, freestyle_prompt)

    # 5. Gemini call
    from src.services.gemini import GeminiUnavailableError, generate
    try:
        raw = await generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError:
        await database.update_job_status(job_id, "error")
        await send_inline_keyboard(
            chat_id,
            f"{tag}\n⚠️ Gemini unavailable. Please try again.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"article_retry:{job_id}"}]],
        )
        return

    data = extract_json(raw)
    promise_gap = data.pop("promise_gap", None)
    tools: list[dict] = data.get("tools", [])
    tools_str = " | ".join(
        f"[{t.get('type', 'tool')}] {t['name']}" + (f" ({t['url']})" if t.get("url") else "")
        for t in tools
    )
    ai_topic = data.get("topic", "")
    ai_objective = data.get("objective", "")
    ai_action_points = " | ".join(data.get("action_points", []))

    # 6. Update job to done
    now = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job_id,
        "done",
        title=title or job.get("title", ""),
        ai_topic=ai_topic,
        ai_objective=ai_objective,
        ai_action_points=ai_action_points,
        ai_tools=tools_str,
        og_image_url=og_image_url,
        promise_gap=json.dumps(promise_gap) if promise_gap else None,
        completed_at=now,
    )

    refreshed = await database.get_job(job_id)
    domain = _get_domain(url)

    # 7. Sheets write (fire-and-forget; overwrite row in-place on freestyle re-run)
    async def _sheets_task() -> None:
        from src.services import sheets
        existing_row = refreshed.get("sheets_row_id") if refreshed else None
        if existing_row:
            await sheets.update_article_row(int(existing_row), refreshed or job, domain=domain)
        else:
            row_idx = await sheets.append_article_row(refreshed or job, domain=domain)
            if row_idx:
                async with database.connection() as conn:
                    await conn.execute(
                        "UPDATE jobs SET sheets_row_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (str(row_idx), job_id),
                    )
                    await conn.commit()

    asyncio.create_task(_sheets_task())

    # 8. Telegram enrichment message + Freestyle button
    msg = _build_enrichment_message(refreshed or job, tools, promise_gap, paywall_warning)
    await send_message(chat_id, msg, parse_mode="HTML")
    await send_inline_keyboard(
        chat_id,
        f"{tag}\nWhat's next?",
        buttons=[[{"text": "✍️ Freestyle", "callback_data": f"template_freestyle:{job_id}"}]],
    )
    # Best-effort UX add-on — a follow-up failure must not block Brain ingest.
    try:
        await offer_repo_followups(refreshed or job, tools, text=body)
    except Exception:
        log.warning("repo_followup_offer_failed", job_id=job_id, exc_info=True)

    # 9. Brain ingest (fire-and-forget — article URL only, no body links)
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain
        asyncio.create_task(
            brain.ingest_links([{"url": url}], topic=ai_topic, source_job_id=job_id)
        )

    log.info("article_complete", job_id=job_id, topic=ai_topic, paywall=paywall_warning)

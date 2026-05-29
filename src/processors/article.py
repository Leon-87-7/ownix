"""Article URL processor — Jina → cache → paywall → Gemini → Sheets → Brain."""

from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from src import database
from src.config import settings
from src.telegram.sender import send_document, send_inline_keyboard, send_message
from src.utils.logger import get_logger

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


def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


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
    action_points_raw = job.get("ai_action_points") or ""

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

    ap_list = [ap.strip() for ap in action_points_raw.split(" | ") if ap.strip()]
    if ap_list:
        parts += ["", "✅ Action Points"]
        parts += [f"• {html.escape(ap)}" for ap in ap_list]

    if tools:
        parts += ["", "🛠 Tools"]
        for t in tools:
            prefix = f"[{html.escape(t.get('type', 'tool'))}]"
            name = html.escape(t["name"])
            if t.get("url"):
                url_attr = html.escape(t["url"], quote=True)
                name = f'<a href="{url_attr}">{name}</a>'
            desc = html.escape(t.get("description", ""))
            parts.append(f"• {prefix} {name}: {desc}")

    gaps = promise_gap.get("gaps", []) if promise_gap else []
    hidden = promise_gap.get("hidden_value", []) if promise_gap else []
    if gaps or hidden:
        parts.append("\n=====PROMISE=GAP=====")
        if gaps:
            parts.append("❌ Unfulfilled:")
            parts += [f"• {html.escape(g)}" for g in gaps]
        if hidden:
            parts.append("💎 Hidden value:")
            parts += [f"• {html.escape(h)}" for h in hidden]

    return "\n".join(p for p in parts if p is not None)


async def run(job: dict, *, skip_document: bool = False) -> None:
    """Article pipeline: Jina → cache → paywall → Gemini → Sheets → Brain."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    url = job["url"]
    tag = f"job_{job_id[-4:]}:"

    await database.update_job_status(job_id, "processing")

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
    from src.services.gemini_client import GeminiUnavailableError, gemini_client
    try:
        raw = await gemini_client.generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError:
        await database.update_job_status(job_id, "error")
        await send_inline_keyboard(
            chat_id,
            f"{tag}\n⚠️ Gemini unavailable. Please try again.",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"article_retry:{job_id}"}]],
        )
        return

    data = _extract_json(raw)
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

    # 9. Brain ingest (fire-and-forget — article URL only, no body links)
    if settings.GOOGLE_DRIVE_FOLDER_BRAIN:
        from src import brain
        asyncio.create_task(
            brain.ingest_links([{"url": url}], topic=ai_topic, source_job_id=job_id)
        )

    log.info("article_complete", job_id=job_id, topic=ai_topic, paywall=paywall_warning)

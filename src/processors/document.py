"""Document processor — PDF parse cache + Gemini enrichment (#154).

Mirrors article.py. Parsed text is content-addressed in GCS and shared across
tenants (parsed/<sha>.txt); the job row stays chat_id-owned. Documents get no
promise_gap ("documents don't pitch", same as repos).
"""
from __future__ import annotations

import asyncio
import html
import json
import re
from datetime import datetime, timezone

from src import database
from src.services import storage
from src.services.parse import ParseError, parse_pdf
from src.telegram.sender import send_document, send_inline_keyboard, send_message
from src.services.gemini import extract_json
from src.utils import job_tag
from src.utils.logger import get_logger

log = get_logger(__name__)


def _sha_from_key(key: str) -> str:
    """documents/<sha>.pdf → <sha>."""
    return key.rsplit("/", 1)[-1].rsplit(".", 1)[0]


async def _cached_parse(sha: str, ext: str, *, output_format: str = "text") -> str:
    """Parsed content for <sha>, served from parsed/<sha>.<ext> or parsed fresh + cached.

    Shared by run() (txt) and deliver_markdown() (md) so the sha→key→
    exists/download/parse/upload dance lives in one place (#156).
    """
    parsed_key = storage.object_key("parsed", sha, ext)
    if await storage.exists(parsed_key):
        return (await storage.download(parsed_key)).decode("utf-8", "replace")
    pdf_bytes = await storage.download(storage.object_key("documents", sha, "pdf"))
    content = await parse_pdf(pdf_bytes, output_format=output_format)  # raises ParseError
    if not content.strip():  # scanned/image-only PDF: don't cache an empty parse
        raise ParseError("No text could be extracted — this PDF may be scanned or image-only (OCR not supported)")
    await storage.upload(parsed_key, content.encode("utf-8"), "text/plain")
    return content


def _build_document_prompt(text: str, freestyle_prompt: str | None = None) -> str:
    extra = f"\n### FREESTYLE INSTRUCTIONS\n{freestyle_prompt}" if freestyle_prompt else ""
    return f"""Analyze the following document text. Extract structured insights.{extra}

### STEP 1: METADATA
Identify the title, author(s), publisher/source, and document type
(e.g. research paper, whitepaper, manual, report, spec).

### STEP 2: EXTRACTION RULES
Summarize the document's objective in one sentence, list the key points, any
referenced works/links, and any tools, libraries, or services mentioned.

### STEP 3: URL RESOLUTION (applies to every entry in `tools`)
The `url` field is REQUIRED for every tool entry. Use the canonical homepage URL
for well-known tools; leave empty only for concepts too generic to have a URL.

### STEP 4: OUTPUT FORMAT
Respond ONLY with a valid JSON object. No markdown, no backticks, no text before or after.

{{
  "title": "Document title",
  "author": "Author(s) or empty string",
  "publisher": "Publisher/source or empty string",
  "document_type": "research paper|whitepaper|manual|report|spec|other",
  "summary": "One sentence: the document's objective",
  "key_points": ["Key point 1", "Key point 2", "Key point 3"],
  "references": ["Referenced work or URL", "..."],
  "tools": [
    {{
      "name": "Tool/Library/Service name",
      "type": "tool|repo|library|service",
      "url": "Canonical URL — empty string only for true concepts",
      "description": "One sentence role/context"
    }}
  ]
}}

### DOCUMENT:
{text}"""


def _tools_str(tools: list[dict]) -> str:
    return " | ".join(
        f"[{t.get('type', 'tool')}] {t['name']}" + (f" ({t['url']})" if t.get("url") else "")
        for t in tools
    )


def _build_enrichment_message(job: dict, tools: list[dict], references: list[str]) -> str:
    tag = f"job_{job['id'][-4:]}:"
    title = html.escape(job.get("title") or "Untitled")
    objective = html.escape(job.get("ai_objective") or "")
    try:
        extra = json.loads(job.get("template_analysis") or "{}")
    except (json.JSONDecodeError, TypeError):
        extra = {}

    parts = [tag, f"📄 {title}"]
    byline = " · ".join(
        x for x in (extra.get("author"), extra.get("publisher"), extra.get("document_type")) if x
    )
    if byline:
        parts.append(f"🏷 {html.escape(byline)}")
    parts += ["", "🎯 Objective", objective]

    ap_list = [ap.strip() for ap in (job.get("ai_action_points") or "").split(" | ") if ap.strip()]
    if ap_list:
        parts += ["", "✅ Key points"] + [f"• {html.escape(ap)}" for ap in ap_list]

    if references:
        parts += ["", "🔗 References"] + [f"• {html.escape(str(r))}" for r in references]

    if tools:
        parts.append("")
        parts.append("🛠 Tools")
        for t in tools:
            prefix = f"[{html.escape(t.get('type', 'tool'))}]"
            name = html.escape(t["name"])
            if t.get("url"):
                name = f'<a href="{html.escape(t["url"], quote=True)}">{name}</a>'
            parts.append(f"• {prefix} {name}: {html.escape(t.get('description', ''))}")

    return "\n".join(parts)


def _safe_filename(title: str, max_len: int = 80) -> str:
    safe = re.sub(r"[^a-zA-Z0-9 \-_]", "", title or "").strip()[:max_len]
    return safe or "document"


async def _deliver(job: dict, text: str, tools: list[dict], references: list[str]) -> None:
    """Send the parsed .txt (primary portable artifact) then the enrichment
    summary. Each send is guarded independently so a delivery failure never
    rolls back the already-persisted 'done' state (#155)."""
    chat_id = job["chat_id"]
    filename = _safe_filename(job.get("title")) + ".txt"
    try:
        await send_document(chat_id, text.encode("utf-8"), filename)
    except Exception:
        log.exception("document.txt_delivery_failed", job_id=job["id"])
    try:
        msg = _build_enrichment_message(job, tools, references)
        await send_message(chat_id, msg, parse_mode="HTML")
    except Exception:
        log.exception("document.summary_delivery_failed", job_id=job["id"])
    try:
        await send_inline_keyboard(
            chat_id,
            f"{job_tag(job['id'])}\nWhat's next?",
            buttons=[[
                {"text": "📄 Get Markdown", "callback_data": f"document_md:{job['id']}"},
                {"text": "✍️ Freestyle", "callback_data": f"template_freestyle:{job['id']}"},
            ]],
        )
    except Exception:
        log.exception("document.buttons_delivery_failed", job_id=job["id"])


async def deliver_markdown(job: dict) -> None:
    """On-demand: serve parsed/<sha>.md (cached or freshly parsed) as a .md document (#156)."""
    sha = _sha_from_key(job["url"])
    md = await _cached_parse(sha, "md", output_format="markdown")
    filename = _safe_filename(job.get("title")) + ".md"
    await send_document(job["chat_id"], md.encode("utf-8"), filename)
    log.info("document.markdown_delivered", job_id=job["id"], sha=sha)


async def run(job: dict, *, skip_document: bool = False) -> None:
    """Document pipeline: parse cache → Gemini enrichment → persist → deliver."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    key = job["url"]  # documents/<sha>.pdf
    tag = job_tag(job_id)
    # Dashboard-originated jobs set telegram_delivery='off'; suppress ALL Telegram
    # traffic for them, including the in-progress status ping (not just _deliver).
    deliver = job.get("telegram_delivery", "on") != "off"

    await database.update_job_status(job_id, "processing")
    if deliver:
        await send_message(chat_id, f"{tag}\n📄 Reading document...")

    # 1. Parse cache: parsed text is shared by sha across tenants.
    sha = _sha_from_key(key)
    text = await _cached_parse(sha, "txt")  # raises ParseError on empty/failed parse
    log.info("document.text_ready", job_id=job_id, sha=sha, chars=len(text))

    # 2. Gemini enrichment (raises GeminiUnavailableError on total failure).
    #    freestyle_prompt is set on a Freestyle re-run (#157); None on first pass.
    from src.services.gemini import gemini_client
    raw = await gemini_client.generate(
        _build_document_prompt(text, job.get("freestyle_prompt")), model="gemini-2.5-flash"
    )
    data = extract_json(raw)

    summary_prompt = (
        "Create a structured Markdown briefing from this parsed document. "
        "Include title, TL;DR, key sections, takeaways, and references.\n\n"
        f"DOCUMENT:\n{text}"
    )
    summary_md = await gemini_client.generate(summary_prompt, model="gemini-2.5-flash")
    summary_key = f"enriched/{sha}_summary.md"
    await storage.upload(summary_key, summary_md.encode("utf-8"), "text/markdown")

    tools: list[dict] = data.get("tools", []) or []  # Gemini may emit null, not absent
    references: list[str] = data.get("references", []) or []
    template_analysis = {
        "author": data.get("author", ""),
        "publisher": data.get("publisher", ""),
        "document_type": data.get("document_type", ""),
        "references": references,
    }

    # 3. Persist (no promise_gap). Reuse article's column mapping (ADR-0008).
    now = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job_id,
        "done",
        title=data.get("title") or job.get("title") or "",
        ai_objective=data.get("summary", ""),
        ai_action_points=" | ".join(data.get("key_points", []) or []),
        ai_tools=_tools_str(tools),
        template_analysis=json.dumps(template_analysis),
        completed_at=now,
    )

    await database.add_document_output(job_id, "raw_txt", storage.object_key("parsed", sha, "txt"), "Raw parse")
    await database.add_document_output(job_id, "summary", summary_key, "Structured summary")

    refreshed = await database.get_job(job_id)

    # 4. Sheets index (fire-and-forget; overwrite the row in-place on a freestyle
    #    re-run so #157 updates rather than appends — mirrors article.py, #158).
    async def _sheets_task() -> None:
        from src.services import sheets
        existing_row = refreshed.get("sheets_row_id") if refreshed else None
        row_idx_int: int | None = None
        if existing_row:
            try:
                row_idx_int = int(existing_row)
            except (TypeError, ValueError):
                log.warning("document.invalid_sheets_row_id", job_id=job_id, sheets_row_id=existing_row)
        if row_idx_int is not None:
            await sheets.update_document_row(row_idx_int, refreshed or job)
        else:
            row_idx = await sheets.append_document_row(refreshed or job)
            if row_idx:
                async with database.connection() as conn:
                    await conn.execute(
                        "UPDATE jobs SET sheets_row_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (str(row_idx), job_id),
                    )
                    await conn.commit()

    asyncio.create_task(_sheets_task())

    if deliver:
        await _deliver(refreshed or job, text, tools, references)
    log.info("document_complete", job_id=job_id, title=data.get("title", "")[:80])

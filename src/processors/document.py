"""Document processor — PDF parse cache + Gemini enrichment (#154).

Mirrors article.py. Parsed text is content-addressed in GCS and shared across
tenants (parsed/<sha>.txt); the job row stays chat_id-owned. Documents get no
promise_gap ("documents don't pitch", same as repos).
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone

from src import database
from src.services import storage
from src.services.parse import ParseError, parse_pdf
from src.telegram.sender import send_document, send_message
from src.utils.logger import get_logger

log = get_logger(__name__)


def _sha_from_key(key: str) -> str:
    """documents/<sha>.pdf → <sha>."""
    return key.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


def _build_document_prompt(text: str) -> str:
    return f"""Analyze the following document text. Extract structured insights.

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


async def run(job: dict, *, skip_document: bool = False) -> None:
    """Document pipeline: parse cache → Gemini enrichment → persist → deliver."""
    job_id = job["id"]
    chat_id = job["chat_id"]
    key = job["url"]  # documents/<sha>.pdf
    tag = f"job_{job_id[-4:]}:"

    await database.update_job_status(job_id, "processing")
    await send_message(chat_id, f"{tag}\n📄 Reading document...")

    # 1. Parse cache: parsed text is shared by sha across tenants.
    sha = _sha_from_key(key)
    parsed_key = storage.object_key("parsed", sha, "txt")
    if await storage.exists(parsed_key):
        text = (await storage.download(parsed_key)).decode("utf-8", "replace")
        log.info("document.parse_cache_hit", job_id=job_id, sha=sha)
    else:
        pdf_bytes = await storage.download(key)
        text = await parse_pdf(pdf_bytes)  # raises ParseError on failure
        if not text.strip():  # scanned/image-only PDF: don't cache an empty parse
            raise ParseError("No text could be extracted — this PDF may be scanned or image-only (OCR not supported)")
        await storage.upload(parsed_key, text.encode("utf-8"), "text/plain")
        log.info("document.parsed", job_id=job_id, sha=sha, chars=len(text))

    # 2. Gemini enrichment (raises GeminiUnavailableError on total failure).
    from src.services.gemini import gemini_client
    raw = await gemini_client.generate(_build_document_prompt(text), model="gemini-2.5-flash")
    data = _extract_json(raw)

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

    refreshed = await database.get_job(job_id)
    await _deliver(refreshed or job, text, tools, references)
    log.info("document_complete", job_id=job_id, title=data.get("title", "")[:80])

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from src import database
from src.config import settings
from src.telegram.sender import send_message, send_inline_keyboard
from src.utils.logger import get_logger

log = get_logger(__name__)

MAX_TRANSCRIPT_CHARS = 12_000
EMBEDDING_DIM = 768


class EnrichmentUnavailableError(RuntimeError):
    pass


@dataclass
class Enrichment:
    category: str
    topic: str
    objective: str
    action_points_str: str  # pipe-joined
    tools_str: str           # pipe-joined
    tools_raw: list[dict]    # raw parsed list for brain feed
    market_data: str


def _build_prompt(title: str, transcript: str) -> str:
    truncated = (
        transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[transcript truncated]"
        if len(transcript) > MAX_TRANSCRIPT_CHARS
        else transcript
    )
    return f"""Analyze this YouTube transcript for a video titled: "{title}".

### STEP 1: CLASSIFICATION
Determine if this video is:
A) Technical Tutorial / Coding walkthrough
B) Market Analysis / Trading strategy
C) General Educational / News content

### STEP 2: TOPIC
Identify the specific subject in 2–5 words. Be concrete, not categorical.
Good: "claude code + n8n", "shadcn table component", "RSI divergence strategy"
Bad: "coding tutorial", "market analysis", "general tips"

### STEP 3: EXTRACTION RULES
- If (A): Focus heavily on software architecture, specific libraries, and repository URLs.
- If (B): Focus on tickers ($), entry/exit strategies, macro indicators, and price targets.
- If (C): Focus on core concepts and a high-level summary.

### STEP 4: URL RESOLUTION RULES (applies to every entry in `tools`)
The `url` field is REQUIRED for every tool entry. Resolve it as follows:
1. If the transcript or video description names a specific URL, use that.
2. Else if the tool is well-known (open-source library, public framework, public SaaS, named API, public GitHub repo), use its canonical homepage URL — even when the video does not explicitly name the URL. Examples: `n8n` → `https://n8n.io`, `OpenWeatherMap` → `https://openweathermap.org`, `GitHub` → `https://github.com`, `Claude` → `https://claude.ai`, `OpenAI` → `https://openai.com`, `Tavily` → `https://tavily.com`, `LangChain` → `https://langchain.com`.
3. For market tickers (`type: "symbol"`), use the exchange URL when unambiguous (`$AAPL` → `https://finance.yahoo.com/quote/AAPL`); otherwise leave empty.
4. Only leave `url` empty when the tool is so generic or obscure that no canonical URL can be reliably inferred (e.g. "HTTP Request", "API Documentation", "Curl Command" — these are concepts, not products).

The `url` field is the primary signal used downstream for semantic-graph ingestion. Populating it for every named product is the single most important quality lever in this prompt.

### STEP 5: OUTPUT FORMAT
Respond ONLY with a valid JSON object. No markdown, no backticks, no text before or after the JSON.

{{
  "category": "Detected Category",
  "topic": "specific subject in 2-5 words",
  "objective": "One sentence: what is the specific goal of this video?",
  "action_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],
  "tools": [
    {{
      "name": "Tool/Library/Ticker name",
      "type": "tool|repo|library|symbol|service",
      "url": "Canonical URL per STEP 4 rules — empty string only for true concepts (e.g. 'HTTP Request')",
      "description": "One sentence role/context"
    }}
  ],
  "market_data": "Summary of symbols, trends, or price levels if Category B, else empty string"
}}

### TRANSCRIPT:
{truncated}"""


def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


def _parse_enrichment(data: dict) -> Enrichment:
    action_points_str = " | ".join(data.get("action_points", []))
    tools = data.get("tools", [])
    tools_str = " | ".join(
        ("$" if t.get("type") == "symbol" else f"[{t.get('type', 'tool')}] ")
        + t["name"]
        + (f" ({t['url']})" if t.get("url") else "")
        + f": {t.get('description', '')}"
        for t in tools
    )
    return Enrichment(
        category=data.get("category", "General"),
        topic=data.get("topic", ""),
        objective=data.get("objective", ""),
        action_points_str=action_points_str,
        tools_str=tools_str,
        tools_raw=tools,
        market_data=data.get("market_data", ""),
    )


def _call_gemini_sync(prompt: str, api_key: str) -> str:
    import google.generativeai as genai  # lazy — not installed in test env
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


async def _call_gemini(prompt: str, api_key: str) -> str:
    return await asyncio.to_thread(_call_gemini_sync, prompt, api_key)


async def enrich(job: dict) -> Enrichment:
    """Call Gemini with free→paid key fallback. Raises EnrichmentUnavailableError if both fail."""
    title = job.get("title", "") or "Untitled"
    transcript = job.get("transcript", "") or ""
    prompt = _build_prompt(title, transcript)

    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            raw = await _call_gemini(prompt, key)
            data = _extract_json(raw)
            result = _parse_enrichment(data)
            log.info("enrichment_ok", category=result.category, topic=result.topic)
            return result
        except Exception:
            log.warning("enrichment_key_failed")

    raise EnrichmentUnavailableError("Both Gemini keys failed for enrichment")


def _build_enrichment_message(job: dict, enrichment: Enrichment) -> str:
    tag = f"job_{job['id'][-4:]}:"
    title = job.get("title", "Untitled")
    drive_url = job.get("drive_url", "")

    tools_lines = []
    for t in enrichment.tools_raw:
        prefix = "$" if t.get("type") == "symbol" else f"[{t.get('type', 'tool')}]"
        url_part = f" ({t['url']})" if t.get("url") else ""
        tools_lines.append(f"• {prefix} {t['name']}{url_part}: {t.get('description', '')}")

    action_lines = [f"• {ap}" for ap in enrichment.action_points_str.split(" | ") if ap]

    transcript_line = f"📄 [Transcript]({drive_url})" if drive_url else "📄 Transcript _(unavailable)_"

    parts = [
        f"{tag}",
        f"=📺 {title}",
        f"🗃️ {enrichment.category}",
        f"🎫 {enrichment.topic}",
        "",
        "🎯 Objective",
        enrichment.objective,
        "",
        "✅ Action Points",
        *action_lines,
        "",
        "🛠 Tools",
        *tools_lines,
        "",
        transcript_line,
        "",
        "📐 Build Spec available — use the button below",
    ]
    return "\n".join(parts)


async def run(job_id: str) -> None:
    """Phase 2 enrichment processor — called by worker for task='enrichment'."""
    job = await database.get_job(job_id)
    if not job:
        log.error("enrichment_job_not_found", job_id=job_id)
        return

    chat_id = job["chat_id"]
    tag = f"job_{job_id[-4:]}:"

    if job.get("status") != "transcript_done":
        log.warning("enrichment_wrong_status", job_id=job_id, status=job.get("status"))

    await database.update_job_status(job_id, "enriching")
    await send_message(chat_id, f"{tag}\n🍪 now bakin' by Gemini")

    try:
        enrichment = await enrich(job)
    except EnrichmentUnavailableError:
        title = job.get("title", "(unknown video)")
        await send_message(chat_id, f"{tag}\n⚠️ Gemini failed to enrich: {title}")
        await database.update_job_status(job_id, "error")
        return

    now = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job_id, "complete",
        ai_category=enrichment.category,
        ai_topic=enrichment.topic,
        ai_objective=enrichment.objective,
        ai_action_points=enrichment.action_points_str,
        ai_tools=enrichment.tools_str,
        ai_market_data=enrichment.market_data,
        completed_at=now,
    )

    msg = _build_enrichment_message(job, enrichment)
    await send_message(chat_id, msg, parse_mode="Markdown")

    await send_inline_keyboard(
        chat_id,
        f"{tag}\nWhat's next?",
        buttons=[[{"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"}]],
    )

    log.info("enrichment_complete", job_id=job_id, category=enrichment.category)

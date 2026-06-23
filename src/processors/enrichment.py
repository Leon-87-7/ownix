from __future__ import annotations

import asyncio
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from json_repair import repair_json

from src import database
from src.brain import EMBEDDING_DIM
from src.config import settings
from src.telegram.sender import send_message, send_inline_keyboard
from src.templates import PROMPT_TEMPLATES, validate_template_choice
from src.utils import job_tag
from src.utils.logger import get_logger

log = get_logger(__name__)

MAX_TRANSCRIPT_CHARS = 12_000

_PROMISE_GAP_SUFFIX = """

### STEP 6: PROMISE-GAP ANALYSIS
Identify where the title/thumbnail sets expectations the content does not fully satisfy.

Add this field to your JSON output (alongside the other fields):
  "promise_gap": {
    "gaps": ["specific promise in the title that the video never delivers"],
    "hidden_value": ["genuinely useful insight not signalled by the title"]
  }

Use empty arrays when nothing fits. This field is REQUIRED in every response."""


class EnrichmentUnavailableError(RuntimeError):
    pass


@dataclass
class Enrichment:
    category: str
    topic: str
    objective: str
    action_points_str: str  # pipe-joined
    tools_str: str  # pipe-joined
    tools_raw: list[dict]  # raw parsed list for brain feed
    market_data: str


def _build_prompt(
    title: str,
    transcript: str,
    template: str = "summary",
    freestyle_prompt: str | None = None,
) -> str:
    truncated = (
        transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[transcript truncated]"
        if len(transcript) > MAX_TRANSCRIPT_CHARS
        else transcript
    )
    if freestyle_prompt:
        extra = f"\n### FREESTYLE INSTRUCTIONS\n{freestyle_prompt}"
    else:
        extra = PROMPT_TEMPLATES.get(template, PROMPT_TEMPLATES["summary"]).extra_instructions
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

{extra}{_PROMISE_GAP_SUFFIX}
### TRANSCRIPT:
{truncated}"""


def _extract_json(raw: str) -> dict:
    from src.services.gemini import extract_json
    try:
        parsed = extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
        clean = re.sub(r"```\s*$", "", clean).strip()
        m = re.search(r"\{[\s\S]*\}", clean)
        text = m.group(0) if m else clean
        try:
            parsed = json.loads(repair_json(text))
        except (json.JSONDecodeError, ValueError) as exc:
            raise EnrichmentUnavailableError(f"Gemini returned unparseable JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise EnrichmentUnavailableError(
            f"Gemini returned non-object JSON: {type(parsed).__name__}"
        )
    return parsed


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


async def enrich(job: dict) -> tuple[Enrichment, dict | None, dict | None]:
    """Call Gemini with free→paid key fallback. Raises EnrichmentUnavailableError if both fail."""
    from src.services.gemini import gemini_client, GeminiUnavailableError

    title = job.get("title", "") or "Untitled"
    transcript = job.get("transcript", "") or ""
    template = job.get("template") or "summary"
    freestyle_prompt = job.get("freestyle_prompt")
    prompt = _build_prompt(title, transcript, template, freestyle_prompt)

    try:
        raw = await gemini_client.generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError as exc:
        raise EnrichmentUnavailableError(str(exc)) from exc
    data = _extract_json(raw)
    template_analysis = data.pop("template_analysis", None)
    promise_gap = data.pop("promise_gap", None)
    result = _parse_enrichment(data)
    log.info("enrichment_ok", category=result.category, topic=result.topic)
    return result, template_analysis, promise_gap


def _build_audio_prompt(title: str, template: str) -> str:
    extra = PROMPT_TEMPLATES.get(template, PROMPT_TEMPLATES["summary"]).extra_instructions
    return f"""Analyze the audio content of this video titled: "{title}".

Listen to the spoken content and produce:
1. A verbatim transcript of all spoken words.
2. The template-specific analysis.

Return ONLY a valid JSON object — no markdown fences, no commentary:

{{
  "transcript": "<verbatim spoken text>",
  "template_analysis": <template-specific object per the instructions below>
}}

{extra}"""


def _build_transcribe_prompt(title: str) -> str:
    return f"""Transcribe the audio content of this video titled: "{title}".

Return only the spoken text verbatim, with no additional commentary, timestamps, or metadata.
If the video has no speech or is completely silent, return an empty string."""


def _call_gemini_audio_sync(audio_b64: str, mime_type: str, prompt: str, api_key: str) -> str:
    import base64

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts = [
        types.Part.from_bytes(data=base64.b64decode(audio_b64), mime_type=mime_type),
        prompt,
    ]
    response = client.models.generate_content(model="gemini-2.5-flash", contents=parts)
    return response.text or ""


async def enrich_audio(job: dict, audio_b64: str, mime_type: str) -> tuple[dict | None, str]:
    """Fused Gemini call: inline audio + template prompt → (template_analysis, transcript_text).

    Free→paid key fallback. Raises EnrichmentUnavailableError if both keys fail.
    The returned transcript_text is the verbatim spoken content extracted alongside
    the template analysis — callers must not make a separate transcription call.
    """
    template = job.get("template") or "summary"
    title = job.get("title", "") or "Untitled"
    prompt = _build_audio_prompt(title, template)

    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            raw = await asyncio.to_thread(
                _call_gemini_audio_sync, audio_b64, mime_type, prompt, key
            )
            data = _extract_json(raw)
            log.info("enrichment_audio_ok", template=template)
            return data.get("template_analysis"), data.get("transcript", "")
        except Exception:
            log.warning("enrichment_audio_key_failed")

    raise EnrichmentUnavailableError("Both Gemini keys failed for audio enrichment")


async def transcribe_audio(audio_b64: str, mime_type: str, title: str = "") -> str:
    """Transcription-only Gemini call: inline audio → plain transcript text.

    Free→paid key fallback. Raises EnrichmentUnavailableError if both keys fail.
    Returns empty string when Gemini produces no output (silent/wordless clip).
    """
    prompt = _build_transcribe_prompt(title)

    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            raw = await asyncio.to_thread(
                _call_gemini_audio_sync, audio_b64, mime_type, prompt, key
            )
            log.info("transcription_ok")
            return raw.strip()
        except Exception:
            log.warning("transcription_key_failed")

    raise EnrichmentUnavailableError("Both Gemini keys failed for audio transcription")


def _escape_html(text: str) -> str:
    """Escape AI-generated text for Telegram's HTML parse mode.

    Only ``&``, ``<`` and ``>`` are special in HTML mode, so arbitrary content
    (underscores, asterisks, brackets, dots) is safe — unlike Markdown V1, where
    an unbalanced ``_``/``*`` would make Telegram reject the whole message (400).
    """
    return html.escape(str(text), quote=False)


def _escape_attr(url: str) -> str:
    """Escape a URL for use inside an HTML attribute (``href="..."``)."""
    return html.escape(str(url), quote=True)


def _text_section(analysis: dict, key: str, label: str) -> list[str]:
    """['', label, value] when *key* is present, else []."""
    if not analysis.get(key):
        return []
    return ["", label, _escape_html(analysis[key])]


def _bullet_section(analysis: dict, key: str, label: str, fmt: str = "• {}") -> list[str]:
    """['', label, '• v1', …] when *key* holds a list, else []."""
    if not analysis.get(key):
        return []
    return ["", label] + [fmt.format(_escape_html(v)) for v in analysis[key]]


def _format_method(analysis: dict) -> list[str]:
    lines = []
    for i, step in enumerate(analysis.get("steps", []), 1):
        action = _escape_html(step.get("action", ""))
        details = _escape_html(step.get("details", ""))
        lines.append(f"{i}. {action}: {details}")
    lines += _text_section(analysis, "common_mistakes", "⚠️ Common Mistakes")
    lines += _text_section(analysis, "pro_tips", "💡 Pro Tips")
    return lines


def _format_technical(analysis: dict) -> list[str]:
    lines = []
    if analysis.get("tech_stack"):
        lines += [
            "",
            "🔧 Tech Stack",
            ", ".join(_escape_html(t) for t in analysis["tech_stack"]),
        ]
    lines += _text_section(analysis, "architecture", "🏗 Architecture")
    lines += _text_section(analysis, "config_notes", "⚙️ Config")
    lines += _text_section(analysis, "debugging", "🐛 Debugging")
    return lines


def _format_review(analysis: dict) -> list[str]:
    lines = []
    for f in analysis.get("features", []):
        rating = f" ({_escape_html(f['rating'])})" if f.get("rating") else ""
        feature = _escape_html(f.get("feature", ""))
        desc = _escape_html(f.get("description", ""))
        lines.append(f"• {feature}{rating}: {desc}")
    lines += _bullet_section(analysis, "pros", "✅ Pros")
    lines += _bullet_section(analysis, "cons", "❌ Cons")
    lines += _text_section(analysis, "verdict", "🏆 Verdict")
    lines += _text_section(analysis, "price_value", "💰 Price/Value")
    return lines


def _format_narrative(analysis: dict) -> list[str]:
    lines = _text_section(analysis, "thesis", "💡 Thesis")
    lines += _bullet_section(analysis, "supporting_points", "📌 Supporting Points")
    lines += _bullet_section(analysis, "key_quotes", "💬 Key Quotes", fmt='"{}"')
    lines += _text_section(analysis, "conclusion", "🎯 Conclusion")
    return lines


_TEMPLATE_FORMATTERS = {
    "method": _format_method,
    "technical": _format_technical,
    "review": _format_review,
    "narrative": _format_narrative,
}


def _format_template_analysis(template: str, analysis: dict) -> str:
    lines = [f"\n📋 {template.capitalize()} Analysis"]
    formatter = _TEMPLATE_FORMATTERS.get(template)
    if formatter:
        lines += formatter(analysis)
    return "\n".join(lines)


def _build_enrichment_message(
    job: dict,
    enrichment: Enrichment,
    template_analysis: dict | None = None,
    promise_gap: dict | None = None,
) -> str:
    tag = f"job_{job['id'][-4:]}:"
    title = _escape_html(job.get("title", "Untitled"))
    drive_url = job.get("drive_url", "")

    tools_lines = []
    for t in enrichment.tools_raw:
        prefix = "$" if t.get("type") == "symbol" else f"[{_escape_html(t.get('type', 'tool'))}]"
        name = _escape_html(t["name"])
        if t.get("url"):
            # URL lives in the href attribute — safe even with underscores/dots.
            name = f'<a href="{_escape_attr(t["url"])}">{name}</a>'
        desc = _escape_html(t.get("description", ""))
        tools_lines.append(f"• {prefix} {name}: {desc}")

    action_lines = [
        f"• {_escape_html(ap)}" for ap in enrichment.action_points_str.split(" | ") if ap
    ]

    transcript_line = (
        f'📄 <a href="{_escape_attr(drive_url)}">Transcript</a>'
        if drive_url
        else "📄 Transcript (unavailable)"
    )

    parts = [
        f"{tag}",
        f"📺 {title}",
        f"🗃️ {_escape_html(enrichment.category)}",
        f"🎫 {_escape_html(enrichment.topic)}",
        "",
        "🎯 Objective",
        _escape_html(enrichment.objective),
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
    if template_analysis:
        template = job.get("template") or "summary"
        parts.append(_format_template_analysis(template, template_analysis))

    gaps = promise_gap.get("gaps", []) if promise_gap else []
    hidden = promise_gap.get("hidden_value", []) if promise_gap else []
    if gaps or hidden:
        parts.append("\n=====PROMISE=GAP=====")
        if gaps:
            parts.append("❌ Unfulfilled:")
            parts.extend(f"• {_escape_html(g)}" for g in gaps)
        if hidden:
            parts.append("💎 Hidden value:")
            parts.extend(f"• {_escape_html(h)}" for h in hidden)

    return "\n".join(parts)


# Telegram caps a single sendMessage text at 4096 UTF-16 code units. Stay below
# it with a margin (multi-unit emoji each count as 2).
TELEGRAM_TEXT_LIMIT = 3900


def _utf16_len(text: str) -> int:
    """Length in UTF-16 code units — the unit Telegram counts message length in."""
    return len(text.encode("utf-16-le")) // 2


def _split_message(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    """Split an HTML message into ``<=limit`` chunks at newline boundaries.

    Each ``<a>…</a>`` lives on a single line, so splitting between lines never
    cuts a tag — every chunk stays valid Telegram HTML. ``"\\n".join(chunks)``
    reproduces the input exactly. A lone line longer than ``limit`` (not expected
    for this content) is hard-split as a last resort.
    """
    if _utf16_len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if current and _utf16_len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
        while _utf16_len(current) > limit:  # pathological single long line
            cut = limit
            while _utf16_len(current[:cut]) > limit:
                cut -= 1
            chunks.append(current[:cut])
            current = current[cut:]
    if current:
        chunks.append(current)
    return chunks


async def run(job_id: str) -> None:
    """Phase 2 enrichment processor — called by worker for task='enrichment'."""
    job = await database.get_job(job_id)
    if not job:
        log.error("enrichment_job_not_found", job_id=job_id)
        return

    chat_id = job["chat_id"]
    tag = job_tag(job_id)

    if job.get("status") != "transcript_done":
        log.warning("enrichment_wrong_status", job_id=job_id, status=job.get("status"))

    await database.update_job_status(job_id, "enriching")
    await send_message(chat_id, f"{tag}\n🍪 now bakin' by Gemini")

    # Mismatch warning — explicit commands only
    if job.get("template_detection_method") == "explicit_command":
        transcript = job.get("transcript", "") or ""
        template = job.get("template") or "summary"
        warning = validate_template_choice(template, transcript)
        if warning:
            await send_message(chat_id, warning)
            await database.update_job_status(job_id, "enriching", validation_warning_sent=1)

    try:
        enrichment, template_analysis, promise_gap = await enrich(job)
    except EnrichmentUnavailableError as exc:
        title = job.get("title", "(unknown video)")
        await send_inline_keyboard(
            chat_id,
            f"{tag}\n⚠️ Gemini failed to enrich\nerror: {exc}\njob_title: {title}",
            buttons=[[{"text": "🔄 Retry", "callback_data": f"enrichment_retry:{job_id}"}]],
        )
        await database.update_job_status(job_id, "error")
        return

    now = datetime.now(timezone.utc).isoformat()
    await database.update_job_status(
        job_id,
        "done",
        ai_category=enrichment.category,
        ai_topic=enrichment.topic,
        ai_objective=enrichment.objective,
        ai_action_points=enrichment.action_points_str,
        ai_tools=enrichment.tools_str,
        ai_market_data=enrichment.market_data,
        template_analysis=json.dumps(template_analysis) if template_analysis else None,
        promise_gap=json.dumps(promise_gap) if promise_gap else None,
        completed_at=now,
    )

    msg = _build_enrichment_message(job, enrichment, template_analysis, promise_gap)
    for chunk in _split_message(msg):
        await send_message(chat_id, chunk, parse_mode="HTML")

    await send_inline_keyboard(
        chat_id,
        f"{tag}\nWhat's next?",
        buttons=[[{"text": "📐 Build Spec", "callback_data": f"prd_build_spec:{job_id}"}]],
    )

    log.info("enrichment_complete", job_id=job_id, category=enrichment.category)

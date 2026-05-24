from __future__ import annotations

import json
import re

from src.utils.logger import get_logger

log = get_logger(__name__)

_VISION_PROMPT = """You are a video content analyzer. Analyze all frames from this short-form video.

Return ONLY a valid JSON object — no markdown fences, no commentary:

{
  "main_frame_index": <integer: index of the most informative/representative frame>,
  "summary": "<2-3 sentence description — mention specific tools, products, or concepts shown>",
  "links": [
    {
      "url": "<exact or inferred full URL>",
      "label": "<short label for this resource>",
      "description": "<one-line description of what this links to>"
    }
  ]
}

Rules:
- main_frame_index: frame with the most visible text, code, or product information
- summary: specific — name the tools, products, and concepts explicitly
- links: extract any URLs, website names, app names, social handles visible in any frame; infer full URL from domain/brand
- If no links found: return "links": []
"""


def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


def _call_vision_sync(frames: list[dict], api_key: str) -> dict:
    import base64
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts: list = [_VISION_PROMPT] + [
        types.Part.from_bytes(data=base64.b64decode(f["base64"]), mime_type=f["mime_type"])
        for f in frames
    ]
    response = client.models.generate_content(model="gemini-2.5-flash", contents=parts)
    return _extract_json(response.text)


async def call_gemini_vision(frames: list[dict], free_key: str, paid_key: str) -> dict:
    """
    Call Gemini 2.5 Flash Vision with inline JPEG frames.
    Tries free_key first, then paid_key. Both fail → raises RuntimeError.
    Returns {main_frame_index, summary, links: [{url, label, description}]}.
    """
    import asyncio

    for key in [free_key, paid_key]:
        if not key:
            continue
        try:
            result = await asyncio.to_thread(_call_vision_sync, frames, key)
            log.info("gemini_vision_ok", links_count=len(result.get("links", [])))
            return result
        except Exception:
            log.warning("gemini_vision_key_failed")

    raise RuntimeError("Both Gemini API keys failed for Vision call")


async def resolve_tool_urls(tools: list[dict]) -> list[dict]:
    """Resolve canonical URLs for tool/product list via Gemini. Returns tools with 'url' key added."""
    import json
    import re as _re
    from src.services.gemini_client import gemini_client, GeminiUnavailableError

    if not tools:
        return tools
    lines = "\n".join(f"- [{t.get('type', 'tool')}] {t['name']}" for t in tools)
    prompt = (
        f"For each item in this list, provide the canonical homepage URL.\n"
        f"Well-known products (open-source libs, SaaS, frameworks, APIs) → canonical URL.\n"
        f"Stock tickers → https://finance.yahoo.com/quote/TICKER.\n"
        f"Concepts (HTTP Request, API Documentation, Curl Command) → null.\n"
        f"Return ONLY JSON array: [{{\"name\": \"...\", \"url\": \"https://...\" or null}}]\n\n"
        f"Items:\n{lines}"
    )
    try:
        raw = await gemini_client.generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError:
        log.error("gemini_resolve_urls_all_keys_failed")
        return [{**t, "url": None} for t in tools]
    clean = _re.sub(r"^```json\s*", "", raw, flags=_re.IGNORECASE)
    clean = _re.sub(r"```\s*$", "", clean).strip()
    m = _re.search(r"\[[\s\S]*\]", clean)
    try:
        resolved = json.loads(m.group(0) if m else clean)
    except Exception:
        log.error("gemini_resolve_urls_parse_failed")
        return [{**t, "url": None} for t in tools]
    url_map = {item["name"]: item.get("url") for item in resolved if "name" in item}
    result = [{**t, "url": url_map.get(t["name"])} for t in tools]
    log.info("gemini_resolve_urls_ok", count=len(result))
    return result

"""Unified Gemini service — free→paid key fallback for text, vision, photo, and embed."""

from __future__ import annotations

import asyncio
import base64
import json
import re

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class GeminiUnavailableError(Exception):
    """Raised when both free and paid Gemini keys fail."""


# ---------------------------------------------------------------------------
# Prompt constants
# ---------------------------------------------------------------------------

_VISION_PROMPT = """You are a video content analyzer. Analyze all frames from this short-form video.

Return ONLY a valid JSON object — no markdown fences, no commentary:

{
  "title": "<specific title, <=8 words, names visible tools/topic, never a creator handle>",
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
- title: specific, <=8 words, name the visible tools/products/topic, never use a creator handle
- main_frame_index: frame with the most visible text, code, or product information
- summary: specific — name the tools, products, and concepts explicitly
- links: extract any URLs, website names, app names, social handles visible in any frame; infer full URL from domain/brand
- If no links found: return "links": []
"""

_PHOTO_PROMPT = """You are an OCR-grounded link extractor. Read the image(s) and return only URLs or domains that are LITERALLY visible as text. Do NOT invent or infer a URL from a brand name, product name, app icon, or logo.

Return ONLY valid JSON — no markdown fences, no commentary:

{
  "summary": "<2-3 sentence description of what is shown in the image(s)>",
  "links": [
    {
      "url": "<full URL with scheme>",
      "label": "<short label for this resource>",
      "description": "<one-line description of what this links to>",
      "verbatim": "<EXACT substring you read from the image — must contain either a full URL, a domain with a '.' TLD (e.g. 'trustmrr.com'), or a social handle '@name' where the platform (instagram/tiktok/x/youtube/etc.) is also visible in the image>"
    }
  ]
}

Rules:
- A link is valid ONLY if you can quote a substring from the image proving the URL/domain/handle was actually rendered as text. That substring goes in "verbatim".
- Do NOT append a TLD (.com, .io, .ai, .app, …) to a brand or product name unless that TLD is actually shown next to it in the image. Example: if "ThreadCan" appears as a card label with no domain, do NOT return "threadcan.com".
- Do NOT list every company, app, or product shown — only those whose URL, domain, or handle is rendered as visible text.
- If you cannot quote a verbatim string that includes the domain or a recognized handle, omit the link entirely.
- If no links found: return "links": []
- summary: always describe what is shown, even when no links are found
"""


# ---------------------------------------------------------------------------
# Photo-filter helpers
# ---------------------------------------------------------------------------

_UI_CHROME_PATTERNS = [
    re.compile(r"\bfollowed by\b", re.IGNORECASE),
]

_HANDLE_PLATFORMS = {
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "twitter.com": "twitter",
    "x.com": "x",
    "youtube.com": "youtube",
}


def _domain_for_match(url: str) -> str:
    netloc = url.split("://", 1)[-1].split("/", 1)[0].lower().strip()
    return netloc.removeprefix("www.")


def _filter_grounded_links(links: list[dict], summary: str) -> list[dict]:
    """Drop links whose domain is not literally present in the model's verbatim quote (or summary)."""
    summary_lc = (summary or "").lower()
    kept: list[dict] = []
    dropped: list[dict] = []
    for link in links:
        url = (link.get("url") or "").strip()
        if not url:
            continue
        domain = _domain_for_match(url)
        if not domain or "." not in domain:
            dropped.append({"url": url, "reason": "no_domain"})
            continue
        verbatim_raw = link.get("verbatim")
        verbatim = verbatim_raw.lower() if isinstance(verbatim_raw, str) else ""
        if any(p.search(verbatim) for p in _UI_CHROME_PATTERNS):
            dropped.append({"url": url, "reason": "ui_chrome", "verbatim": verbatim_raw})
            continue
        platform = _HANDLE_PLATFORMS.get(domain)
        if platform and platform in verbatim and verbatim.lstrip().startswith("@"):
            kept.append(link)
            continue
        if domain in verbatim or domain in summary_lc:
            kept.append(link)
            continue
        dropped.append({"url": url, "reason": "ungrounded", "verbatim": verbatim_raw})
    if dropped:
        log.warning("gemini.photo_dropped_ungrounded", dropped=dropped, kept=len(kept))
    return kept


# ---------------------------------------------------------------------------
# Shared infrastructure — ONE fallback loop, ONE _call_sync, ONE extract_json
# ---------------------------------------------------------------------------


def extract_json(raw: str, *, root: str = "object") -> dict | list:
    """Strip markdown fences and parse a JSON object (default) or array."""
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    pattern = r"\{[\s\S]*\}" if root == "object" else r"\[[\s\S]*\]"
    m = re.search(pattern, clean)
    return json.loads(m.group(0) if m else clean)


def _call_sync(parts: object, *, api_key: str, model: str, schema: type | dict | None = None):
    """Sync generate_content call — run inside asyncio.to_thread by _call_with_fallback."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    if schema is not None:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        )
        return client.models.generate_content(model=model, contents=parts, config=config)
    return client.models.generate_content(model=model, contents=parts)


async def _call_with_fallback(fn, *args, log_ok: str, log_fail: str, **fn_kwargs):
    """Try GEMINI_FREE_API_KEY then GEMINI_PAID_API_KEY. Raises GeminiUnavailableError if both fail."""
    last_error: str | None = None
    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            result = await asyncio.to_thread(fn, *args, api_key=key, **fn_kwargs)
            log.info(log_ok)
            return result
        except Exception as exc:
            last_error = str(exc).splitlines()[0][:120]
            log.warning(log_fail, error=last_error)
    raise GeminiUnavailableError(last_error or "Both Gemini keys failed")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate(
    prompt: str,
    *,
    model: str,
    schema: type | dict | None = None,
) -> str:
    """Text generation: free→paid fallback. Raises GeminiUnavailableError on total failure."""
    response = await _call_with_fallback(
        _call_sync, prompt,
        model=model, schema=schema,
        log_ok="gemini.generate_ok",
        log_fail="gemini.generate_key_failed",
    )
    return response.text or ""


async def call_gemini_vision(frames: list[dict]) -> dict:
    """Analyze inline JPEG frames. Raises GeminiUnavailableError on total failure.

    frames: [{"base64": str, "mime_type": str}, ...]
    Returns {main_frame_index, summary, links: [{url, label, description}]}.
    """
    from google.genai import types

    parts: list = [_VISION_PROMPT] + [
        types.Part.from_bytes(data=base64.b64decode(f["base64"]), mime_type=f["mime_type"])
        for f in frames
    ]
    response = await _call_with_fallback(
        _call_sync, parts,
        model="gemini-2.5-flash",
        log_ok="gemini.vision_ok",
        log_fail="gemini.vision_key_failed",
    )
    return extract_json(response.text or "")


async def call_gemini_photo_links(
    images: list[dict],
    *,
    caption: str | None = None,
) -> dict:
    """Extract verbatim-grounded URLs from photos. Raises GeminiUnavailableError on total failure.

    images: [{"bytes": bytes, "mime_type": str}, ...]
    Returns {"summary": str, "links": [{url, label, description, verbatim}]}.
    """
    from google.genai import types

    parts: list = [_PHOTO_PROMPT]
    for img in images:
        parts.append(types.Part.from_bytes(data=img["bytes"], mime_type=img["mime_type"]))
    if caption:
        parts.append(f"User caption context: {caption}")

    response = await _call_with_fallback(
        _call_sync, parts,
        model="gemini-2.5-flash",
        log_ok="gemini.photo_ok",
        log_fail="gemini.photo_key_failed",
    )
    data = extract_json(response.text or "")
    raw_links = data.get("links", []) or []
    grounded = _filter_grounded_links(raw_links, data.get("summary", ""))
    data["links"] = grounded
    log.info("gemini.photo_links_filtered", kept=len(grounded), dropped=len(raw_links) - len(grounded))
    return data


async def resolve_tool_urls(tools: list[dict]) -> list[dict]:
    """Resolve canonical URLs for a tool/product list via Gemini. Returns tools with 'url' added."""
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
        raw = await generate(prompt, model="gemini-2.5-flash")
    except GeminiUnavailableError:
        log.error("gemini.resolve_urls_all_keys_failed")
        return [{**t, "url": None} for t in tools]
    try:
        resolved = extract_json(raw, root="array")
        if not isinstance(resolved, list):
            raise ValueError("expected JSON array")
    except Exception:
        log.error("gemini.resolve_urls_parse_failed")
        return [{**t, "url": None} for t in tools]
    url_map = {item["name"]: item.get("url") for item in resolved if "name" in item}
    result = [{**t, "url": url_map.get(t["name"])} for t in tools]
    log.info("gemini.resolve_urls_ok", count=len(result))
    return result


# ---------------------------------------------------------------------------
# Backward-compat: GeminiClient shim used by many callers
# ---------------------------------------------------------------------------


class GeminiClient:
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        schema: type | dict | None = None,
    ) -> str:
        return await generate(prompt, model=model, schema=schema)


gemini_client = GeminiClient()

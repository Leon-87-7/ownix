"""Gemini Vision for photo link extraction."""

from __future__ import annotations

import asyncio
import json
import re

from src.utils.logger import get_logger

log = get_logger(__name__)

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
        platform = _HANDLE_PLATFORMS.get(domain)
        if platform and platform in verbatim and verbatim.lstrip().startswith("@"):
            kept.append(link)
            continue
        if domain in verbatim or domain in summary_lc:
            kept.append(link)
            continue
        dropped.append({"url": url, "reason": "ungrounded", "verbatim": verbatim_raw})
    if dropped:
        log.warning("gemini_photo_dropped_ungrounded", dropped=dropped, kept=len(kept))
    return kept


def _extract_json(raw: str) -> dict:
    clean = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\s*$", "", clean).strip()
    m = re.search(r"\{[\s\S]*\}", clean)
    return json.loads(m.group(0) if m else clean)


def _call_photo_sync(images: list[dict], api_key: str, caption: str | None) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    parts: list = [_PHOTO_PROMPT]
    for img in images:
        parts.append(types.Part.from_bytes(data=img["bytes"], mime_type=img["mime_type"]))
    if caption:
        parts.append(f"User caption context: {caption}")
    response = client.models.generate_content(model="gemini-2.5-flash", contents=parts)
    return _extract_json(response.text or "")


async def call_gemini_photo_links(
    images: list[dict],
    free_key: str,
    paid_key: str,
    caption: str | None = None,
) -> dict:
    """
    images: [{"bytes": bytes, "mime_type": str}, ...]
    Returns {"summary": str, "links": [{url, label, description}]}
    Raises RuntimeError if both keys fail.
    """
    for key in [free_key, paid_key]:
        if not key:
            continue
        try:
            result = await asyncio.to_thread(_call_photo_sync, images, key, caption)
            raw_links = result.get("links", []) or []
            grounded = _filter_grounded_links(raw_links, result.get("summary", ""))
            result["links"] = grounded
            log.info(
                "gemini_photo_ok",
                links_count=len(grounded),
                dropped_count=len(raw_links) - len(grounded),
            )
            return result
        except Exception:
            log.warning("gemini_photo_key_failed")
    raise RuntimeError("Both Gemini API keys failed for photo links call")

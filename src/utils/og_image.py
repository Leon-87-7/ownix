"""og:image extraction — shared by the article processor and Brain link previews."""

from __future__ import annotations

import html
import re
from urllib.parse import urljoin, urlparse

from src.utils.public_html import fetch_public_html

_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r"""([:\w-]+)\s*=\s*(['"])(.*?)\2""", re.IGNORECASE | re.DOTALL)


def extract_og_image_url(markup: str, base_url: str | None = None) -> str | None:
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


async def fetch_og_image_url(url: str) -> str | None:
    result = await fetch_public_html(url)
    if result is None:
        return None
    return extract_og_image_url(result.html, result.final_url)

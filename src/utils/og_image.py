"""og:image extraction — shared by the article processor and Brain link previews."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from src.utils.public_html import fetch_public_html

ESSENTIAL_OG_KEYS = (
    "og:title",
    "og:description",
    "og:site_name",
    "og:type",
    "og:image",
    "twitter:card",
    "twitter:site",
)


class _MetaTagParser(HTMLParser):
    """Collects the Essential OG collection from <meta> start tags in one pass."""

    def __init__(self, base_url: str | None) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.found: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr_map = {name: (value or "").strip() for name, value in attrs}
        key = (attr_map.get("property") or attr_map.get("name") or "").lower()
        content = attr_map.get("content", "").strip()
        if key not in ESSENTIAL_OG_KEYS or not content or key in self.found:
            return
        if key == "og:image":
            resolved = urljoin(self.base_url, content) if self.base_url else content
            if urlparse(resolved).scheme not in ("http", "https"):
                return
            content = resolved
        self.found[key] = content


def extract_essential_og(markup: str, base_url: str | None = None) -> dict[str, str]:
    """Extract the Essential OG collection in one pass over meta tags."""
    parser = _MetaTagParser(base_url)
    parser.feed(markup)
    return parser.found


def flatten_essential_og(tags: dict[str, str]) -> str:
    return " · ".join(f"{key}: {tags[key]}" for key in ESSENTIAL_OG_KEYS if tags.get(key))


def extract_og_image_url(markup: str, base_url: str | None = None) -> str | None:
    """Extract og:image from an HTML document."""
    return extract_essential_og(markup, base_url).get("og:image")


async def fetch_og_image_url(url: str) -> str | None:
    result = await fetch_public_html(url)
    if result is None:
        return None
    return extract_og_image_url(result.html, result.final_url)

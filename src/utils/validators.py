"""URL routing and description-link extraction utilities."""

import re
import unicodedata
from typing import Literal
from urllib.parse import parse_qs, urlparse

Pipeline = Literal["short", "long", "rejected"]

_TIKTOK_VIDEO_PATH = re.compile(r"^/@[^/]+/video/\d+", re.IGNORECASE)


def detect_pipeline(url: str) -> Pipeline:
    """Return the pipeline a URL should be routed to.

    Short pipeline:
        - youtube.com/shorts/{id}
        - instagram.com/reel/{id}
        - tiktok.com/@{user}/video/{id}

    Long pipeline:
        - youtube.com/watch?v={id}
        - youtu.be/{id}

    Rejected (no job created):
        - instagram.com/p/{id} (carousel/photo posts)
        - anything else
    """
    if not isinstance(url, str) or not url.strip():
        return "rejected"

    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return "rejected"

    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if not host:
        return "rejected"

    # Short — YouTube Shorts
    if host.endswith("youtube.com") and path.startswith("/shorts/") and len(path) > len("/shorts/"):
        return "short"

    # Short — Instagram Reels (NOT /p/ carousels)
    if host.endswith("instagram.com") and path.startswith("/reel/"):
        return "short"

    # Short — TikTok user video paths
    if host.endswith("tiktok.com") and _TIKTOK_VIDEO_PATH.match(path):
        return "short"

    # Long — standard YouTube watch (must include ?v=<id>)
    if host.endswith("youtube.com") and path == "/watch":
        v = parse_qs(parsed.query).get("v", [""])[0]
        if v:
            return "long"

    # Long — youtu.be short links
    if host == "youtu.be" and len(path) > 1:
        return "long"

    return "rejected"


def is_video_url(text: str) -> bool:
    """True if the entire message text is a single URL the bot would accept."""
    return detect_pipeline(text) in {"short", "long"}


# ---------------------------------------------------------------------------
# Description-link extraction (PRD §7)
# ---------------------------------------------------------------------------

GENERIC_ROOTS = {
    "github.com", "claude.ai", "openai.com", "twitter.com", "x.com",
    "discord.gg", "discord.com", "linkedin.com", "youtube.com", "youtu.be",
    "patreon.com", "ko-fi.com", "buymeacoffee.com", "bit.ly", "t.co",
    "linktr.ee", "instagram.com", "facebook.com", "tiktok.com", "reddit.com",
}

PROMO_SUBDOMAINS = {"get", "try", "go", "link", "ref", "promo", "deal", "offers", "start"}

LABEL_KEYWORDS = {
    "free", "resource", "github", "repo", "guide", "apis", "markdown",
    "by", "+", "docs", "self", "hosted", "source",
}

_URL_RE = re.compile(r"https?://\S+")
_TRAILING_JUNK = re.compile(r"[.,;:!?)\"'​‌‍﻿]+$")


def _clean_url(raw: str) -> str:
    """Strip trailing punctuation and zero-width / non-ASCII junk."""
    cleaned = _TRAILING_JUNK.sub("", raw)
    return "".join(c for c in cleaned if unicodedata.category(c) not in ("Cf",))


def _is_generic(parsed) -> bool:
    """True when the URL should be filtered as a generic social/link root."""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path_segs = [s for s in (parsed.path or "").split("/") if s]

    if host not in GENERIC_ROOTS:
        return False
    # github.com bare root → filtered; github.com/anything → passes
    if host == "github.com":
        return len(path_segs) == 0
    # Other GENERIC_ROOTS: filter when path has fewer than 2 segments
    return len(path_segs) < 2


def _is_promo(parsed) -> bool:
    """True when the subdomain is a promo keyword and path has exactly 1 segment."""
    host = parsed.hostname or ""
    parts = host.split(".")
    subdomain = parts[0] if len(parts) > 2 else ""
    path_segs = [s for s in (parsed.path or "").split("/") if s]
    return subdomain.lower() in PROMO_SUBDOMAINS and len(path_segs) == 1


def _has_label_keyword(label: str) -> bool:
    label_lower = label.lower()
    return any(kw in label_lower for kw in LABEL_KEYWORDS)


def _is_github_path(parsed) -> bool:
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path_segs = [s for s in (parsed.path or "").split("/") if s]
    return host == "github.com" and len(path_segs) >= 1


def extract_description_links(description: str) -> list[dict]:
    """
    Extract meaningful links from a YouTube video description (PRD §7).
    Returns list[{"url": str, "label": str | None}].
    """
    if not description:
        return []

    lines = description.splitlines()
    # Map each URL to the line it appears on (for label extraction)
    url_to_line: dict[str, str] = {}
    for line in lines:
        for raw in _URL_RE.findall(line):
            url = _clean_url(raw)
            if url and url not in url_to_line:
                url_to_line[url] = line

    results: list[dict] = []
    for url, line in url_to_line.items():
        try:
            parsed = urlparse(url)
        except Exception:
            continue

        if _is_generic(parsed):
            continue
        if _is_promo(parsed):
            continue

        label = line.strip() or None
        is_github = _is_github_path(parsed)

        if not is_github and (label is None or not _has_label_keyword(label)):
            continue

        results.append({"url": url, "label": label})

    return results


def slugify(s: str) -> str:
    """lowercase, non-alnum → '_', strip leading/trailing '_', max 80 chars."""
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", s.lower()))[:80]

"""URL routing for the Telegram webhook.

Pipeline selection per PRD §3.3 — short videos use frame extraction; long videos use
transcript extraction; everything else is rejected with no job created.
"""

import re
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

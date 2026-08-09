"""URL routing and description-link extraction utilities."""

import re
import unicodedata
from typing import Literal
from urllib.parse import parse_qs, urlparse

Pipeline = Literal["short", "long", "unsized", "article", "repo", "document", "rejected"]

_UNSIZED_VIDEO_HOSTS = frozenset({"facebook.com", "x.com", "twitter.com"})

_TIKTOK_VIDEO_PATH = re.compile(r"^/@[^/]+/video/\d+", re.IGNORECASE)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str | None:
    """Return normalized email when it matches VIG's shared email policy."""
    normalized = email.strip().lower()
    if len(normalized) > 254:  # RFC 5321 §4.5.3.1.3 max total length
        return None
    return normalized if _EMAIL_RE.fullmatch(normalized) else None


_GITHUB_RESERVED_PATHS: frozenset[str] = frozenset(
    {
        "features",
        "pricing",
        "marketplace",
        "sponsors",
        "topics",
        "explore",
        "settings",
        "notifications",
        "codespaces",
        "login",
        "signup",
        "apps",
        "orgs",
        "about",
        "security",
        "trending",
        "readme",
    }
)

_REPO_HINT = (
    "If you meant a repository, the URL should look like https://github.com/<owner>/<repo>."
)

ARTICLE_DEFAULT_DOMAINS: frozenset[str] = frozenset(
    {
        "substack.com",
        "medium.com",
        "dev.to",
        "ghost.io",
        "hashnode.com",
        "freecodecamp.org",
        "css-tricks.com",
        "smashingmagazine.com",
        "stackoverflow.blog",
        "aws.amazon.com",
        "blog.cloudflare.com",
        "github.blog",
        "netflixtechblog.com",
        "engineering.fb.com",
        "engineering.linkedin.com",
    }
)

_ARTICLE_HINT = "If this is an article you'd like to track, try /allowlist <domain> first."

_DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


def _host_matches(host: str, target: str) -> bool:
    return host == target or host.endswith("." + target)


def is_valid_domain_name(domain: str) -> bool:
    normalized = domain.strip().lower().removeprefix("www.").rstrip(".")
    labels = normalized.split(".")
    return (
        len(labels) >= 2
        and len(normalized) <= 253
        and all(_DNS_LABEL_RE.fullmatch(label) for label in labels)
        and not labels[-1].isdigit()
    )


def detect_pipeline(
    url: str,
    extra_domains: frozenset[str] = frozenset(),
) -> Pipeline:
    """Return the pipeline a URL should be routed to.

    Short pipeline:
        - youtube.com/shorts/{id}
        - instagram.com/reel/{id}
        - tiktok.com/@{user}/video/{id}
        - vt.tiktok.com/{code} (TikTok's short-link redirect domain)

    Long pipeline:
        - youtube.com/watch?v={id}
        - youtu.be/{id}

    Unsized video pipeline:
        - facebook.com, x.com, or twitter.com (including subdomains)

    Article pipeline:
        - host in ARTICLE_DEFAULT_DOMAINS (or a subdomain thereof)
        - host in extra_domains (per-chat allowlist, caller-supplied)

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

    if parsed.scheme not in {"http", "https"}:
        return "rejected"

    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path or ""

    if not host:
        return "rejected"

    if _match_short(host, path):
        return "short"
    if _match_long(host, path, parsed.query):
        return "long"
    github = _match_github(host, path)
    if github is not None:
        return github
    # Document pipeline: route by extension only (.pdf). No arxiv host special-
    # casing at MVP (ADR-0023) — that returns when someone actually sends one.
    if path.lower().endswith(".pdf"):
        return "document"
    if any(_host_matches(host, video_host) for video_host in _UNSIZED_VIDEO_HOSTS):
        return "unsized"
    if _match_article(host, extra_domains):
        return "article"
    return "rejected"


def _match_short(host: str, path: str) -> bool:
    """YouTube Shorts, Instagram Reels (NOT /p/ carousels), TikTok user videos
    or short-link redirects (vt.tiktok.com)."""
    if (
        _host_matches(host, "youtube.com")
        and path.startswith("/shorts/")
        and len(path) > len("/shorts/")
    ):
        return True
    if _host_matches(host, "instagram.com") and path.startswith("/reel/"):
        return True
    if _host_matches(host, "tiktok.com") and _TIKTOK_VIDEO_PATH.match(path):
        return True
    # vt.tiktok.com links carry an opaque redirect code, not /@user/video/id —
    # same shape as youtu.be, so the same "non-empty path" check applies.
    return _host_matches(host, "vt.tiktok.com") and len(path) > 1


def _match_long(host: str, path: str, query: str) -> bool:
    """Standard YouTube watch (must include ?v=<id>) or youtu.be short links."""
    if _host_matches(host, "youtube.com") and path == "/watch":
        return bool(parse_qs(query).get("v", [""])[0])
    return host == "youtu.be" and len(path) > 1


def _match_github(host: str, path: str) -> Pipeline | None:
    """'repo', 'rejected' (gists / enterprise hosts / org-only), or None when not GitHub."""
    if host == "gist.github.com":
        return "rejected"
    if host.startswith("github.") and host != "github.com" and host != "github.blog":
        return "rejected"
    if host != "github.com":
        return None
    segments = [s for s in path.split("/") if s]
    if not segments or segments[0].lower() in _GITHUB_RESERVED_PATHS:
        return "rejected"
    if len(segments) < 2:
        return "rejected"  # org-only
    return "repo"


def _match_article(host: str, extra_domains: frozenset[str]) -> bool:
    """Default article domains plus the per-chat allowlist (subdomains included)."""
    all_article_domains = ARTICLE_DEFAULT_DOMAINS | extra_domains
    return any(_host_matches(host, d) for d in all_article_domains)


def normalize_repo_url(url: str) -> str:
    """Strip subpaths from a github.com URL, returning canonical https://github.com/{owner}/{repo}."""
    segments = [s for s in urlparse(url.strip()).path.split("/") if s]
    if len(segments) < 2:
        raise ValueError(f"Not a full owner/repo URL, cannot normalize as a repo URL: {url!r}")
    return f"https://github.com/{segments[0]}/{segments[1]}"


# A registrable TLD is alphabetic and at least two characters. Kills `e.g` and
# `v1.2.3` without a registry list.
_TLD_RE = re.compile(r"^[a-z]{2,}$", re.IGNORECASE)


def is_fetchable_url(url: str) -> bool:
    """True when *url* is an absolute http(s) URL with a real hostname.

    The minimum bar for direct-add link jobs (/addlink), which bypass
    detect_pipeline — keeps javascript:/data:/garbage strings out of the
    jobs table and the dashboard's <a href>.

    Internal whitespace is rejected outright: urlparse reads a hostname off the
    first token of "https://a.com https://b.com" and shoves the rest into
    ``path``, so a whitespace-joined blob of URLs used to pass as one URL.
    """
    stripped = url.strip()
    if not stripped or any(c.isspace() for c in stripped):
        return False
    try:
        parsed = urlparse(stripped)
    except ValueError:
        return False
    # .scheme is already lowercased by urlparse, so HTTPS:// is fine here.
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname or ""
    # ponytail: 2+ alphabetic TLD, no registry list — `file.txt` and `Node.js`
    # still coerce to URLs. Swap in a real TLD set only if junk rows show up.
    return is_valid_domain_name(host) and bool(_TLD_RE.fullmatch(host.rstrip(".").split(".")[-1]))


def coerce_url(token: str) -> str | None:
    """A pasted token → an absolute http(s) URL, or None if it isn't one.

    The single implementation of "is this a URL" behind every intake surface —
    the Ingest Link box, batch link paste and Telegram /addlink — so a bare
    domain works everywhere or nowhere. See CONTEXT.md "URL coercion".
    """
    token = token.strip()
    candidate = token if token.lower().startswith(("http://", "https://")) else f"https://{token}"
    return candidate if is_fetchable_url(candidate) else None


def is_video_url(text: str) -> bool:
    """True if text is a single video or article URL (excludes repo URLs)."""
    return detect_pipeline(text) in {"short", "long", "unsized", "article"}


# ---------------------------------------------------------------------------
# Description-link extraction (PRD §7)
# ---------------------------------------------------------------------------

GENERIC_ROOTS = {
    "github.com",
    "claude.ai",
    "openai.com",
    "twitter.com",
    "x.com",
    "discord.gg",
    "discord.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "patreon.com",
    "ko-fi.com",
    "buymeacoffee.com",
    "bit.ly",
    "t.co",
    "linktr.ee",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "reddit.com",
}

PROMO_SUBDOMAINS = {
    "get",
    "try",
    "go",
    "link",
    "ref",
    "promo",
    "deal",
    "offers",
    "start",
}

LABEL_KEYWORDS = {
    "free",
    "resource",
    "github",
    "repo",
    "guide",
    "apis",
    "markdown",
    "by",
    "+",
    "docs",
    "self",
    "hosted",
    "source",
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


def filter_vision_links(
    links: list[dict], extra_ignored: set[str] | frozenset[str] = frozenset()
) -> list[dict]:
    """Drop generic-root, promo, and user-ignored links; deduplicate by hostname+first-path-segment."""
    seen_prefix: set[str] = set()
    result = []
    for lnk in links:
        url = lnk.get("url") or ""
        try:
            parsed = urlparse(url)
        except Exception:
            continue
        if _is_generic(parsed) or _is_promo(parsed):
            continue
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if host in extra_ignored:
            continue
        segs = [s for s in (parsed.path or "").split("/") if s]
        prefix = f"{host}/{segs[0]}" if segs else host
        if prefix in seen_prefix:
            continue
        seen_prefix.add(prefix)
        result.append(lnk)
    return result


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


def slugify(s: str, max_len: int = 80) -> str:
    """lowercase, non-alnum → '_', strip leading/trailing '_', max max_len chars."""
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", s.lower()))[:max_len]


def sanitize_filename_chars(
    text: str, *, extra_chars: str = "", strip_extra: str = "", max_len: int = 80
) -> str:
    """Keep only alnum/space/hyphen/underscore (+ extra_chars), trim, cap length.

    Preserves case and spaces — unlike slugify(), this is for a readable filename
    stem, not a URL-safe slug. Returns '' when nothing survives; callers supply
    their own fallback.
    """
    pattern = r"[^a-zA-Z0-9 \-_" + re.escape(extra_chars) + r"]"
    cleaned = re.sub(pattern, "", text or "")
    if strip_extra:
        cleaned = cleaned.strip(strip_extra)
    return cleaned.strip()[:max_len]

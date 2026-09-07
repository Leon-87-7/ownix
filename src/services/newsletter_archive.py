"""Newsletter archive resolver — pure resolution, no writes (ADR-0060, PLAN.md §2).

Given whatever a user types — a "view in browser" issue link, an archive
root, or a sender email address — resolves it to a [[Watched newsletter]]'s
public archive: a feed where one exists, its archive page otherwise. This
module never touches the database; `POST /api/newsletter-digest/resolve`
(`src/api/newsletter_digest.py`) calls it directly, and the future
`POST /api/newsletter-digest` (#609) re-resolves again server-side rather than
trusting a client-supplied resolution.

Feed and archive share one fetch-and-extract path (`src.services.jina.fetch_html`)
and one acceptance rule — **at least 2 distinct issue links** — so no XML
parser is ever introduced for RSS/Atom feeds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from src.intake import rate_limit
from src.processors.email_digest import DigestLink, extract_digest_links
from src.services.jina import JinaFetchError, JinaOversizeError, fetch_html
from src.utils.logger import get_logger
from src.utils.public_html import is_public_url
from src.utils.validators import normalize_email

log = get_logger(__name__)

# Abuse controls (PLAN.md §2 / issue #608 acceptance criteria).
_MAX_PROBE_FETCHES = 4
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 10
_CACHE_TTL_SECONDS = 300.0
_MAX_RECENT_ISSUES = 10

_FEED_ALTERNATE_TYPES = {"application/rss+xml", "application/atom+xml"}
_FEED_SUFFIXES = ("feed.xml", "atom.xml", "feed", "rss")


class NewsletterResolutionError(Exception):
    """Raised when no public newsletter archive could be resolved for the input."""


@dataclass(frozen=True)
class RecentIssue:
    """One issue link discovered on a feed or archive page."""

    slug: str
    title: str
    url: str


@dataclass(frozen=True)
class NewsletterResolution:
    """Pure resolution result — no database identifiers, nothing persisted."""

    archive_url: str
    feed_url: str | None
    issue_path_prefix: str
    fetched_title: str
    recent_issues: list[RecentIssue]


# --------------------------------------------------------------------------
# Cache — normalized query -> resolution, short TTL, re-validated on every hit.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _CacheEntry:
    result: NewsletterResolution
    expires_at: float


_cache: dict[str, _CacheEntry] = {}


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def reset_cache() -> None:
    """Test-only: clear resolver cache state between test cases."""
    _cache.clear()


# --------------------------------------------------------------------------
# Abuse controls
# --------------------------------------------------------------------------


async def _is_public_url(url: str) -> bool:
    """Public-URL gate applied to every target before an `r.jina.ai/<url>`
    string is built. Delegates to the one shared rule in
    `src/utils/public_html.py` so the resolver, the poll worker and the digest
    processor cannot drift apart on what "public" means.
    """
    return await is_public_url(url)


def enforce_resolve_rate_limit(chat_id: int) -> None:
    """Per-chat_id rate limit on the resolve endpoint (raises HTTP 429)."""
    rate_limit.enforce(
        f"newsletter_resolve:{chat_id}",
        max_requests=_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=_RATE_LIMIT_WINDOW_SECONDS,
    )


# --------------------------------------------------------------------------
# Input parsing — URL vs. email, candidate archive roots
# --------------------------------------------------------------------------


def _looks_like_url(query: str) -> bool:
    return "://" in query


def _url_to_root(url: str) -> str:
    """Strip a query string and a trailing issue path, leaving the archive root.

    Real-world input is typically a "view in browser" link, e.g.
    `https://www.slothbytes.dev/p/next-js-16-3?utm_source=...` — any path at
    all is treated as an issue path and stripped back to the bare host root.
    """
    parts = urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    return urlunsplit((scheme, parts.netloc.lower(), "", "", ""))


def _email_candidate_roots(email: str) -> list[str]:
    """Probe order for a sender email: `[f"{local}.{root}", root, domain]`.

    `root` is the sender domain minus its leading label — e.g.
    `slothbytes@tx2.beehiiv.com` -> `beehiiv.com`, yielding the beehiiv mirror
    `slothbytes.beehiiv.com` as the first probe. Verified 3/3 against
    AlphaSignal, Sloth Bytes, and Import React (PLAN.md's evidence table).
    """
    local, _, domain = email.rpartition("@")
    root = domain.split(".", 1)[1] if "." in domain else domain
    hosts = [f"{local}.{root}", root, domain]
    seen: set[str] = set()
    roots: list[str] = []
    for host in hosts:
        if host in seen or not host:
            continue
        seen.add(host)
        roots.append(f"https://{host}")
    return roots


def _candidate_roots(query: str) -> list[str]:
    """Return candidate archive-root URLs to probe, in priority order."""
    stripped = query.strip()
    if not stripped:
        return []
    if _looks_like_url(stripped):
        return [_url_to_root(stripped)]
    email = normalize_email(stripped)
    if email:
        return _email_candidate_roots(email)
    # Not a URL, not an email — try it as a bare hostname.
    return [f"https://{stripped}"]


# --------------------------------------------------------------------------
# HTML extraction — small stdlib HTMLParser subclasses, no new dependency.
# --------------------------------------------------------------------------


class _HeadParser(HTMLParser):
    """Collects everything the resolver needs from one document in a single
    pass: `<title>`, the first alternate RSS/Atom `<link>`, and the canonical
    URL (`<link rel="canonical">`, else `<meta property="og:url">`).

    One parser rather than three because `_resolve_root` needs the title and
    the feed href off the *same* root HTML — separate parsers meant parsing
    that document twice.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.feed_href: str | None = None
        self.canonical: str | None = None
        self.og_url: str | None = None
        self._in_title = False
        self._title_done = False
        self._title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            if not self._title_done:
                self._in_title = True
            return
        attr_map = {name.lower(): (value or "").strip() for name, value in attrs}
        if tag == "link":
            rel = attr_map.get("rel", "").lower()
            href = attr_map.get("href")
            if not href:
                return
            if (
                rel == "alternate"
                and self.feed_href is None
                and attr_map.get("type", "").lower() in _FEED_ALTERNATE_TYPES
            ):
                self.feed_href = href
            elif rel == "canonical" and self.canonical is None:
                self.canonical = href
        elif tag == "meta" and self.og_url is None:
            key = (attr_map.get("property") or attr_map.get("name") or "").lower()
            if key == "og:url" and attr_map.get("content"):
                self.og_url = attr_map["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
            self._title_done = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self._title_parts).split())


def _parse_head(html: str) -> _HeadParser:
    parser = _HeadParser()
    parser.feed(html or "")
    return parser


def _extract_canonical(html: str, base_url: str) -> str | None:
    parsed = _parse_head(html)
    href = parsed.canonical or parsed.og_url
    return urljoin(base_url, href) if href else None


def _group_issue_links(
    links: list[DigestLink], base_url: str
) -> tuple[str, list[RecentIssue]] | None:
    """Group same-origin links by first path segment; keep the richest group.

    This is how `issue_path_prefix` is learned — `/p/` for beehiiv, `/news/`
    for AlphaSignal — with no provider allowlist. Accepts only when the
    winning group carries at least 2 distinct issue slugs; this is what
    correctly rejects beehiiv's `/feed`, which returns its HTML app shell
    (a 200 that carries no repeated dated-child path shape).
    """
    base_netloc = urlsplit(base_url).netloc.lower()
    groups: dict[str, dict[str, RecentIssue]] = {}
    for link in links:
        href = (link.href or "").strip()
        if not href or href.startswith("#"):
            continue
        resolved = urljoin(base_url, href)
        parts = urlsplit(resolved)
        if parts.scheme not in {"http", "https"} or parts.netloc.lower() != base_netloc:
            continue
        segments = [s for s in parts.path.split("/") if s]
        if len(segments) < 2:
            continue
        prefix_segment, slug = segments[0], segments[1]
        clean_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        bucket = groups.setdefault(prefix_segment, {})
        bucket.setdefault(slug, RecentIssue(slug=slug, title=link.text.strip(), url=clean_url))

    if not groups:
        return None
    best_prefix, best_bucket = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(best_bucket) < 2:
        return None
    return f"/{best_prefix}/", list(best_bucket.values())[:_MAX_RECENT_ISSUES]


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------


async def _try_feed(
    root_url: str, inline_feed_href: str | None, budget: int
) -> tuple[tuple[str, str, list[RecentIssue]] | None, int]:
    """Try feed candidates in priority order; first with >=2 issue links wins."""
    candidates: list[str] = []
    if inline_feed_href:
        candidates.append(urljoin(root_url, inline_feed_href))
    base = root_url.rstrip("/") + "/"
    candidates.extend(urljoin(base, suffix) for suffix in _FEED_SUFFIXES)

    for feed_url in candidates:
        if budget <= 0:
            break
        # The inline `<link rel="alternate">` href is publisher-controlled and may
        # be absolute to any host, so it gets the same pre-`r.jina.ai` public-URL
        # check as the root. The `_FEED_SUFFIXES` candidates are same-origin by
        # construction, but re-checking them is free and keeps one rule here.
        if not await _is_public_url(feed_url):
            log.info("newsletter_archive.feed_candidate_rejected", url=feed_url[:200])
            continue
        try:
            feed_html = await fetch_html(feed_url)
        except (JinaFetchError, JinaOversizeError) as exc:
            log.info("newsletter_archive.feed_probe_failed", url=feed_url[:200], error=str(exc)[:120])
            budget -= 1
            continue
        budget -= 1
        grouped = _group_issue_links(extract_digest_links(feed_html), feed_url)
        if grouped is not None:
            issue_path_prefix, issues = grouped
            return (feed_url, issue_path_prefix, issues), budget
    return None, budget


async def _canonicalize(issues: list[RecentIssue], fallback_root: str, budget: int) -> tuple[str, int]:
    """Fetch one issue page for `<link rel=canonical>` / `og:url`; derive the root from it.

    Canonicalization is a refinement, not a requirement: with no budget left,
    or no canonical hint on the page, the caller's own root stands.
    """
    if not issues or budget <= 0:
        return fallback_root, budget
    try:
        issue_html = await fetch_html(issues[0].url)
    except (JinaFetchError, JinaOversizeError):
        return fallback_root, budget - 1
    budget -= 1
    canonical = _extract_canonical(issue_html, issues[0].url)
    if canonical is None:
        return fallback_root, budget
    return _url_to_root(canonical), budget


async def _resolve_root(root_url: str, budget: int) -> tuple[NewsletterResolution | None, int]:
    if budget <= 0:
        return None, budget
    try:
        root_html = await fetch_html(root_url)
    except (JinaFetchError, JinaOversizeError) as exc:
        log.info("newsletter_archive.root_fetch_failed", url=root_url[:200], error=str(exc)[:120])
        return None, budget - 1
    budget -= 1

    # One parse of the root document for both the title and the inline feed
    # link, rather than one parser pass each.
    head = _parse_head(root_html)
    fetched_title = head.title

    feed_result, budget = await _try_feed(root_url, head.feed_href, budget)
    if feed_result is not None:
        feed_url, issue_path_prefix, issues = feed_result
        archive_url, budget = await _canonicalize(issues, root_url, budget)
        return (
            NewsletterResolution(
                archive_url=archive_url,
                feed_url=feed_url,
                issue_path_prefix=issue_path_prefix,
                fetched_title=fetched_title,
                recent_issues=issues,
            ),
            budget,
        )

    grouped = _group_issue_links(extract_digest_links(root_html), root_url)
    if grouped is None:
        return None, budget
    issue_path_prefix, issues = grouped
    archive_url, budget = await _canonicalize(issues, root_url, budget)
    return (
        NewsletterResolution(
            archive_url=archive_url,
            feed_url=None,
            issue_path_prefix=issue_path_prefix,
            fetched_title=fetched_title,
            recent_issues=issues,
        ),
        budget,
    )


async def resolve_newsletter_archive(query: str, *, chat_id: int) -> NewsletterResolution:
    """Resolve *query* (URL or email) to a newsletter's public archive.

    Pure resolution — performs no writes. Rate-limited per `chat_id`; results
    are cached by normalized query for a short TTL, and every cache hit is
    re-validated against the public-URL check before being served, so a
    resolution can never outlive that guard across the cache's lifetime.

    Raises :class:`NewsletterResolutionError` when nothing resolves.
    """
    enforce_resolve_rate_limit(chat_id)

    normalized = _normalize_query(query)
    if not normalized:
        raise NewsletterResolutionError("Enter a newsletter URL or sender email")

    cached = _cache.get(normalized)
    if cached is not None:
        # Re-validate *every* URL the cached result would hand onward, not just
        # the archive root — `feed_url` is what the poller actually fetches.
        cached_urls = [cached.result.archive_url]
        if cached.result.feed_url:
            cached_urls.append(cached.result.feed_url)
        still_public = cached.expires_at > time.monotonic() and all(
            [await _is_public_url(url) for url in cached_urls]
        )
        if still_public:
            return cached.result
        _cache.pop(normalized, None)

    roots = _candidate_roots(query)
    if not roots:
        raise NewsletterResolutionError("Enter a newsletter URL or sender email")

    budget = _MAX_PROBE_FETCHES
    for root_url in roots:
        if budget <= 0:
            break
        if not await _is_public_url(root_url):
            log.info("newsletter_archive.root_rejected", url=root_url[:200])
            continue
        result, budget = await _resolve_root(root_url, budget)
        if result is not None:
            _cache[normalized] = _CacheEntry(result=result, expires_at=time.monotonic() + _CACHE_TTL_SECONDS)
            return result

    raise NewsletterResolutionError("Could not find a public newsletter archive for that input")

"""Unit tests for src/services/newsletter_archive.py — pure archive resolution.

Covers PLAN.md §2 / issue #608's acceptance criteria: resolver abuse limits
(scheme, private host, probe cap, rate limit), cache re-validation,
feed-vs-scrape selection (including beehiiv's "200 but an HTML app shell"
`/feed`), and `issue_path_prefix` discovery against `/p/` and `/news/`
fixtures.
"""

from __future__ import annotations

import pytest

from src.intake import rate_limit
from src.services import newsletter_archive as archive
from src.services.jina import JinaFetchError


@pytest.fixture(autouse=True)
def _reset_state():
    rate_limit.reset()
    archive.reset_cache()
    yield
    rate_limit.reset()
    archive.reset_cache()


class _FakeLoop:
    def __init__(self, addrinfo_result: list[tuple]) -> None:
        self._result = addrinfo_result

    async def getaddrinfo(self, host, port):
        return self._result


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch):
    """Default every hostname to resolve to a public address, so resolution
    tests don't depend on real DNS — individual tests override this to
    exercise the private-address rejection path."""
    # The public-URL rule now lives in src/utils/public_html.py and the
    # resolver delegates to it, so DNS is patched there.
    from src.utils import public_html

    monkeypatch.setattr(
        public_html.asyncio,
        "get_running_loop",
        lambda: _FakeLoop([(2, 1, 6, "", ("93.184.216.34", 0))]),
    )


def _fetch_html_stub(routes: dict[str, str]):
    """Return a fake `fetch_html` plus a call-count list, keyed by exact URL."""

    calls: list[str] = []

    async def _fake(url: str, *, client=None) -> str:
        calls.append(url)
        if url not in routes:
            raise JinaFetchError(404)
        return routes[url]

    return _fake, calls


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def test_url_to_root_strips_query_and_issue_path():
    root = archive._url_to_root(
        "https://www.slothbytes.dev/p/next-js-16-3?utm_source=newsletter"
    )
    assert root == "https://www.slothbytes.dev"


def test_url_to_root_leaves_bare_root_unchanged():
    assert archive._url_to_root("https://alphasignal.ai") == "https://alphasignal.ai"


@pytest.mark.parametrize(
    "email,expected",
    [
        (
            "news@alphasignal.ai",
            ["https://news.ai", "https://ai", "https://alphasignal.ai"],
        ),
        (
            "slothbytes@tx2.beehiiv.com",
            [
                "https://slothbytes.beehiiv.com",
                "https://beehiiv.com",
                "https://tx2.beehiiv.com",
            ],
        ),
        (
            "importreact@mail.beehiiv.com",
            [
                "https://importreact.beehiiv.com",
                "https://beehiiv.com",
                "https://mail.beehiiv.com",
            ],
        ),
    ],
)
def test_candidate_roots_matches_verified_email_examples(email, expected):
    assert archive._candidate_roots(email) == expected


def test_candidate_roots_accepts_a_bare_hostname():
    """Neither a URL nor an email — `alphasignal.ai` typed without a scheme is
    a plausible thing to paste, so it is probed as a host rather than rejected.
    Unspecified in PLAN.md §2; kept deliberately and pinned here."""
    assert archive._candidate_roots("alphasignal.ai") == ["https://alphasignal.ai"]


def test_candidate_roots_rejects_empty_input():
    assert archive._candidate_roots("   ") == []


def test_candidate_roots_for_url_input_is_single_root():
    roots = archive._candidate_roots("https://www.slothbytes.dev/p/some-issue")
    assert roots == ["https://www.slothbytes.dev"]


# ---------------------------------------------------------------------------
# Abuse controls: pure public-URL validator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_public_url_rejects_non_http_scheme():
    assert await archive._is_public_url("ftp://example.com") is False


@pytest.mark.asyncio
async def test_is_public_url_rejects_missing_hostname():
    assert await archive._is_public_url("https://") is False


@pytest.mark.asyncio
async def test_is_public_url_rejects_private_address(monkeypatch):
    from src.utils import public_html

    monkeypatch.setattr(
        public_html.asyncio,
        "get_running_loop",
        lambda: _FakeLoop([(2, 1, 6, "", ("127.0.0.1", 0))]),
    )
    assert await archive._is_public_url("https://internal.example") is False


@pytest.mark.asyncio
async def test_is_public_url_rejects_non_default_port(monkeypatch):
    """The shared rule also blocks non-default ports, which the resolver's own
    earlier copy did not — `http://internal-host:6379/p/x` is the shape a
    hostile publisher page would use to aim the proxy at a service port."""
    assert await archive._is_public_url("http://example.com:6379/p/x") is False


@pytest.mark.asyncio
async def test_is_public_url_accepts_globally_routable_address():
    # The autouse `_public_dns` fixture already resolves every host publicly.
    assert await archive._is_public_url("https://example.com") is True


# ---------------------------------------------------------------------------
# issue_path_prefix discovery
# ---------------------------------------------------------------------------

_ALPHASIGNAL_ROOT_HTML = """
<html><head>
<title>AlphaSignal</title>
<link rel="alternate" type="application/rss+xml" href="/feed.xml">
</head><body>no archive listing here, feed only</body></html>
"""

_ALPHASIGNAL_FEED_HTML = """
<html><body>
<h3><a href="/news/gpt-6-launch">GPT-6 launches</a></h3>
<h3><a href="/news/new-agent-framework">New agent framework</a></h3>
<h3><a href="/news/rag-tips">RAG tips</a></h3>
</body></html>
"""

_BEEHIIV_ROOT_HTML = """
<html><head><title>Sloth Bytes</title></head><body>
<a href="/p/next-js-16-3">Next.js 16.3</a>
<a href="/p/react-compiler-ga">React Compiler is GA</a>
<a href="/pricing">Pricing</a>
</body></html>
"""

_BEEHIIV_FEED_SHELL_HTML = """
<html><head><title>App</title></head><body>
<a href="/pricing">Pricing</a>
<a href="/about">About</a>
</body></html>
"""


@pytest.mark.asyncio
async def test_resolve_prefers_feed_and_discovers_news_prefix(monkeypatch):
    fake_fetch, calls = _fetch_html_stub(
        {
            "https://alphasignal.ai": _ALPHASIGNAL_ROOT_HTML,
            "https://alphasignal.ai/feed.xml": _ALPHASIGNAL_FEED_HTML,
        }
    )
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)

    result = await archive.resolve_newsletter_archive("https://alphasignal.ai", chat_id=1)

    assert result.feed_url == "https://alphasignal.ai/feed.xml"
    assert result.issue_path_prefix == "/news/"
    assert {issue.slug for issue in result.recent_issues} == {
        "gpt-6-launch",
        "new-agent-framework",
        "rag-tips",
    }
    assert result.fetched_title == "AlphaSignal"


@pytest.mark.asyncio
async def test_resolve_rejects_inline_feed_link_pointing_at_a_private_host(monkeypatch):
    """An inline `<link rel="alternate">` href is publisher-controlled and may be
    absolute to any host, so it must pass the same public-URL check as the root
    before `r.jina.ai/<url>` is built for it."""
    root_html = (
        '<html><head><title>Evil</title>'
        '<link rel="alternate" type="application/rss+xml" href="http://169.254.169.254/latest/meta-data">'
        "</head><body>"
        '<a href="/p/one">One</a><a href="/p/two">Two</a>'
        "</body></html>"
    )
    fake_fetch, calls = _fetch_html_stub({"https://evil.example": root_html})

    async def _public_except_link_local(url: str) -> bool:
        return "169.254.169.254" not in url

    monkeypatch.setattr(archive, "fetch_html", fake_fetch)
    monkeypatch.setattr(archive, "_is_public_url", _public_except_link_local)

    result = await archive.resolve_newsletter_archive("https://evil.example", chat_id=1)

    # The private-host feed candidate was never fetched; resolution fell through
    # to scraping the archive instead.
    assert "http://169.254.169.254/latest/meta-data" not in calls
    assert result.feed_url is None
    assert result.issue_path_prefix == "/p/"


@pytest.mark.asyncio
async def test_resolve_rejects_beehiiv_feed_shell_and_falls_back_to_scrape(monkeypatch):
    fake_fetch, calls = _fetch_html_stub(
        {
            "https://www.slothbytes.dev": _BEEHIIV_ROOT_HTML,
            "https://www.slothbytes.dev/feed.xml": _BEEHIIV_FEED_SHELL_HTML,
            "https://www.slothbytes.dev/atom.xml": _BEEHIIV_FEED_SHELL_HTML,
            "https://www.slothbytes.dev/feed": _BEEHIIV_FEED_SHELL_HTML,
            "https://www.slothbytes.dev/rss": _BEEHIIV_FEED_SHELL_HTML,
            # No canonical/og:url hint here — canonicalization is a no-op and
            # the scraped root stands as the archive_url.
            "https://www.slothbytes.dev/p/next-js-16-3": "<html><head><title>Next.js 16.3</title></head></html>",
        }
    )
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)
    monkeypatch.setattr(archive, "_MAX_PROBE_FETCHES", 10)  # enough budget to try all 4 feed suffixes

    result = await archive.resolve_newsletter_archive("https://www.slothbytes.dev", chat_id=1)

    assert result.feed_url is None
    assert result.issue_path_prefix == "/p/"
    assert {issue.slug for issue in result.recent_issues} == {
        "next-js-16-3",
        "react-compiler-ga",
    }
    assert result.archive_url == "https://www.slothbytes.dev"
    # Root fetch + 4 feed-suffix probes (all rejected for too few issue
    # links) + 1 canonicalization fetch of the first scraped issue.
    assert calls.count("https://www.slothbytes.dev") == 1
    assert len(calls) == 6


@pytest.mark.asyncio
async def test_resolve_canonicalizes_beehiiv_mirror_to_custom_domain(monkeypatch):
    issue_html = """
    <html><head><link rel="canonical" href="https://www.slothbytes.dev/p/next-js-16-3"></head></html>
    """
    fake_fetch, calls = _fetch_html_stub(
        {
            "https://slothbytes.beehiiv.com": _BEEHIIV_ROOT_HTML,
            "https://slothbytes.beehiiv.com/feed.xml": _BEEHIIV_FEED_SHELL_HTML,
            "https://slothbytes.beehiiv.com/atom.xml": _BEEHIIV_FEED_SHELL_HTML,
            "https://slothbytes.beehiiv.com/feed": _BEEHIIV_FEED_SHELL_HTML,
            "https://slothbytes.beehiiv.com/rss": _BEEHIIV_FEED_SHELL_HTML,
            "https://slothbytes.beehiiv.com/p/next-js-16-3": issue_html,
        }
    )
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)
    monkeypatch.setattr(archive, "_MAX_PROBE_FETCHES", 6)

    result = await archive.resolve_newsletter_archive(
        "slothbytes@tx2.beehiiv.com", chat_id=1
    )

    assert result.archive_url == "https://www.slothbytes.dev"


@pytest.mark.asyncio
async def test_resolve_raises_when_nothing_found(monkeypatch):
    async def always_404(url: str, *, client=None) -> str:
        raise JinaFetchError(404)

    monkeypatch.setattr(archive, "fetch_html", always_404)

    with pytest.raises(archive.NewsletterResolutionError):
        await archive.resolve_newsletter_archive("https://nobody-publishes-here.example", chat_id=1)


@pytest.mark.asyncio
async def test_resolve_enforces_max_probe_fetches(monkeypatch):
    root_html_no_links = "<html><head><title>Nothing here</title></head><body></body></html>"
    fake_fetch, calls = _fetch_html_stub({"https://example.com": root_html_no_links})
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)

    with pytest.raises(archive.NewsletterResolutionError):
        await archive.resolve_newsletter_archive("https://example.com", chat_id=1)

    # 1 root fetch + 3 of the 4 feed-suffix probes exhausts the 4-fetch budget
    # before the 4th suffix is tried.
    assert len(calls) == archive._MAX_PROBE_FETCHES


@pytest.mark.asyncio
async def test_resolve_enforces_per_chat_rate_limit(monkeypatch):
    async def always_fail(url: str, *, client=None) -> str:
        raise JinaFetchError(404)

    monkeypatch.setattr(archive, "fetch_html", always_fail)
    monkeypatch.setattr(archive, "_RATE_LIMIT_MAX_REQUESTS", 2)

    for _ in range(2):
        with pytest.raises(archive.NewsletterResolutionError):
            await archive.resolve_newsletter_archive("https://example.com", chat_id=42)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await archive.resolve_newsletter_archive("https://example.com", chat_id=42)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_resolve_caches_by_normalized_query(monkeypatch):
    fake_fetch, calls = _fetch_html_stub(
        {
            "https://alphasignal.ai": _ALPHASIGNAL_ROOT_HTML,
            "https://alphasignal.ai/feed.xml": _ALPHASIGNAL_FEED_HTML,
        }
    )
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)

    first = await archive.resolve_newsletter_archive("  HTTPS://ALPHASIGNAL.AI  ", chat_id=1)
    fetches_after_first = len(calls)
    second = await archive.resolve_newsletter_archive("https://alphasignal.ai", chat_id=1)

    assert first.archive_url == second.archive_url
    assert len(calls) == fetches_after_first  # no new fetches on the cache hit


@pytest.mark.asyncio
async def test_resolve_cache_hit_is_revalidated_against_public_url_check(monkeypatch):
    fake_fetch, calls = _fetch_html_stub(
        {
            "https://alphasignal.ai": _ALPHASIGNAL_ROOT_HTML,
            "https://alphasignal.ai/feed.xml": _ALPHASIGNAL_FEED_HTML,
        }
    )
    monkeypatch.setattr(archive, "fetch_html", fake_fetch)

    await archive.resolve_newsletter_archive("https://alphasignal.ai", chat_id=1)
    assert len(calls) > 0

    async def now_private(url: str) -> bool:
        return False

    monkeypatch.setattr(archive, "_is_public_url", now_private)

    with pytest.raises(archive.NewsletterResolutionError):
        await archive.resolve_newsletter_archive("https://alphasignal.ai", chat_id=1)


# ---------------------------------------------------------------------------
# _group_issue_links
# ---------------------------------------------------------------------------


def test_group_issue_links_requires_at_least_two_distinct_slugs():
    from src.processors.email_digest import DigestLink

    links = [DigestLink(href="/p/only-one", text="Only one")]
    assert archive._group_issue_links(links, "https://example.com") is None


def test_group_issue_links_ignores_cross_origin_links():
    from src.processors.email_digest import DigestLink

    links = [
        DigestLink(href="https://other.example/p/a", text="A"),
        DigestLink(href="https://other.example/p/b", text="B"),
    ]
    assert archive._group_issue_links(links, "https://example.com") is None


def test_group_issue_links_picks_richest_prefix_group():
    from src.processors.email_digest import DigestLink

    links = [
        DigestLink(href="/p/slug-a", text="A"),
        DigestLink(href="/p/slug-b", text="B"),
        DigestLink(href="/p/slug-c", text="C"),
        DigestLink(href="/help/faq", text="FAQ"),
    ]
    grouped = archive._group_issue_links(links, "https://example.com")
    assert grouped is not None
    prefix, issues = grouped
    assert prefix == "/p/"
    assert len(issues) == 3

import pytest

from src.utils.validators import detect_pipeline, extract_description_links, is_video_url, slugify


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/papers/whitepaper.pdf",
        "https://arxiv.org/pdf/2401.00001v1.pdf",
        "https://host.tld/Doc.PDF",
        "https://example.com/a.pdf?download=1",
    ],
)
def test_document_pipeline(url: str) -> None:
    assert detect_pipeline(url) == "document"


def test_non_pdf_article_url_unaffected() -> None:
    assert detect_pipeline("https://medium.com/@x/post") == "article"


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/shorts/abc123",
        "https://www.youtube.com/shorts/abc123",
        "https://m.youtube.com/shorts/abc123",
        "https://youtube.com/shorts/abc123?si=xyz",
        "https://instagram.com/reel/DVNolBNE6vV/",
        "https://www.instagram.com/reel/DVNolBNE6vV/?igsh=a2ZodGgxOXN4Ynp3",
        "https://tiktok.com/@implementationai/video/7234567890123456789",
        "https://www.tiktok.com/@some.user/video/1234567890",
    ],
)
def test_short_pipeline(url: str) -> None:
    assert detect_pipeline(url) == "short"


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com/watch?v=abc123",
        "https://www.youtube.com/watch?v=qZkX_gIlwsY&si=itIa0Odc7jdqCDh7",
        "https://m.youtube.com/watch?v=abc123",
        "https://youtu.be/qZkX_gIlwsY",
        "https://youtu.be/4bfKyZ7hbsU?si=msGtIDZ4Cuqxgz17",
    ],
)
def test_long_pipeline(url: str) -> None:
    assert detect_pipeline(url) == "long"


@pytest.mark.parametrize(
    "url",
    [
        # Instagram non-reel paths
        "https://instagram.com/p/DV12345/",
        "https://www.instagram.com/p/abc/?igsh=xyz",
        "https://instagram.com/stories/user/12345",
        # YouTube non-video paths
        "https://youtube.com/",
        "https://youtube.com/shorts/",
        "https://youtube.com/watch",  # missing ?v= → rejected per PRD §3.3
        "https://youtube.com/watch?foo=bar",  # query without v= → rejected
        "https://youtube.com/channel/UC123",
        # TikTok non-video paths
        "https://tiktok.com/",
        "https://tiktok.com/@user",
        "https://tiktok.com/discover",
        # Other platforms
        "https://twitter.com/x/status/123",
        "https://example.com/video",
        "https://vimeo.com/123",
        # Non-URLs and malformed
        "",
        "   ",
        "not a url",
        "javascript:alert(1)",
        "ftp://example.com/file",
    ],
)
def test_rejected(url: str) -> None:
    assert detect_pipeline(url) == "rejected"


def test_youtu_be_requires_path() -> None:
    assert detect_pipeline("https://youtu.be/") == "rejected"
    assert detect_pipeline("https://youtu.be") == "rejected"


def test_youtube_shorts_requires_id() -> None:
    assert detect_pipeline("https://youtube.com/shorts/") == "rejected"


def test_tiktok_requires_at_and_video() -> None:
    assert detect_pipeline("https://tiktok.com/@user/foo/123") == "rejected"
    assert detect_pipeline("https://tiktok.com/video/123") == "rejected"


def test_non_string_inputs() -> None:
    assert detect_pipeline(None) == "rejected"  # type: ignore[arg-type]
    assert detect_pipeline(123) == "rejected"  # type: ignore[arg-type]


def test_is_video_url() -> None:
    assert is_video_url("https://youtu.be/abc123") is True
    assert is_video_url("https://instagram.com/reel/xyz/") is True
    assert is_video_url("https://example.com") is False
    assert is_video_url("not a url") is False


# ---------------------------------------------------------------------------
# extract_description_links
# ---------------------------------------------------------------------------

def test_extract_description_links_generic_roots_bare() -> None:
    desc = "Follow me on GitHub: https://github.com"
    results = extract_description_links(desc)
    urls = [r["url"] for r in results]
    assert "https://github.com" not in urls


def test_extract_description_links_github_repo_passes() -> None:
    desc = "Source repo: https://github.com/user/myrepo — check the source"
    results = extract_description_links(desc)
    urls = [r["url"] for r in results]
    assert any("github.com/user/myrepo" in u for u in urls)


def test_extract_description_links_promo_subdomain() -> None:
    desc = "Try for free: https://get.example.com/start"
    results = extract_description_links(desc)
    urls = [r["url"] for r in results]
    assert "https://get.example.com/start" not in urls


def test_extract_description_links_label_keyword() -> None:
    desc = "📚 docs: https://docs.example.com/guide"
    results = extract_description_links(desc)
    urls = [r["url"] for r in results]
    assert any("docs.example.com" in u for u in urls)


def test_extract_description_links_empty() -> None:
    assert extract_description_links("") == []
    assert extract_description_links("No links here, just text.") == []


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

def test_slugify_basic() -> None:
    assert slugify("Hello World") == "hello_world"


def test_slugify_unicode() -> None:
    result = slugify("Héllo Wörld")
    # unicode chars get folded to underscores
    assert re.match(r"^[a-z0-9_]+$", result)


def test_slugify_empty() -> None:
    assert slugify("") == ""


def test_slugify_all_special() -> None:
    assert slugify("!@#$%^&*()") == ""


def test_slugify_max_length() -> None:
    long_title = "a" * 100
    assert len(slugify(long_title)) == 80


import re  # noqa: E402 — imported here to avoid top-level shadowing in this test module


# ---------------------------------------------------------------------------
# ARTICLE_DEFAULT_DOMAINS + rejection hint (issue #61)
# ---------------------------------------------------------------------------

from src.utils.validators import ARTICLE_DEFAULT_DOMAINS, _ARTICLE_HINT


def test_article_default_domains_is_frozenset() -> None:
    assert isinstance(ARTICLE_DEFAULT_DOMAINS, frozenset)


def test_article_default_domains_contains_named_platforms() -> None:
    expected = {
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
    assert expected <= ARTICLE_DEFAULT_DOMAINS


def test_article_hint_verbatim_in_module() -> None:
    assert "If this is an article you'd like to track, try /allowlist <domain> first." in _ARTICLE_HINT


# ---------------------------------------------------------------------------
# GitHub repo routing (issue #66)
# ---------------------------------------------------------------------------

from src.utils.validators import normalize_repo_url, _REPO_HINT, _GITHUB_RESERVED_PATHS


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/anthropics/claude-code",
        "https://www.github.com/anthropics/claude-code",
        "https://github.com/anthropics/claude-code/blob/main/README.md",
        "https://github.com/anthropics/claude-code/tree/main/src",
        "https://github.com/anthropics/claude-code/issues/123",
        "https://github.com/anthropics/claude-code/pulls",
        "https://github.com/owner/repo/wiki",
    ],
)
def test_repo_pipeline(url: str) -> None:
    assert detect_pipeline(url) == "repo"


@pytest.mark.parametrize(
    "url",
    [
        # Org-only (no repo segment)
        "https://github.com/anthropics",
        "https://github.com/anthropics/",
        # Reserved first-path segments
        "https://github.com/pricing",
        "https://github.com/features",
        "https://github.com/marketplace",
        "https://github.com/login",
        "https://github.com/trending",
        # Gist
        "https://gist.github.com/anyone/abc123",
        # Enterprise GitHub
        "https://github.mycompany.com/owner/repo",
        # Bare github.com root
        "https://github.com",
        "https://github.com/",
    ],
)
def test_github_rejected(url: str) -> None:
    assert detect_pipeline(url) == "rejected"


def test_repo_reserved_paths_case_insensitive() -> None:
    assert detect_pipeline("https://github.com/PRICING") == "rejected"
    assert detect_pipeline("https://github.com/Features") == "rejected"


def test_normalize_repo_url_strips_subpath() -> None:
    assert normalize_repo_url(
        "https://github.com/anthropics/claude-code/blob/main/README.md"
    ) == "https://github.com/anthropics/claude-code"


def test_normalize_repo_url_bare() -> None:
    assert normalize_repo_url(
        "https://github.com/owner/repo"
    ) == "https://github.com/owner/repo"


def test_repo_hint_constant() -> None:
    assert "github.com/<owner>/<repo>" in _REPO_HINT


def test_github_reserved_paths_contains_blocklist() -> None:
    for path in ("pricing", "features", "marketplace", "login", "trending"):
        assert path in _GITHUB_RESERVED_PATHS

import pytest

from src.utils.validators import detect_pipeline, extract_description_links, is_video_url, slugify


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

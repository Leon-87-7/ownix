"""Unit tests for src/utils/markdown.py formatting helpers."""

from __future__ import annotations

import pytest

from src.utils.markdown import (
    _humanize_age,
    build_enriched_links_message,
    build_plain_links_message,
)


@pytest.mark.parametrize(
    "days,expected",
    [
        (-3, "today"),
        (0, "today"),
        (1, "yesterday"),
        (3, "3 days ago"),
        (29, "29 days ago"),
        (30, "1 month ago"),
        (60, "2 months ago"),
        (240, "8 months ago"),
        (364, "12 months ago"),
        (365, "1 year ago"),
        (800, "2 years ago"),
    ],
)
def test_humanize_age(days: int, expected: str) -> None:
    assert _humanize_age(days) == expected


def test_enriched_message_uses_humanized_age() -> None:
    links = [
        {
            "url": "https://github.com/foo/bar",
            "label": "bar",
            "_enriched": True,
            "_stars": 10,
            "_forks": 2,
            "_language": "Python",
            "_days_ago": 240,
            "_gh_description": "A bar",
        }
    ]
    msg = build_enriched_links_message(links)
    assert "📅 8 months ago" in msg
    assert "days ago" not in msg


def test_plain_links_message_is_bare_urls_one_per_line() -> None:
    links = [
        {"url": "http://12ft.io", "label": "12ft.io", "description": "Bypass any paywall"},
        {"url": "http://libgen.is", "label": "libgen.is", "description": "Free textbooks"},
    ]
    msg = build_plain_links_message(links)
    assert msg == "http://12ft.io\nhttp://libgen.is"
    # No labels, descriptions, or decoration leak into the plain list.
    assert "—" not in msg
    assert "🔗" not in msg
    assert "12ft.io — " not in msg


def test_plain_links_message_orders_enriched_first_by_popularity() -> None:
    links = [
        {"url": "http://plain.example", "label": "plain"},
        {
            "url": "https://github.com/low/repo",
            "_enriched": True,
            "_stars": 1,
            "_forks": 0,
        },
        {
            "url": "https://github.com/high/repo",
            "_enriched": True,
            "_stars": 100,
            "_forks": 5,
        },
    ]
    msg = build_plain_links_message(links)
    assert msg == (
        "https://github.com/high/repo\n"
        "https://github.com/low/repo\n"
        "http://plain.example"
    )


def test_plain_links_message_empty() -> None:
    assert build_plain_links_message([]) == ""

import pytest

from src.services.jobs import task_for_content_type
from src.utils.og_image import extract_essential_og, flatten_essential_og


HTML = """
<html><head>
<meta property="og:title" content="Example Title">
<meta property="og:description" content="Example Description">
<meta property="og:site_name" content="Example Site">
<meta property="og:type" content="article">
<meta property="og:image" content="/image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@example">
</head></html>
"""


def test_extract_essential_og_collection_in_one_pass():
    tags = extract_essential_og(HTML, "https://example.com/page")

    assert tags == {
        "og:title": "Example Title",
        "og:description": "Example Description",
        "og:site_name": "Example Site",
        "og:type": "article",
        "og:image": "https://example.com/image.png",
        "twitter:card": "summary_large_image",
        "twitter:site": "@example",
    }
    assert flatten_essential_og(tags) == (
        "og:title: Example Title · og:description: Example Description · "
        "og:site_name: Example Site · og:type: article · "
        "og:image: https://example.com/image.png · twitter:card: summary_large_image · "
        "twitter:site: @example"
    )


def test_link_content_type_dispatches_to_link_task():
    assert task_for_content_type("link", default="link") == "link"

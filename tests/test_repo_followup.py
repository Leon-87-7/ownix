import json

from src.services.repo_followup import _job_links, extract_repo_candidates


def test_job_links_parses_json_column_and_tolerates_junk():
    links = [{"url": "https://github.com/a/b", "description": "repo"}]
    assert _job_links({"links": json.dumps(links)}) == links
    assert _job_links({"links": links}) == links
    assert _job_links({"links": "not json"}) == []
    assert _job_links({}) == []


def test_extract_repo_candidates_scans_raw_text():
    text = (
        "Grab the code at https://github.com/langchain-ai/langchain.\n"
        "More info: https://example.com/blog and https://github.com/pricing"
    )
    candidates = extract_repo_candidates([], text=text)
    assert candidates == [
        {"name": "langchain-ai/langchain", "url": "https://github.com/langchain-ai/langchain"}
    ]


def test_extract_repo_candidates_dedupes_items_against_text():
    items = [{"name": "LangChain", "url": "https://github.com/langchain-ai/langchain"}]
    text = "see https://github.com/langchain-ai/langchain/tree/main and https://github.com/a/b"
    candidates = extract_repo_candidates(items, text=text)
    assert candidates == [
        {"name": "LangChain", "url": "https://github.com/langchain-ai/langchain"},
        {"name": "a/b", "url": "https://github.com/a/b"},
    ]


def test_extract_repo_candidates_filters_normalizes_dedupes_and_caps():
    items = [
        {"name": "Not a repo", "url": "https://example.com/tool"},
        {"name": "VIG", "type": "library", "url": "https://github.com/Leon-87-7/vig/tree/main"},
        {"name": "Duplicate", "url": "https://github.com/Leon-87-7/vig"},
        {"name": "One", "url": "https://github.com/a/one"},
        {"name": "Two", "url": "https://github.com/a/two"},
        {"name": "Three", "url": "https://github.com/a/three"},
        {"name": "Four", "url": "https://github.com/a/four"},
        {"name": "Five", "url": "https://github.com/a/five"},
    ]

    candidates = extract_repo_candidates(items)

    assert candidates == [
        {"name": "VIG", "url": "https://github.com/Leon-87-7/vig"},
        {"name": "One", "url": "https://github.com/a/one"},
        {"name": "Two", "url": "https://github.com/a/two"},
        {"name": "Three", "url": "https://github.com/a/three"},
        {"name": "Four", "url": "https://github.com/a/four"},
    ]

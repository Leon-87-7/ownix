from src.services.repo_followup import extract_repo_candidates


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

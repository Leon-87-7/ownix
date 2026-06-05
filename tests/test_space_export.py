"""Golden tests for compose_space_export (issue #95 / S8).

Pure function — no DB, no mocks needed. Verifies:
  - blobs lead in sort_order;
  - tag legend lists only used tags (skips unused ones);
  - each source carries full enrichment + **My notes:**;
  - transcript is absent from the output.
"""
from __future__ import annotations

from src.services.space_export import compose_space_export

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPACE = {"id": "sp1", "chat_id": 1, "name": "Research Space", "color": "#6366f1"}

BLOBS = [
    {"id": "b1", "space_id": "sp1", "name": "Frame A", "content": "## Frame A\nThis is the lens.", "sort_order": 1},
    {"id": "b2", "space_id": "sp1", "name": "Frame B", "content": "## Frame B\nSecondary context.", "sort_order": 2},
]

TAGS_CATALOG = [
    {"id": "t1", "name": "actionable", "meaning": "Has clear next steps", "color": "#ff0"},
    {"id": "t2", "name": "evergreen", "meaning": "Stays relevant long-term", "color": "#0f0"},
    {"id": "t3", "name": "unused-tag", "meaning": "Should not appear in legend", "color": "#f00"},
]

JOBS = [
    {
        "id": "j1",
        "title": "How to build in public",
        "url": "https://example.com/build-in-public",
        "content_type": "long",
        "ai_topic": "Community building",
        "ai_objective": "Grow an audience",
        "ai_action_points": "Post daily updates",
        "ai_tools": "Twitter, Beehiiv",
        "promise_gap": "No mention of monetisation",
        "template_analysis": "Standard narrative arc",
        "transcript": "Full transcript here — must not appear in output",
        "notes": "Great framing for our next sprint",
        "tags": [
            {"id": "t1", "name": "actionable", "meaning": "Has clear next steps"},
            {"id": "t2", "name": "evergreen", "meaning": "Stays relevant long-term"},
        ],
    },
    {
        "id": "j2",
        "title": "Second video",
        "url": "https://example.com/second",
        "content_type": "short",
        "ai_topic": None,
        "ai_objective": None,
        "ai_action_points": None,
        "ai_tools": None,
        "promise_gap": None,
        "template_analysis": None,
        "transcript": "Another transcript — absent from export",
        "notes": "",
        "tags": [],
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_space_heading() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert md.startswith("# Research Space\n")


def test_blobs_lead_in_sort_order() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    blob_a_pos = md.index("Frame A")
    blob_b_pos = md.index("Frame B")
    sources_pos = md.index("## Sources")
    assert blob_a_pos < blob_b_pos < sources_pos


def test_tag_legend_lists_only_used_tags() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert "actionable" in md
    assert "evergreen" in md
    assert "unused-tag" not in md


def test_tag_legend_section_present() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert "## Tag legend" in md
    assert "Name: actionable meaning: Has clear next steps" in md


def test_sources_contain_enrichment_fields() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert "Community building" in md
    assert "Grow an audience" in md
    assert "Post daily updates" in md
    assert "Twitter, Beehiiv" in md
    assert "No mention of monetisation" in md
    assert "Standard narrative arc" in md


def test_sources_contain_notes() -> None:
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert "**My notes:** Great framing for our next sprint" in md


def test_transcript_absent() -> None:
    """Transcripts must never appear in the export."""
    md = compose_space_export(SPACE, BLOBS, JOBS, TAGS_CATALOG)
    assert "Full transcript here" not in md
    assert "Another transcript" not in md


def test_no_tag_legend_when_no_tags_used() -> None:
    jobs_no_tags = [{**j, "tags": []} for j in JOBS]
    md = compose_space_export(SPACE, BLOBS, jobs_no_tags, TAGS_CATALOG)
    assert "## Tag legend" not in md


def test_empty_space_no_blobs_no_jobs() -> None:
    md = compose_space_export(SPACE, [], [], [])
    assert "# Research Space" in md
    assert "## Tag legend" not in md
    assert "## Sources" not in md

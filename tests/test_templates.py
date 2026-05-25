import pytest

from src.templates import (
    PROMPT_TEMPLATES,
    PromptTemplate,
    score_template_match,
    validate_template_choice,
)


# ---------------------------------------------------------------------------
# PromptTemplate structure
# ---------------------------------------------------------------------------

def test_all_five_templates_present() -> None:
    assert set(PROMPT_TEMPLATES.keys()) == {"summary", "method", "technical", "review", "narrative"}


def test_summary_extra_instructions_empty() -> None:
    assert PROMPT_TEMPLATES["summary"].extra_instructions == ""


@pytest.mark.parametrize("key", ["method", "technical", "review", "narrative"])
def test_non_summary_extra_instructions_contain_template_analysis(key: str) -> None:
    assert "template_analysis" in PROMPT_TEMPLATES[key].extra_instructions


def test_brave_search_flags() -> None:
    assert PROMPT_TEMPLATES["technical"].brave_search is True
    assert PROMPT_TEMPLATES["review"].brave_search is True
    assert PROMPT_TEMPLATES["summary"].brave_search is False
    assert PROMPT_TEMPLATES["method"].brave_search is False
    assert PROMPT_TEMPLATES["narrative"].brave_search is False


def test_summary_has_no_trigger_patterns() -> None:
    assert PROMPT_TEMPLATES["summary"].trigger_patterns == []


def test_method_trigger_patterns_include_tutorial() -> None:
    assert "tutorial" in PROMPT_TEMPLATES["method"].trigger_patterns


def test_all_templates_are_prompt_template_instances() -> None:
    for t in PROMPT_TEMPLATES.values():
        assert isinstance(t, PromptTemplate)


# ---------------------------------------------------------------------------
# Scoring + mismatch warning (migrated from the deleted src/validation.py — #38)
# ---------------------------------------------------------------------------

def test_score_template_match_returns_dict_with_all_keyworded_templates() -> None:
    scores = score_template_match("some text")
    assert set(scores.keys()) == {"method", "technical", "review", "narrative"}


def test_score_template_match_counts_keywords() -> None:
    # "step" x2, "then" x1, "click" x1, "navigate" x1 are all method keywords
    text = "step one step two then click navigate"
    scores = score_template_match(text)
    assert scores["method"] >= 3


def test_validate_returns_none_for_good_method_match() -> None:
    tutorial_transcript = " ".join([
        "step first next then click navigate configure open select"
    ] * 10)
    assert validate_template_choice("method", tutorial_transcript) is None


def test_validate_returns_warning_for_method_on_review_content() -> None:
    review_transcript = " ".join([
        "recommend rating pros cons worth price quality feature versus"
        " recommend rating pros cons worth price quality feature versus"
    ] * 10)
    result = validate_template_choice("method", review_transcript)
    assert result is not None
    assert "review" in result.lower() or "method" in result.lower()


def test_validate_returns_none_for_summary_template() -> None:
    # "summary" has no keywords in the unified table -> always returns None
    assert validate_template_choice("summary", "any text here" * 20) is None


def test_validate_returns_none_for_unknown_template() -> None:
    assert validate_template_choice("nonexistent", "some text") is None


def test_warning_message_contains_better_template_name() -> None:
    review_text = " ".join([
        "recommend rating pros cons worth price quality feature versus"
    ] * 10)
    warning = validate_template_choice("method", review_text)
    assert warning is not None
    assert "review" in warning


# ---------------------------------------------------------------------------
# Unification guarantee (#38): auto-routing and the mismatch warning read ONE
# keyword table. A keyword that historically lived in only one of the two old
# tables must now drive BOTH paths.
# ---------------------------------------------------------------------------

def test_unified_table_holds_both_routing_phrases_and_scoring_indicators() -> None:
    method = PROMPT_TEMPLATES["method"].trigger_patterns
    assert "tutorial" in method   # was a routing-only trigger_pattern
    assert "click" in method      # was a scoring-only TEMPLATE_INDICATOR


def test_indicator_word_now_drives_auto_routing() -> None:
    # "click"/"navigate"/"configure" lived only in validation's table pre-#38;
    # after unification they must also auto-route a plain-URL job.
    from src.processors.long_video import detect_template

    assert detect_template("click navigate configure the settings", "") == "method"


def test_routing_phrase_now_counts_toward_mismatch_scoring() -> None:
    # "tutorial" lived only in the routing table pre-#38; after unification it
    # must also count toward the method score used by the mismatch warning.
    scores = score_template_match("tutorial tutorial tutorial")
    assert scores["method"] > 0

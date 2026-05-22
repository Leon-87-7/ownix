from src.validation import validate_template_choice, score_template_match


def test_score_template_match_returns_dict_with_all_templates() -> None:
    scores = score_template_match("some text")
    assert set(scores.keys()) == {"method", "technical", "review", "narrative"}


def test_score_template_match_counts_keywords() -> None:
    # "step" and "click" are method keywords
    text = "step one step two then click navigate"
    scores = score_template_match(text)
    assert scores["method"] >= 3  # "step"x2 + "click"x1


def test_validate_returns_none_for_good_method_match() -> None:
    tutorial_transcript = " ".join([
        "step first next then click navigate configure open select"
    ] * 10)
    result = validate_template_choice("method", tutorial_transcript)
    assert result is None


def test_validate_returns_warning_for_method_on_review_content() -> None:
    review_transcript = " ".join([
        "recommend rating pros cons worth price quality feature versus"
        " recommend rating pros cons worth price quality feature versus"
    ] * 10)
    result = validate_template_choice("method", review_transcript)
    assert result is not None
    assert "review" in result.lower() or "method" in result.lower()


def test_validate_returns_none_for_summary_template() -> None:
    # "summary" is not in TEMPLATE_INDICATORS — always returns None
    result = validate_template_choice("summary", "any text here" * 20)
    assert result is None


def test_validate_returns_none_for_unknown_template() -> None:
    result = validate_template_choice("nonexistent", "some text")
    assert result is None


def test_warning_message_contains_better_template_name() -> None:
    review_text = " ".join([
        "recommend rating pros cons worth price quality feature versus"
    ] * 10)
    warning = validate_template_choice("method", review_text)
    assert warning is not None
    assert "review" in warning

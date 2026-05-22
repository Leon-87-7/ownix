from src.analysis import extract_key_phrases


def test_returns_list_of_strings() -> None:
    result = extract_key_phrases("hello world python python")
    assert isinstance(result, list)
    assert all(isinstance(p, str) for p in result)


def test_respects_max_phrases() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    result = extract_key_phrases(text, max_phrases=3)
    assert len(result) <= 3


def test_stripe_and_nextjs_appear_in_results() -> None:
    transcript = (
        "In this tutorial we use stripe stripe stripe for payments. "
        "nextjs nextjs nextjs is our framework. We also talk about nextjs stripe. "
        "Authentication is important. Stripe provides the payment gateway. "
        "Next.js pages router is used with nextjs components."
    )
    result = extract_key_phrases(transcript, max_phrases=8)
    assert "stripe" in result
    assert "nextjs" in result


def test_stopwords_excluded() -> None:
    text = "this that what have with from python python python"
    result = extract_key_phrases(text, max_phrases=8)
    for word in ["this", "that", "what", "have", "with", "from"]:
        assert word not in result


def test_short_words_excluded() -> None:
    text = "hi bye the and are was"
    result = extract_key_phrases(text, max_phrases=8)
    assert result == []


def test_empty_transcript_returns_empty_list() -> None:
    assert extract_key_phrases("") == []


def test_default_max_phrases_is_8() -> None:
    words = " ".join([f"word{i}word{i}" for i in range(20)])
    result = extract_key_phrases(words)
    assert len(result) <= 8

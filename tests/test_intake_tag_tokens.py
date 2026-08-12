"""Tests for `#tag` token parsing (`src/intake/tag_tokens.py`, issue #482).

The two rules that carry real risk are covered hardest: the `#` must be
whitespace- or start-anchored (or a URL fragment gets eaten and the job is
created against a truncated URL), and name matching normalizes both sides
(or `#readlater` spawns a near-duplicate of an existing "Read Later").
"""

from __future__ import annotations

import pytest

from src.intake import tag_tokens


class TestExtract:
    def test_trailing_token(self) -> None:
        text, names = tag_tokens.extract("https://youtube.com/shorts/abc #GoTo")
        assert text == "https://youtube.com/shorts/abc"
        assert names == ["GoTo"]

    def test_leading_token(self) -> None:
        text, names = tag_tokens.extract("#GoTo https://youtube.com/shorts/abc")
        assert text == "https://youtube.com/shorts/abc"
        assert names == ["GoTo"]

    def test_position_is_not_meaningful(self) -> None:
        leading = tag_tokens.extract("#GoTo https://example.com/a")
        trailing = tag_tokens.extract("https://example.com/a #GoTo")
        assert leading == trailing

    def test_multiple_tokens_keep_order(self) -> None:
        text, names = tag_tokens.extract("#a https://example.com/x #b")
        assert text == "https://example.com/x"
        assert names == ["a", "b"]

    def test_duplicate_tokens_collapse(self) -> None:
        _, names = tag_tokens.extract("https://example.com/x #GoTo #goto")
        assert names == ["GoTo"]

    def test_url_fragment_is_not_a_tag(self) -> None:
        """The regression this regex exists to prevent."""
        text, names = tag_tokens.extract("https://docs.example.com/guide#installation")
        assert text == "https://docs.example.com/guide#installation"
        assert names == []

    def test_fragment_and_tag_together(self) -> None:
        text, names = tag_tokens.extract("https://docs.example.com/guide#installation #GoTo")
        assert text == "https://docs.example.com/guide#installation"
        assert names == ["GoTo"]

    def test_hash_glued_to_word_is_not_a_tag(self) -> None:
        text, names = tag_tokens.extract("issue#482")
        assert text == "issue#482"
        assert names == []

    def test_bare_token_leaves_empty_text(self) -> None:
        text, names = tag_tokens.extract("#GoTo")
        assert text == ""
        assert names == ["GoTo"]

    def test_hyphenated_name(self) -> None:
        _, names = tag_tokens.extract("https://example.com/x #read-later")
        assert names == ["read-later"]

    def test_empty_input(self) -> None:
        assert tag_tokens.extract("") == ("", [])


class TestNormalize:
    @pytest.mark.parametrize("raw", ["Read Later", "READ_LATER", "  read   later  "])
    def test_whitespace_and_underscore_share_one_key(self, raw: str) -> None:
        assert tag_tokens.normalize(raw) == "read_later"

    def test_other_punctuation_is_literal(self) -> None:
        assert tag_tokens.normalize("read-later") == "read-later"
        assert tag_tokens.normalize("readlater") == "readlater"

    def test_non_ascii_survives(self) -> None:
        """`str.isalnum` keeps Cyrillic/CJK — a regex of [a-z0-9] would blank them."""
        assert tag_tokens.normalize("Читать") == "читать"
        assert tag_tokens.normalize("読む") == "読む"

    def test_matches_existing_tag_name(self) -> None:
        assert tag_tokens.normalize("#read_later".lstrip("#")) == tag_tokens.normalize("Read Later")

    @pytest.mark.parametrize("payload", ["c++", "r&d", "ai/ml", "foo#bar", "design_🎨"])
    def test_arbitrary_non_whitespace_payload_is_lossless(self, payload: str) -> None:
        _, names = tag_tokens.extract(f"https://example.com/x #{payload}")
        assert names == [tag_tokens.decode(payload)]

    def test_casefold_beyond_ascii_lower(self) -> None:
        """`str.lower` doesn't case-fold; `Straße`/`STRASSE` must still collide."""
        assert tag_tokens.normalize("Straße") == tag_tokens.normalize("STRASSE")

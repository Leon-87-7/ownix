"""`#tag` token parsing for intake messages (issue #482, CONTEXT.md "Tag token").

Channel-neutral on purpose: Telegram, the dashboard and the extension all route
through `src/intake/router.py`, so parsing here is what guarantees they agree.
Telegram additionally auto-highlights hashtags client-side as `MessageEntity`,
but the adapter deliberately does not read `entities` — this parse is the single
source of truth.
"""

from __future__ import annotations

import re

# The `#` must be whitespace- or start-anchored. A URL fragment's `#` never is,
# so `…/guide#installation` keeps its fragment instead of being truncated into a
# job URL plus a tag named `installation`.
TAG_TOKEN = re.compile(r"(?:^|\s)#([\w-]+)")


def normalize(name: str) -> str:
    """Collapse a tag name to its match key: casefolded, alphanumerics only.

    Uses `str.isalnum` rather than an `[a-z0-9]` class so Cyrillic/CJK names
    survive — a regex class would blank them and make every non-Latin tag
    collide on the empty string.
    """
    return "".join(ch for ch in name.lower() if ch.isalnum())


def extract(text: str) -> tuple[str, list[str]]:
    """Split `text` into (remaining text, tag names).

    Names keep the casing the user typed — that is what a newly created tag is
    named — but duplicates are collapsed on the normalized key, so `#GoTo #goto`
    yields one name.
    """
    if not text:
        return "", []

    names: list[str] = []
    seen: set[str] = set()

    def _take(match: re.Match[str]) -> str:
        raw = match.group(1)
        key = normalize(raw)
        if key and key not in seen:
            seen.add(key)
            names.append(raw)
        # Replace with a space, not "": the token may have been separating two
        # words, and the caller re-collapses whitespace anyway.
        return " "

    remaining = TAG_TOKEN.sub(_take, text)
    return " ".join(remaining.split()), names


__all__ = ["TAG_TOKEN", "extract", "normalize"]

"""Canonical codec and catalog matching for intake ``#tag`` tokens."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping

# A hash is syntax only at the start of the input or after whitespace.  The
# payload deliberately includes every non-whitespace character (ADR-0049).
TAG_TOKEN = re.compile(r"(?<!\S)#(\S+)")


def decode(payload: str) -> str:
    """Decode a token payload to display text (underscores encode whitespace)."""
    return " ".join(payload.replace("_", " ").split())


def encode(name: str) -> str:
    """Return the canonical, copyable payload for a stored display name."""
    return "_".join(name.split()).casefold()


def normalize(name: str) -> str:
    """Return the canonical comparison key for display text or decoded text."""
    return encode(name)


def groups(tags: Iterable[Mapping]) -> dict[str, list[Mapping]]:
    """Group catalog rows by canonical token without hiding collisions."""
    result: dict[str, list[Mapping]] = defaultdict(list)
    for tag in tags:
        result[normalize(str(tag["name"]))].append(tag)
    return dict(result)


def extract(text: str) -> tuple[str, list[str]]:
    """Split text into remaining prose and deduplicated decoded tag names."""
    if not text:
        return "", []
    names: list[str] = []
    seen: set[str] = set()

    def take(match: re.Match[str]) -> str:
        name = decode(match.group(1))
        key = normalize(name)
        if name and key not in seen:
            seen.add(key)
            names.append(name)
        return " "

    return " ".join(TAG_TOKEN.sub(take, text).split()), names


__all__ = ["TAG_TOKEN", "decode", "encode", "extract", "groups", "normalize"]

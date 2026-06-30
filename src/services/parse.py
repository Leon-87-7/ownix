"""Inline PDF text extraction via liteparse (#153).

liteparse is synchronous and CPU-bound, so parsing runs in asyncio.to_thread.
PDF-only at MVP: no OCR, no sidecar, no native binaries (ADR-0023).
"""
from __future__ import annotations

import asyncio

import liteparse


class ParseError(Exception):
    """Raised when liteparse cannot extract text from the document."""


def _parse_sync(data: bytes, output_format: str) -> str:
    result = liteparse.LiteParse(
        ocr_enabled=False, quiet=True, output_format=output_format
    ).parse(data)
    # get_page is 1-indexed and ParseResult has no aggregate .text of its own,
    # so join each page's text (verified against the 2.0.7 wheel). In
    # output_format="markdown" the same .text accessor yields Markdown.
    pages = (result.get_page(i) for i in range(1, result.num_pages + 1))
    return "\n".join(p.text for p in pages if p is not None)


async def parse_pdf(data: bytes, *, output_format: str = "text") -> str:
    """Extract text from PDF bytes. output_format='markdown' yields Markdown.
    Raises ParseError on any parse failure."""
    try:
        return await asyncio.to_thread(_parse_sync, data, output_format)
    except Exception as exc:  # liteparse.ParseError + any native parse failure
        raise ParseError(str(exc)) from exc

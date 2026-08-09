"""Unit tests for src/services/parse.py — liteparse inline PDF wrapper (#153)."""
from __future__ import annotations

import pytest

from tests.conftest import TINY_PDF


@pytest.mark.asyncio
async def test_parse_pdf_returns_text():
    from src.services.parse import parse_pdf

    text = await parse_pdf(TINY_PDF)
    assert "Hello Vig" in text


@pytest.mark.asyncio
async def test_parse_pdf_raises_catchable_parse_error_on_garbage():
    from src.services.parse import ParseError, parse_pdf

    with pytest.raises(ParseError):
        await parse_pdf(b"this is not a pdf at all")

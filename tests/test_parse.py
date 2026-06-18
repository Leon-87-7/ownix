"""Unit tests for src/services/parse.py — liteparse inline PDF wrapper (#153)."""
from __future__ import annotations

import pytest

# Minimal one-page PDF whose content stream draws the text "Hello Vig".
_TINY_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 44>>stream
BT /F1 24 Tf 20 100 Td (Hello Vig) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R/Size 6>>
%%EOF"""


@pytest.mark.asyncio
async def test_parse_pdf_returns_text():
    from src.services.parse import parse_pdf

    text = await parse_pdf(_TINY_PDF)
    assert "Hello Vig" in text


@pytest.mark.asyncio
async def test_parse_pdf_raises_catchable_parse_error_on_garbage():
    from src.services.parse import ParseError, parse_pdf

    with pytest.raises(ParseError):
        await parse_pdf(b"this is not a pdf at all")

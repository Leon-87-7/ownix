"""Format routing in src/services/parse.py (ADR-0023 Office support via anydoc).

Hermetic: CSV exercises the anydoc path (no signature, format named by extension)
and the shared `tiny_pdf` fixture exercises the liteparse path. No Office-file
generators needed, so the suite stays dependency-light.
"""
from __future__ import annotations

import pytest

from src.services.parse import ParseError, parse_document


@pytest.mark.asyncio
async def test_csv_routes_to_anydoc_as_gfm_table():
    data = b"name,role\nliteparse,pdf\nanydoc,office\n"
    md = await parse_document(data, "csv")
    assert "| name | role |" in md
    assert "| anydoc | office |" in md


@pytest.mark.asyncio
async def test_pdf_routes_to_liteparse(tiny_pdf):
    text = await parse_document(tiny_pdf, "pdf")
    assert "Hello Vig" in text


@pytest.mark.asyncio
async def test_pdf_markdown_output_format_is_honored(tiny_pdf):
    md = await parse_document(tiny_pdf, "pdf", output_format="markdown")
    assert "Hello Vig" in md


@pytest.mark.asyncio
async def test_unsupported_extension_raises_parse_error():
    with pytest.raises(ParseError, match="Unsupported document format"):
        await parse_document(b"whatever", "xyz")


@pytest.mark.asyncio
async def test_malformed_office_bytes_raise_parse_error():
    # anydoc's ConvertError family is wrapped as ParseError, never leaked raw.
    with pytest.raises(ParseError):
        await parse_document(b"not a real docx", "docx")


def test_validators_document_exts_stay_in_sync():
    # validators keeps a local copy of the routing extension set (to stay
    # stdlib-only); guard against drift from parse.SUPPORTED_EXTS.
    from src.services.parse import SUPPORTED_EXTS
    from src.utils.validators import _DOCUMENT_EXTS

    assert _DOCUMENT_EXTS == SUPPORTED_EXTS

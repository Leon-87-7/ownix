"""Format routing in src/services/parse.py (ADR-0023 Office support via anydoc).

Hermetic: CSV exercises the anydoc path (no signature, format named by extension)
and a runtime-built minimal PDF exercises the liteparse path. No Office-file
generators needed, so the suite stays dependency-light.
"""
from __future__ import annotations

import pytest

from src.services.parse import ParseError, parse_document


def _minimal_pdf(lines: list[str]) -> bytes:
    """A valid single-page text PDF with correct xref offsets."""
    text_ops = b"BT /F1 18 Tf 72 700 Td "
    for i, line in enumerate(lines):
        if i:
            text_ops += b"0 -30 Td "
        text_ops += b"(%s) Tj " % line.encode("latin-1")
    text_ops += b"ET"
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length %d>>stream\n%s\nendstream" % (len(text_ops), text_ops),
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj" % i + body + b"endobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        xref_pos,
    )
    return out


@pytest.mark.asyncio
async def test_csv_routes_to_anydoc_as_gfm_table():
    data = b"name,role\nliteparse,pdf\nanydoc,office\n"
    md = await parse_document(data, "csv")
    assert "| name | role |" in md
    assert "| anydoc | office |" in md


@pytest.mark.asyncio
async def test_pdf_routes_to_liteparse():
    pdf = _minimal_pdf(["Second Brain Design Doc", "Semantic link graph."])
    text = await parse_document(pdf, "pdf")
    assert "Second Brain Design Doc" in text
    assert "Semantic link graph." in text


@pytest.mark.asyncio
async def test_pdf_markdown_output_format_is_honored():
    pdf = _minimal_pdf(["Heading"])
    md = await parse_document(pdf, "pdf", output_format="markdown")
    assert "Heading" in md


@pytest.mark.asyncio
async def test_unsupported_extension_raises_parse_error():
    with pytest.raises(ParseError, match="Unsupported document format"):
        await parse_document(b"whatever", "xyz")


@pytest.mark.asyncio
async def test_malformed_office_bytes_raise_parse_error():
    # anydoc's ConvertError family is wrapped as ParseError, never leaked raw.
    with pytest.raises(ParseError):
        await parse_document(b"not a real docx", "docx")

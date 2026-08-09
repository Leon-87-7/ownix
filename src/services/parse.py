"""Document text/Markdown extraction, routed by format (#153, ADR-0023).

PDF → liteparse; every other supported format (DOCX/PPTX/XLSX, ODF, RTF, EPUB,
CSV) → anydoc. Both are synchronous and CPU-bound (run via asyncio.to_thread) and
neither does OCR — a scanned/image-only input raises ParseError. Why this split
and why anydoc over the LibreOffice stack: docs/adr/0023-liteparse-document-pipeline.md
and docs/plans/anydoc-office-parsing-spike.md.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

import anydoc
import liteparse

from src.utils.document_formats import ANYDOC_EXTS, SUPPORTED_DOCUMENT_EXTS

# Canonical formats the anydoc path parses — the anydoc `Format` enum minus PDF.
# Callers (intake validation, the document processor) consult these to route
# without importing anydoc directly.
# Extension allowlist for URL/filename routing (detect_pipeline, upload filenames).
# The canonical set plus common OOXML variants that share a ZIP container anydoc
# detects by content (docm→docx, xlsm→xlsx, pptm→pptx). The authoritative gate is
# always detect_format() on the actual bytes; this only decides "looks like a doc".
SUPPORTED_EXTS = SUPPORTED_DOCUMENT_EXTS

# Canonical source extension → storage/HTTP content type. Keyed by what
# detect_format() returns (always a canonical ext), so every stored source object
# gets an honest MIME regardless of the client-declared type.
MIME_BY_EXT: dict[str, str] = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "rtf": "application/rtf",
    "epub": "application/epub+zip",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odp": "application/vnd.oasis.opendocument.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "csv": "text/csv",
}


class ParseError(Exception):
    """Raised when a document cannot be converted to text/Markdown."""


def _norm_ext(ext: str) -> str:
    return ext.lower().lstrip(".")


def _ext_from_name(name: str | None) -> str:
    """Lowercased extension of a filename/path, or '' when there is none."""
    if not name:
        return ""
    leaf = urlsplit(name).path.rsplit("/", 1)[-1]
    if "." not in leaf:
        return ""
    return leaf.rsplit(".", 1)[-1].lower()


def detect_format(data: bytes, filename: str | None = None) -> str | None:
    """Canonical source extension for supported document bytes, or None.

    Content-based (anydoc reads the PDF header, RTF open group, OLE stream names,
    and the ZIP package mimetype), so a mislabeled or renamed file still routes
    correctly — never trust a client Content-Type. CSV alone carries no signature,
    so it is accepted only when the filename names it.
    """
    fmt = anydoc.format_from_bytes(data)  # 'pdf', 'docx', 'xlsx', … or None
    if fmt:
        return fmt
    if _ext_from_name(filename) == "csv":
        return "csv"
    return None


def content_type_for(ext: str) -> str:
    """Storage/HTTP content type for a canonical source extension."""
    return MIME_BY_EXT.get(_norm_ext(ext), "application/octet-stream")


def _parse_pdf_sync(data: bytes, output_format: str) -> str:
    result = liteparse.LiteParse(
        ocr_enabled=False, quiet=True, output_format=output_format
    ).parse(data)
    # get_page is 1-indexed and ParseResult has no aggregate .text of its own,
    # so join each page's text (verified against the 2.0.7 wheel). In
    # output_format="markdown" the same .text accessor yields Markdown.
    pages = (result.get_page(i) for i in range(1, result.num_pages + 1))
    return "\n".join(p.text for p in pages if p is not None)


def _parse_anydoc_sync(data: bytes, ext: str) -> str:
    # anydoc always renders GitHub-Flavored Markdown; there is no separate
    # plaintext renderer, so the "text" and "markdown" output formats collapse to
    # the same clean Markdown for these formats. Pass the extension-derived format
    # explicitly so signature-less inputs (CSV) still convert.
    fmt = anydoc.format_from_extension(ext) or anydoc.format_from_bytes(data)
    return anydoc.to_markdown_bytes(data, fmt)


async def parse_pdf(data: bytes, *, output_format: str = "text") -> str:
    """Extract text from PDF bytes. output_format='markdown' yields Markdown.
    Raises ParseError on any parse failure."""
    try:
        return await asyncio.to_thread(_parse_pdf_sync, data, output_format)
    except Exception as exc:  # liteparse.ParseError + any native parse failure
        raise ParseError(str(exc)) from exc


async def parse_document(data: bytes, ext: str, *, output_format: str = "text") -> str:
    """Convert a document to text/Markdown, routing by extension.

    ext 'pdf' → liteparse (honors output_format); any other supported ext →
    anydoc (always Markdown). Raises ParseError on unsupported formats or any
    parse failure (including scanned/OCR-only inputs, which neither parser reads).
    """
    ext = _norm_ext(ext)
    if ext == "pdf":
        return await parse_pdf(data, output_format=output_format)
    if ext not in SUPPORTED_EXTS:
        raise ParseError(f"Unsupported document format: .{ext or '?'}")
    try:
        return await asyncio.to_thread(_parse_anydoc_sync, data, ext)
    except Exception as exc:  # anydoc.ConvertError subclasses + OSError
        raise ParseError(str(exc)) from exc

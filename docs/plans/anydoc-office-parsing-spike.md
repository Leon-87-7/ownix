# Spike: anydoc for non-PDF document parsing

**Date:** 2026-08-09
**Question:** Is [firecrawl/anydoc](https://github.com/firecrawl/anydoc) a good fit for the doc-parser pipeline?
**Outcome:** ✅ Adopt for Office/other formats. Keep PDF on liteparse.
**Relates to:** ADR-0023 (which deferred DOCX/PPTX/XLSX because the liteparse Office path pulls in a ~1 GB LibreOffice/ImageMagick/Tesseract stack).

## Decision

Route by format in `src/services/parse.py`:

| Formats | Parser | Why |
| --- | --- | --- |
| PDF | **liteparse** (unchanged) | Layout-aware reading-order reconstruction (columns, tables, reading flow). |
| DOCX, PPTX, XLSX, DOC, PPT, XLS, ODT, ODS, ODP, RTF, EPUB, CSV | **firecrawl-anydoc** | Self-contained Rust wheel, no LibreOffice. Lifts the ADR-0023 Office deferral. |

## What the spike verified

1. **Install is lean.** `pip install firecrawl-anydoc` pulls a prebuilt
   `manylinux_2_17_x86_64` **abi3** wheel — **3.4 MB**, works on CPython ≥3.10, **no
   Rust toolchain at install**. This is the whole reason to prefer it over
   liteparse's Office path: it replaces the ~1 GB native stack that first-narrowed
   the pipeline to PDF-only. Package name is `firecrawl-anydoc`; it **imports as
   `anydoc`** (the bare `anydoc` name on PyPI is an unrelated dead package).

2. **Output quality is clean GFM.** Real generated samples (python-docx /
   openpyxl / python-pptx):
   - **DOCX** → headings, `**bold**`, bullet lists, and a proper GFM table.
   - **XLSX** → GFM table. *Caveat:* formula cells with no cached value render
     empty (e.g. a `=SUM()` written by openpyxl without a computed value).
   - **PPTX** → per-slide `##` headings + bullet bodies.
   - **CSV** → GFM table. CSV has no content signature, so the format **must be
     named** (we pass it from the file extension).

3. **PDF stays on liteparse — deliberately.** On the same PDF, liteparse
   preserves line breaks (`…Design Doc\nSemantic link graph.`) via its
   reading-order analysis, while anydoc flattens them to a space. anydoc's PDF
   support is explicitly text-only and not its strength, so PDFs keep the
   layout-aware path.

4. **Failure modes are typed and wrapped.** anydoc raises `ConvertError`
   subclasses (`EncryptedError`, `MalformedError`, `MissingPartError`,
   `ResourceLimitError`, `UnsupportedError`) and `OSError`; the router wraps them
   as `ParseError`, so callers keep their existing "no text could be extracted"
   handling. **No OCR** — scanned/image-only inputs raise, same as liteparse today.

## API used

```python
import anydoc
md  = anydoc.to_markdown_bytes(data, fmt)      # fmt from extension; None = detect
fmt = anydoc.format_from_extension(ext)        # 'docx', 'csv', … or None
```

`Format` is a string literal: `doc, docx, odt, pdf, ppt, pptx, rtf, epub, xlsx, ods, odp, csv`.

## What shipped in this spike

- `src/services/parse.py` — added `parse_document(data, ext, *, output_format)`
  router + `SUPPORTED_EXTS` / `ANYDOC_EXTS`. `parse_pdf` unchanged.
- `requirements.txt` — `firecrawl-anydoc==0.1.7`.
- `tests/test_parse_router.py` — hermetic routing/exception tests (5 passing).

## Follow-up (not in this spike)

The parser layer now handles any supported format, but the intake path is still
PDF-only end-to-end. To actually accept Office uploads:

1. **Intake validation** (`src/services/pdf_intake.py`, `src/intake/uploads.py`,
   `src/api/parsed.py`) — accept the new extensions/magic bytes, not just `%PDF`.
2. **Storage keys** (`src/processors/document.py::_sha_from_key`,
   `documents/<sha>.pdf`) — carry the real source extension so `_cached_parse`
   can call `parse_document(data, ext)` instead of the hardcoded PDF path.
3. **ADR-0023 amendment** — record that the Office deferral is lifted via anydoc
   (no sidecar needed) rather than the deferred LibreOffice sidecar design.

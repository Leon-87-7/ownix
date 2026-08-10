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

## Follow-up — shipped (2026-08-09)

The full multi-format rollout is now implemented; any format the Doc Parser and
intake pages list runs exactly like PDF did.

1. **Format detection + MIME map** — `src/services/parse.py` gained
   `detect_format(data, filename)` (content-sniff gate), `content_type_for(ext)`,
   `SUPPORTED_EXTS`/`ANYDOC_EXTS`, alongside the `parse_document` router.
2. **Intake trust boundary** — `src/services/pdf_intake.py` now exposes
   `validate_document()` (returns canonical ext) and `fetch_remote_document()`;
   the SSRF/size guards are unchanged.
3. **Storage keys carry the source format** —
   `documents/<sha>.<srcext>`; `src/processors/document.py::_cached_parse` derives
   the ext from the key and calls `parse_document`.
4. **All ingest channels** — Doc Parser API (`src/api/parsed.py`, with an
   image→photo-OCR branch), intake pipeline (`src/intake/mime_sniff.py` +
   `uploads.py`), Telegram webhook (`src/telegram/webhook.py`), and URL routing
   (`src/utils/validators.py`).
5. **Frontend** — doc-parser page format-filter tabs (soon badges removed),
   `doc-upload-panel` accepts all formats + renders image-OCR links, intake
   dropzone accepts office formats.
6. **ADR-0023 amendment** — records the Office deferral lifted via anydoc, no
   sidecar (see the 2026-08-09 update at the top of ADR-0023).

Images remain a separate concern: anydoc has no OCR, so image uploads fork to the
existing photo-OCR link-extraction pipeline (ADR-0003) rather than a document job.

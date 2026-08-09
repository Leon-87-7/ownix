---
adr: "0023"
title: Document pipeline via liteparse sidecar with GCS-as-cache
status: accepted
date: 2026-06-08
---

## Office support via anydoc — no sidecar (2026-08-09 update)

The Office-format deferral below is **lifted**, and **without** the deferred
`vig-document` sidecar. The sidecar existed only to quarantine liteparse's ~1 GB
native stack (LibreOffice = the DOCX/PPTX/XLSX path; ImageMagick + Tesseract = the
image/OCR path). [firecrawl/anydoc](https://github.com/firecrawl/anydoc) parses
DOCX/PPTX/XLSX, ODF, RTF, EPUB, and CSV in a **single self-contained Rust wheel**
(`firecrawl-anydoc`, ~3.4 MB manylinux abi3, no LibreOffice, no Rust toolchain at
install), so those formats now run **inline in `vig-worker`** exactly like PDF.
Spike + rationale: `docs/plans/anydoc-office-parsing-spike.md`.

What this changes:

- **Routing by format, one seam.** `src/services/parse.py` routes **PDF →
  liteparse** (kept for its layout-aware reading-order reconstruction) and
  **everything else → anydoc**. `parse_document(data, ext)` is the single entry
  point; `detect_format(data, filename)` is the authoritative content-sniff gate
  (anydoc reads the PDF header / OLE stream names / ZIP package mimetype; CSV,
  signature-less, is trusted by filename only).
- **Storage key carries the source format.** Objects are content-addressed as
  `documents/<sha>.<srcext>` (was hardcoded `.pdf`), so `_cached_parse` re-routes
  a cache miss to the right parser. Parsed output stays sha-addressed and shared.
- **All three ingest channels generalized** behind that gate — the Doc Parser
  dashboard (`/api/parsed/*`), the channel-neutral intake API
  (`/api/intake/upload` → `mime_sniff` → `uploads`), and the Telegram webhook —
  plus URL routing (`detect_pipeline`). The 20 MB cap and SSRF guards are
  unchanged.
- **Images are still not documents.** anydoc has no OCR (scanned/image-only inputs
  raise), so images uploaded to the Doc Parser / intake pages **fork to the
  existing photo-OCR link-extraction pipeline** (ADR-0003) via a new branch rather
  than creating a document job.
- **Still unadopted:** the sidecar, and OCR for scanned PDFs/images. Those return
  only if a format anydoc can't handle earns real demand.

## MVP scope (2026-06-18 update)

The first shipping slice (issues #150–#155) is **narrowed to PDF-only**, which
changes two of the structural decisions below. The full design (Office + image
formats, the sidecar) remains the accepted target; it is **deferred**, not
rejected.

- **PDF-only at MVP.** Verified against the package and upstream docs: liteparse
  parses **PDF with zero native system dependencies** (no LibreOffice, no
  ImageMagick, no Tesseract). Those binaries are not removable bloat — each maps
  1:1 to a format family: LibreOffice *is* the DOCX/PPTX/XLSX path, and
  ImageMagick+Tesseract *is* the image/OCR path. So "lean" is only achievable by
  narrowing format scope. DOCX/PPTX/XLSX/PNG/JPG/JPEG are deferred until there is
  real upload demand.
- **No `vig-document` sidecar at MVP (supersedes Decision #1 and #2 for now).**
  The sidecar's sole justification was quarantining the ~1GB native-binary
  stack. PDF-only liteparse is a plain `pip install`, so it runs **inline in
  `vig-worker`** — `src/processors/document.py` calls `liteparse` in-process.
  No new always-on container, no HTTP contract, no `src/services/liteparse.py`
  client. If/when Office+image formats are added, the sidecar (and the GCS
  reference-in/text-out HTTP contract in Decision #2) returns exactly as
  specified below.
- **Unchanged by this narrowing:** the GCS content-addressed cache (Decision #4),
  tenant isolation (Decision #5), the `content_type="document"` /
  `{"task":"document"}` / `src/processors/document.py` shape (Decision #6), the
  document enrichment schema, on-demand Markdown (Decision #3), and the 20MB
  Telegram rejection (Decision #7). The `📄 Get Markdown` and `✍️ Freestyle`
  buttons (issues #156/#157) land in a follow-up PR — the MVP slice delivers the
  `.txt` + enrichment summary without those buttons rather than ship dead UI.

## Context

vig has four URL-routed pipelines (short video, long video, article, repo).
A fifth content shape — **uploaded documents** (PDF, DOCX, PPTX, XLSX, and
images sent as files) — has no URL and no clean fit in the existing pipelines:

- The **article pipeline** (Jina Reader) fetches *web pages*; it cannot parse a
  binary file the user uploads, and Jina mangles arxiv-style PDFs.
- The **photo pipeline** extracts *links from screenshots*; it is Telegram-only
  and deliberately stays so. An image sent "as a file" for full parsing is a
  different intent.

The candidate parser is [liteparse](https://github.com/run-llama/liteparse)
(run-llama). Its core value is **fast, local, layout-aware text extraction**:
it uses internal spatial/bounding-box analysis to reconstruct reading order
(columns, tables, slides) correctly, and bundles OCR for scanned content. It
supports PDF natively, Office formats via **LibreOffice**, and images via
**ImageMagick**, with **Tesseract OCR** bundled.

**Verified against the actual package (v2.0.7), not the README:**

- **License is inconsistent upstream.** The GitHub `LICENSE` file (and GitHub's
  SPDX detection) is **Apache-2.0**; the published PyPI metadata declares
  **MIT** (`license_expression: MIT`, classifier `OSI Approved :: MIT
  License`). Both are permissive and fine for commercial SaaS use, but the
  discrepancy is real. **Mitigation: pin a specific liteparse version and retain
  a copy of the LICENSE actually shipped with that version.**
- **Liteparse does NOT output Markdown.** The README's "Markdown" framing is
  marketing. The Python API (`LiteParse().parse()`) returns a `ParseResult`
  with `.text` (whole-doc, layout-ordered **plain text**), `.pages[].text`
  (per-page plain text), and `.pages[].text_items[]` (the spatial bounding-box
  data: `text, x, y, width, height, font_name, font_size, confidence`). A
  separate `.screenshot()` call returns per-page PNG bytes. `output_format` is
  only `"json"` or `"text"` — there is no Markdown serializer. Markdown, if
  wanted, must be produced downstream by Gemini.

Two structural facts drove the design:

1. **Liteparse pulls in heavy native binaries** — LibreOffice (hundreds of MB),
   ImageMagick, Tesseract. Embedding these in `vig-worker` would bloat the
   image by ~1GB and couple the core service to a stack of OS-level
   dependencies.
2. **Uploaded files have no URL.** Every existing cache is URL-keyed
   (`markdown_cache.url`, `github_repo_bundle:{owner}/{repo}`). Files need a
   content-derived key, and the same file can arrive from multiple users and
   multiple channels (Telegram now, web UI later).

This builds directly on [ADR-0022](0022-centralized-platform-storage.md):
storage is centralized and platform-owned (GCS), not the operator's personal
Drive.

## Decision

**1. Liteparse runs in its own `vig-document` sidecar container.**
This mirrors the `vig-transcript` sidecar (yt-dlp) and the weight-quarantine
reasoning of [ADR-0017](0017-notebooklm-push-forked-sidecar.md) (Chromium). The
sidecar owns LibreOffice/ImageMagick/Tesseract; `vig-worker` and `vig-api` stay
lean. The worker calls it over HTTP.

**2. The sidecar contract is: GCS object reference in, plain text out.**
The file is already in GCS at ingestion time, so the worker sends a reference
(not bytes); the sidecar pulls the bytes itself, runs `liteparse.parse()`, and
returns the layout-ordered **plain text** (`ParseResult.text`). The sidecar is
intentionally dumb — it parses only. Liteparse's spatial bounding-box JSON and
page screenshots are **not returned for MVP** (no delivery surface consumes
coordinates). Carrying the spatial JSON is deferred to a future dashboard PDF
viewer with source-highlighting.

**3. Two artifacts: plain text (auto) and Markdown (on-demand).**
Liteparse produces plain text, not Markdown (see Context). The two artifacts
serve different purposes:

- **Plain text (`.txt`) — the PRIMARY, portable, user-owned artifact.**
  Liteparse's raw layout-ordered text, cached and delivered automatically. It
  is neutral and tool-agnostic so the user can take it anywhere outside vig.
- **Markdown (`.md`) — VIG's structured rendering, produced ON DEMAND.** There
  is **no automatic Markdown rendering** — a `📄 Get Markdown` button is offered
  after delivery; tapping it runs a Gemini pass over the plain text to produce
  structured Markdown, caches it, and delivers the `.md`. This avoids spending
  a Gemini call for Markdown on every document — most users want only the text
  plus the enrichment.

Document **enrichment** (the document-specific Gemini analysis) still runs
**automatically** — it is the core vig value, consistent with every other
pipeline. Markdown rendering is a separate, optional, cached Gemini call.

**4. The GCS bucket IS the cache, keyed by content hash (SHA-256).**
- Raw file: `documents/{sha256}.{ext}`
- Parsed plain text: `parsed/{sha256}.txt` (always)
- Rendered Markdown: `parsed/{sha256}.md` (only after a `📄 Get Markdown` tap)

"Already parsed?" is a GCS exists-check on `parsed/{sha256}.txt`; "Markdown
already rendered?" is an exists-check on `parsed/{sha256}.md`. No separate
`markdown_cache`-style table. Direct file URLs are downloaded, hashed, and from
there identical to uploads. This gives automatic cross-user, cross-channel
dedup: a byte-identical PDF uploaded by three users parses once (and renders
Markdown at most once).

**5. Tenant isolation: shared parse, per-`chat_id` job rows.**
Content-hash dedup means the *parsed text/Markdown* is shared across users who
upload byte-identical files — acceptable, since it is purely derived from
identical bytes. But `jobs` rows remain strictly `chat_id`-scoped: ownership,
visibility, enrichment output, and Second Brain entries never cross tenants. The
shared layer is the derived parse only.

**6. The pipeline follows the article/repo pattern verbatim.**
- Routing: Telegram `message.document` (PDF/DOCX/PPTX/XLSX + image-as-file);
  direct file URLs via `detect_pipeline` extension-sniff + curated host patterns
  (arxiv) running before the article-allowlist check.
- `content_type = "document"`; worker task `{"task": "document"}`;
  `src/processors/document.py`.
- New services: `src/services/liteparse.py` (sidecar HTTP client, mirrors
  `transcript.py`) and `src/services/storage.py` (GCS wrapper).
- Document-specific enrichment schema: `title, author, publisher,
  document_type, summary, key_points, references[], tools[]`. Maps `title→title`,
  `summary→ai_objective`, `key_points→ai_action_points`, `tools→ai_tools`;
  `author`/`publisher`/`document_type`/`references` in `jobs.template_analysis`
  JSON blob ([ADR-0008](0008-template-analysis-json-blob.md)). No `promise_gap`
  (documents don't pitch — same reasoning as repos).
- Delivery: Telegram-only for MVP (send `.txt`, then the enrichment message,
  then buttons `[✍️ Freestyle] [📄 Get Markdown]`). Freestyle re-run reuses the
  `awaiting_freestyle` seam and the cached parse. `📄 Get Markdown` triggers the
  on-demand Markdown render (cached at `parsed/{sha256}.md`).
- Drive/Sheets writes are opt-in exports per ADR-0022 (new `Document Analysis`
  tab).

**7. Telegram's 20MB `getFile` cap is handled by rejection for MVP.**
Files over 20MB are rejected with *"📄 File too large for Telegram (max 20MB).
Upload via the web dashboard — feature coming soon."* A self-hosted
`telegram-bot-api` server (raises the cap to 2000MB, stays bot-based) is the
flagged upgrade path.

## Consequences

- **Pro:** `vig-worker`/`vig-api` images stay lean; the ~1GB native-binary
  stack is quarantined in `vig-document`.
- **Pro:** Storage and cache are one thing — a GCS exists-check replaces a DB
  cache table, and the raw file + parsed Markdown sit together.
- **Pro:** Automatic dedup across users and channels; expensive parsing happens
  once per unique file.
- **Pro:** The pipeline slots into existing patterns (`_dispatch`, Sheets tabs,
  Freestyle seam) with one genuinely new module (`storage.py`), which the
  platform-storage migration needs anyway.
- **Con:** A new always-on sidecar container to operate, monitor, and resource
  (LibreOffice is memory-hungry on large files).
- **Con:** GCS is now on the document-ingestion hot path; a GCS outage blocks
  document jobs (other pipelines unaffected).
- **Con:** Content-hash dedup requires hashing every uploaded file up front
  (cheap) and a clear privacy story (the shared-parse vs per-tenant-row split
  must hold).
- **Con:** Discarding spatial JSON now means re-parsing (or a contract change)
  if/when source-highlighting is built — acceptable, the parse is cached.

## Considered Alternatives

- **Liteparse inline in the worker** — Rejected: ~1GB of LibreOffice/
  ImageMagick/Tesseract in the core image, OS-dependency coupling. Same
  reasoning that sidecar-ed yt-dlp (`vig-transcript`) and Chromium (ADR-0017).
- **Jina Reader for documents too** (reuse the article transport) — Rejected:
  Jina parses web pages, not uploaded binaries, and mangles PDFs. Liteparse is
  purpose-built for document text extraction.

### Markdown-strategy alternatives (resolved after API verification)

Liteparse outputs plain text, not Markdown, so the Markdown deliverable had to
come from somewhere:

- **Plain text only, no Markdown** — Ship the `.txt` and stop. Rejected as the
  *sole* output: loses the structured Markdown some users want. **Adopted in
  part**: plain text IS the automatic primary artifact.
- **Auto Markdown via Gemini on every document** — Liteparse text → Gemini →
  Markdown for every job. Rejected: spends a Gemini call on every document when
  most users want only text + enrichment. **Adopted on-demand instead** (the
  `📄 Get Markdown` button).
- **Screenshots → Gemini Vision → Markdown** — Use liteparse `.screenshot()`
  page PNGs through the existing `call_gemini_vision`. Highest fidelity on
  visual docs/slides but highest cost, and it shrinks liteparse's role to
  OCR/screenshots. Rejected for MVP; revisit if text-based Markdown proves
  inadequate for slide-heavy decks.
- **Raw bytes over the wire to the sidecar** (transcript audio-fallback
  pattern) — Rejected: the file is already in GCS; round-tripping bytes through
  the worker is wasteful. GCS reference is leaner.
- **Personal Google Drive staging** — Rejected by ADR-0022 (SaaS storage is
  platform-owned GCS, not the operator's Drive).
- **Redis byte store / shared filesystem volume** — Rejected: Redis memory
  budget can't hold large PDFs/PPTXs; a shared volume breaks horizontal scaling
  and doesn't serve the future web-upload channel cleanly.
- **URL-keyed cache (mirror `markdown_cache`)** — Rejected: uploads have no
  URL, and a URL key misses cross-user dedup of identical files.
- **MTProto user-session for large files** (e.g. Telegram-Drive / Telethon /
  Pyrogram user login) — Rejected: reintroduces the ToS-gray, account-
  suspension, throwaway-account risk profile quarantined in ADR-0017. The
  self-hosted Bot API server reaches the same goal while staying bot-based.
- **Content-type HEAD-sniff for direct URL routing** — Rejected: adds a network
  round-trip to the synchronous, network-free `detect_pipeline` router.

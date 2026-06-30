---
adr: "0029"
title: Doc Parser dashboard page — web upload, Gemini-as-transformer, SSE status
status: accepted
date: 2026-06-25
---

## Context

The document pipeline (ADR-0023) ships end-to-end but is Telegram-only: PDFs
enter via bot upload or URL message, and results are delivered exclusively to
Telegram. There is no web surface for uploading, viewing, or managing document
jobs. Meanwhile, Gemini's role in the pipeline is **analyzer-only** — it
extracts metadata (title, summary, key points, tools, references) into a JSON
card, but the parsed `.txt`/`.md` files are raw liteparse output untouched by
Gemini. Users who click "Freestyle" get back the same raw parse with different
metadata extraction, not a transformed document.

Two gaps to close:

1. **No dashboard entry point.** The feed page has tabs for short/long/article/
   repo but no document tab, and no way to upload from the web.
2. **Gemini doesn't transform.** The enrichment summary is a metadata sidecar;
   users expect Gemini to produce new documents — a structured summary, a
   cleaned version, or a freestyle-prompted output.

This ADR extends ADR-0023 with a new dashboard page and a richer Gemini output
model.

## Decision

### 1. New page: `/doc-parser` ("Doc Parser")

A new dashboard route at `/doc-parser` with a sidebar entry directly below Feed,
using the `FileCodeCorner` Lucide icon.

**Layout (desktop):**
- **Top bar:** Format tabs (PDF active; Word, Spreadsheet, Presentation, Image
  greyed out until format support lands) with counters + search bar. Status
  filter pills (All / Done / Pending / Processing / Error). Recovery bar (stale
  in-flight, Retry pending, Retry failed, Clear failed).
- **Left half:** URL text input on top, file dropzone underneath.
- **Right half:** Job list — each row shows title, status badge, tags, file-type
  badges (enriched outputs decorated with a sparkle icon), and a per-job
  Telegram toggle.

**Layout (mobile):** Upload area collapses to a compact bar (same pattern as
`/controls`); job list takes full width; tap to expand the upload area.

### 2. Two REST upload endpoints

- `POST /api/parsed/upload` — multipart file upload (PDF, 20 MB cap).
- `POST /api/parsed/url` — JSON body `{ "url": "..." }`.

Both replicate the Telegram ingestion logic: validate → SHA-256 hash → GCS
upload (`documents/<sha>.pdf`) → create job (`content_type="document"`) →
enqueue `{"task": "document"}`. The `chat_id` is taken from the authenticated
dashboard session (1:1 Telegram-to-dashboard user mapping).

Error handling: field-level validation errors (wrong format, too large) on the
input element; system errors (GCS, network) as a dismissable toast.

### 3. Gemini as transformer — three output types

Gemini's role expands from metadata-only to producing new documents:

- **Structured summary** (auto, part of pipeline): Gemini reads the full parsed
  text and generates a new `.md` briefing — title, TL;DR, key sections,
  takeaways, references. Runs automatically on every document job. Stored at
  `enriched/<sha>_summary.md`.
- **Clean version** (on-demand button): Gemini takes the raw parsed text (often
  messy from PDF extraction — broken lines, lost formatting, merged columns) and
  produces a clean, properly formatted markdown of the *same content*. Stored at
  `enriched/<sha>_clean.md`.
- **Freestyle** (on-demand button): User provides a custom prompt; Gemini
  generates a new `.md` based on that prompt. Each run is stored separately at
  `enriched/<sha>_freestyle_<timestamp>.md`. All freestyle outputs accumulate as
  history — the detail page shows every run, not just the latest.

Metadata extraction (title, author, summary, key points, tools, references)
continues alongside the structured summary — the existing enrichment card is
preserved.

### 4. Freestyle modal with random + saved prompts

The freestyle button opens a modal with:

- A text area pre-filled with a random prompt from a hardcoded pool (e.g.,
  "Summarize into the 5 most important takeaways", "Extract all actionable steps
  as a checklist", "Explain this to a non-technical person").
- A shuffle button to roll a new random prompt.
- A dropdown to select from the user's saved prompts (from the existing
  templates system on `/prompts`).

Two prompt layers: hardcoded general-purpose prompts (frontend constant array)
and user-managed prompts (persisted in the templates/prompts backend).

### 5. Detail page at `/doc-parser/[id]`

Clicking a job row navigates to `/doc-parser/[id]` (same pattern as
`/jobs/[id]`). Contents:

- **Output cards:** Every output (parsed text, structured summary, clean
  version, each freestyle run) is presented as a card with a scrollable preview
  of the first few lines and an expand icon that opens the full content in a new
  browser tab.
- **Action buttons:** Clean, Freestyle, Get Markdown (raw parse).
- **Freestyle modal** (as described above).
- **Download/export actions**, link to original PDF in GCS, Sheets row link.
- **Telegram toggle** (same three-state icon as the job row).

### 6. Per-job Telegram toggle (three-state)

A Telegram icon on each job row and detail page with three states:

- **Grey:** Off — nothing sent to Telegram.
- **Colored:** On — future outputs sent to Telegram (source PDF + parsed `.txt`
  + structured summary `.md`).
- **Colored + glow (long-press):** Retroactive — sends all existing outputs now
  + future ones, then drops to colored state.

The glow state activates via a **1.5-second press-and-hold**: a radial
clock-fill animation progressively fills the icon border; releasing early resets
(nothing sent). On completion: haptic feedback on mobile, a toast confirms
("Sent N outputs to Telegram"), and the icon drops to regular colored state.

Persisted per job as a new `telegram_delivery` column on the `jobs` table.

On-demand actions (Clean, Freestyle) also respect the toggle — if colored, the
new output is sent to Telegram immediately after generation.

### 7. SSE for real-time status, REST for actions

- **SSE endpoint** (e.g., `GET /api/parsed/events`): Pushes job status
  transitions (`pending → processing → done`, error) to the connected client.
  Uses FastAPI `StreamingResponse` with `text/event-stream`.
- **REST for all actions:** Upload, trigger clean/freestyle, toggle Telegram
  delivery. SSE is unidirectional (server → client only).

This avoids WebSocket complexity while keeping the page responsive. If
bidirectional needs emerge later (e.g., collaborative features), migrating to
WebSocket is straightforward.

### 8. GCS storage layout for enriched outputs

Extends the existing `documents/` and `parsed/` prefixes:

| Key pattern                               | Content                      |
| ----------------------------------------- | ---------------------------- |
| `documents/<sha>.pdf`                     | Source PDF (existing)         |
| `parsed/<sha>.txt`                        | Raw parsed text (existing)   |
| `parsed/<sha>.md`                         | Raw parsed markdown (existing) |
| `enriched/<sha>_summary.md`               | Gemini structured summary    |
| `enriched/<sha>_clean.md`                 | Gemini cleaned version       |
| `enriched/<sha>_freestyle_<timestamp>.md` | Gemini freestyle output      |

## Consequences

- **Pro:** The document pipeline gains a full web surface — upload, status
  tracking, output viewing — without breaking the existing Telegram flow.
- **Pro:** Gemini evolves from metadata-only to producing user-facing documents
  (summary, clean, freestyle), making the pipeline significantly more useful.
- **Pro:** The three-state Telegram toggle gives users fine-grained control over
  cross-channel delivery without clutter.
- **Pro:** SSE is simpler than WebSocket for the unidirectional status-push
  need; migration path to WebSocket is clean if needed later.
- **Con:** New SSE endpoint adds connection management and cleanup logic that
  doesn't exist in the codebase yet.
- **Con:** Three Gemini output types (summary auto, clean on-demand, freestyle
  on-demand) increase Gemini API cost per document vs. the metadata-only
  baseline.
- **Con:** Freestyle history accumulates unbounded GCS objects per SHA; may need
  a retention policy or cap in the future.
- **Con:** The long-press interaction (three-state toggle) requires custom
  component work and is harder to discover than a simple toggle; the radial
  animation adds frontend complexity.

## Considered Alternatives

- **Document tab in the existing feed page** — Rejected: the feed is read-only
  with no upload surface, and document jobs need their own upload UX, format
  tabs, and output card layout that don't fit the feed's grid/list pattern.
- **WebSocket instead of SSE** — Deferred: WebSocket is bidirectional but all
  client→server actions are standard REST calls. SSE covers the unidirectional
  status-push need at lower complexity. WebSocket is the upgrade path if
  bidirectional streaming is needed.
- **Polling (like the feed page)** — Rejected: the feed's 10-second poll works
  but is wasteful and less responsive. SSE is a better fit for a page where
  users upload and wait for results.
- **Global Telegram toggle on upload form** — Rejected: per-job toggle is more
  flexible. Users may want Telegram delivery for some documents but not others,
  and may decide after seeing results rather than at upload time.
- **Simple on/off Telegram toggle** — Rejected: a two-state toggle forces the
  user to choose between "send everything retroactively" (noisy, accidental) or
  "future only" (misses existing outputs). The three-state design with
  long-press guard solves both without accidental spam.

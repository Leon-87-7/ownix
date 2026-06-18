# Handoff — Document pipeline fast-follow (#156, #157, #158)

**Status:** not started. Follows the MVP, which shipped in PR
<https://github.com/Leon-87-7/vig/pull/182>.

**Read first (not repeated here):**

- MVP scope + decisions: [`document-pipeline-mvp.md`](document-pipeline-mvp.md)
  (esp. decision #1 = these three are the fast-follow, decision #5 = buttons
  deferred until their handlers exist).
- Pipeline scope: [ADR-0023](../adr/0023-liteparse-document-pipeline.md).
- Sheets tab routing / column convention: ADR-0013.
- Column-reuse pattern for enrichment: ADR-0008.
- Built MVP code these extend: `src/processors/document.py`,
  `src/telegram/webhook.py`, `src/services/{storage,parse}.py`.

This file only records the **net-new seams** each issue needs. Mirror the
article pipeline's equivalents — they already do all three.

---

## #157 — `✍️ Freestyle` re-run (do this first; #155 already left the hook)

`document.run(job, *, skip_document=False)` already takes the freestyle-shaped
signature but ignores `freestyle_prompt`. Three small edits, all mirroring
article:

1. **Prompt:** `_build_document_prompt(text)` → add a `freestyle_prompt` arg and
   append it, exactly like `article._build_article_prompt` (`article.py:101`).
2. **Re-run wiring:** `webhook._handle_awaiting_freestyle` (`webhook.py:861`) has
   a per-`content_type` enqueue ladder — it has no `document` branch, so a
   freestyle reply on a document job silently does nothing. Add
   `elif job.content_type == "document": enqueue({"task":"document",...})`.
3. **Button:** add the `✍️ Freestyle` inline button to `document._deliver`'s
   summary send, reusing callback `template_freestyle:{job_id}` — the callback
   handler `_cb_template_freestyle` (`webhook.py:191`) is content-type-agnostic
   and already arms `awaiting_freestyle`, so no callback changes needed.

Freestyle re-run must **skip re-parse** — the parsed text is cached at
`parsed/<sha>.txt`, so `run` already serves it from cache on the second pass.
No `skip_document` plumbing needed beyond what exists.

## #156 — `📄 Get Markdown` button + on-demand markdown

- liteparse **does** emit markdown: `LiteParse(output_format="markdown", ...)`
  (verified on the 2.0.7 wheel — the `output_format` init kwarg). Add a
  `parse_pdf_markdown(data)` alongside `parse_pdf` in `src/services/parse.py`,
  or parametrise the existing one.
- Cache key already reserved: `storage.object_key("parsed", sha, "md")`
  (the `.md` shape — the MVP removed only its *docstring mention*, the helper
  takes any ext).
- Button callback is new (no existing analog). Add a `document_md:{job_id}`
  callback in the `webhook.py` dispatch table (`webhook.py:343` neighbourhood):
  derive sha from the job's `url` (`documents/<sha>.pdf`), serve
  `parsed/<sha>.md` from GCS if present else parse-to-md + upload, then
  `send_document(.md)`. The sha→key→`storage.exists`/`download`/`upload` dance
  is identical to `document.run`'s cache block — factor that into a shared
  `_cached_parse(sha, ext, parser)` helper in `document.py` and call it from
  both the processor and the button.

## #158 — Drive/Sheets export

The document processor has **no** Sheets/Drive write yet (article's
`run` fires `_sheets_task` at `article.py:322`; document's `run` does not).

- **Sheets:** add `append_document_row` / `update_document_row` +
  `_document_row(job)` to `src/services/sheets.py` (mirror `_article_row` /
  `append_article_row` at `sheets.py:218`), pick a tab name per ADR-0013, and
  fire a fire-and-forget `_sheets_task` from `document.run` after the `done`
  update — copy article's task verbatim incl. the `sheets_row_id` write-back so
  freestyle re-runs overwrite the row instead of appending.
- **Drive:** documents already live in GCS, not Drive. Decide whether #158 means
  "also copy the source PDF / parsed text into the Drive folder" (needs a new
  `GOOGLE_DRIVE_FOLDER_*` setting + a Drive upload akin to the video/article
  Drive writes) or just the Sheets index. Resolve this in the issue before
  building — the MVP deliberately routed storage to GCS, so Drive is additive,
  not a move.

---

## Notes

- Keep delivery guarded (the `_deliver` try/except pattern) — a Sheets/Drive or
  button-send failure must never roll back `done`.
- No new migration: `freestyle_prompt`, `template_analysis`, `sheets_row_id`
  columns all already exist and the `document` content_type is live as of #151.
- Run tests via `rtk proxy python -m pytest` from the repo root (`vig/`, not
  `vig/web/`).

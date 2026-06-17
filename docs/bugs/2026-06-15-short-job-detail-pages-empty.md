# Bug: Short-pipeline job detail pages render empty (long pipeline populates fine)

- **Reported:** 2026-06-15
- **Area:** Job detail page + `GET /api/jobs/{id}` + short-video pipeline
- **Severity:** High — short jobs are the majority of the feed (110 / 174) and their detail pages carry no analysis.

## Symptoms

The job detail page populates for **long** jobs but is empty for **short** jobs.

- Populated (long): `https://app.leondev.xyz/jobs/20260608_182431_DEFFF2A0`
- Empty (short): `https://app.leondev.xyz/jobs/20260615_165551_C5A97190`

A short job's detail page shows only the header (title/URL/badges) and, at most,
the "Open in Drive" link — no analysis cards.

## Root cause

The detail page and its API are built **exclusively around the long/article
enrichment schema**. The short pipeline never writes those columns.

### What the detail page renders

`web/lib/job-detail-utils.ts:5` — `ENRICHMENT_FIELDS` is the only thing the page
body renders (`web/app/(dashboard)/jobs/[id]/page.tsx:203` filters to the present
ones):

```
ai_topic, ai_objective, ai_action_points, ai_tools, ai_market_data,
promise_gap, template_analysis
```

### What the API returns

`src/api/jobs.py:269` — `_DETAIL_FIELDS` returns the same `ai_*` columns plus
`template_analysis` and `template`. Notably it does **not** include `transcript`,
`key_phrases`, `platform`, or `video_id`.

### What each pipeline actually writes

- **Long** (`src/processors/long_video.py` Phase 1 → `src/processors/enrichment.py:517`):
  the Phase-2 Gemini step writes `ai_category/ai_topic/ai_objective/ai_action_points/
  ai_tools/ai_market_data/template_analysis/promise_gap`. So an **enriched** long job
  fills every field the page renders. (Note: a long job that stopped at
  `transcript_done` and never had "Run Gemini" pressed would *also* be empty — same
  underlying coupling.)

- **Short** (`src/processors/short_video.py`): writes only `drive_url`, `title`,
  `processing_time_ms`, `best_frame_index`, `platform`, `video_id`, and later
  `transcript` + `key_phrases` (`short_video.py:348`). The Gemini **vision summary**
  (`summary`, `short_video.py:213`) is uploaded to the Drive markdown only
  (`_build_analysis_markdown`) and **never persisted to a DB column**.
  `template_analysis` is written **only when the job has a template attached**
  (`short_video.py:304`); plain short jobs have none.

So for a typical short job (no template): every field in `ENRICHMENT_FIELDS` is
NULL → the page body is empty. Even the data that *is* persisted (`transcript`,
`key_phrases`) never reaches the client because it isn't in `_DETAIL_FIELDS` and the
page has no renderer for it.

## Suggested fix direction (not yet implemented)

Two viable approaches:

1. **Give short jobs a detail schema of their own.** Persist the vision `summary`
   to a queryable column, add `summary`/`transcript`/`key_phrases`/extracted-links to
   `_DETAIL_FIELDS`, and render a short-specific field set on the detail page keyed off
   `content_type === "short"`.

2. **Map short outputs onto the shared `ai_*` schema** (e.g. vision summary →
   `ai_topic`/`ai_objective`) so the existing renderer just works. Lower frontend
   cost, but conflates "AI enrichment" semantics across pipelines.

Approach 1 is cleaner given the schemas genuinely differ. Either way the detail page
should stop assuming the long/article field set is universal.

## Files involved

- `web/app/(dashboard)/jobs/[id]/page.tsx:203` — renders only `ENRICHMENT_FIELDS`
- `web/lib/job-detail-utils.ts:5` — `ENRICHMENT_FIELDS` definition
- `web/lib/hooks/useJobDetail.ts:5` — `JobDetail` type (no short fields)
- `src/api/jobs.py:269` — `_DETAIL_FIELDS` (no short fields)
- `src/processors/short_video.py:213,234,304,348` — what short actually persists
- `src/processors/enrichment.py:517` — where long fills the `ai_*` columns

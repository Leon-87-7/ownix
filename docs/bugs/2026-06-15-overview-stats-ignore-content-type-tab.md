# Bug: Overview status cards always show global counts, not the active tab's

- **Reported:** 2026-06-15
- **Area:** Overview stat cards + `GET /api/jobs/stats` + `useFeedData`
- **Severity:** Medium — the headline numbers contradict the tab the user is viewing.

## Symptoms

The Overview cards (Total / Done / Pending / Error / Processing) stay fixed on the
**global** totals across all content types, regardless of which content-type tab
(Short / Long / Article / Repo) is selected.

Expected: selecting a tab should scope the cards to that type. E.g. on the **Article**
tab with 9 jobs — 3 done, 1 pending, 0 processing, 5 error — the cards should read
Total 9 / Done 3 / Pending 1 / Processing 0 / Error 5. Today they keep showing the
whole-feed numbers (Total 175, etc.).

> Scope note: this is about the **content-type tab** (Short/Long/Article/Repo)
> driving the cards. The status pills (All/Done/Pending/Processing/Error) are a
> separate filter and should *not* collapse the cards — the cards should still show
> the full status breakdown for the selected content type.

## Root cause

The stats endpoint computes counts over **all** of the user's jobs and takes no
content-type argument:

- `src/api/jobs.py:27` — `get_job_stats` runs
  `SELECT status, COUNT(*) ... WHERE chat_id = ? GROUP BY status` with no
  `content_type` predicate.
- `web/lib/hooks/useFeedData.ts:22` — `fetchFeed` calls `fetch('/api/jobs/stats')`
  with no query params, even though it already knows `ct`.
- `web/components/feed/stats-overview.tsx:4` then renders those global numbers.

So the cards can never reflect the active tab — the data to do so is never requested.

## Suggested fix direction (not yet implemented)

1. Add an optional `content_type` query param to `GET /api/jobs/stats`
   (`src/api/jobs.py:27`) and apply it to the `WHERE` clause of the status-breakdown
   query. Keep the `by_content_type` breakdown unfiltered so the tab count chips stay
   correct. Filter by `content_type` only — **not** by `status` — so the cards always
   show the full status split for the selected type.
2. In `fetchFeed` (`web/lib/hooks/useFeedData.ts:22`), pass the current `ct` to the
   stats request (mirror the jobs request). When no tab is active, omit it for global
   totals.
3. `StatsOverview` needs no change — it just consumes whatever breakdown it's handed.

Note the "Processing" card already aggregates `processing + enriching +
transcript_done` (`stats-overview.tsx:15`); that aggregation should be preserved
under the scoped counts.

## Interaction with the tab-filter race

The fetch-sequencing gap described in
[`2026-06-15-feed-tab-shows-wrong-content-types.md`](./2026-06-15-feed-tab-shows-wrong-content-types.md)
applies to `setStats` too. Once stats become tab-scoped, an out-of-order stats
response could show the wrong tab's numbers — so the request-sequencing guard should
cover the stats setter as well, not just the jobs list.

## Files involved

- `src/api/jobs.py:27` — `get_job_stats` (no content_type filter)
- `web/lib/hooks/useFeedData.ts:22` — `fetchFeed` (stats fetched without `ct`)
- `web/components/feed/stats-overview.tsx:4` — renders the (global) breakdown
- `web/app/(dashboard)/page.tsx:70` — mounts `StatsOverview`

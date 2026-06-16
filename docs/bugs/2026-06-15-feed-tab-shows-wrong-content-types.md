# Bug: Feed content-type tab shows cards of other types (e.g. Short tab shows Long/Repo)

- **Reported:** 2026-06-15
- **Area:** Feed page data fetching (`web/lib/hooks/useFeedData.ts`)
- **Severity:** Medium — intermittent; misleads the user about what's in a tab.

## Symptoms

While on the **Short** tab, Long and Repo job cards sometimes appear in the list.
Intermittent — depends on timing of tab switches and the background poll.

## Root cause

Server-side filtering is correct (`src/api/jobs.py:146` filters
`content_type = ?`), so the bug is entirely client-side: **the feed has no
request-sequencing guard, so a stale response can overwrite fresh state.**

`web/lib/hooks/useFeedData.ts` has two independent fetch paths that both call
`setJobs(...)` with no "latest request wins" check and no abort:

- `load(ct, st)` — fires from a `useEffect` on `[ctFilter, stFilter]`
  (`useFeedData.ts:75`) whenever the user switches tabs.
- `reload()` — fired every 10s by `useInFlightPolling` while any job is
  pending/processing (`web/lib/hooks/useInFlightPolling.ts:20`), reading the
  current filter from `ctRef`/`stRef`.

Two failure modes, both producing wrong-type cards:

1. **Stale list shown during the in-flight fetch.** `load` calls `setLoading(true)`
   but does **not** clear `jobs`. The previous tab's list (which can include all
   content types, e.g. coming from "All") stays rendered until the new fetch
   resolves. The list is driven purely by the server filter — `useFuseSearch` does
   no client-side type filtering when the query is empty
   (`web/lib/hooks/useFuseSearch.ts`) — so nothing hides the mismatched cards in
   the meantime.

2. **Out-of-order resolution (the real bug).** When switching All → Short quickly,
   or when a background `reload()` started under the old filter is still in flight,
   two requests race. There is no request id / generation counter, so whichever
   response resolves **last** wins — not whichever was **requested** last. If the
   older "All" (or previous-tab) response lands after the "Short" response,
   `setJobs` repaints the Short tab with all-type cards and they persist until the
   next refetch.

## Suggested fix direction (not yet implemented)

- Add a monotonically increasing request id (or `AbortController`) in `useFeedData`
  shared by both `load` and `reload`; ignore/abort any response that isn't from the
  latest dispatched request before calling `setJobs`/`setStats`/`setTotal`.
- Optionally clear `jobs` (or gate rendering on a `loading` of the *current* filter)
  on filter change so a stale list isn't shown during the in-flight fetch.
- Defensive belt-and-suspenders: when a content-type filter is active, drop any item
  whose `content_type` doesn't match before rendering, so a race can never surface
  the wrong type.

## Files involved

- `web/lib/hooks/useFeedData.ts:44` — `load` (no sequencing guard, no list clear)
- `web/lib/hooks/useFeedData.ts:64` — `reload` (background poll, same setters)
- `web/lib/hooks/useInFlightPolling.ts:20` — 10s poll that calls `reload`
- `web/app/(dashboard)/page.tsx:32` — wires the hook to the tabs
- `src/api/jobs.py:146` — server filter (correct; confirms bug is client-side)

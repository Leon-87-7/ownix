'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { JobSummary } from '@/components/feed/job-card';
import type { FeedScope } from '@/lib/feed-scope';

export interface FeedStats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
  /** Global per-tag job counts. The only source of the filter dropdown's counts
   * past CLIENT_MODE_LIMIT, where the browser isn't holding the jobs to count. */
  by_tag?: Record<string, number>;
}

interface JobsResponse {
  items: JobSummary[];
  total: number;
}

// The guardrail threshold from CONTEXT.md §92: client-side model holds to ~1000 jobs.
const CLIENT_MODE_LIMIT = 1000;

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchAllJobs(restricted = false): Promise<{ jobs: JobSummary[]; total: number }> {
  const res = await fetch(`${restricted ? '/api/preview/jobs' : '/api/jobs'}?limit=${CLIENT_MODE_LIMIT}`);
  if (!res.ok) throw new Error('Failed to load jobs');
  const data = (await res.json()) as JobsResponse;
  return { jobs: data.items, total: data.total };
}

async function fetchStats(restricted = false): Promise<FeedStats> {
  const res = await fetch(restricted ? '/api/preview/jobs/stats' : '/api/jobs/stats');
  if (!res.ok) throw new Error('Failed to load stats');
  return (await res.json()) as FeedStats;
}

/** Server-side fetch used in server mode (>1000 jobs) or for the fallback reload. */
async function fetchFeedServerMode(
  ct: string,
  st: string,
  restricted = false,
  checklistOnly = false,
  tagIds: string[] = [],
): Promise<{ stats: FeedStats; jobs: JobSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (ct) params.set('content_type', ct);
  if (st) params.set('status', st);
  // Backed by jobs.link_id since the job->link key is persisted, so tag
  // narrowing means the same thing here as it does client-side.
  if (tagIds.length) params.set('tags', tagIds.join(','));
  // Server-side so the count stays truthful past CLIENT_MODE_LIMIT, where the
  // client only holds one 50-row page and can't filter the rest.
  if (checklistOnly) params.set('has_checklist', 'true');
  params.set('limit', '50');

  // Stats scoped by content_type only — never status, never the checklist
  // toggle — so Overview cards show the full split for the active tab rather
  // than collapsing to whatever narrowing is on. Omit for global totals.
  // `deriveStats` deliberately mirrors this in client mode.
  const statsParams = new URLSearchParams();
  if (ct) statsParams.set('content_type', ct);
  const statsQuery = statsParams.toString();

  const [statsRes, jobsRes] = await Promise.all([
    fetch(statsQuery ? `${restricted ? '/api/preview/jobs/stats' : '/api/jobs/stats'}?${statsQuery}` : (restricted ? '/api/preview/jobs/stats' : '/api/jobs/stats')),
    fetch(`${restricted ? '/api/preview/jobs' : '/api/jobs'}?${params}`),
  ]);
  if (!statsRes.ok) throw new Error('Failed to load stats');
  if (!jobsRes.ok) throw new Error('Failed to load jobs');
  const [stats, jobsData] = await Promise.all([
    statsRes.json() as Promise<FeedStats>,
    jobsRes.json() as Promise<JobsResponse>,
  ]);
  return { stats, jobs: jobsData.items, total: jobsData.total };
}

// ---------------------------------------------------------------------------
// Client-mode derivation helpers
// ---------------------------------------------------------------------------

/**
 * Filter the full job list by content_type and status (exact match —
 * matching the server-side WHERE status = ? semantics).
 *
 * `tagIds` narrows with OR semantics (a job matches if it carries ANY selected
 * tag) — client-mode only; server-mode has no backend support for this yet
 * (job→link resolution isn't SQL-joinable, see useFeedData's serverMode gap).
 */
function deriveJobs(
  allJobs: JobSummary[],
  ct: string,
  st: string,
  checklistOnly: boolean,
  tagIds: string[],
): JobSummary[] {
  let list = allJobs;
  if (ct) list = list.filter((j) => j.content_type === ct);
  if (st) list = list.filter((j) => j.status === st);
  if (checklistOnly) list = list.filter((j) => Boolean(j.checklists_generated_at));
  if (tagIds.length) list = list.filter((j) => j.tags?.some((t) => tagIds.includes(t.id)));
  return list;
}

/** {tag id: how many loaded jobs carry it} — powers the usage count shown per
 * row in the tag filter dropdown. Always computed off the full unfiltered
 * `allJobs`, not the narrowed list, so picking one tag doesn't change another
 * tag's displayed count. */
function deriveTagCounts(allJobs: JobSummary[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const job of allJobs) {
    for (const tag of job.tags ?? []) {
      counts[tag.id] = (counts[tag.id] ?? 0) + 1;
    }
  }
  return counts;
}

/**
 * Derive FeedStats from the in-memory job list.
 *
 * - `by_content_type`: always global (all jobs) — powers tab count chips.
 * - `by_status`: scoped to the active content_type (matching what the server
 *   returns when you pass content_type to /api/jobs/stats) — powers Overview cards.
 * - `total`: sum of by_status values for the scoped slice (matching server behaviour).
 *
 * Takes `ct` and nothing else on purpose: status and the checklist toggle both
 * narrow the *list*, never the Overview cards, so the cards keep showing what
 * the tab holds. `fetchFeedServerMode` scopes its stats request the same way.
 */
function deriveStats(allJobs: JobSummary[], ct: string): FeedStats {
  const by_content_type: Record<string, number> = {};
  for (const j of allJobs) {
    by_content_type[j.content_type] = (by_content_type[j.content_type] ?? 0) + 1;
  }

  const scopedJobs = ct ? allJobs.filter((j) => j.content_type === ct) : allJobs;
  const by_status: Record<string, number> = {};
  for (const j of scopedJobs) {
    by_status[j.status] = (by_status[j.status] ?? 0) + 1;
  }
  const total = scopedJobs.length;

  return { total, by_status, by_content_type };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Feed data for a given narrowing.
 *
 * The scope is a parameter, not state owned here: the Feed page holds it and
 * projects it onto the URL, so there is exactly one copy of "what is the user
 * looking at". This hook used to own `ctFilter`/`stFilter`/... and hand back
 * setters, which meant the same narrowing lived in two places and had to be
 * reconciled by effects on every change.
 */
export function useFeedData(scope: FeedScope, restricted = false) {
  const ctFilter = scope.contentType ?? '';
  const stFilter = scope.status ?? '';
  const checklistOnly = scope.checklistOnly ?? false;
  const tagFilter = useMemo(() => scope.tags ?? [], [scope.tags]);
  // Effects below key on this rather than the array identity: a caller that
  // rebuilds its scope object each render would otherwise re-fetch forever.
  const tagKey = tagFilter.join(',');

  // The full unfiltered job list (client mode) or the per-filter list (server mode).
  const [allJobs, setAllJobs] = useState<JobSummary[]>([]);
  // The server preload component always uses the first unfiltered jobs. Keep
  // their positions even in server mode, where the rendered list is filtered.
  const [preloadJobs, setPreloadJobs] = useState<JobSummary[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Whether we're in server mode (total > CLIENT_MODE_LIMIT at mount time).
  const [serverMode, setServerMode] = useState(false);

  // Server-mode only: per-filter stats fetched on each filter change.
  const [serverStats, setServerStats] = useState<FeedStats | null>(null);
  // Server-mode only: filtered job list from server.
  const [serverJobs, setServerJobs] = useState<JobSummary[]>([]);
  const [serverFilteredTotal, setServerFilteredTotal] = useState(0);

  // Monotonic request-id counter: every dispatch increments before await;
  // response is discarded if the captured id no longer matches the latest.
  const reqIdRef = useRef(0);

  // Separate counter that only the initial mount load bumps, used solely to
  // gate the loading flag (mirrors the original loadIdRef pattern so a slow
  // background reload() can never strand loading=true).
  const loadIdRef = useRef(0);

  // reload() is called by background polling and must always read the current
  // narrowing without being re-created (and re-subscribed) on every change.
  const scopeRef = useRef({ ctFilter, stFilter, checklistOnly, tagFilter });
  scopeRef.current = { ctFilter, stFilter, checklistOnly, tagFilter };
  const serverModeRef = useRef(serverMode);
  serverModeRef.current = serverMode;

  // -------------------------------------------------------------------------
  // Initial mount fetch (client mode path)
  // -------------------------------------------------------------------------

  const mountLoad = useCallback(async () => {
    const reqId = ++reqIdRef.current;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);

    try {
      const [{ jobs, total }, stats] = await Promise.all([
        fetchAllJobs(restricted),
        fetchStats(restricted),
      ]);

      if (reqId !== reqIdRef.current) return;

      if (total > CLIENT_MODE_LIMIT) {
        // Server mode: too many jobs to hold client-side.
        // Populate from the already-fetched list; filter changes will re-fetch.
        setServerMode(true);
        setServerJobs(jobs);
        setServerFilteredTotal(total);
        setServerStats(stats);
      } else {
        setServerMode(false);
        setAllJobs(jobs);
      }
      setPreloadJobs(jobs);
    } catch (e) {
      if (reqId !== reqIdRef.current) return;
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      if (loadId === loadIdRef.current) setLoading(false);
    }
  }, [restricted]);

  // -------------------------------------------------------------------------
  // Server-mode filter fetch (called on filter change when in server mode)
  // -------------------------------------------------------------------------

  const serverLoad = useCallback(
    async (ct: string, st: string, checklist: boolean, tags: string[]) => {
    const reqId = ++reqIdRef.current;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);

    try {
      const { stats, jobs, total } = await fetchFeedServerMode(
        ct,
        st,
        restricted,
        checklist,
        tags,
      );
      if (reqId !== reqIdRef.current) return;

      const filtered = ct ? jobs.filter((j) => j.content_type === ct) : jobs;
      setServerStats(stats);
      setServerJobs(filtered);
      setServerFilteredTotal(total);
    } catch (e) {
      if (reqId !== reqIdRef.current) return;
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      if (loadId === loadIdRef.current) setLoading(false);
    }
  }, [restricted]);

  // -------------------------------------------------------------------------
  // reload() — called by polling (issue #177 background poll triggers this)
  // -------------------------------------------------------------------------

  const reload = useCallback(async () => {
    // Background poll: increment reqIdRef so a concurrent load() dispatched
    // after this poll does not get clobbered by a slow poll response.
    const reqId = ++reqIdRef.current;

    try {
      if (serverModeRef.current) {
        // Server mode: re-fetch with current filters.
        const current = scopeRef.current;
        const { stats, jobs, total } = await fetchFeedServerMode(
          current.ctFilter,
          current.stFilter,
          restricted,
          current.checklistOnly,
          current.tagFilter,
        );
        if (reqId !== reqIdRef.current) return;
        const ct = current.ctFilter;
        const filtered = ct ? jobs.filter((j) => j.content_type === ct) : jobs;
        setServerStats(stats);
        setServerJobs(filtered);
        setServerFilteredTotal(total);
      } else {
        // Client mode: silently re-fetch the full list, swap allJobs.
        // No loading flag flip — no skeleton, active filter/search survive.
        const { jobs } = await fetchAllJobs(restricted);
        if (reqId !== reqIdRef.current) return;
        setAllJobs(jobs);
        setPreloadJobs(jobs);
      }
    } catch {
      // swallow during background polling
    }
  }, [restricted]);

  // -------------------------------------------------------------------------
  // Effects
  // -------------------------------------------------------------------------

  // Mount: run the initial fetch once.
  useEffect(() => {
    mountLoad();
  }, [mountLoad]);

  // Tracks whether the server-mode effect has already consumed its first run.
  // mountLoad populates serverJobs/serverStats/serverFilteredTotal directly when
  // it flips serverMode on, so the run triggered by that flip must NOT call
  // serverLoad — doing so would double-fetch, re-flip loading=true (skeleton
  // re-flash), and overwrite the mount data with a paginated 50-item page.
  const serverEffectPrimedRef = useRef(false);

  // Server-mode filter change: re-fetch from server when filters change.
  // In client mode this effect does nothing (no API call on filter change).
  useEffect(() => {
    if (!serverMode) return;
    if (!serverEffectPrimedRef.current) {
      serverEffectPrimedRef.current = true;
      // mountLoad populated server state from an *unfiltered* probe. Skip the
      // redundant serverLoad on the mount-time mode flip ONLY when no filter is
      // active — otherwise (e.g. a deep link carrying ?type=short) the mount
      // data is unscoped, so we must fetch the filtered view rather than show
      // the wrong list.
      if (!ctFilter && !stFilter && !checklistOnly && !tagFilter.length) return;
    }
    serverLoad(ctFilter, stFilter, checklistOnly, tagFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverMode, ctFilter, stFilter, checklistOnly, tagKey, serverLoad]);

  // -------------------------------------------------------------------------
  // Derived state (client mode only — computed synchronously, no fetch)
  // -------------------------------------------------------------------------

  const derivedJobs = useMemo(
    () =>
      serverMode ? null : deriveJobs(allJobs, ctFilter, stFilter, checklistOnly, tagFilter),
    [serverMode, allJobs, ctFilter, stFilter, checklistOnly, tagFilter],
  );

  const derivedStats = useMemo(
    () => (serverMode ? null : deriveStats(allJobs, ctFilter)),
    [serverMode, allJobs, ctFilter],
  );

  // Client mode counts the jobs it holds; server mode can't (it holds one 50-row
  // page), so it reads the global GROUP BY the stats endpoint returns.
  const derivedTagCounts = useMemo(() => deriveTagCounts(allJobs), [allJobs]);
  const tagCounts = serverMode
    ? (serverStats?.by_tag ?? {})
    : derivedTagCounts;

  const preloadIndexes = useMemo(
    () => new Map(preloadJobs.map((job, index) => [job.id, index])),
    [preloadJobs],
  );

  // -------------------------------------------------------------------------
  // Unified returned values
  // -------------------------------------------------------------------------

  const jobs = serverMode ? serverJobs : (derivedJobs ?? []);
  const stats = serverMode ? serverStats : derivedStats;
  // total: filtered count (matches today's behaviour — count label reflects active view)
  const total = serverMode ? serverFilteredTotal : (derivedJobs?.length ?? 0);

  return {
    tagCounts,
    stats,
    jobs,
    total,
    loading,
    error,
    reload,
    preloadIndexes,
  };
}

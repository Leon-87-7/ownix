'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { JobSummary } from '@/components/job-card';

export interface FeedStats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
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

async function fetchAllJobs(): Promise<{ jobs: JobSummary[]; total: number }> {
  const res = await fetch(`/api/jobs?limit=${CLIENT_MODE_LIMIT}`);
  if (!res.ok) throw new Error('Failed to load jobs');
  const data = (await res.json()) as JobsResponse;
  return { jobs: data.items, total: data.total };
}

async function fetchStats(): Promise<FeedStats> {
  const res = await fetch('/api/jobs/stats');
  if (!res.ok) throw new Error('Failed to load stats');
  return (await res.json()) as FeedStats;
}

/** Server-side fetch used in server mode (>1000 jobs) or for the fallback reload. */
async function fetchFeedServerMode(
  ct: string,
  st: string,
): Promise<{ stats: FeedStats; jobs: JobSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (ct) params.set('content_type', ct);
  if (st) params.set('status', st);
  params.set('limit', '50');

  // Stats scoped by content_type (never status) so Overview cards show full
  // status split for the active tab. Omit for global totals.
  const statsParams = new URLSearchParams();
  if (ct) statsParams.set('content_type', ct);
  const statsQuery = statsParams.toString();

  const [statsRes, jobsRes] = await Promise.all([
    fetch(statsQuery ? `/api/jobs/stats?${statsQuery}` : '/api/jobs/stats'),
    fetch(`/api/jobs?${params}`),
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
 */
function deriveJobs(allJobs: JobSummary[], ct: string, st: string): JobSummary[] {
  let list = allJobs;
  if (ct) list = list.filter((j) => j.content_type === ct);
  if (st) list = list.filter((j) => j.status === st);
  return list;
}

/**
 * Derive FeedStats from the in-memory job list.
 *
 * - `by_content_type`: always global (all jobs) — powers tab count chips.
 * - `by_status`: scoped to the active content_type (matching what the server
 *   returns when you pass content_type to /api/jobs/stats) — powers Overview cards.
 * - `total`: sum of by_status values for the scoped slice (matching server behaviour).
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

export function useFeedData(initialContentType = '') {
  const [ctFilter, setCtFilter] = useState(initialContentType);
  const [stFilter, setStFilter] = useState('');

  // The full unfiltered job list (client mode) or the per-filter list (server mode).
  const [allJobs, setAllJobs] = useState<JobSummary[]>([]);

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

  // Keep refs so reload() always sees current filter values without
  // being listed in the useCallback deps array.
  const ctRef = useRef(ctFilter);
  ctRef.current = ctFilter;
  const stRef = useRef(stFilter);
  stRef.current = stFilter;
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
        fetchAllJobs(),
        fetchStats(),
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
    } catch (e) {
      if (reqId !== reqIdRef.current) return;
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      if (loadId === loadIdRef.current) setLoading(false);
    }
  }, []);

  // -------------------------------------------------------------------------
  // Server-mode filter fetch (called on filter change when in server mode)
  // -------------------------------------------------------------------------

  const serverLoad = useCallback(async (ct: string, st: string) => {
    const reqId = ++reqIdRef.current;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);

    try {
      const { stats, jobs, total } = await fetchFeedServerMode(ct, st);
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
  }, []);

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
        const { stats, jobs, total } = await fetchFeedServerMode(
          ctRef.current,
          stRef.current,
        );
        if (reqId !== reqIdRef.current) return;
        const ct = ctRef.current;
        const filtered = ct ? jobs.filter((j) => j.content_type === ct) : jobs;
        setServerStats(stats);
        setServerJobs(filtered);
        setServerFilteredTotal(total);
      } else {
        // Client mode: silently re-fetch the full list, swap allJobs.
        // No loading flag flip — no skeleton, active filter/search survive.
        const { jobs } = await fetchAllJobs();
        if (reqId !== reqIdRef.current) return;
        setAllJobs(jobs);
      }
    } catch {
      // swallow during background polling
    }
  }, []);

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
      if (!ctFilter && !stFilter) return;
    }
    serverLoad(ctFilter, stFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverMode, ctFilter, stFilter, serverLoad]);

  // -------------------------------------------------------------------------
  // Derived state (client mode only — computed synchronously, no fetch)
  // -------------------------------------------------------------------------

  const derivedJobs = useMemo(
    () => (serverMode ? null : deriveJobs(allJobs, ctFilter, stFilter)),
    [serverMode, allJobs, ctFilter, stFilter],
  );

  const derivedStats = useMemo(
    () => (serverMode ? null : deriveStats(allJobs, ctFilter)),
    [serverMode, allJobs, ctFilter],
  );

  // -------------------------------------------------------------------------
  // Unified returned values
  // -------------------------------------------------------------------------

  const jobs = serverMode ? serverJobs : (derivedJobs ?? []);
  const stats = serverMode ? serverStats : derivedStats;
  // total: filtered count (matches today's behaviour — count label reflects active view)
  const total = serverMode ? serverFilteredTotal : (derivedJobs?.length ?? 0);

  return {
    ctFilter,
    setCtFilter,
    stFilter,
    setStFilter,
    stats,
    jobs,
    total,
    loading,
    error,
    reload,
  };
}

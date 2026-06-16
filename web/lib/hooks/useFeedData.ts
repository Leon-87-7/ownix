'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
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

async function fetchFeed(
  ct: string,
  st: string,
): Promise<{ stats: FeedStats; jobs: JobSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (ct) params.set('content_type', ct);
  if (st) params.set('status', st);
  params.set('limit', '50');

  // Stats are scoped by content_type only (never status) so the Overview cards
  // show the full status split for the active tab. Omit it for global totals.
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

export function useFeedData(initialContentType = '') {
  const [ctFilter, setCtFilter] = useState(initialContentType);
  const [stFilter, setStFilter] = useState('');
  const [stats, setStats] = useState<FeedStats | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Monotonic request-id counter. Every dispatch (load + reload) increments
  // this before the await; after the await, the response is discarded unless
  // the captured id still matches the latest.
  const reqIdRef = useRef(0);

  // Separate counter that only load() bumps, used solely to gate the loading
  // flag. reload() (the background poll) must not touch this — otherwise a poll
  // firing mid-load would advance reqIdRef and strand loading=true forever,
  // since load's finally would see its reqId superseded and skip setLoading(false).
  const loadIdRef = useRef(0);

  const load = useCallback(async (ct: string, st: string) => {
    const reqId = ++reqIdRef.current;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);

    try {
      const { stats, jobs, total } = await fetchFeed(ct, st);

      // Discard if a newer request has been dispatched while we were awaiting.
      if (reqId !== reqIdRef.current) return;

      // Defensive: drop items whose content_type doesn't match the filter that
      // was active when this request was dispatched. This catches server-side
      // bugs and further neutralises any residual race at the item level.
      const filtered = ct ? jobs.filter((j) => j.content_type === ct) : jobs;

      setStats(stats);
      setJobs(filtered);
      setTotal(total);
    } catch (e) {
      if (reqId !== reqIdRef.current) return;
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      // Gate the loading flag on loadId (bumped only by load), not reqId. A
      // background reload() advances reqIdRef but not loadIdRef, so a poll
      // firing mid-load can't strand loading=true; only a newer load() clears
      // this one's right to flip the flag.
      if (loadId === loadIdRef.current) setLoading(false);
    }
  }, []);

  const ctRef = useRef(ctFilter);
  ctRef.current = ctFilter;
  const stRef = useRef(stFilter);
  stRef.current = stFilter;

  const reload = useCallback(async () => {
    // Background poll: increment the req-id so a concurrent load() dispatched
    // after this poll does not get clobbered by a slow poll response.
    const reqId = ++reqIdRef.current;

    try {
      const { stats, jobs, total } = await fetchFeed(ctRef.current, stRef.current);

      if (reqId !== reqIdRef.current) return;

      const ct = ctRef.current;
      const filtered = ct ? jobs.filter((j) => j.content_type === ct) : jobs;

      setStats(stats);
      setJobs(filtered);
      setTotal(total);
    } catch {
      // swallow during background polling
    }
  }, []);

  useEffect(() => {
    // Clear synchronously on filter change so neither stale-type cards nor the
    // previous tab's counts linger while the new request is in flight.
    setJobs([]);
    setStats(null);
    load(ctFilter, stFilter);
  }, [ctFilter, stFilter, load]);

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

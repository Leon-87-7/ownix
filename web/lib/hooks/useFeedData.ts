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

async function fetchFeed(ct: string, st: string): Promise<{ stats: FeedStats; jobs: JobSummary[]; total: number }> {
  const params = new URLSearchParams();
  if (ct) params.set('content_type', ct);
  if (st) params.set('status', st);
  params.set('limit', '50');
  const [statsRes, jobsRes] = await Promise.all([
    fetch('/api/jobs/stats'),
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

  const load = useCallback(async (ct: string, st: string) => {
    setLoading(true);
    setError(null);
    try {
      const { stats, jobs, total } = await fetchFeed(ct, st);
      setStats(stats);
      setJobs(jobs);
      setTotal(total);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  const ctRef = useRef(ctFilter);
  ctRef.current = ctFilter;
  const stRef = useRef(stFilter);
  stRef.current = stFilter;

  const reload = useCallback(async () => {
    try {
      const { stats, jobs, total } = await fetchFeed(ctRef.current, stRef.current);
      setStats(stats);
      setJobs(jobs);
      setTotal(total);
    } catch {
      // swallow during background polling
    }
  }, []);

  useEffect(() => {
    load(ctFilter, stFilter);
  }, [ctFilter, stFilter, load]);

  return { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload };
}

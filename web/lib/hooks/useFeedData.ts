'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { JobSummary } from '@/components/job-card';

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
}

interface JobsResponse {
  items: JobSummary[];
  total: number;
}

export function useFeedData() {
  const [ctFilter, setCtFilter] = useState('');
  const [stFilter, setStFilter] = useState('');
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (ct: string, st: string) => {
    setLoading(true);
    setError(null);
    try {
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
      const [statsData, jobsData] = await Promise.all([
        statsRes.json() as Promise<Stats>,
        jobsRes.json() as Promise<JobsResponse>,
      ]);
      setStats(statsData);
      setJobs(jobsData.items);
      setTotal(jobsData.total);
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
      const params = new URLSearchParams();
      if (ctRef.current) params.set('content_type', ctRef.current);
      if (stRef.current) params.set('status', stRef.current);
      params.set('limit', '50');
      const [statsRes, jobsRes] = await Promise.all([
        fetch('/api/jobs/stats'),
        fetch(`/api/jobs?${params}`),
      ]);
      if (!statsRes.ok || !jobsRes.ok) return;
      const [statsData, jobsData] = await Promise.all([
        statsRes.json() as Promise<Stats>,
        jobsRes.json() as Promise<JobsResponse>,
      ]);
      setStats(statsData);
      setJobs(jobsData.items);
      setTotal(jobsData.total);
    } catch {
      // swallow during background polling
    }
  }, []);

  useEffect(() => {
    load('', '');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isFirst = useRef(true);
  useEffect(() => {
    if (isFirst.current) { isFirst.current = false; return; }
    load(ctFilter, stFilter);
  }, [ctFilter, stFilter, load]);

  return { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload };
}

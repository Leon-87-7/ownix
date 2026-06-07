'use client';

import { useCallback, useEffect, useState } from 'react';
import { swapSortOrder } from '@/lib/fetch-utils';
import type { JobSummary } from '@/components/job-card';

export interface SpaceUrl {
  id: string;
  title: string | null;
  url: string;
  content_type: string;
  status: string;
  sort_order: number;
  added_at: string;
}

export function useSpaceUrls(spaceId: string) {
  const [spaceUrls, setSpaceUrls] = useState<SpaceUrl[]>([]);
  const [allJobs, setAllJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchUrls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/urls`);
      if (res.ok) setSpaceUrls((await res.json()) as SpaceUrl[]);
    } finally {
      setLoading(false);
    }
  }, [spaceId]);

  const fetchAllJobs = useCallback(async () => {
    const res = await fetch('/api/jobs?limit=50');
    if (res.ok) {
      const data = (await res.json()) as { items: JobSummary[] };
      setAllJobs(data.items);
    }
  }, []);

  useEffect(() => {
    fetchUrls();
    fetchAllJobs();
  }, [fetchUrls, fetchAllJobs]);

  const addJob = useCallback(async (jobId: string) => {
    await fetch(`/api/spaces/${spaceId}/urls`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId }),
    });
    await fetchUrls();
  }, [spaceId, fetchUrls]);

  const removeUrl = useCallback(async (jobId: string) => {
    await fetch(`/api/spaces/${spaceId}/urls/${jobId}`, { method: 'DELETE' });
    await fetchUrls();
  }, [spaceId, fetchUrls]);

  const reorderUrl = useCallback(async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= spaceUrls.length) return;
    const a = spaceUrls[index];
    const b = spaceUrls[targetIndex];
    setSpaceUrls((prev) => {
      const next = [...prev];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
    await swapSortOrder(
      `/api/spaces/${spaceId}/urls/${a.id}`, b.sort_order,
      `/api/spaces/${spaceId}/urls/${b.id}`, a.sort_order,
    );
    await fetchUrls();
  }, [spaceId, spaceUrls, fetchUrls]);

  return { spaceUrls, allJobs, loading, addJob, removeUrl, reorderUrl };
}

'use client';

import { useEffect, useRef } from 'react';
import { IN_FLIGHT_STATUSES, startPolling } from '@/lib/polling';
import type { JobSummary } from '@/components/feed/job-card';

export function useInFlightPolling(jobs: JobSummary[], reload: () => Promise<void>) {
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;

  useEffect(() => {
    const isIdle = () => jobsRef.current.every((j) => !IN_FLIGHT_STATUSES.has(j.status));
    return startPolling(reload, isIdle, 10_000);
  }, [reload]);
}

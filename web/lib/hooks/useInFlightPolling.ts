'use client';

import { useEffect, useRef } from 'react';
import { startPolling } from '@/lib/polling';
import type { JobSummary } from '@/components/job-card';

const IN_FLIGHT_STATUSES = new Set([
  'pending',
  'processing',
  'enriching',
  'transcript_done',
]);

export function useInFlightPolling(jobs: JobSummary[], reload: () => Promise<void>) {
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;

  useEffect(() => {
    const isIdle = () => jobsRef.current.every((j) => !IN_FLIGHT_STATUSES.has(j.status));
    return startPolling(reload, isIdle, 10_000);
  }, [reload]);
}

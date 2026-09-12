'use client';

import { useEffect, useRef, useState } from 'react';
import Fuse from 'fuse.js';
import type { JobSummary } from '@/components/feed/job-card';

export function useFuseSearch(jobs: JobSummary[], initialQuery = '') {
  // Seeded, not synced: the input stays the live source of truth so typing is
  // never gated on a router round-trip. The Feed mirrors it into `?q=` so a
  // back-navigation remount seeds it right back (#309 follow-up).
  const [query, setQuery] = useState(initialQuery);
  const fuseRef = useRef<Fuse<JobSummary> | null>(null);

  useEffect(() => {
    fuseRef.current = new Fuse(jobs, { keys: ['title', 'url'], threshold: 0.4 });
  }, [jobs]);

  const displayedJobs =
    query.trim() && fuseRef.current
      ? fuseRef.current.search(query).map((r) => r.item)
      : jobs;

  return { query, setQuery, displayedJobs };
}

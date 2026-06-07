'use client';

import { useEffect, useRef, useState } from 'react';
import Fuse from 'fuse.js';
import type { JobSummary } from '@/components/job-card';

export function useFuseSearch(jobs: JobSummary[]) {
  const [query, setQuery] = useState('');
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

'use client';

import { useMemo, useState } from 'react';
import Fuse from 'fuse.js';
import type { JobSummary } from '@/components/feed/job-card';

export function useFuseSearch(jobs: JobSummary[], initialQuery = '') {
  // Seeded, not synced: the input stays the live source of truth so typing is
  // never gated on a router round-trip. The Feed mirrors it into `?q=` so a
  // back-navigation remount seeds it right back (#309 follow-up).
  const [query, setQuery] = useState(initialQuery);
  // useMemo, not a ref rebuilt in an effect: an effect runs after render, so a
  // query restored alongside a `jobs` change would search the previous
  // render's (possibly empty) index for one frame — and nothing re-renders
  // again on its own to pick up the corrected one, leaving the Feed looking
  // permanently empty/stale (CodeRabbit, PR #626).
  const fuse = useMemo(
    () => new Fuse(jobs, { keys: ['title', 'url'], threshold: 0.4 }),
    [jobs],
  );

  const displayedJobs = query.trim() ? fuse.search(query).map((r) => r.item) : jobs;

  return { query, setQuery, displayedJobs };
}

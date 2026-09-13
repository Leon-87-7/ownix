'use client';

import { useMemo, useState } from 'react';
import Fuse from 'fuse.js';
import type { JobSummary } from '@/components/feed/job-card';

/** Fuzzy-match `jobs` against `query`. A pure derivation: the caller owns the
 * query, which lets the Feed keep it in the one scope object it already
 * projects onto the URL instead of holding a second copy here. */
export function useFuseFilter(jobs: JobSummary[], query: string): JobSummary[] {
  // useMemo, not a ref rebuilt in an effect: an effect runs after render, so a
  // query restored alongside a `jobs` change would search the previous
  // render's (possibly empty) index for one frame — and nothing re-renders
  // again on its own to pick up the corrected one, leaving the Feed looking
  // permanently empty/stale (CodeRabbit, PR #626).
  const fuse = useMemo(
    () => new Fuse(jobs, { keys: ['title', 'url'], threshold: 0.4 }),
    [jobs],
  );

  return query.trim() ? fuse.search(query).map((r) => r.item) : jobs;
}

/** `useFuseFilter` plus its own query state, for callers with nowhere else to
 * keep it (the intake Add search). */
export function useFuseSearch(jobs: JobSummary[], initialQuery = '') {
  const [query, setQuery] = useState(initialQuery);
  return { query, setQuery, displayedJobs: useFuseFilter(jobs, query) };
}

'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FetchState } from '@/lib/fetch-utils';

export interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
}

export function useJobTags(jobId: string, fetchState: FetchState) {
  const [jobTags, setJobTags] = useState<TagSummary[]>([]);
  const [allTags, setAllTags] = useState<TagSummary[]>([]);

  useEffect(() => {
    if (fetchState !== 'ok') return;
    fetch(`/api/jobs/${jobId}/tags`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(setJobTags)
      .catch(() => {});
    fetch('/api/controls/tags', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(setAllTags)
      .catch(() => {});
  }, [fetchState, jobId]);

  const refetchTags = useCallback(() => {
    fetch(`/api/jobs/${jobId}/tags`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(setJobTags)
      .catch(() => {});
  }, [jobId]);

  return { jobTags, allTags, refetchTags };
}

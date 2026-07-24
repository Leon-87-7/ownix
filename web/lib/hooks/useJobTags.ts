'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FetchState } from '@/lib/fetch-utils';
import { useTagAttachment } from '@/lib/hooks/useTagAttachment';

interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
}

// Coerce to array — the UI maps over these, so a non-array body must not crash render.
const asTags = (d: unknown): TagSummary[] => (Array.isArray(d) ? d : []);

export function useJobTags(jobId: string, fetchState: FetchState, disabled = false) {
  const [jobTags, setJobTags] = useState<TagSummary[]>([]);
  const [allTags, setAllTags] = useState<TagSummary[]>([]);

  const refetchTags = useCallback(() => {
    fetch(`/api/jobs/${jobId}/tags`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setJobTags(asTags(d)))
      .catch(() => {});
  }, [jobId]);

  const refetchAll = useCallback(() => {
    fetch('/api/controls/tags', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setAllTags(asTags(d)))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (disabled || fetchState !== 'ok') return;
    refetchTags();
    refetchAll();
  }, [fetchState, refetchTags, refetchAll, disabled]);

  const { toggleTag, createTag } = useTagAttachment({
    path: (tagId) =>
      `/api/jobs/${encodeURIComponent(jobId)}/tags${tagId ? `/${encodeURIComponent(tagId)}` : ''}`,
    itemLabel: 'job',
    refetchTags,
    refetchAll,
    disabled,
  });

  return { jobTags, allTags, refetchTags, toggleTag, createTag };
}

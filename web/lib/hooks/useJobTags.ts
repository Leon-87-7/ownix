'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FetchState } from '@/lib/fetch-utils';
import { useTagAttachment } from '@/lib/hooks/useTagAttachment';
import { fetchVocabulary, type TagSummary } from '@/lib/hooks/useLinkTags';

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

  // Vocabulary loads through the module-level cache shared with useLinkTags —
  // a feed of N job cards must not fire N identical /api/controls/tags requests.
  const refetchAll = useCallback((force = false) => {
    void fetchVocabulary(force).then(setAllTags);
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

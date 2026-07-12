'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FetchState } from '@/lib/fetch-utils';
import type { TagFormState } from '@/lib/hooks/useTagList';

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

  const toggleTag = useCallback(
    async (tagId: string, attached: boolean) => {
      if (disabled) return;
      const res = await fetch(`/api/jobs/${jobId}/tags/${tagId}`, {
        method: attached ? 'DELETE' : 'POST',
        credentials: 'include',
      });
      if (res.ok) refetchTags(); // res.ok covers 200/201/204
    },
    [jobId, refetchTags, disabled],
  );

  // Create a tag in the user's library, then attach it to this job.
  const createTag = useCallback(
    async (values: TagFormState) => {
      if (disabled) return;
      const res = await fetch('/api/controls/tags', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      if (!res.ok) {
        throw new Error(res.status === 409 ? 'Tag name already exists' : 'Create failed');
      }
      const tag = (await res.json()) as TagSummary;
      const attach = await fetch(`/api/jobs/${jobId}/tags/${tag.id}`, { method: 'POST', credentials: 'include' });
      if (!attach.ok) throw new Error('Tag created but could not be attached to this job');
      refetchAll();
      refetchTags();
    },
    [jobId, refetchAll, refetchTags, disabled],
  );

  return { jobTags, allTags, refetchTags, toggleTag, createTag };
}

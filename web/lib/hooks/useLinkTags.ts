'use client';

import { useCallback, useEffect, useState } from 'react';
import type { TagFormState } from '@/lib/hooks/useTagList';

export interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
  icon?: string | null;
}

const asTags = (d: unknown): TagSummary[] => (Array.isArray(d) ? d : []);

// Fixed-shape, same-origin API path with every dynamic segment URI-encoded —
// IDs come from our own database, never from a user-typed URL.
function linkTagsPath(linkId: string, tagId?: string): string {
  const base = '/api/brain/links/' + encodeURIComponent(linkId) + '/tags';
  return tagId ? base + '/' + encodeURIComponent(tagId) : base;
}

// One vocabulary request shared by every cluster on the page (a 50-row table
// mounts 100 clusters across the two responsive branches). Invalidated on
// tag creation so new tags appear everywhere.
let vocabularyPromise: Promise<TagSummary[]> | null = null;
function fetchVocabulary(force = false): Promise<TagSummary[]> {
  if (force || !vocabularyPromise) {
    vocabularyPromise = fetch('/api/controls/tags', { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then(asTags)
      .catch(() => {
        vocabularyPromise = null;
        return [];
      });
  }
  return vocabularyPromise;
}

export function useLinkTags(linkId: string, initialTags: TagSummary[] = []) {
  const [linkTags, setLinkTags] = useState<TagSummary[]>(initialTags);
  const [allTags, setAllTags] = useState<TagSummary[]>([]);

  const refetchTags = useCallback(() => {
    // nosemgrep -- same-origin relative API path; segments are server-issued IDs, URI-encoded in linkTagsPath
    fetch(linkTagsPath(linkId), { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : []))
      .then((d) => setLinkTags(asTags(d)))
      .catch(() => {});
  }, [linkId]);

  const refetchAll = useCallback((force = false) => {
    void fetchVocabulary(force).then(setAllTags);
  }, []);

  // Vocabulary loads through the shared module cache; linkTags seeds from
  // useState(initialTags) above. Never sync on initialTags identity —
  // `link.tags ?? []` makes a fresh array per render, which would loop
  // setState forever.
  useEffect(() => {
    refetchAll();
  }, [refetchAll]);

  const toggleTag = useCallback(async (tagId: string, attached: boolean) => {
    // nosemgrep -- same-origin relative API path; segments are server-issued IDs, URI-encoded in linkTagsPath
    const res = await fetch(linkTagsPath(linkId, tagId), {
      method: attached ? 'DELETE' : 'POST',
      credentials: 'include',
    });
    if (res.ok) refetchTags();
  }, [linkId, refetchTags]);

  const createTag = useCallback(async (values: TagFormState) => {
    const res = await fetch('/api/controls/tags', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
    if (!res.ok) throw new Error(res.status === 409 ? 'Tag name already exists' : 'Create failed');
    const tag = (await res.json()) as TagSummary;
    // nosemgrep -- same-origin relative API path; segments are server-issued IDs, URI-encoded in linkTagsPath
    const attach = await fetch(linkTagsPath(linkId, tag.id), { method: 'POST', credentials: 'include' });
    if (!attach.ok) throw new Error('Tag created but could not be attached to this link');
    refetchAll(true);
    refetchTags();
  }, [linkId, refetchAll, refetchTags]);

  return { linkTags, allTags, toggleTag, createTag };
}

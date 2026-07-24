'use client';

import { useCallback } from 'react';
import type { TagFormState } from '@/lib/hooks/useTagList';

interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
  icon?: string | null;
}

/** Shared attach/detach/create-and-attach flow for a `.../<itemId>/tags[/<tagId>]`
 * endpoint. Callers own fetching their own item tags + vocabulary (the fetch
 * gating and caching strategy differ per item type) — this only wraps the
 * mutation calls both share. */
export function useTagAttachment({
  path,
  itemLabel,
  refetchTags,
  refetchAll,
  disabled = false,
}: {
  path: (tagId?: string) => string;
  itemLabel: string;
  refetchTags: () => void;
  refetchAll: (force?: boolean) => void;
  disabled?: boolean;
}) {
  const toggleTag = useCallback(
    async (tagId: string, attached: boolean) => {
      if (disabled) return;
      const res = await fetch(path(tagId), {
        method: attached ? 'DELETE' : 'POST',
        credentials: 'include',
      });
      if (res.ok) refetchTags(); // res.ok covers 200/201/204
    },
    [path, refetchTags, disabled],
  );

  // Create a tag in the user's library, then attach it to this item.
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
      const attach = await fetch(path(tag.id), { method: 'POST', credentials: 'include' });
      if (!attach.ok) throw new Error(`Tag created but could not be attached to this ${itemLabel}`);
      refetchAll(true);
      refetchTags();
    },
    [path, itemLabel, refetchAll, refetchTags, disabled],
  );

  return { toggleTag, createTag };
}

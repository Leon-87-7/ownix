'use client';

import { useCallback } from 'react';
import { useFetchList, apiPost, apiPut, apiDelete } from '@/lib/fetch-utils';

export interface Tag {
  id: string;
  name: string;
  meaning: string;
  color: string;
  icon?: string | null;
  pinned?: boolean;
  created_at?: string;
}

export interface TagFormState {
  name: string;
  meaning: string;
  color: string;
  icon?: string | null;
}

export function useTagList() {
  const { data: tags, setData: setTags, loading, fetchError } = useFetchList<Tag>('/api/controls/tags', 'tags');

  const createTag = useCallback(async (values: TagFormState): Promise<void> => {
    const result = await apiPost<Tag>('/api/controls/tags', values);
    if (!result.ok) {
      throw new Error(result.status === 409 ? 'Tag name already exists' : result.detail);
    }
    setTags((prev) => [...prev, result.data].sort((a, b) => a.name.localeCompare(b.name)));
  }, [setTags]);

  const deleteTag = useCallback(async (id: string): Promise<void> => {
    await apiDelete(`/api/controls/tags/${id}`);
    setTags((prev) => prev.filter((t) => t.id !== id));
  }, [setTags]);

  const updateTag = useCallback(async (id: string, values: TagFormState): Promise<void> => {
    const updated = await apiPut<Tag>(`/api/controls/tags/${id}`, values, 'Update failed');
    setTags((prev) => prev.map((t) => (t.id === id ? { ...t, ...updated } : t)).sort((a, b) => a.name.localeCompare(b.name)));
  }, [setTags]);

  // GoTo quick-jump: any number of a user's own tags can be pinned. Nothing is
  // locked — pinning is just this one boolean, toggled freely like color/icon.
  const toggleTagPinned = useCallback(async (id: string, pinned: boolean): Promise<void> => {
    if (pinned) {
      const result = await apiPost<Tag>(`/api/controls/tags/${id}/pin`, {});
      if (!result.ok) throw new Error(result.detail);
    } else {
      await apiDelete(`/api/controls/tags/${id}/pin`, 'Unpin failed');
    }
    setTags((prev) => prev.map((t) => (t.id === id ? { ...t, pinned } : t)));
  }, [setTags]);

  return { tags, loading, fetchError, createTag, deleteTag, updateTag, toggleTagPinned };
}

'use client';

import { useCallback } from 'react';
import { useFetchList, apiPost } from '@/lib/fetch-utils';

export interface Tag {
  id: string;
  name: string;
  meaning: string;
  color: string;
  created_at?: string;
}

export interface TagFormState {
  name: string;
  meaning: string;
  color: string;
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
    const res = await fetch(`/api/controls/tags/${id}`, { method: 'DELETE' });
    if (res.ok || res.status === 204) { setTags((prev) => prev.filter((t) => t.id !== id)); return; }
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? 'Delete failed');
  }, [setTags]);

  const updateTag = useCallback(async (id: string, values: TagFormState): Promise<void> => {
    const res = await fetch(`/api/controls/tags/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { detail?: string }).detail ?? 'Update failed');
    }
    const updated: Tag = await res.json();
    setTags((prev) => prev.map((t) => (t.id === id ? { ...t, ...updated } : t)).sort((a, b) => a.name.localeCompare(b.name)));
  }, [setTags]);

  return { tags, loading, fetchError, createTag, deleteTag, updateTag };
}

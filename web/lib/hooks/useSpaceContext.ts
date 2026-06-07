'use client';

import { useCallback, useEffect, useState } from 'react';
import { swapSortOrder } from '@/lib/fetch-utils';

export interface ContextBlob {
  id: string;
  space_id: string;
  name: string;
  content: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export function useSpaceContext(spaceId: string) {
  const [blobs, setBlobs] = useState<ContextBlob[]>([]);
  const [loading, setLoading] = useState(false);
  const [blobError, setBlobError] = useState<string | null>(null);

  const fetchBlobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/blobs`);
      if (res.ok) setBlobs((await res.json()) as ContextBlob[]);
    } finally {
      setLoading(false);
    }
  }, [spaceId]);

  useEffect(() => { fetchBlobs(); }, [fetchBlobs]);

  const addBlob = useCallback(async (name: string) => {
    const res = await fetch(`/api/spaces/${spaceId}/blobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) { setBlobError('Failed to add context document. Please try again.'); return; }
    setBlobError(null);
    await fetchBlobs();
  }, [spaceId, fetchBlobs]);

  const updateBlob = useCallback(async (blobId: string, name: string, content: string) => {
    const res = await fetch(`/api/spaces/${spaceId}/blobs/${blobId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, content }),
    });
    if (!res.ok) setBlobError('Failed to save. Please try again.');
    else setBlobError(null);
  }, [spaceId]);

  const deleteBlob = useCallback(async (blobId: string) => {
    const res = await fetch(`/api/spaces/${spaceId}/blobs/${blobId}`, { method: 'DELETE' });
    if (!res.ok) { setBlobError('Failed to remove context document. Please try again.'); return; }
    setBlobError(null);
    await fetchBlobs();
  }, [spaceId, fetchBlobs]);

  const reorderBlob = useCallback(async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= blobs.length) return;
    const a = blobs[index];
    const b = blobs[targetIndex];
    await swapSortOrder(
      `/api/spaces/${spaceId}/blobs/${a.id}`, b.sort_order,
      `/api/spaces/${spaceId}/blobs/${b.id}`, a.sort_order,
    );
    await fetchBlobs();
  }, [spaceId, blobs, fetchBlobs]);

  const patchBlobName = useCallback((blobId: string, name: string) => {
    setBlobs((prev) => prev.map((b) => b.id === blobId ? { ...b, name } : b));
  }, []);

  return { blobs, loading, blobError, setBlobError, addBlob, updateBlob, deleteBlob, reorderBlob, patchBlobName };
}

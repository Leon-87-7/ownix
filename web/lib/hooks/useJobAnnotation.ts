'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FetchState } from '@/lib/fetch-utils';

interface Annotation {
  notes: string;
  updated_at: string | null;
}

export function useJobAnnotation(jobId: string, fetchState: FetchState, disabled = false) {
  const [annotation, setAnnotation] = useState<Annotation>({ notes: '', updated_at: null });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (disabled) { setLoaded(true); return; }
    if (fetchState !== 'ok') return;
    fetch(`/api/jobs/${jobId}/annotations`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => { if (data) setAnnotation(data); setLoaded(true); })
      .catch(() => { setLoaded(true); });
  }, [fetchState, jobId, disabled]);

  const handleSave = useCallback(async (md: string) => {
    if (disabled) return;
    try {
      const res = await fetch(`/api/jobs/${jobId}/annotations`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: md }),
      });
      if (res.ok) {
        const saved: Annotation = await res.json();
        setAnnotation(saved);
      }
    } catch {
      // silently ignore network errors during auto-save
    }
  }, [jobId, disabled]);

  return { annotation, loaded, handleSave };
}

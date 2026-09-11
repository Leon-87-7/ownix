'use client';

import { useCallback, useState } from 'react';
import { apiDelete, apiPost } from '@/lib/fetch-utils';

interface ChecklistsResult {
  checklists_md: string;
  checklists_generated_at: string;
}

export function useChecklists(jobId: string) {
  const [generating, setGenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async (): Promise<ChecklistsResult | null> => {
    setGenerating(true);
    setError(null);
    try {
      const result = await apiPost<ChecklistsResult>(
        `/api/jobs/${jobId}/checklists`,
        {},
        'Checklist generation failed',
      );
      if (!result.ok) {
        setError(result.detail);
        return null;
      }
      return result.data;
    } catch {
      setError('Checklist generation failed');
      return null;
    } finally {
      setGenerating(false);
    }
  }, [jobId]);

  /** Clear the stored checklist. Resolves false on failure (never throws) so
   * ConfirmDialog closes and the error surfaces in the section's alert slot —
   * same shape as the job delete on this page. */
  const remove = useCallback(
    async (generatedAt: string | null): Promise<boolean> => {
    setDeleting(true);
    setError(null);
    try {
      // Pin the delete to the checklist actually on screen: one generated in
      // another tab since this page loaded must not be erased by this click.
      // The server answers 409 and the message tells the user to reload.
      const query = generatedAt
        ? `?generated_at=${encodeURIComponent(generatedAt)}`
        : '';
      await apiDelete(
        `/api/jobs/${jobId}/checklists${query}`,
        'Checklist delete failed',
      );
      return true;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Checklist delete failed',
      );
      return false;
    } finally {
      setDeleting(false);
    }
    },
    [jobId],
  );

  return { generating, deleting, error, run, remove };
}

'use client';

import { useCallback, useState } from 'react';
import { apiPost } from '@/lib/fetch-utils';

interface ChecklistsResult {
  checklists_md: string;
  checklists_generated_at: string;
}

export function useChecklists(jobId: string) {
  const [generating, setGenerating] = useState(false);
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

  return { generating, error, run };
}

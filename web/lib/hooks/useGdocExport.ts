'use client';

import { useCallback, useState } from 'react';

export type ExportStatus = 'idle' | 'exporting' | 'done' | 'error';

export function useGdocExport(spaceId: string) {
  const [status, setStatus] = useState<ExportStatus>('idle');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const trigger = useCallback(async () => {
    setStatus('exporting');
    setError(null);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: 'gdoc' }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        if (data.error === 'drive_not_configured') {
          setError('Google Drive is not configured. Use the .md, .txt, or PDF buttons above.');
          setStatus('error');
          return;
        }
        throw new Error(data.detail || data.error || 'Export failed');
      }
      setResultUrl(data.url as string);
      setStatus('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setStatus('error');
    }
  }, [spaceId]);

  return { trigger, status, error, resultUrl };
}

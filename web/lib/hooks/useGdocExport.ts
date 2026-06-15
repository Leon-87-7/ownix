'use client';

import { useCallback, useState } from 'react';

type ExportStatus = 'idle' | 'exporting' | 'done' | 'error';
type ExportErrorCode = 'drive_not_configured' | null;

export function useGdocExport(spaceId: string) {
  const [status, setStatus] = useState<ExportStatus>('idle');
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<ExportErrorCode>(null);

  const trigger = useCallback(async () => {
    setStatus('exporting');
    setError(null);
    setErrorCode(null);
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
          setErrorCode('drive_not_configured');
          setStatus('error');
          return;
        }
        throw new Error(data.detail || data.error || 'Export failed');
      }
      setResultUrl(data.url as string);
      setStatus('done');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setErrorCode(null);
      setStatus('error');
    }
  }, [spaceId]);

  return { trigger, status, error, errorCode, resultUrl };
}

'use client';

import { useCallback, useEffect, useState } from 'react';

export interface RecoverySummary {
  stale_pending: number;
  error_jobs: number;
  stale_in_flight: number;
}

const EMPTY_SUMMARY: RecoverySummary = {
  stale_pending: 0,
  error_jobs: 0,
  stale_in_flight: 0,
};

async function fetchSummary(contentType: string, signal?: AbortSignal): Promise<RecoverySummary> {
  const params = new URLSearchParams();
  if (contentType) params.set('content_type', contentType);
  const qs = params.toString();
  const res = await fetch(`/api/jobs/recovery/summary${qs ? `?${qs}` : ''}`, { signal });
  if (!res.ok) throw new Error('Failed to load recovery summary');
  return (await res.json()) as RecoverySummary;
}

async function runAction(path: string, contentType: string): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content_type: contentType || null }),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as { detail?: string }).detail ?? 'Recovery action failed');
  }
}

export function useRecovery(contentType: string, onRecovered: () => Promise<void> | void) {
  const [summary, setSummary] = useState<RecoverySummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchSummary(contentType, signal);
      if (signal?.aborted) return;
      setSummary(next);
    } catch (err) {
      if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) return;
      setError(err instanceof Error ? err.message : 'Failed to load recovery summary');
      setSummary(EMPTY_SUMMARY);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [contentType]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const act = useCallback(async (key: string, path: string) => {
    setActing(key);
    setError(null);
    try {
      await runAction(path, contentType);
      await load();
      await onRecovered();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Recovery action failed');
    } finally {
      setActing(null);
    }
  }, [contentType, load, onRecovered]);

  return {
    summary,
    loading,
    acting,
    error,
    retryPending: () => act('pending', '/api/jobs/recovery/retry-pending'),
    retryError: () => act('error', '/api/jobs/recovery/retry-error'),
    clearFailed: () => act('clear', '/api/jobs/recovery/clear-failed'),
  };
}

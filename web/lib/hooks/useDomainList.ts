'use client';

import { useCallback } from 'react';
import { useFetchList } from '@/lib/fetch-utils';

export function useDomainList(apiPath: string, label: string) {
  const { data: domains, setData: setDomains, loading, fetchError } = useFetchList<string>(apiPath, label.toLowerCase());

  const addDomain = useCallback(async (domain: string): Promise<void> => {
    const res = await fetch(apiPath, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error((data as { detail?: string }).detail ?? 'Add failed');
    }
    const created = (await res.json()) as { domain: string };
    setDomains((prev) => Array.from(new Set([...prev, created.domain])).sort());
  }, [apiPath, setDomains]);

  const removeDomain = useCallback(async (domain: string): Promise<void> => {
    const res = await fetch(`${apiPath}/${encodeURIComponent(domain)}`, { method: 'DELETE' });
    if (res.ok) { setDomains((prev) => prev.filter((d) => d !== domain)); return; }
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? 'Remove failed');
  }, [apiPath, setDomains]);

  return { domains, loading, fetchError, addDomain, removeDomain };
}

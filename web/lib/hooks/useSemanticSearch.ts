'use client';

import { useCallback, useState } from 'react';

export interface BrainResult {
  title: string;
  url: string;
  topic: string;
  score: number;
}

export type SearchState = 'idle' | 'loading' | 'results' | 'empty' | 'error';

export function useSemanticSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<BrainResult[]>([]);
  const [searchState, setSearchState] = useState<SearchState>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const runSearch = useCallback(async () => {
    const q = query.trim();
    setSearchState('loading');
    setErrorMessage('');
    try {
      const params = new URLSearchParams({ q });
      const res = await fetch(`/api/brain/search?${params}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = (data as { detail?: string }).detail ?? `Request failed (${res.status})`;
        setErrorMessage(detail);
        setSearchState('error');
        return;
      }
      const data: BrainResult[] = await res.json();
      setResults(data);
      setSearchState(data.length === 0 ? 'empty' : 'results');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error — could not reach the server.';
      setErrorMessage(msg);
      setSearchState('error');
    }
  }, [query]);

  return { query, setQuery, results, searchState, errorMessage, runSearch };
}

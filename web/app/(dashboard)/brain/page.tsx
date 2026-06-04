'use client';

import { useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrainResult {
  title: string;
  url: string;
  topic: string;
  score: number;
}

// ---------------------------------------------------------------------------
// Idle / empty / error banners
// ---------------------------------------------------------------------------

function IdleBanner() {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 px-6 py-12 text-center">
      <p className="text-lg font-medium text-gray-300">Search your Second Brain</p>
      <p className="mt-1 text-sm text-gray-500">
        Type a query above to find semantically similar videos and articles you have saved.
      </p>
    </div>
  );
}

function EmptyBanner() {
  return (
    <p className="rounded-lg border border-gray-700 bg-gray-800/50 px-6 py-8 text-center text-sm text-gray-400">
      No results found. Try a different query or add more videos to your Brain.
    </p>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-md bg-red-900/40 px-4 py-3 text-sm text-red-300">
      {message}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Result row
// ---------------------------------------------------------------------------

function ResultRow({ result }: { result: BrainResult }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-gray-700 bg-gray-800 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-white">{result.title}</span>
        {result.topic && (
          <span className="rounded bg-indigo-900/60 px-2 py-0.5 text-xs font-medium text-indigo-300">
            {result.topic}
          </span>
        )}
        <span className="ml-auto shrink-0 text-xs text-gray-500">
          {result.score.toFixed(4)}
        </span>
      </div>
      <a
        href={result.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block max-w-full truncate text-sm text-indigo-400 hover:text-indigo-300 hover:underline"
      >
        {result.url}
      </a>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type PageState = 'idle' | 'loading' | 'results' | 'empty' | 'error';

export default function BrainPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<BrainResult[]>([]);
  const [pageState, setPageState] = useState<PageState>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [blankWarning, setBlankWarning] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const runSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed) {
      setBlankWarning(true);
      inputRef.current?.focus();
      return;
    }
    setBlankWarning(false);
    setPageState('loading');
    setErrorMessage('');

    try {
      const params = new URLSearchParams({ q: trimmed });
      const res = await fetch(`/api/brain/search?${params.toString()}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail =
          (data as { detail?: string }).detail ?? `Request failed (${res.status})`;
        setErrorMessage(detail);
        setPageState('error');
        return;
      }
      const data: BrainResult[] = await res.json();
      setResults(data);
      setPageState(data.length === 0 ? 'empty' : 'results');
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Network error — could not reach the server.';
      setErrorMessage(msg);
      setPageState('error');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      runSearch();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    if (blankWarning && e.target.value.trim()) {
      setBlankWarning(false);
    }
  };

  const loading = pageState === 'loading';

  return (
    <div className="space-y-6">
      <div>
        <h2 className="mb-1 text-xl font-semibold text-white">Brain</h2>
        <p className="text-sm text-gray-500">
          Semantic search across everything saved to your Second Brain.
        </p>
      </div>

      {/* Search bar */}
      <section className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="e.g. machine learning, startup advice…"
          className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={runSearch}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Searching…
            </span>
          ) : (
            'Search'
          )}
        </button>
      </section>

      {/* Blank query warning */}
      {blankWarning && (
        <p className="text-xs text-amber-400">Please enter a search query.</p>
      )}

      {/* Body */}
      {pageState === 'idle' && <IdleBanner />}
      {pageState === 'error' && <ErrorBanner message={errorMessage} />}
      {pageState === 'empty' && <EmptyBanner />}
      {pageState === 'results' && (
        <section>
          <p className="mb-2 text-xs uppercase tracking-wide text-gray-500">
            {results.length} result{results.length === 1 ? '' : 's'}
          </p>
          <ul className="space-y-2">
            {results.map((r) => (
              <ResultRow key={r.url} result={r} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
